from datetime import timedelta
from sqlalchemy import select

from app.competitions.models import Question, QuestionSource
from app.jobs.models import BackgroundJob, JobStatus
from app.jobs.service import claim_next_job
from app.monitoring.classification import FakeMaterialityClassifier, FakeRelevanceClassifier
from app.monitoring.ingestion import IngestionFailure, current_cursor, process_provider_result
from app.monitoring.models import MonitoringConfig, MonitoringRun, MonitoringRunStatus, utcnow
from app.monitoring.policy import monitoring_interval_minutes, retry_at
from app.operations import log_event
from app.monitoring.providers.base import ProviderFailure, QuestionContext

ALLOWED_PROVIDERS = frozenset({'web', 'news', 'metaculus'})

def _add(total, counts):
    for key in total: total[key] += counts[key]

def _finish(session_factory, *, job_id, run_id, config_id, total, attempted, succeeded, failed, error_code=None):
    now = utcnow()
    with session_factory.begin() as session:
        job, run, config = session.get(BackgroundJob, job_id), session.get(MonitoringRun, run_id), session.get(MonitoringConfig, config_id)
        run.raw_items_seen, run.normalized_findings, run.duplicates_removed = total['raw'], total['normalized'], total['duplicates']
        run.relevant_findings, run.material_findings, run.candidates_created = total['relevant'], total['material'], total['candidates']
        run.providers_attempted, run.providers_succeeded, run.providers_failed, run.completed_at = attempted, succeeded, failed, now
        config.last_run_at = now
        if error_code is None:
            run.status, job.status, job.finished_at = MonitoringRunStatus.SUCCEEDED.value, JobStatus.SUCCEEDED.value, now
            resolve_at = session.scalar(select(QuestionSource.resolve_at).where(QuestionSource.question_id == config.question_id))
            interval = monitoring_interval_minutes(resolve_at, explicit_interval_minutes=None if config.adaptive_schedule_enabled else config.monitoring_interval_minutes, now=now)
            config.last_success_at, config.next_run_at = now, now + timedelta(minutes=interval)
        else:
            run.status, run.safe_error_summary = MonitoringRunStatus.FAILED.value, 'Monitoring provider or classification failed; retry is scheduled.'
            job.last_error_code, job.last_error_message = error_code, 'Monitoring provider or classification failed'
            job.status, job.scheduled_for, job.finished_at = (JobStatus.RETRY_WAIT.value if job.attempt_count < job.max_attempts else JobStatus.FAILED.value), retry_at(job.attempt_count, now=now), now
        log_event('monitoring_run_finished', job_id=job_id, status=job.status, attempt_count=job.attempt_count, safe_error_code=error_code)

def run_one_monitoring_job(session_factory, providers, relevance=None, materiality=None):
    job = claim_next_job(session_factory, job_types=('monitor_question',))
    if not job: return None
    with session_factory.begin() as session:
        claimed = session.get(BackgroundJob, job.id); config = session.get(MonitoringConfig, claimed.payload_json.get('config_id')); question = session.get(Question, claimed.question_id)
        if not config or not question or config.user_id != claimed.user_id or config.question_id != claimed.question_id or not config.enabled:
            claimed.status, claimed.finished_at, claimed.last_error_code, claimed.last_error_message = JobStatus.FAILED.value, utcnow(), 'missing_configuration', 'Monitoring configuration is unavailable'
            return claimed.id
        context = QuestionContext(question.id, question.title, session.scalar(select(QuestionSource.resolution_criteria).where(QuestionSource.question_id == question.id, QuestionSource.user_id == claimed.user_id)))
        selected = [(name, provider) for name, provider in providers.items() if name in ALLOWED_PROVIDERS and ((name == 'web' and config.web_monitoring_enabled) or (name == 'news' and config.news_monitoring_enabled) or (name == 'metaculus' and config.metaculus_refresh_enabled))]
        run = MonitoringRun(user_id=claimed.user_id, question_id=claimed.question_id, job_id=claimed.id); session.add(run); session.flush()
        job_id, run_id, config_id, user_id, question_id = claimed.id, run.id, config.id, claimed.user_id, claimed.question_id
    total = {'raw': 0, 'normalized': 0, 'duplicates': 0, 'relevant': 0, 'material': 0, 'candidates': 0}; attempted = succeeded = failed = 0
    try:
        for name, provider in selected:
            attempted += 1
            result = provider.fetch(context, current_cursor(session_factory, user_id=user_id, question_id=question_id, provider=name))
            counts = process_provider_result(session_factory, user_id=user_id, question_id=question_id, run_id=run_id, provider=name,
                items=result.items, next_cursor=result.next_cursor, question=context, relevance=relevance or FakeRelevanceClassifier(), materiality=materiality or FakeMaterialityClassifier())
            _add(total, counts); succeeded += 1
    except IngestionFailure as exc:
        _add(total, exc.counts); failed += 1; _finish(session_factory, job_id=job_id, run_id=run_id, config_id=config_id, total=total, attempted=attempted, succeeded=succeeded, failed=failed, error_code=exc.code)
        return job_id
    except ProviderFailure as exc:
        failed += 1; code = exc.code if exc.code in {'provider_failure', 'provider_unavailable', 'provider_timeout'} else 'provider_failure'
        _finish(session_factory, job_id=job_id, run_id=run_id, config_id=config_id, total=total, attempted=attempted, succeeded=succeeded, failed=failed, error_code=code)
        return job_id
    except Exception:
        failed += 1; _finish(session_factory, job_id=job_id, run_id=run_id, config_id=config_id, total=total, attempted=attempted, succeeded=succeeded, failed=failed, error_code='persistence_failure')
        return job_id
    _finish(session_factory, job_id=job_id, run_id=run_id, config_id=config_id, total=total, attempted=attempted, succeeded=succeeded, failed=failed)
    return job_id

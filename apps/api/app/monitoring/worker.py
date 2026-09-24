from datetime import timedelta
from sqlalchemy import select
from app.competitions.models import Question, QuestionSource
from app.jobs.models import JobStatus
from app.jobs.service import claim_next_job
from app.monitoring.models import MonitoringConfig, MonitoringRun, MonitoringRunStatus, utcnow
from app.monitoring.providers.base import ProviderFailure, QuestionContext


def run_one_monitoring_job(session_factory, providers):
    job = claim_next_job(session_factory)
    if not job or job.job_type != 'monitor_question': return None
    with session_factory.begin() as session:
        job = session.get(type(job), job.id)
        config = session.get(MonitoringConfig, job.payload_json.get('config_id'))
        question = session.get(Question, job.question_id)
        if not config or not question or config.user_id != job.user_id or not config.enabled:
            job.status, job.finished_at, job.last_error_code, job.last_error_message = JobStatus.FAILED.value, utcnow(), 'missing_configuration', 'Monitoring configuration is unavailable'
            return job.id
        run = MonitoringRun(user_id=job.user_id, question_id=job.question_id, job_id=job.id)
        session.add(run); session.flush()
        context = QuestionContext(question.id, question.title, (session.scalar(select(QuestionSource.resolution_criteria).where(QuestionSource.question_id == question.id, QuestionSource.user_id == job.user_id))))
    try:
        selected = [p for name, p in providers.items() if name in {'web', 'news', 'metaculus'} and ((name == 'web' and config.web_monitoring_enabled) or (name == 'news' and config.news_monitoring_enabled) or (name == 'metaculus' and config.metaculus_refresh_enabled))]
        outcomes = [provider.fetch(context, None) for provider in selected]
        with session_factory.begin() as session:
            job, run, config = session.get(type(job), job.id), session.get(MonitoringRun, run.id), session.get(MonitoringConfig, config.id)
            run.status, run.completed_at, run.providers_attempted, run.providers_succeeded = MonitoringRunStatus.SUCCEEDED.value, utcnow(), len(selected), len(selected)
            run.raw_items_seen = sum(len(result.items) for result in outcomes)
            job.status, job.finished_at = JobStatus.SUCCEEDED.value, utcnow()
            config.last_run_at = config.last_success_at = utcnow(); config.next_run_at = utcnow() + timedelta(minutes=config.monitoring_interval_minutes)
        return job.id
    except ProviderFailure as exc:
        code = exc.code if exc.code in {'provider_failure','provider_unavailable','provider_timeout'} else 'provider_failure'
    except Exception:
        code = 'unknown_failure'
    with session_factory.begin() as session:
        job, run, config = session.get(type(job), job.id), session.get(MonitoringRun, run.id), session.get(MonitoringConfig, config.id)
        run.status, run.completed_at, run.providers_attempted, run.providers_failed, run.safe_error_summary = MonitoringRunStatus.FAILED.value, utcnow(), 1, 1, 'Provider unavailable'
        job.last_error_code, job.last_error_message = code, 'Provider unavailable'
        job.status = JobStatus.RETRY_WAIT.value if job.attempt_count < job.max_attempts else JobStatus.FAILED.value
        job.scheduled_for, job.finished_at = utcnow() + timedelta(minutes=1), utcnow()
        config.last_run_at = utcnow()
    return job.id

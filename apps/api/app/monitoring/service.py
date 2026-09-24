from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.audit.service import record_audit
from app.forecasts.service import get_owned_question
from app.jobs.service import enqueue_job
from app.jobs.models import BackgroundJob, JobStatus
from app.monitoring.models import MonitoringConfig, MonitoringRun, utcnow
from app.monitoring.schemas import MonitoringEnable, MonitoringStatusResponse, MonitoringRunResponse


def _config(session, user_id, question_id):
    get_owned_question(session, question_id, user_id)
    return session.scalar(select(MonitoringConfig).where(MonitoringConfig.user_id == user_id, MonitoringConfig.question_id == question_id))


def enable_monitoring(session, *, user_id, question_id, settings: MonitoringEnable):
    config = _config(session, user_id, question_id)
    if config is None:
        config = MonitoringConfig(user_id=user_id, question_id=question_id)
        session.add(config)
    config.enabled = True
    for field, value in settings.model_dump().items(): setattr(config, field, value)
    config.next_run_at = utcnow()
    session.flush()
    record_audit(session, user_id=user_id, question_id=question_id, action='monitoring_enabled', entity_type='monitoring_config', entity_id=config.id)
    return config


def disable_monitoring(session, *, user_id, question_id):
    config = _config(session, user_id, question_id)
    if config is None: raise HTTPException(status_code=409, detail='Monitoring is not configured')
    config.enabled, config.next_run_at = False, None
    record_audit(session, user_id=user_id, question_id=question_id, action='monitoring_disabled', entity_type='monitoring_config', entity_id=config.id)
    return config


def enqueue_manual_run(session, *, user_id, question_id):
    config = _config(session, user_id, question_id)
    if config is None or not config.enabled: raise HTTPException(status_code=409, detail='Monitoring must be enabled')
    active = session.scalar(select(BackgroundJob).where(BackgroundJob.user_id == user_id, BackgroundJob.question_id == question_id, BackgroundJob.job_type == 'monitor_question', BackgroundJob.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value, JobStatus.RETRY_WAIT.value])))
    if active: return active
    return enqueue_job(session, user_id=user_id, question_id=question_id, job_type='monitor_question', payload_json={'config_id': config.id}, scheduled_for=utcnow(), idempotency_key=f'manual:{config.id}:{uuid4()}')


def get_status(session, *, user_id, question_id):
    config = _config(session, user_id, question_id)
    if config is None: return MonitoringStatusResponse(id='', enabled=False, monitoring_interval_minutes=360, last_run_at=None, last_success_at=None, next_run_at=None)
    run = session.scalar(select(MonitoringRun).where(MonitoringRun.user_id == user_id, MonitoringRun.question_id == question_id).order_by(MonitoringRun.started_at.desc()))
    return MonitoringStatusResponse.model_validate(config).model_copy(update={'latest_run': MonitoringRunResponse.model_validate(run) if run else None})


def list_runs(session, *, user_id, question_id):
    _config(session, user_id, question_id)
    return [MonitoringRunResponse.model_validate(run) for run in session.scalars(select(MonitoringRun).where(MonitoringRun.user_id == user_id, MonitoringRun.question_id == question_id).order_by(MonitoringRun.started_at.desc())).all()]

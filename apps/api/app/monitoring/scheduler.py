from sqlalchemy import select
from app.jobs.service import enqueue_job
from app.monitoring.models import MonitoringConfig


def enqueue_due_monitoring_jobs(session, now):
    result = []
    for config in session.scalars(select(MonitoringConfig).where(MonitoringConfig.enabled.is_(True), MonitoringConfig.next_run_at <= now)).all():
        key = f'schedule:{config.id}:{config.next_run_at.isoformat()}'
        job = enqueue_job(session, user_id=config.user_id, question_id=config.question_id, job_type='monitor_question', payload_json={'config_id': config.id}, scheduled_for=config.next_run_at, idempotency_key=key)
        if job and job not in result: result.append(job)
    return result

"""Worker entry point; the caller supplies the fixed application provider registry."""
from sqlalchemy import select
from app.jobs.models import BackgroundJob, JobStatus, utcnow
from app.notifications.service import deliver_attempt

def run_one_notification_job(session_factory, providers):
    with session_factory.begin() as session:
        job = session.scalar(select(BackgroundJob).where(
            BackgroundJob.job_type == 'deliver_notification',
            BackgroundJob.status.in_([JobStatus.QUEUED.value, JobStatus.RETRY_WAIT.value]),
            BackgroundJob.scheduled_for <= utcnow(),
        ).order_by(BackgroundJob.scheduled_for, BackgroundJob.created_at).limit(1))
        if job is None: return None
        job.status, job.started_at, job.attempt_count = JobStatus.RUNNING.value, utcnow(), job.attempt_count + 1
        job_id, attempt_id = job.id, job.payload_json['attempt_id']
    try:
        deliver_attempt(session_factory, attempt_id, providers)
    except Exception:
        with session_factory.begin() as session:
            job = session.get(BackgroundJob, job_id); job.status, job.last_error_code, job.last_error_message, job.finished_at = JobStatus.RETRY_WAIT.value, 'delivery_failure', 'Notification delivery failed', utcnow()
        return job_id
    with session_factory.begin() as session:
        job = session.get(BackgroundJob, job_id); job.status, job.finished_at = JobStatus.SUCCEEDED.value, utcnow()
    return job_id

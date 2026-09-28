"""Worker entry point; the caller supplies the fixed application provider registry."""
from app.jobs.models import BackgroundJob, JobStatus, utcnow
from app.jobs.service import claim_next_job
from app.monitoring.policy import retry_at
from app.operations import log_event
from app.notifications.models import NotificationAttempt
from app.notifications.service import deliver_attempt

def run_one_notification_job(session_factory, providers):
    job = claim_next_job(session_factory, job_types=('deliver_notification',))
    if job is None: return None
    job_id, attempt_id = job.id, job.payload_json['attempt_id']
    try:
        deliver_attempt(session_factory, attempt_id, providers)
    except Exception:
        with session_factory.begin() as session:
            job = session.get(BackgroundJob, job_id)
            job.status, job.last_error_code, job.last_error_message, job.finished_at = (JobStatus.RETRY_WAIT.value if job.attempt_count < job.max_attempts else JobStatus.FAILED.value), 'delivery_failure', 'Notification delivery failed', utcnow()
            if job.status == JobStatus.RETRY_WAIT.value: job.scheduled_for = retry_at(job.attempt_count)
            log_event('job_retry', job_id=job.id, job_type=job.job_type, status=job.status, safe_error_code='delivery_failure')
        return job_id
    with session_factory.begin() as session:
        job = session.get(BackgroundJob, job_id)
        attempt = session.get(NotificationAttempt, attempt_id)
        job.status, job.finished_at = (JobStatus.SUCCEEDED.value if attempt.status == 'succeeded' else JobStatus.RETRY_WAIT.value), utcnow()
        if job.status == JobStatus.RETRY_WAIT.value: job.scheduled_for = attempt.scheduled_for
    return job_id


def run_one_configured_notification_job(app):
    """Production entry point restricted to the application-owned registry."""
    return run_one_notification_job(app.state.session_factory, app.state.notification_providers)

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.jobs.models import BackgroundJob, JobStatus, utcnow


def enqueue_job(session, *, user_id, question_id, job_type, payload_json, scheduled_for, idempotency_key):
    job = BackgroundJob(user_id=user_id, question_id=question_id, job_type=job_type,
                        payload_json=payload_json, scheduled_for=scheduled_for,
                        idempotency_key=idempotency_key)
    session.add(job)
    try:
        session.flush()
        return job
    except IntegrityError:
        session.rollback()
        return session.scalar(select(BackgroundJob).where(
            BackgroundJob.user_id == user_id, BackgroundJob.job_type == job_type,
            BackgroundJob.idempotency_key == idempotency_key,
        ))


def build_claim_query(dialect_name: str, now: datetime):
    query = select(BackgroundJob).where(
        BackgroundJob.status.in_([JobStatus.QUEUED.value, JobStatus.RETRY_WAIT.value]),
        BackgroundJob.scheduled_for <= now,
    ).order_by(BackgroundJob.scheduled_for, BackgroundJob.created_at).limit(1)
    return query.with_for_update(skip_locked=True) if dialect_name == 'postgresql' else query


def claim_next_job(session_factory):
    with session_factory.begin() as session:
        job = session.scalar(build_claim_query(session.bind.dialect.name, utcnow()))
        if job is None:
            return None
        job.status = JobStatus.RUNNING.value
        job.started_at = utcnow()
        job.attempt_count += 1
        session.flush()
        return job

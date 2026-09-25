from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.jobs.models import BackgroundJob, JobStatus, utcnow
from app.monitoring.policy import STALE_JOB_LEASE_MINUTES, as_utc, retry_at
from app.operations import log_event


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


def build_claim_query(dialect_name: str, now: datetime, job_types: tuple[str, ...] | None = None):
    query = select(BackgroundJob).where(
        BackgroundJob.status.in_([JobStatus.QUEUED.value, JobStatus.RETRY_WAIT.value]),
        BackgroundJob.scheduled_for <= now,
    )
    if job_types:
        query = query.where(BackgroundJob.job_type.in_(job_types))
    query = query.order_by(BackgroundJob.scheduled_for, BackgroundJob.created_at).limit(1)
    return query.with_for_update(skip_locked=True) if dialect_name == 'postgresql' else query


def claim_next_job(session_factory, *, job_types: tuple[str, ...] | None = None):
    with session_factory.begin() as session:
        job = session.scalar(build_claim_query(session.bind.dialect.name, utcnow(), job_types))
        if job is None:
            return None
        job.status = JobStatus.RUNNING.value
        job.started_at = utcnow()
        job.attempt_count += 1
        session.flush()
        log_event('job_claimed', job_id=job.id, job_type=job.job_type, attempt_count=job.attempt_count)
        return job


def recover_stale_jobs(session_factory, *, now: datetime | None = None, lease_minutes: int = STALE_JOB_LEASE_MINUTES) -> int:
    """Return leased jobs to bounded retry processing after a worker crash."""
    now = as_utc(now or utcnow())
    cutoff = now - timedelta(minutes=lease_minutes)
    recovered = 0
    with session_factory.begin() as session:
        jobs = session.scalars(select(BackgroundJob).where(
            BackgroundJob.status == JobStatus.RUNNING.value,
            BackgroundJob.started_at.is_not(None),
            BackgroundJob.started_at <= cutoff,
        ).with_for_update(skip_locked=session.bind.dialect.name == 'postgresql')).all()
        for job in jobs:
            job.finished_at = now
            job.last_error_code, job.last_error_message = 'lease_expired', 'Worker lease expired; retry is scheduled.'
            if job.attempt_count >= job.max_attempts:
                job.status = JobStatus.FAILED.value
            else:
                job.status, job.scheduled_for = JobStatus.RETRY_WAIT.value, retry_at(job.attempt_count, now=now)
            recovered += 1
            log_event('job_recovered', job_id=job.id, job_type=job.job_type, status=job.status, attempt_count=job.attempt_count)
    return recovered

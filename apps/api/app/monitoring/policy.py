"""Centralized, deterministic monitoring and retry timing policy."""
from datetime import datetime, timedelta, timezone

RETRY_DELAYS_MINUTES = (1, 5, 15, 60)
STALE_JOB_LEASE_MINUTES = 15


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def monitoring_interval_minutes(resolve_at: datetime | None, *, explicit_interval_minutes: int | None = None, now: datetime | None = None) -> int:
    if explicit_interval_minutes is not None:
        return explicit_interval_minutes
    now = as_utc(now or datetime.now(timezone.utc))
    if resolve_at is None:
        return 720
    days = (as_utc(resolve_at) - now).total_seconds() / 86400
    if days > 90:
        return 720
    if days > 30:
        return 360
    if days > 7:
        return 180
    return 60


def retry_at(attempt_count: int, *, now: datetime | None = None) -> datetime:
    delay = RETRY_DELAYS_MINUTES[min(max(attempt_count - 1, 0), len(RETRY_DELAYS_MINUTES) - 1)]
    return as_utc(now or datetime.now(timezone.utc)) + timedelta(minutes=delay)

from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from app.jobs.service import enqueue_job
from app.monitoring.alerts import AlertEvent, Digest
from app.notifications.models import NotificationAttempt, NotificationPreference, utcnow
from app.notifications.providers import NotificationProviderFailure

SAFE_CODES = frozenset({'provider_unavailable', 'authentication_failure', 'rate_limited', 'delivery_failure', 'malformed_provider_response', 'unknown_failure'})

def get_preference(session, user_id):
    return session.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user_id, NotificationPreference.channel == 'in_app', NotificationPreference.provider == 'fake'))

def save_preference(session, *, user_id, values):
    pref = get_preference(session, user_id)
    if pref is None:
        pref = NotificationPreference(user_id=user_id); session.add(pref)
    for field in ('enabled', 'immediate_alerts_enabled', 'digest_enabled'):
        if field in values: setattr(pref, field, values[field])
    session.flush(); return pref

def _schedule(session, *, user_id, alert_id=None, digest_id=None):
    if bool(alert_id) == bool(digest_id): raise ValueError('Exactly one notification source is required')
    source = session.get(AlertEvent, alert_id) if alert_id else session.get(Digest, digest_id)
    if source is None or source.user_id != user_id: raise HTTPException(status_code=404, detail='Notification source not found')
    pref = get_preference(session, user_id)
    allowed = pref and pref.enabled and (pref.immediate_alerts_enabled if alert_id else pref.digest_enabled)
    if not allowed: raise HTTPException(status_code=409, detail='Notification delivery is disabled')
    if digest_id and source.status != 'generated': raise HTTPException(status_code=409, detail='Digest is not eligible')
    key = f'alert:{alert_id}:in_app:fake' if alert_id else f'digest:{digest_id}:in_app:fake'
    attempt = session.scalar(select(NotificationAttempt).where(NotificationAttempt.user_id == user_id, NotificationAttempt.idempotency_key == key))
    if attempt is None:
        attempt = NotificationAttempt(user_id=user_id, alert_event_id=alert_id, digest_id=digest_id, channel='in_app', provider='fake', idempotency_key=key)
        session.add(attempt); session.flush()
        enqueue_job(session, user_id=user_id, question_id=source.question_id if alert_id else None, job_type='deliver_notification', payload_json={'attempt_id': attempt.id}, scheduled_for=utcnow(), idempotency_key=key)
    return attempt

def schedule_alert_delivery(session, *, user_id, alert_id): return _schedule(session, user_id=user_id, alert_id=alert_id)
def schedule_digest_delivery(session, *, user_id, digest_id): return _schedule(session, user_id=user_id, digest_id=digest_id)

def deliver_attempt(session_factory, attempt_id, providers):
    with session_factory.begin() as session:
        attempt = session.get(NotificationAttempt, attempt_id)
        if attempt is None or attempt.status == 'succeeded': return attempt_id
        provider = providers.get(attempt.provider)
        if provider is None: raise ValueError('Provider is not allowlisted')
        attempt.status, attempt.started_at, attempt.attempt_number = 'running', utcnow(), attempt.attempt_number + 1
        if attempt.alert_event_id:
            source = session.get(AlertEvent, attempt.alert_event_id); payload = {'kind':'alert', 'title':source.severity, 'summary':source.reason, 'idempotency_key':attempt.idempotency_key}
        else:
            source = session.get(Digest, attempt.digest_id); payload = {'kind':'digest', 'title':'Digest', 'summary':f'{source.period_start.isoformat()}-{source.period_end.isoformat()}', 'idempotency_key':attempt.idempotency_key}
    try:
        result = provider.send(payload)
    except NotificationProviderFailure as exc:
        code = exc.code if exc.code in SAFE_CODES else 'delivery_failure'
        with session_factory.begin() as session:
            attempt = session.get(NotificationAttempt, attempt_id); attempt.status, attempt.last_error_code, attempt.last_error_message = 'retry_wait', code, 'Notification provider failed; retry is scheduled.'
            attempt.completed_at, attempt.scheduled_for = utcnow(), utcnow() + timedelta(minutes=1)
        return attempt_id
    with session_factory.begin() as session:
        attempt = session.get(NotificationAttempt, attempt_id); attempt.status, attempt.completed_at, attempt.external_message_id = 'succeeded', utcnow(), result.external_message_id
        if attempt.digest_id: session.get(Digest, attempt.digest_id).delivered_at = utcnow()
    return attempt_id

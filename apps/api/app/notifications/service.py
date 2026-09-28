from fastapi import HTTPException
import os
from sqlalchemy import select
from app.jobs.service import enqueue_job
from app.monitoring.alerts import AlertEvent, Digest
from app.monitoring.models import EventCluster, Finding, FindingEventLink
from app.monitoring.alerts import DigestItem
from app.competitions.models import Question
from app.notifications.models import NotificationAttempt, NotificationPreference, utcnow
from app.notifications.providers import NotificationProviderFailure
from app.monitoring.policy import retry_at
from app.operations import log_event

SAFE_CODES = frozenset({'provider_unavailable', 'authentication_failure', 'rate_limited', 'timeout', 'invalid_destination', 'delivery_failure', 'malformed_provider_response', 'unknown_failure'})

def _delivery_target():
    return ('email', 'resend') if os.getenv('NOTIFICATION_PROVIDER', '').lower() == 'resend' else ('in_app', 'fake')

def get_preference(session, user_id):
    channel, provider = _delivery_target()
    return session.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user_id, NotificationPreference.channel == channel, NotificationPreference.provider == provider))

def save_preference(session, *, user_id, values):
    pref = get_preference(session, user_id)
    if pref is None:
        channel, provider = _delivery_target()
        pref = NotificationPreference(user_id=user_id, channel=channel, provider=provider); session.add(pref)
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
    key = f'alert:{alert_id}:{pref.channel}:{pref.provider}' if alert_id else f'digest:{digest_id}:{pref.channel}:{pref.provider}'
    attempt = session.scalar(select(NotificationAttempt).where(NotificationAttempt.user_id == user_id, NotificationAttempt.idempotency_key == key))
    if attempt is None:
        attempt = NotificationAttempt(user_id=user_id, alert_event_id=alert_id, digest_id=digest_id, channel=pref.channel, provider=pref.provider, idempotency_key=key)
        session.add(attempt); session.flush()
        enqueue_job(session, user_id=user_id, question_id=source.question_id if alert_id else None, job_type='deliver_notification', payload_json={'attempt_id': attempt.id}, scheduled_for=utcnow(), idempotency_key=key)
    return attempt

def schedule_alert_delivery(session, *, user_id, alert_id): return _schedule(session, user_id=user_id, alert_id=alert_id)
def schedule_digest_delivery(session, *, user_id, digest_id): return _schedule(session, user_id=user_id, digest_id=digest_id)


def _as_text(value, limit=1000):
    return str(value or '').replace('\r', ' ').replace('\n', ' ').strip()[:limit]


def _finding_lines(finding, cluster):
    """Render persisted finding and corroboration data; never invoke intelligence here."""
    source = _as_text(getattr(finding, 'normalized_source', None) or getattr(finding, 'source_name', None) or 'Unknown source', 255)
    lines = [
        f'Finding: {_as_text(getattr(finding, "title", None), 500)}',
        f'Materiality: {_as_text(getattr(finding, "materiality_class", None) or "unknown", 40)}',
        f'Source: {source}',
        f'Source type: {_as_text(getattr(finding, "source_type", None) or "unknown", 40)}',
        f'Reliability signal: {_as_text(getattr(finding, "source_reliability", None) or "unknown", 40)}',
    ]
    if cluster is not None:
        lines.extend([
            f'Event summary: {_as_text(getattr(cluster, "canonical_summary", None), 500)}',
            f'Cluster members: {getattr(cluster, "total_findings", 0) or 0}',
            f'Independent reports: {getattr(cluster, "independent_source_count", 0) or 0}',
            f'Primary source present: {"yes" if getattr(cluster, "primary_source_present", False) else "no"}',
        ])
    reason = _as_text(getattr(finding, 'materiality_reason', None), 500)
    if reason:
        lines.append(f'AI classification reason: {reason}')
    summary = _as_text(getattr(finding, 'summary', None), 1000)
    if summary:
        lines.append(f'Summary: {summary}')
    timestamp = _as_text(getattr(finding, 'discovered_at', None), 100)
    if timestamp:
        lines.append(f'Timestamp: {timestamp}')
    return lines


def build_delivery_payload(*, kind, source, question, items):
    """Build bounded plain-text content from owner-scoped persisted records only."""
    question_title = _as_text(getattr(question, 'title', None) or 'Unknown question', 500)
    if kind == 'alert':
        title = f'Alert: {question_title}'
        lines = [f'Question: {question_title}', f'Severity: {_as_text(getattr(source, "severity", None) or "unknown", 40)}']
        if _as_text(getattr(source, 'reason', None), 500):
            lines.append(f'Alert reason: {_as_text(getattr(source, "reason", None), 500)}')
    else:
        start, end = _as_text(getattr(source, 'period_start', None), 100), _as_text(getattr(source, 'period_end', None), 100)
        title = f'Digest: {start} to {end} — {question_title}'
        lines = [f'Digest period: {start} to {end}', f'Question: {question_title}']
    for finding, cluster in items:
        lines.extend(['', *_finding_lines(finding, cluster)])
    return {'kind': kind, 'title': title[:1000], 'summary': '\n'.join(lines)[:8000]}


def _cluster_for_finding(session, finding):
    return session.scalar(select(EventCluster).join(FindingEventLink, FindingEventLink.event_cluster_id == EventCluster.id).where(
        FindingEventLink.finding_id == finding.id,
        FindingEventLink.user_id == finding.user_id,
        FindingEventLink.question_id == finding.question_id,
        EventCluster.user_id == finding.user_id,
        EventCluster.question_id == finding.question_id,
    ))


def _payload_for_attempt(session, attempt):
    if attempt.alert_event_id:
        source = session.scalar(select(AlertEvent).where(AlertEvent.id == attempt.alert_event_id, AlertEvent.user_id == attempt.user_id))
        finding = session.scalar(select(Finding).where(Finding.id == source.finding_id, Finding.user_id == attempt.user_id, Finding.question_id == source.question_id))
        question = session.get(Question, source.question_id)
        payload = build_delivery_payload(kind='alert', source=source, question=question, items=[] if finding is None else [(finding, _cluster_for_finding(session, finding))])
    else:
        source = session.scalar(select(Digest).where(Digest.id == attempt.digest_id, Digest.user_id == attempt.user_id))
        rows = session.execute(select(DigestItem, Finding).join(Finding, Finding.id == DigestItem.finding_id).where(
            DigestItem.user_id == attempt.user_id,
            DigestItem.included_in_digest_id == source.id,
            Finding.user_id == attempt.user_id,
            Finding.question_id == DigestItem.question_id,
        ).order_by(DigestItem.eligible_at, DigestItem.id)).all()
        question_ids = {finding.question_id for _, finding in rows}
        question = session.get(Question, next(iter(question_ids))) if len(question_ids) == 1 else None
        payload = build_delivery_payload(kind='digest', source=source, question=question, items=[(finding, _cluster_for_finding(session, finding)) for _, finding in rows])
    payload['idempotency_key'] = attempt.idempotency_key
    return payload

def deliver_attempt(session_factory, attempt_id, providers):
    with session_factory.begin() as session:
        attempt = session.get(NotificationAttempt, attempt_id)
        if attempt is None or attempt.status == 'succeeded': return attempt_id
        provider = providers.get(attempt.provider)
        attempt.status, attempt.started_at, attempt.attempt_number = 'running', utcnow(), attempt.attempt_number + 1
        payload = _payload_for_attempt(session, attempt)
    try:
        if provider is None:
            raise NotificationProviderFailure('provider_unavailable', 'Notification provider is unavailable')
        result = provider.send(payload)
    except NotificationProviderFailure as exc:
        code = exc.code if exc.code in SAFE_CODES else 'delivery_failure'
        with session_factory.begin() as session:
            attempt = session.get(NotificationAttempt, attempt_id); terminal = code in {'authentication_failure', 'invalid_destination', 'malformed_provider_response'}
            attempt.status, attempt.last_error_code, attempt.last_error_message = ('failed' if terminal else 'retry_wait'), code, ('Notification provider rejected configuration or response.' if terminal else 'Notification provider failed; retry is scheduled.')
            attempt.completed_at = utcnow()
            if not terminal: attempt.scheduled_for = retry_at(attempt.attempt_number)
            log_event('notification_attempt_finished', attempt_id=attempt.id, provider=attempt.provider, status=attempt.status, safe_error_code=code)
        return attempt_id
    with session_factory.begin() as session:
        attempt = session.get(NotificationAttempt, attempt_id); attempt.status, attempt.completed_at, attempt.external_message_id = 'succeeded', utcnow(), result.external_message_id
        if attempt.digest_id: session.get(Digest, attempt.digest_id).delivered_at = utcnow()
        log_event('notification_attempt_finished', attempt_id=attempt.id, provider=attempt.provider, status=attempt.status)
    return attempt_id

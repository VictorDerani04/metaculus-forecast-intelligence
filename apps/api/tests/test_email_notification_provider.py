import httpx
import json
import pytest
from types import SimpleNamespace


def test_resend_provider_uses_fixed_endpoint_escaped_content_and_attempt_key():
    from app.notifications.providers import EmailNotificationProvider

    seen = {}
    def handler(request):
        seen['url'] = str(request.url)
        seen['headers'] = dict(request.headers)
        seen['body'] = json.loads(request.content)
        return httpx.Response(200, json={'id': 'external-1'})

    provider = EmailNotificationProvider(
        api_key='secret-key', from_email='alerts@example.test', to_email='owner@example.test',
        transport=httpx.MockTransport(handler),
    )
    result = provider.send({'kind': 'alert', 'title': '<script>x</script>', 'summary': 'line\r\nBcc: bad@example.test', 'idempotency_key': 'attempt-1'})

    assert result.external_message_id == 'external-1'
    assert seen['url'] == 'https://api.resend.com/emails'
    assert seen['headers']['idempotency-key'] == 'attempt-1'
    assert seen['body']['to'] == ['owner@example.test']
    assert '&lt;script&gt;x&lt;/script&gt;' in seen['body']['html']
    assert '<script>' not in seen['body']['html']
    assert 'Bcc:' not in seen['body']['text']


@pytest.mark.parametrize(
    ('status_code', 'body', 'expected_code'),
    [
        (429, {}, 'rate_limited'),
        (500, {}, 'delivery_failure'),
        (401, {}, 'authentication_failure'),
        (200, {}, 'malformed_provider_response'),
        (200, {'id': 9}, 'malformed_provider_response'),
    ],
)
def test_resend_provider_maps_http_and_malformed_failures_without_secrets(status_code, body, expected_code):
    from app.notifications.providers import EmailNotificationProvider, NotificationProviderFailure

    provider = EmailNotificationProvider(
        api_key='secret-key', from_email='alerts@example.test', to_email='owner@example.test',
        transport=httpx.MockTransport(lambda request: httpx.Response(status_code, json=body)),
    )
    with pytest.raises(NotificationProviderFailure) as error:
        provider.send({'title': 'Alert', 'summary': 'Summary', 'idempotency_key': 'attempt-1'})
    assert error.value.code == expected_code
    assert 'secret' not in error.value.message.lower()


def test_resend_provider_timeout_is_retry_safe_and_registry_is_allowlisted(monkeypatch):
    from app.notifications.providers import EmailNotificationProvider, NotificationProviderFailure, build_notification_provider_registry

    provider = EmailNotificationProvider(
        api_key='secret-key', from_email='alerts@example.test', to_email='owner@example.test',
        transport=httpx.MockTransport(lambda request: (_ for _ in ()).throw(httpx.ReadTimeout('timeout'))),
    )
    with pytest.raises(NotificationProviderFailure, match='timed out') as error:
        provider.send({'title': 'Alert', 'summary': 'Summary', 'idempotency_key': 'attempt-1'})
    assert error.value.code == 'timeout'

    monkeypatch.setenv('NOTIFICATION_PROVIDER', 'not-a-module')
    monkeypatch.setenv('NOTIFICATION_API_KEY', 'secret-key')
    monkeypatch.setenv('NOTIFICATION_FROM_EMAIL', 'alerts@example.test')
    monkeypatch.setenv('NOTIFICATION_TO_EMAIL', 'owner@example.test')
    assert build_notification_provider_registry() == {}
    monkeypatch.setenv('NOTIFICATION_PROVIDER', 'resend')
    assert set(build_notification_provider_registry()) == {'resend'}
    monkeypatch.setenv('NOTIFICATION_TIMEOUT_SECONDS', '0')
    assert build_notification_provider_registry() == {}


def test_delivery_payload_renders_persisted_source_intelligence_and_digest_deterministically():
    from app.notifications.service import build_delivery_payload

    finding = SimpleNamespace(
        title='"><img src=x onerror=alert(1)>', summary='<script>alert("x")</script>',
        source_name='Source\r\nBcc: injected@example.test', normalized_source='reuters.com',
        source_type='wire_service', source_reliability='high', materiality_class='critical',
        materiality_reason='Persisted classifier reason', discovered_at='2026-09-26T12:00:00Z',
    )
    question = SimpleNamespace(title='Will <script>this happen?</script>')
    cluster = SimpleNamespace(canonical_summary='Event summary', total_findings=2, independent_source_count=2, primary_source_present=False)
    digest = SimpleNamespace(period_start='2026-09-25T00:00:00Z', period_end='2026-09-26T00:00:00Z')
    alert = SimpleNamespace(severity='critical', reason='Persisted classifier reason')

    alert_payload = build_delivery_payload(kind='alert', source=alert, question=question, items=[(finding, cluster)])
    digest_payload = build_delivery_payload(kind='digest', source=digest, question=question, items=[(finding, cluster)])

    assert 'Will <script>this happen?</script>' in alert_payload['title']
    assert 'Reliability signal: high' in alert_payload['summary']
    assert 'Independent reports: 2' in alert_payload['summary']
    assert 'Primary source present: no' in alert_payload['summary']
    assert digest_payload['title'].startswith('Digest: 2026-09-25')
    assert digest_payload['summary'] == build_delivery_payload(kind='digest', source=digest, question=question, items=[(finding, cluster)])['summary']

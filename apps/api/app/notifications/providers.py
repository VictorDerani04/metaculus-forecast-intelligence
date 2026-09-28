from dataclasses import dataclass
from html import escape
import os
import re
from typing import Protocol

import httpx

@dataclass(frozen=True)
class NotificationResult:
    external_message_id: str | None
    provider_status: str

class NotificationProviderFailure(Exception):
    def __init__(self, code='delivery_failure', message='Delivery provider failed'):
        self.code, self.message = code, message

class NotificationProvider(Protocol):
    provider_name: str
    def send(self, payload: dict) -> NotificationResult: ...

class FakeNotificationProvider:
    provider_name = 'fake'
    def __init__(self, *, error_code=None, error_message='provider failure'):
        self.error_code, self.error_message, self.sent_keys = error_code, error_message, set()
    def send(self, payload):
        if self.error_code: raise NotificationProviderFailure(self.error_code, self.error_message)
        key = payload['idempotency_key']; self.sent_keys.add(key)
        return NotificationResult(f'fake-{key}', 'accepted')


class EmailNotificationProvider:
    """Resend-compatible fixed-endpoint email delivery; recipients are server-owned."""
    provider_name = 'resend'
    endpoint = 'https://api.resend.com/emails'

    def __init__(self, *, api_key: str, from_email: str, to_email: str, timeout_seconds: int = 10, transport=None):
        if not all(isinstance(value, str) and value and '\n' not in value and '\r' not in value for value in (api_key, from_email, to_email)):
            raise ValueError('Invalid notification configuration')
        if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 30:
            raise ValueError('Invalid notification configuration')
        self.api_key, self.from_email, self.to_email = api_key, from_email, to_email
        self.timeout_seconds, self.transport = timeout_seconds, transport

    @staticmethod
    def _clean(value) -> str:
        value = re.sub(r'[\r\n]+', ' ', str(value or ''))
        return re.sub(r'(?i)\b(?:bcc|cc|to):', '', value).strip()[:1000]

    def send(self, payload: dict) -> NotificationResult:
        title, summary = self._clean(payload.get('title')), self._clean(payload.get('summary'))
        subject = f'Forecast intelligence: {title[:160] or "Notification"}'
        text = f'{title}\n\n{summary}\n\nNo forecast or evidence state was changed.'
        html = f'<h1>{escape(title)}</h1><p>{escape(summary)}</p><p>No forecast or evidence state was changed.</p>'
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport, follow_redirects=False) as client:
                response = client.post(self.endpoint, headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Idempotency-Key': payload['idempotency_key'],
                }, json={'from': self.from_email, 'to': [self.to_email], 'subject': subject, 'text': text, 'html': html})
        except httpx.TimeoutException as exc:
            raise NotificationProviderFailure('timeout', 'Notification provider timed out') from exc
        except httpx.HTTPError as exc:
            raise NotificationProviderFailure('delivery_failure', 'Notification provider request failed') from exc
        if response.status_code == 429: raise NotificationProviderFailure('rate_limited', 'Notification provider is rate limited')
        if response.status_code in (401, 403): raise NotificationProviderFailure('authentication_failure', 'Notification provider authentication failed')
        if response.status_code >= 500: raise NotificationProviderFailure('delivery_failure', 'Notification provider is temporarily unavailable')
        if response.status_code >= 400: raise NotificationProviderFailure('invalid_destination', 'Notification delivery was rejected')
        try: message_id = response.json()['id']
        except (ValueError, KeyError, TypeError) as exc: raise NotificationProviderFailure('malformed_provider_response', 'Notification provider returned an invalid response') from exc
        if not isinstance(message_id, str) or not message_id: raise NotificationProviderFailure('malformed_provider_response', 'Notification provider returned an invalid response')
        return NotificationResult(message_id[:255], 'accepted')


def build_notification_provider_registry():
    if os.getenv('NOTIFICATION_PROVIDER', '').lower() != 'resend': return {}
    key, sender, destination = os.getenv('NOTIFICATION_API_KEY'), os.getenv('NOTIFICATION_FROM_EMAIL'), os.getenv('NOTIFICATION_TO_EMAIL')
    if not all((key, sender, destination)): return {}
    try:
        return {'resend': EmailNotificationProvider(api_key=key, from_email=sender, to_email=destination, timeout_seconds=int(os.getenv('NOTIFICATION_TIMEOUT_SECONDS', '10')))}
    except (ValueError, TypeError): return {}

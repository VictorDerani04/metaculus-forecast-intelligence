from dataclasses import dataclass
from typing import Protocol

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

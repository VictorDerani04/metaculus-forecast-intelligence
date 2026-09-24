from app.monitoring.providers.base import ProviderFailure, ProviderResult, QuestionContext


class FakeMonitoringProvider:
    """Deterministic test double; never registered by the production app."""
    provider_name = 'fake'
    def __init__(self, *, items=None, error_code: str | None = None):
        self.items, self.error_code = items or [], error_code
    def fetch(self, question: QuestionContext, cursor=None) -> ProviderResult:
        if self.error_code:
            raise ProviderFailure(self.error_code)
        return ProviderResult(items=self.items)

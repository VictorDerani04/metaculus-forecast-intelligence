from typing import Protocol

from app.copilot.schemas import ForecastContext, ProviderResponse


class CopilotProvider(Protocol):
    def respond(self, context: ForecastContext, message: str) -> ProviderResponse: ...


class UnavailableCopilotProvider:
    def respond(self, context: ForecastContext, message: str) -> ProviderResponse:
        raise RuntimeError('No copilot provider is configured')

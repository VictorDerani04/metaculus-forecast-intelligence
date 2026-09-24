from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class QuestionContext:
    question_id: str
    title: str
    resolution_criteria: str | None


@dataclass(frozen=True)
class ProviderResult:
    items: list[dict[str, Any]] = field(default_factory=list)
    next_cursor: str | None = None
    rate_limit_metadata: dict[str, Any] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


class ProviderFailure(Exception):
    def __init__(self, code: str = 'provider_failure'):
        self.code = code
        super().__init__(code)


class MonitoringProvider(Protocol):
    provider_name: str
    def fetch(self, question: QuestionContext, cursor: None = None) -> ProviderResult: ...

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.forecasts.schemas import HumanForecastResponse, RoomQuestion
from app.research.schemas import CandidateResponse, EvidenceResponse


class ProbabilityLayers(BaseModel):
    prior_base_rate: float | None = None
    model: float | None = None
    human_final: float | None = None
    metaculus_community: float | None = None


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal['user', 'assistant']
    content: str
    created_at: datetime

    @field_validator('created_at')
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class ForecastContextData(BaseModel):
    question: RoomQuestion
    probabilities: ProbabilityLayers
    forecast_history: list[HumanForecastResponse]
    approved_evidence: list[EvidenceResponse]
    untrusted_research: list[CandidateResponse]
    recent_chat: list[ChatMessageResponse]
    causal_drivers: list[dict]
    active_model_metadata: dict | None


class ForecastContext(BaseModel):
    system_instructions: str
    untrusted_forecast_data: ForecastContextData


class ActionProposal(BaseModel):
    model_config = ConfigDict(extra='forbid')

    action: Literal[
        'investigate_base_rate', 'inspect_assumption', 'gather_evidence',
        'consider_model_family', 'perform_sensitivity_analysis', 'reconsider_probability',
    ]
    summary: str = Field(min_length=1, max_length=2000)


class ProviderResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    content: str = Field(min_length=1, max_length=20000)
    proposed_actions: list[ActionProposal] = Field(default_factory=list)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=10000)


class ChatExchangeResponse(BaseModel):
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    proposed_actions: list[ActionProposal]


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageResponse]

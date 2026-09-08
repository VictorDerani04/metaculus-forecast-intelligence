from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HumanForecastCreate(BaseModel):
    probability: float = Field(strict=True, ge=0, le=1, allow_inf_nan=False)
    rationale: str | None = None


class HumanForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_id: str
    user_id: str
    probability: float
    rationale: str | None
    created_at: datetime

    @field_validator('created_at')
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        # SQLite drops timezone information from UTC DateTime columns.
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class RoomQuestion(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    competition_id: str
    title: str
    source_url: str | None = None
    resolution_criteria: str | None = None
    question_type: str | None = None
    close_at: datetime | None = None
    resolve_at: datetime | None = None


class ForecastRoomResponse(BaseModel):
    question: RoomQuestion
    prior_probability: float | None = None
    model_probability: float | None = None
    human_forecast: HumanForecastResponse | None = None
    community_probability: float | None = None
    history: list[HumanForecastResponse] = Field(default_factory=list)

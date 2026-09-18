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


class DecisionCreate(BaseModel):
    rationale: str = Field(min_length=1, max_length=10000)


class DecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    question_id: str
    competition_id: str
    human_probability: float | None
    rationale: str
    prior_probability: float | None
    model_probability: float | None
    crowd_probability: float | None
    evidence_ids: list[str]
    model_spec_id: str | None
    model_run_id: str | None
    created_at: datetime

    @classmethod
    def from_snapshot(cls, *, user_id, question, human, source, model, evidence_ids, rationale):
        return cls(
            id=__import__('uuid').uuid4().hex,
            user_id=user_id,
            question_id=question.id,
            competition_id=question.competition_id,
            human_probability=human.probability if human else None,
            rationale=rationale,
            prior_probability=None,
            model_probability=model.probability if model else None,
            crowd_probability=source.crowd_probability if source else None,
            evidence_ids=evidence_ids,
            model_spec_id=model.model_spec_id if model else None,
            model_run_id=model.id if model else None,
            created_at=datetime.now(timezone.utc),
        )

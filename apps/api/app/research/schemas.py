from typing import Literal
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator, model_validator


class CandidateCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    question_id: str
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1)
    source_url: str
    source_name: str = Field(min_length=1, max_length=255)


    @field_validator('source_url')
    @classmethod
    def provenance_url(cls, value):
        return str(TypeAdapter(HttpUrl).validate_python(value))


class DecisionResponse(BaseModel):
    related_item_id: str | None = None
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: str
    decision: str
    created_at: datetime

    @field_validator('created_at')
    @classmethod
    def utc_timestamp(cls, value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class CandidateResponse(CandidateCreate):
    decisions: list[DecisionResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    status: str
    created_at: datetime

    @field_validator('created_at')
    @classmethod
    def utc_timestamp(cls, value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

class DecisionCreate(BaseModel):
    related_item_id: str | None = None
    dependency_evidence_ids: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra='forbid')
    decision: Literal['approved', 'rejected', 'deferred', 'duplicate', 'superseded']


    @model_validator(mode='after')
    def validate_links(self):
        linked = self.decision in ('duplicate', 'superseded')
        if linked != bool(self.related_item_id):
            raise ValueError('Duplicate and superseded decisions require a related candidate; other decisions do not')
        if self.dependency_evidence_ids and self.decision != 'approved':
            raise ValueError('Only approval can record evidence dependencies')
        if len(self.dependency_evidence_ids) != len(set(self.dependency_evidence_ids)):
            raise ValueError('Evidence dependencies must be unique')
        return self


class EvidenceResponse(CandidateCreate):
    dependency_evidence_ids: list[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)
    id: str
    research_item_id: str
    user_id: str
    decision: str
    approved_at: datetime

    @field_validator('approved_at')
    @classmethod
    def utc_timestamp(cls, value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

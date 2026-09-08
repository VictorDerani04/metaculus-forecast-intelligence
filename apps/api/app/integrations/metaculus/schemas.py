from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class MetaculusQuestionData(BaseModel):
    title: str | None = None
    resolution_criteria: str | None = None
    question_type: str | None = None
    close_at: datetime | None = None
    resolve_at: datetime | None = None
    crowd_probability: float | None = None
    source_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator('title', 'resolution_criteria', 'question_type', mode='before')
    @classmethod
    def optional_text(cls, value, info):
        limit = {'title': 500, 'question_type': 100}.get(info.field_name)
        if isinstance(value, str) and value.strip() and (limit is None or len(value) <= limit):
            return value
        return None

    @field_validator('close_at', 'resolve_at', mode='before')
    @classmethod
    def optional_date(cls, value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                pass
        return None

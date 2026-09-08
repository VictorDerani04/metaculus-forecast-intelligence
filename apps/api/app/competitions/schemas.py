from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ManualQuestionDetails(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    resolution_criteria: str | None = None

    @field_validator('title')
    @classmethod
    def nonblank_title(cls, value):
        if not value.strip():
            raise ValueError('Enter a question title')
        return value.strip()


class QuestionImport(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    manual_details: ManualQuestionDetails | None = None


class ImportedQuestionResponse(BaseModel):
    id: str
    competition_id: str
    title: str
    source_post_id: int
    source_url: str
    resolution_criteria: str | None
    question_type: str | None
    close_at: datetime | None
    resolve_at: datetime | None
    crowd_probability: float | None
    import_status: Literal['imported', 'partial', 'manual']

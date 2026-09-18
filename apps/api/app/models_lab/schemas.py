from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

ModelFamily = Literal['base_rate', 'bayesian_likelihood_ratio', 'weighted_driver', 'scenario_tree', 'seeded_monte_carlo']

class ModelSpecCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    family: ModelFamily
    rationale: str = Field(min_length=1)
    parameters: dict
    assumptions: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def evidence_dependencies_are_unique(self):
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError('Evidence dependencies must be unique')
        from app.models_lab.runners import run_model
        try:
            run_model({'family': self.family, 'parameters': self.parameters})
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('Invalid model parameters') from exc
        return self

class ModelSpecResponse(ModelSpecCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    question_id: str
    status: Literal['draft', 'approved']
    version: int
    source_model_id: str | None
    approved_at: datetime | None
    created_at: datetime

class ModelRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    model_spec_id: str
    question_id: str
    user_id: str
    status: Literal['succeeded', 'failed']
    probability: float | None
    inputs: dict
    evidence_ids: list[str]
    model_version: int
    spec_snapshot: dict
    created_at: datetime

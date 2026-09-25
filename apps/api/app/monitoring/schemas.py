from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class MonitoringEnable(BaseModel):
    monitoring_interval_minutes: int | None = Field(default=None, ge=1, le=10080)
    materiality_threshold: float = Field(default=.75, ge=0, le=1)
    digest_threshold: float = Field(default=.30, ge=0, le=1)


class MonitoringRunResponse(BaseModel):
    id: str; job_id: str; status: str; started_at: datetime; completed_at: datetime | None
    providers_attempted: int; providers_succeeded: int; providers_failed: int
    raw_items_seen: int; normalized_findings: int; duplicates_removed: int
    relevant_findings: int; material_findings: int; digest_findings: int; candidates_created: int
    safe_error_summary: str | None
    model_config = ConfigDict(from_attributes=True)


class MonitoringStatusResponse(BaseModel):
    id: str; enabled: bool; monitoring_interval_minutes: int
    last_run_at: datetime | None; last_success_at: datetime | None; next_run_at: datetime | None
    latest_run: MonitoringRunResponse | None = None
    model_config = ConfigDict(from_attributes=True)

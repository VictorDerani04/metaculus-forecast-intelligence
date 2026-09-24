import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MonitoringRunStatus(str, Enum):
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'


class MonitoringConfig(Base):
    __tablename__ = 'monitoring_configs'
    __table_args__ = (UniqueConstraint('user_id', 'question_id', name='uq_monitoring_config_user_question'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey('questions.id'), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metaculus_refresh_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    web_monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    news_monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    monitoring_interval_minutes: Mapped[int] = mapped_column(Integer, default=360, nullable=False)
    materiality_threshold: Mapped[float] = mapped_column(Float, default=.75, nullable=False)
    digest_threshold: Mapped[float] = mapped_column(Float, default=.30, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class MonitoringRun(Base):
    __tablename__ = 'monitoring_runs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey('questions.id'), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey('background_jobs.id'), nullable=False, unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default=MonitoringRunStatus.RUNNING.value, nullable=False)
    providers_attempted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    providers_succeeded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    providers_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    raw_items_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    normalized_findings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicates_removed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    relevant_findings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    material_findings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    digest_findings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    candidates_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    safe_error_summary: Mapped[str | None] = mapped_column(String(255))


def install_monitoring_guards(engine) -> None:
    with engine.begin() as connection:
        if engine.dialect.name == 'sqlite':
            connection.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS monitoring_runs_completed_no_update
                BEFORE UPDATE ON monitoring_runs WHEN OLD.status IN ('succeeded', 'failed')
                BEGIN SELECT RAISE(ABORT, 'Completed monitoring runs are immutable'); END""")
            connection.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS monitoring_runs_completed_no_delete
                BEFORE DELETE ON monitoring_runs WHEN OLD.status IN ('succeeded', 'failed')
                BEGIN SELECT RAISE(ABORT, 'Completed monitoring runs are immutable'); END""")
        elif engine.dialect.name == 'postgresql':
            connection.exec_driver_sql("""CREATE OR REPLACE FUNCTION reject_completed_monitoring_run_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN IF OLD.status IN ('succeeded', 'failed') THEN RAISE EXCEPTION 'Completed monitoring runs are immutable'; END IF; RETURN NEW; END; $$""")
            connection.exec_driver_sql("""CREATE OR REPLACE TRIGGER monitoring_runs_completed_no_mutation
                BEFORE UPDATE OR DELETE ON monitoring_runs FOR EACH ROW EXECUTE FUNCTION reject_completed_monitoring_run_mutation()""")

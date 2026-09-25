import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON, UniqueConstraint, inspect
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
    adaptive_schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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
    # A retry is another immutable execution attempt of the same job.
    job_id: Mapped[str] = mapped_column(ForeignKey('background_jobs.id'), nullable=False, index=True)
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

class ProviderCursor(Base):
    __tablename__ = 'provider_cursors'
    __table_args__ = (UniqueConstraint('user_id', 'question_id', 'provider', name='uq_provider_cursor'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey('questions.id'), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    cursor_value: Mapped[str | None] = mapped_column(String(500))
    last_seen_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_external_id: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

class RawFinding(Base):
    __tablename__ = 'raw_findings'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey('questions.id'), nullable=False, index=True)
    monitoring_run_id: Mapped[str] = mapped_column(ForeignKey('monitoring_runs.id'), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    raw_title: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    raw_metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

class Finding(Base):
    __tablename__ = 'findings'
    __table_args__ = (UniqueConstraint('user_id', 'question_id', 'content_fingerprint', name='uq_finding_fingerprint'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey('questions.id'), nullable=False, index=True)
    monitoring_run_id: Mapped[str] = mapped_column(ForeignKey('monitoring_runs.id'), nullable=False)
    raw_finding_id: Mapped[str] = mapped_column(ForeignKey('raw_findings.id'), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_external_id: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_domain: Mapped[str | None] = mapped_column(String(255))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    relevance_class: Mapped[str] = mapped_column(String(20), default='uncertain', nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    relevance_confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    relevance_reason: Mapped[str] = mapped_column(Text, default='', nullable=False)
    materiality_class: Mapped[str] = mapped_column(String(20), default='irrelevant', nullable=False)
    materiality_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    materiality_confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    materiality_direction: Mapped[str] = mapped_column(String(20), default='neutral', nullable=False)
    materiality_reason: Mapped[str] = mapped_column(Text, default='', nullable=False)
    classifier_provider: Mapped[str] = mapped_column(String(80), default='fake', nullable=False)
    classifier_model: Mapped[str] = mapped_column(String(120), default='deterministic', nullable=False)
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    classifier_schema_version: Mapped[str] = mapped_column(String(80), default='stage-3.2-v1', nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='new', nullable=False)


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


def install_monitoring_schema_upgrades(engine) -> None:
    """Apply additive compatibility upgrades for deployments without migrations."""
    with engine.begin() as connection:
        config_columns = {column['name'] for column in inspect(connection).get_columns('monitoring_configs')}
        if 'adaptive_schedule_enabled' not in config_columns:
            default = 'TRUE' if engine.dialect.name == 'postgresql' else '1'
            connection.exec_driver_sql(
                f'ALTER TABLE monitoring_configs ADD COLUMN adaptive_schedule_enabled BOOLEAN NOT NULL DEFAULT {default}'
            )
        inspector = inspect(connection)
        finding_columns = {column['name'] for column in inspector.get_columns('findings')} if inspector.has_table('findings') else set()
        upgrades = {
            'relevance_confidence': 'FLOAT NOT NULL DEFAULT 0',
            'materiality_confidence': 'FLOAT NOT NULL DEFAULT 0',
            "materiality_direction": "VARCHAR(20) NOT NULL DEFAULT 'neutral'",
            "classifier_provider": "VARCHAR(80) NOT NULL DEFAULT 'fake'",
            "classifier_model": "VARCHAR(120) NOT NULL DEFAULT 'deterministic'",
            'classified_at': 'TIMESTAMP WITH TIME ZONE',
            "classifier_schema_version": "VARCHAR(80) NOT NULL DEFAULT 'stage-3.2-v1'",
        }
        for column, definition in upgrades.items():
            if finding_columns and column not in finding_columns:
                connection.exec_driver_sql(f'ALTER TABLE findings ADD COLUMN {column} {definition}')

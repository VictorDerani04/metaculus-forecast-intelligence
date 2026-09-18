from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelSpec(Base):
    __tablename__ = 'model_specs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey('questions.id'), index=True)
    family: Mapped[str] = mapped_column(String(40))
    rationale: Mapped[str] = mapped_column(Text)
    parameters: Mapped[dict] = mapped_column(JSON)
    assumptions: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_model_id: Mapped[str | None] = mapped_column(ForeignKey('model_specs.id'), index=True)
    status: Mapped[str] = mapped_column(String(20), default='draft')
    version: Mapped[int] = mapped_column(default=1)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ModelRun(Base):
    __tablename__ = 'model_runs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    model_spec_id: Mapped[str] = mapped_column(ForeignKey('model_specs.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey('questions.id'), index=True)
    status: Mapped[str] = mapped_column(String(20), default='succeeded')
    probability: Mapped[float | None]
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    model_version: Mapped[int] = mapped_column()
    spec_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def install_model_guards(engine) -> None:
    """Keep approved specifications and every recorded run immutable."""
    with engine.begin() as connection:
        if engine.dialect.name == 'sqlite':
            connection.exec_driver_sql("""
                CREATE TRIGGER IF NOT EXISTS approved_model_specs_no_update
                BEFORE UPDATE ON model_specs
                WHEN OLD.status = 'approved'
                BEGIN
                    SELECT RAISE(ABORT, 'Approved model specs are immutable');
                END
            """)
            connection.exec_driver_sql("""
                CREATE TRIGGER IF NOT EXISTS model_runs_no_update
                BEFORE UPDATE ON model_runs
                BEGIN
                    SELECT RAISE(ABORT, 'Model runs are append-only');
                END
            """)
            for table in ('model_specs', 'model_runs'):
                connection.exec_driver_sql(f"""
                    CREATE TRIGGER IF NOT EXISTS {table}_no_delete
                    BEFORE DELETE ON {table}
                    BEGIN
                        SELECT RAISE(ABORT, '{'Approved model specs are immutable' if table == 'model_specs' else 'Model runs are append-only'}');
                    END
                """)
        elif engine.dialect.name == 'postgresql':
            connection.exec_driver_sql("""
                CREATE OR REPLACE FUNCTION reject_model_mutation()
                RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    RAISE EXCEPTION 'Approved model specs are immutable';
                END;
                $$
            """)
            connection.exec_driver_sql("""
                CREATE OR REPLACE FUNCTION reject_model_run_mutation()
                RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    RAISE EXCEPTION 'Model runs are append-only';
                END;
                $$
            """)
            connection.exec_driver_sql("""
                CREATE OR REPLACE TRIGGER approved_model_specs_no_update
                BEFORE UPDATE ON model_specs
                FOR EACH ROW WHEN (OLD.status = 'approved') EXECUTE FUNCTION reject_model_mutation()
            """)
            connection.exec_driver_sql("""
                CREATE OR REPLACE TRIGGER model_specs_no_delete
                BEFORE DELETE ON model_specs
                FOR EACH ROW EXECUTE FUNCTION reject_model_mutation()
            """)
            connection.exec_driver_sql("""
                CREATE OR REPLACE TRIGGER model_runs_no_mutation
                BEFORE UPDATE OR DELETE ON model_runs
                FOR EACH ROW EXECUTE FUNCTION reject_model_run_mutation()
            """)

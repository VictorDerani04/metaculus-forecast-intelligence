from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditEvent(Base):
    __tablename__ = 'audit_events'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    question_id: Mapped[str | None] = mapped_column(ForeignKey('questions.id'), index=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(36))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True,
    )


def install_audit_guards(engine) -> None:
    with engine.begin() as connection:
        if engine.dialect.name == 'sqlite':
            connection.exec_driver_sql("""
                CREATE TRIGGER IF NOT EXISTS audit_events_no_update
                BEFORE UPDATE ON audit_events
                BEGIN
                    SELECT RAISE(ABORT, 'Audit events are append-only');
                END
            """)
            connection.exec_driver_sql("""
                CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
                BEFORE DELETE ON audit_events
                BEGIN
                    SELECT RAISE(ABORT, 'Audit events are append-only');
                END
            """)
        elif engine.dialect.name == 'postgresql':
            connection.exec_driver_sql("""
                CREATE OR REPLACE FUNCTION reject_audit_mutation()
                RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    RAISE EXCEPTION 'Audit events are append-only';
                END;
                $$;
            """)
            connection.exec_driver_sql("""
                CREATE OR REPLACE TRIGGER audit_events_no_mutation
                BEFORE UPDATE OR DELETE ON audit_events
                FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()
            """)


class DecisionJournal(Base):
    __tablename__ = 'decision_journal'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey('questions.id'), index=True)
    competition_id: Mapped[str] = mapped_column(ForeignKey('competitions.id'))
    human_probability: Mapped[float | None]
    rationale: Mapped[str] = mapped_column(Text)
    prior_probability: Mapped[float | None]
    model_probability: Mapped[float | None]
    crowd_probability: Mapped[float | None]
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    model_spec_id: Mapped[str | None] = mapped_column(String(36))
    model_run_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True,
    )


def install_journal_guards(engine) -> None:
    with engine.begin() as connection:
        if engine.dialect.name == 'sqlite':
            for operation in ('UPDATE', 'DELETE'):
                connection.exec_driver_sql(f"""
                    CREATE TRIGGER IF NOT EXISTS decision_journal_no_{operation.lower()}
                    BEFORE {operation} ON decision_journal
                    BEGIN
                        SELECT RAISE(ABORT, 'Decision journal is append-only');
                    END
                """)
        elif engine.dialect.name == 'postgresql':
            connection.exec_driver_sql("""
                CREATE OR REPLACE FUNCTION reject_decision_journal_mutation()
                RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    RAISE EXCEPTION 'Decision journal is append-only';
                END;
                $$;
            """)
            connection.exec_driver_sql("""
                CREATE OR REPLACE TRIGGER decision_journal_no_mutation
                BEFORE UPDATE OR DELETE ON decision_journal
                FOR EACH ROW EXECUTE FUNCTION reject_decision_journal_mutation()
            """)

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResearchItem(Base):
    __tablename__ = 'research_items'
    __table_args__ = (Index('uq_research_item_monitoring_finding', 'finding_id', unique=True),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    question_id: Mapped[str] = mapped_column(ForeignKey('questions.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(255))
    origin: Mapped[str] = mapped_column(String(30), default='manual', nullable=False)
    monitoring_run_id: Mapped[str | None] = mapped_column(ForeignKey('monitoring_runs.id'), nullable=True, index=True)
    finding_id: Mapped[str | None] = mapped_column(ForeignKey('findings.id'), nullable=True, index=True)
    provider: Mapped[str | None] = mapped_column(String(80))
    materiality_score: Mapped[float | None] = mapped_column()
    materiality_class: Mapped[str | None] = mapped_column(String(20))
    classification_reason: Mapped[str | None] = mapped_column(Text)
    decisions: Mapped[list['ResearchDecision']] = relationship(order_by='ResearchDecision.id', foreign_keys='ResearchDecision.research_item_id')
    status: Mapped[str] = mapped_column(String(20), default='candidate')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Evidence(Base):
    __tablename__ = 'evidence'
    __table_args__ = (Index('uq_evidence_candidate', 'research_item_id', unique=True),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    research_item_id: Mapped[str] = mapped_column(ForeignKey('research_items.id'))
    question_id: Mapped[str] = mapped_column(ForeignKey('questions.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(255))
    decision: Mapped[str] = mapped_column(String(20), default='approved')
    dependency_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ResearchDecision(Base):
    __tablename__ = 'research_decisions'
    id: Mapped[int] = mapped_column(primary_key=True)
    research_item_id: Mapped[str] = mapped_column(ForeignKey('research_items.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    related_item_id: Mapped[str | None] = mapped_column(ForeignKey('research_items.id'))
    decision: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def install_evidence_guards(engine):
    """Protect accepted evidence and its decision provenance from row mutation."""
    # Also install the additive unique index for an already-created table.
    next(index for index in Evidence.__table__.indexes if index.name == 'uq_evidence_candidate').create(engine, checkfirst=True)
    with engine.begin() as connection:
        if engine.dialect.name == 'sqlite':
            connection.exec_driver_sql("""
                CREATE TRIGGER IF NOT EXISTS evidence_no_duplicate_candidate
                BEFORE INSERT ON evidence
                WHEN EXISTS (SELECT 1 FROM evidence WHERE research_item_id = NEW.research_item_id)
                BEGIN
                    SELECT RAISE(ABORT, 'Evidence and decisions are append-only');
                END
            """)
        for table in ('evidence', 'research_decisions'):
            if engine.dialect.name == 'sqlite':
                connection.exec_driver_sql(f"""
                    CREATE TRIGGER IF NOT EXISTS {table}_no_replace
                    BEFORE INSERT ON {table}
                    WHEN EXISTS (SELECT 1 FROM {table} WHERE id = NEW.id)
                    BEGIN
                        SELECT RAISE(ABORT, 'Evidence and decisions are append-only');
                    END
                """)
                for operation in ('UPDATE', 'DELETE'):
                    connection.exec_driver_sql(f"""
                        CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()}
                        BEFORE {operation} ON {table}
                        BEGIN
                            SELECT RAISE(ABORT, 'Evidence and decisions are append-only');
                        END
                    """)
            elif engine.dialect.name == 'postgresql':
                connection.exec_driver_sql("""
                    CREATE OR REPLACE FUNCTION reject_evidence_mutation()
                    RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN
                        RAISE EXCEPTION 'Evidence and decisions are append-only';
                    END;
                    $$
                """)
                connection.exec_driver_sql(f"""
                    CREATE OR REPLACE TRIGGER {table}_no_mutation
                    BEFORE UPDATE OR DELETE ON {table}
                    FOR EACH ROW EXECUTE FUNCTION reject_evidence_mutation()
                """)


def install_research_schema_upgrades(engine):
    """Additive compatibility upgrades for pre-Task-2 local databases."""
    additions = {
        'origin': "VARCHAR(30) NOT NULL DEFAULT 'manual'",
        'monitoring_run_id': 'VARCHAR(36)',
        'finding_id': 'VARCHAR(36)',
        'provider': 'VARCHAR(80)',
        'materiality_score': 'FLOAT',
        'materiality_class': 'VARCHAR(20)',
        'classification_reason': 'TEXT',
    }
    with engine.begin() as connection:
        if engine.dialect.name == 'sqlite':
            columns = {row[1] for row in connection.exec_driver_sql('PRAGMA table_info(research_items)')}
            for name, definition in additions.items():
                if name not in columns:
                    connection.exec_driver_sql(f'ALTER TABLE research_items ADD COLUMN {name} {definition}')
        elif engine.dialect.name == 'postgresql':
            for name, definition in additions.items():
                connection.exec_driver_sql(f'ALTER TABLE research_items ADD COLUMN IF NOT EXISTS {name} {definition}')
        connection.exec_driver_sql('CREATE UNIQUE INDEX IF NOT EXISTS uq_research_item_monitoring_finding ON research_items (finding_id)')

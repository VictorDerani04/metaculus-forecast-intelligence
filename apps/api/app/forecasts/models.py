from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HumanForecast(Base):
    __tablename__ = 'human_forecasts'

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[str] = mapped_column(ForeignKey('questions.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    probability: Mapped[float]
    rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )


def install_history_guards(engine) -> None:
    """Enforce append-only history, including bulk SQL updates and deletes."""
    with engine.begin() as connection:
        if engine.dialect.name == 'sqlite':
            connection.exec_driver_sql("""
                CREATE TRIGGER IF NOT EXISTS human_forecasts_no_replace
                BEFORE INSERT ON human_forecasts
                WHEN EXISTS (SELECT 1 FROM human_forecasts WHERE id = NEW.id)
                BEGIN
                    SELECT RAISE(ABORT, 'Human forecasts are append-only');
                END
            """)
            for operation in ('UPDATE', 'DELETE'):
                connection.exec_driver_sql(f"""
                    CREATE TRIGGER IF NOT EXISTS human_forecasts_no_{operation.lower()}
                    BEFORE {operation} ON human_forecasts
                    BEGIN
                        SELECT RAISE(ABORT, 'Human forecasts are append-only');
                    END
                """)
        elif engine.dialect.name == 'postgresql':
            connection.exec_driver_sql("""
                CREATE OR REPLACE FUNCTION reject_human_forecast_mutation()
                RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    RAISE EXCEPTION 'Human forecasts are append-only';
                END;
                $$
            """)
            connection.exec_driver_sql("""
                CREATE OR REPLACE TRIGGER human_forecasts_no_mutation
                BEFORE UPDATE OR DELETE ON human_forecasts
                FOR EACH ROW EXECUTE FUNCTION reject_human_forecast_mutation()
            """)

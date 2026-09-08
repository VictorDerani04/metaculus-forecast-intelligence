import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    competition_id: Mapped[str] = mapped_column(
        ForeignKey("competitions.id"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )


class QuestionSource(Base):
    __tablename__ = 'question_sources'

    question_id: Mapped[str] = mapped_column(ForeignKey('questions.id'), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    source_post_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_criteria: Mapped[str | None] = mapped_column(Text)
    question_type: Mapped[str | None] = mapped_column(String(100))
    close_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolve_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    crowd_probability: Mapped[float | None] = mapped_column(Float)
    import_status: Mapped[str] = mapped_column(String(30), nullable=False)
    source_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

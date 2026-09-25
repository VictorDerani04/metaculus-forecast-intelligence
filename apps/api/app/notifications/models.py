import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

def utcnow(): return datetime.now(timezone.utc)

class NotificationPreference(Base):
    __tablename__ = 'notification_preferences'
    __table_args__ = (UniqueConstraint('user_id', 'channel', 'provider', name='uq_notification_preference'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(40), default='in_app', nullable=False)
    provider: Mapped[str] = mapped_column(String(80), default='fake', nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    immediate_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    digest_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

class NotificationAttempt(Base):
    __tablename__ = 'notification_attempts'
    __table_args__ = (
        UniqueConstraint('user_id', 'idempotency_key', name='uq_notification_attempt_idempotency'),
        CheckConstraint('(alert_event_id IS NOT NULL AND digest_id IS NULL) OR (alert_event_id IS NULL AND digest_id IS NOT NULL)', name='ck_notification_attempt_one_source'),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    alert_event_id: Mapped[str | None] = mapped_column(ForeignKey('alert_events.id'), index=True)
    digest_id: Mapped[str | None] = mapped_column(ForeignKey('digests.id'), index=True)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='queued', nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_message_id: Mapped[str | None] = mapped_column(String(255))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error_message: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

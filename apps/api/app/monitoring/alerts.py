"""Internal attention artifacts; delivery and consequential actions are out of scope."""
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from app.db.base import Base
from app.monitoring.models import Finding, FindingEventLink

def utcnow(): return datetime.now(timezone.utc)

class AlertEvent(Base):
    __tablename__ = 'alert_events'; __table_args__ = (UniqueConstraint('user_id', 'finding_id', name='uq_alert_finding'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False, index=True); question_id: Mapped[str] = mapped_column(ForeignKey('questions.id'), nullable=False, index=True); finding_id: Mapped[str] = mapped_column(ForeignKey('findings.id'), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False); reason: Mapped[str] = mapped_column(String(500), nullable=False); status: Mapped[str] = mapped_column(String(20), default='new', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False); seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class Digest(Base):
    __tablename__ = 'digests'; __table_args__ = (UniqueConstraint('user_id', 'period_start', 'period_end', name='uq_digest_period'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4())); user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False); period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False); status: Mapped[str] = mapped_column(String(20), default='generated', nullable=False); generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False); delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class DigestItem(Base):
    __tablename__ = 'digest_items'; __table_args__ = (UniqueConstraint('user_id', 'finding_id', name='uq_digest_item_finding'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4())); user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False, index=True); question_id: Mapped[str] = mapped_column(ForeignKey('questions.id'), nullable=False, index=True); finding_id: Mapped[str] = mapped_column(ForeignKey('findings.id'), nullable=False)
    eligible_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False); included_in_digest_id: Mapped[str | None] = mapped_column(ForeignKey('digests.id')); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

def route_finding(session: Session, finding: Finding):
    cluster_link = session.scalar(select(FindingEventLink).where(FindingEventLink.finding_id == finding.id, FindingEventLink.user_id == finding.user_id, FindingEventLink.question_id == finding.question_id))
    if cluster_link:
        prior_findings = select(FindingEventLink.finding_id).where(FindingEventLink.event_cluster_id == cluster_link.event_cluster_id, FindingEventLink.user_id == finding.user_id, FindingEventLink.finding_id != finding.id)
        # The first routed material finding represents the event. Subsequent
        # same-event copies add corroboration but never duplicate attention.
        if session.scalar(select(AlertEvent.id).where(AlertEvent.user_id == finding.user_id, AlertEvent.finding_id.in_(prior_findings))):
            return
    if finding.materiality_class in {'material', 'critical'}:
        if not session.scalar(select(AlertEvent.id).where(AlertEvent.user_id == finding.user_id, AlertEvent.finding_id == finding.id)):
            session.add(AlertEvent(user_id=finding.user_id, question_id=finding.question_id, finding_id=finding.id, severity=finding.materiality_class, reason=finding.materiality_reason))
    elif finding.materiality_class == 'digest':
        if not session.scalar(select(DigestItem.id).where(DigestItem.user_id == finding.user_id, DigestItem.finding_id == finding.id)):
            session.add(DigestItem(user_id=finding.user_id, question_id=finding.question_id, finding_id=finding.id, eligible_at=finding.discovered_at))

def get_owned_alert(session: Session, *, user_id: str, alert_id: str):
    alert = session.scalar(select(AlertEvent).where(AlertEvent.id == alert_id, AlertEvent.user_id == user_id))
    if alert is None: raise HTTPException(status_code=404, detail='Alert not found')
    return alert

def transition_alert(session: Session, *, user_id: str, alert_id: str, target: str):
    alert = get_owned_alert(session, user_id=user_id, alert_id=alert_id)
    if target == 'dismissed' and alert.status != 'dismissed': alert.status, alert.dismissed_at = 'dismissed', utcnow()
    elif target == 'seen' and alert.status == 'new': alert.status, alert.seen_at = 'seen', utcnow()
    return alert

def get_owned_digest(session: Session, *, user_id: str, digest_id: str):
    digest = session.scalar(select(Digest).where(Digest.id == digest_id, Digest.user_id == user_id))
    if digest is None: raise HTTPException(status_code=404, detail='Digest not found')
    return digest

def generate_daily_digest(session: Session, *, user_id: str, period_start: datetime, period_end: datetime):
    if period_start.tzinfo is None or period_end.tzinfo is None or period_end <= period_start: raise ValueError('Digest period must be a non-empty UTC-aware interval')
    existing = session.scalar(select(Digest).where(Digest.user_id == user_id, Digest.period_start == period_start, Digest.period_end == period_end))
    if existing is not None: return existing
    digest = Digest(user_id=user_id, period_start=period_start, period_end=period_end); session.add(digest); session.flush()
    eligible = session.scalars(select(DigestItem).where(DigestItem.user_id == user_id, DigestItem.included_in_digest_id.is_(None), DigestItem.eligible_at >= period_start, DigestItem.eligible_at < period_end).order_by(DigestItem.eligible_at, DigestItem.id)).all()
    for item in eligible: item.included_in_digest_id = digest.id
    return digest

from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from app.audit.service import record_audit
from app.auth.models import User
from app.auth.routes import get_current_user
from app.monitoring.alerts import AlertEvent, Digest, DigestItem, get_owned_digest, transition_alert
from app.monitoring.models import Finding
from app.competitions.models import Question

router = APIRouter(tags=['alerts'])
class AlertResponse(BaseModel):
    id: str; question_id: str; question_title: str = ''; finding_id: str; severity: str; reason: str; status: str; created_at: datetime; seen_at: datetime | None; dismissed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
class DigestSummary(BaseModel):
    id: str; period_start: datetime; period_end: datetime; status: str; generated_at: datetime; delivered_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
class FindingSummary(BaseModel):
    id: str; title: str; summary: str; question_id: str; materiality_class: str
    model_config = ConfigDict(from_attributes=True)
class DigestItemResponse(BaseModel): id: str; eligible_at: datetime; finding: FindingSummary
class DigestDetail(DigestSummary): items: list[DigestItemResponse]

@router.get('/alerts', response_model=list[AlertResponse])
def list_alerts(request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        rows = session.execute(select(AlertEvent, Question.title).join(Question, Question.id == AlertEvent.question_id).where(AlertEvent.user_id == user.id).order_by(AlertEvent.created_at.desc(), AlertEvent.id.desc())).all()
        return [AlertResponse(**(AlertResponse.model_validate(alert).model_dump() | {'question_title': title})) for alert, title in rows]
def _transition(request, user, alert_id, target):
    with request.app.state.session_factory() as session:
        alert = transition_alert(session, user_id=user.id, alert_id=alert_id, target=target); title = session.scalar(select(Question.title).where(Question.id == alert.question_id)); record_audit(session, user_id=user.id, question_id=alert.question_id, action=f'alert_{target}', entity_type='alert_event', entity_id=alert.id); session.commit(); return AlertResponse(**(AlertResponse.model_validate(alert).model_dump() | {'question_title': title or 'Unknown question'}))
@router.post('/alerts/{alert_id}/seen', response_model=AlertResponse)
def mark_seen(alert_id: str, request: Request, user: Annotated[User, Depends(get_current_user)]): return _transition(request, user, alert_id, 'seen')
@router.post('/alerts/{alert_id}/dismiss', response_model=AlertResponse)
def dismiss(alert_id: str, request: Request, user: Annotated[User, Depends(get_current_user)]): return _transition(request, user, alert_id, 'dismissed')
@router.get('/digests', response_model=list[DigestSummary])
def list_digests(request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session: return [DigestSummary.model_validate(x) for x in session.scalars(select(Digest).where(Digest.user_id == user.id).order_by(Digest.period_start.desc(), Digest.id.desc())).all()]
@router.get('/digests/{digest_id}', response_model=DigestDetail)
def digest_detail(digest_id: str, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        digest = get_owned_digest(session, user_id=user.id, digest_id=digest_id); rows = session.execute(select(DigestItem, Finding).join(Finding, Finding.id == DigestItem.finding_id).where(DigestItem.user_id == user.id, DigestItem.included_in_digest_id == digest.id).order_by(DigestItem.eligible_at, DigestItem.id)).all()
        return DigestDetail(**DigestSummary.model_validate(digest).model_dump(), items=[DigestItemResponse(id=i.id, eligible_at=i.eligible_at, finding=FindingSummary.model_validate(f)) for i, f in rows])

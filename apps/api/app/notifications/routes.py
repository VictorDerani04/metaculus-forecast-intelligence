from typing import Annotated
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from app.auth.models import User
from app.auth.routes import get_current_user
from app.notifications.models import NotificationAttempt, NotificationPreference
from app.notifications.service import save_preference, schedule_alert_delivery, schedule_digest_delivery

router = APIRouter(tags=['notifications'])
class PreferenceInput(BaseModel): enabled: bool; immediate_alerts_enabled: bool; digest_enabled: bool
class PreferenceResponse(PreferenceInput):
    id: str; user_id: str; channel: str; provider: str
    model_config = ConfigDict(from_attributes=True)
class AttemptResponse(BaseModel):
    id: str; alert_event_id: str | None; digest_id: str | None; channel: str; provider: str; status: str; attempt_number: int; external_message_id: str | None; last_error_code: str | None; last_error_message: str | None
    model_config = ConfigDict(from_attributes=True)
@router.get('/notification-preferences', response_model=list[PreferenceResponse])
def list_preferences(request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session: return [PreferenceResponse.model_validate(x) for x in session.scalars(select(NotificationPreference).where(NotificationPreference.user_id == user.id)).all()]
@router.put('/notification-preferences', response_model=PreferenceResponse)
def update_preferences(payload: PreferenceInput, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        result = save_preference(session, user_id=user.id, values=payload.model_dump()); session.commit(); return PreferenceResponse.model_validate(result)
@router.get('/notification-attempts', response_model=list[AttemptResponse])
def list_attempts(request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session: return [AttemptResponse.model_validate(x) for x in session.scalars(select(NotificationAttempt).where(NotificationAttempt.user_id == user.id).order_by(NotificationAttempt.created_at.desc())).all()]
@router.post('/alerts/{alert_id}/deliver', response_model=AttemptResponse)
def deliver_alert(alert_id: str, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        result = schedule_alert_delivery(session, user_id=user.id, alert_id=alert_id); session.commit(); return AttemptResponse.model_validate(result)
@router.post('/digests/{digest_id}/deliver', response_model=AttemptResponse)
def deliver_digest(digest_id: str, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        result = schedule_digest_delivery(session, user_id=user.id, digest_id=digest_id); session.commit(); return AttemptResponse.model_validate(result)

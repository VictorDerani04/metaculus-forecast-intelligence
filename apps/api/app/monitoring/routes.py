from typing import Annotated
from datetime import datetime
from fastapi import APIRouter, Depends, Request, status

from app.auth.models import User
from app.auth.routes import get_current_user
from app.audit.service import record_audit
from app.monitoring.schemas import MonitoringEnable, MonitoringStatusResponse, MonitoringRunResponse
from app.monitoring.service import disable_monitoring, enable_monitoring, enqueue_manual_run, get_status, list_runs
from app.forecasts.service import get_owned_question
from app.monitoring.models import Finding
from sqlalchemy import select
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix='/questions', tags=['monitoring'])

@router.get('/{question_id}/monitoring', response_model=MonitoringStatusResponse)
def monitoring_status(question_id: str, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        return get_status(session, user_id=user.id, question_id=question_id)

@router.post('/{question_id}/monitoring/enable', response_model=MonitoringStatusResponse)
def monitoring_enable(question_id: str, payload: MonitoringEnable, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        config = enable_monitoring(session, user_id=user.id, question_id=question_id, settings=payload)
        session.commit()
        return get_status(session, user_id=user.id, question_id=question_id)

@router.post('/{question_id}/monitoring/disable', response_model=MonitoringStatusResponse)
def monitoring_disable(question_id: str, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        disable_monitoring(session, user_id=user.id, question_id=question_id)
        session.commit()
        return get_status(session, user_id=user.id, question_id=question_id)

@router.post('/{question_id}/monitoring/run', status_code=status.HTTP_202_ACCEPTED)
def monitoring_run(question_id: str, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        job = enqueue_manual_run(session, user_id=user.id, question_id=question_id)
        record_audit(session, user_id=user.id, question_id=question_id, action='monitoring_manual_run', entity_type='background_job', entity_id=job.id)
        session.commit()
        return {'job_id': job.id, 'status': job.status}

@router.get('/{question_id}/monitoring/runs', response_model=list[MonitoringRunResponse])
def monitoring_runs(question_id: str, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        return list_runs(session, user_id=user.id, question_id=question_id)

class FindingResponse(BaseModel):
    id: str; provider: str; source_url: str | None; canonical_url: str | None; title: str; summary: str; source_name: str; source_domain: str | None
    normalized_source: str | None; source_type: str; source_reliability: str; source_reliability_reason: str; reporting_origin: str | None
    relevance_class: str; relevance_score: float; relevance_confidence: float; relevance_reason: str
    materiality_class: str; materiality_score: float; materiality_confidence: float; materiality_direction: str; materiality_reason: str
    classifier_provider: str; classifier_model: str; classified_at: datetime | None; classifier_schema_version: str; status: str
    model_config = ConfigDict(from_attributes=True)

@router.get('/{question_id}/findings', response_model=list[FindingResponse])
def findings(question_id: str, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        get_owned_question(session, question_id, user.id)
        return [FindingResponse.model_validate(row) for row in session.scalars(select(Finding).where(Finding.question_id == question_id, Finding.user_id == user.id).order_by(Finding.discovered_at.desc(), Finding.id.desc())).all()]

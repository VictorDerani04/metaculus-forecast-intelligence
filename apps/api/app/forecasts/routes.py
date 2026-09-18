from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict

from app.auth.models import User
from app.auth.routes import get_current_user
from app.forecasts.schemas import ForecastRoomResponse, HumanForecastCreate, HumanForecastResponse, DecisionCreate, DecisionResponse
from app.forecasts.service import create_human_forecast, get_forecast_room
from app.forecasts.decision_service import create_decision, list_decisions, list_audit

class ForecastRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def validated(request: Request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                # Invalid NaN/Infinity inputs cannot be echoed in JSON responses.
                details = [{key: error[key] for key in ('loc', 'msg', 'type')}
                           for error in exc.errors()]
                return JSONResponse(status_code=422, content={'detail': details})

        return validated


router = APIRouter(prefix='/questions', tags=['forecasts'], route_class=ForecastRoute)


@router.post('/{question_id}/forecasts', response_model=HumanForecastResponse, status_code=201)
def record_human_forecast(
    question_id: str,
    payload: HumanForecastCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    with request.app.state.session_factory() as session:
        return create_human_forecast(session, question_id, user.id, payload)


@router.get('/{question_id}/room', response_model=ForecastRoomResponse)
def forecast_room(
    question_id: str,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    with request.app.state.session_factory() as session:
        return get_forecast_room(session, question_id, user.id)


@router.post('/{question_id}/decisions', response_model=DecisionResponse, status_code=201)
def record_decision(
    question_id: str,
    payload: DecisionCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    with request.app.state.session_factory() as session:
        return create_decision(session, question_id, user.id, payload)


@router.get('/{question_id}/decisions', response_model=list[DecisionResponse])
def decision_history(
    question_id: str,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    with request.app.state.session_factory() as session:
        return list_decisions(session, question_id, user.id)


class AuditEventResponse(BaseModel):
    id: str
    action: str
    entity_type: str
    entity_id: str
    question_id: str | None
    details: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get('/{question_id}/audit', response_model=list[AuditEventResponse])
def audit_history(
    question_id: str,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    with request.app.state.session_factory() as session:
        return list_audit(session, question_id, user.id)

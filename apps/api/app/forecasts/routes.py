from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.auth.models import User
from app.auth.routes import get_current_user
from app.forecasts.schemas import ForecastRoomResponse, HumanForecastCreate, HumanForecastResponse
from app.forecasts.service import create_human_forecast, get_forecast_room

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

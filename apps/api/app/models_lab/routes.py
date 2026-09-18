from typing import Annotated
from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from app.auth.models import User
from app.auth.routes import get_current_user
from app.models_lab.schemas import ModelRunResponse, ModelSpecCreate, ModelSpecResponse
from app.models_lab.service import approve_model, create_model, create_model_version, get_model, list_models, run_approved_model

class ModelRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def validated(request: Request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                return JSONResponse(status_code=422, content={'detail': [
                    {key: error[key] for key in ('loc', 'msg', 'type')} for error in exc.errors()
                ]})
        return validated


router = APIRouter(tags=['models'], route_class=ModelRoute)

@router.post('/questions/{question_id}/models', response_model=ModelSpecResponse, status_code=201)
def create(question_id: str, payload: ModelSpecCreate, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        return create_model(session, question_id, user.id, payload)

@router.get('/questions/{question_id}/models', response_model=list[ModelSpecResponse])
def list_question_models(question_id: str, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        return list_models(session, question_id, user.id)

@router.get('/models/{model_id}', response_model=ModelSpecResponse)
def get(model_id: str, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        return get_model(session, model_id, user.id)

@router.post('/models/{model_id}/versions', response_model=ModelSpecResponse, status_code=201)
def create_version(model_id: str, payload: ModelSpecCreate, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        return create_model_version(session, model_id, user.id, payload)

@router.post('/models/{model_id}/activate', response_model=ModelSpecResponse)
def activate(model_id: str, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        return approve_model(session, model_id, user.id)

@router.post('/models/{model_id}/run', response_model=ModelRunResponse, status_code=201)
def run(model_id: str, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        return run_approved_model(session, model_id, user.id)

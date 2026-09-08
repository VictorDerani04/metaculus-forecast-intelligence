from typing import Annotated
from fastapi import APIRouter, Depends, Request
from app.auth.models import User
from app.auth.routes import get_current_user
from app.research.schemas import CandidateCreate, CandidateResponse, DecisionCreate
from app.research.service import create_candidate, research_for_question, decide_candidate

router = APIRouter(tags=['research'])


@router.post('/research-items', response_model=CandidateResponse, status_code=201)
def add_research(payload: CandidateCreate, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        return create_candidate(session, user.id, payload)


@router.get('/questions/{question_id}/research')
def read_research(question_id: str, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        return research_for_question(session, question_id, user.id)


@router.post('/research-items/{item_id}/decision', response_model=CandidateResponse)
def decide_research(item_id: str, payload: DecisionCreate, request: Request, user: Annotated[User, Depends(get_current_user)]):
    with request.app.state.session_factory() as session:
        return decide_candidate(session, item_id, user.id, payload)

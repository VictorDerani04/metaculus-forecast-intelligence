from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.auth.models import User
from app.auth.routes import get_current_user
from app.competitions.models import Competition, Question


router = APIRouter(prefix="/competitions", tags=["competitions"])


class CompetitionCreate(BaseModel):
    name: str


class CompetitionResponse(BaseModel):
    id: str
    name: str
    question_count: int = 0


class QuestionCreate(BaseModel):
    title: str


class QuestionResponse(BaseModel):
    id: str
    competition_id: str
    title: str


@router.get("", response_model=list[CompetitionResponse])
def list_competitions(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    session_factory = request.app.state.session_factory

    with session_factory() as session:
        competitions = session.scalars(
            select(Competition)
            .where(Competition.user_id == user.id)
            .order_by(Competition.name)
        ).all()

        return [
            CompetitionResponse(
                id=competition.id,
                name=competition.name,
                question_count=session.scalar(
                    select(func.count(Question.id)).where(
                        Question.competition_id == competition.id
                    )
                )
                or 0,
            )
            for competition in competitions
        ]

@router.post(
    "",
    response_model=CompetitionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_competition(
    payload: CompetitionCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    session_factory = request.app.state.session_factory

    with session_factory() as session:
        competition = Competition(
            user_id=user.id,
            name=payload.name,
        )
        session.add(competition)
        session.commit()
        session.refresh(competition)

        return CompetitionResponse(
            id=competition.id,
            name=competition.name,
        )


def get_owned_competition(session, competition_id: str, user_id: str) -> Competition:
    competition = session.scalar(
        select(Competition).where(
            Competition.id == competition_id,
            Competition.user_id == user_id,
        )
    )

    if not competition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Competition not found",
        )

    return competition


@router.post(
    "/{competition_id}/questions",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_question(
    competition_id: str,
    payload: QuestionCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    session_factory = request.app.state.session_factory

    with session_factory() as session:
        get_owned_competition(session, competition_id, user.id)

        question = Question(
            competition_id=competition_id,
            title=payload.title,
        )
        session.add(question)
        session.commit()
        session.refresh(question)

        return QuestionResponse(
            id=question.id,
            competition_id=question.competition_id,
            title=question.title,
        )


@router.get(
    "/{competition_id}/questions",
    response_model=list[QuestionResponse],
)
def list_questions(
    competition_id: str,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    session_factory = request.app.state.session_factory

    with session_factory() as session:
        get_owned_competition(session, competition_id, user.id)

        questions = session.scalars(
            select(Question)
            .where(Question.competition_id == competition_id)
            .order_by(Question.title)
        ).all()

        return [
            QuestionResponse(
                id=question.id,
                competition_id=question.competition_id,
                title=question.title,
            )
            for question in questions
        ]

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.competitions.models import Question, QuestionSource
from app.competitions.routes import get_owned_competition

from app.forecasts.models import HumanForecast
from app.forecasts.schemas import (
    ForecastRoomResponse, HumanForecastCreate, HumanForecastResponse, RoomQuestion,
)


def get_owned_question(session: Session, question_id: str, user_id: str) -> Question:
    question = session.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail='Question not found')
    get_owned_competition(session, question.competition_id, user_id)
    return question


def create_human_forecast(
    session: Session, question_id: str, user_id: str, payload: HumanForecastCreate,
) -> HumanForecastResponse:
    get_owned_question(session, question_id, user_id)
    forecast = HumanForecast(question_id=question_id, user_id=user_id, **payload.model_dump())
    session.add(forecast)
    session.flush()
    result = HumanForecastResponse.model_validate(forecast)
    session.commit()
    return result


def get_forecast_room(session: Session, question_id: str, user_id: str) -> ForecastRoomResponse:
    question = get_owned_question(session, question_id, user_id)
    records = session.scalars(
        select(HumanForecast)
        .where(HumanForecast.question_id == question_id, HumanForecast.user_id == user_id)
        .order_by(HumanForecast.created_at, HumanForecast.id)
    ).all()
    history = [HumanForecastResponse.model_validate(record) for record in records]
    source = session.scalar(select(QuestionSource).where(
        QuestionSource.question_id == question_id, QuestionSource.user_id == user_id,
    ))
    room_question = RoomQuestion.model_validate(question)
    if source:
        room_question = room_question.model_copy(update={
            field: getattr(source, field) for field in (
                'source_url', 'resolution_criteria', 'question_type', 'close_at', 'resolve_at',
            )
        })
    return ForecastRoomResponse(
        question=room_question,
        community_probability=source.crowd_probability if source else None,
        history=history,
        human_forecast=history[-1] if history else None,
    )

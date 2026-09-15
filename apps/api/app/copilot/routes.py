from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select

from app.auth.models import User
from app.auth.routes import get_current_user
from app.copilot.context import build_forecast_context
from app.copilot.models import ChatMessage, ChatThread
from app.copilot.schemas import (
    ChatExchangeResponse,
    ChatHistoryResponse,
    ChatMessageResponse,
    ChatRequest,
    ProviderResponse,
)
from app.forecasts.service import get_owned_question


router = APIRouter(tags=['copilot'])


@router.get('/questions/{question_id}/chat', response_model=ChatHistoryResponse)
def read_chat(
    question_id: str,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    with request.app.state.session_factory() as session:
        get_owned_question(session, question_id, user.id)
        messages = session.scalars(select(ChatMessage).where(
            ChatMessage.user_id == user.id,
            ChatMessage.question_id == question_id,
        ).order_by(ChatMessage.created_at, ChatMessage.id)).all()
        return ChatHistoryResponse(
            messages=[ChatMessageResponse.model_validate(message) for message in messages],
        )


@router.post(
    '/questions/{question_id}/chat',
    response_model=ChatExchangeResponse,
    status_code=201,
)
def send_chat(
    question_id: str,
    payload: ChatRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    with request.app.state.session_factory() as session:
        context = build_forecast_context(user.id, question_id, session=session)
        try:
            output = ProviderResponse.model_validate(
                request.app.state.copilot_provider.respond(context, payload.content),
            )
        except (Exception, ValidationError) as exc:
            raise HTTPException(
                status_code=503,
                detail='Copilot temporarily unavailable',
            ) from exc

        thread = session.scalar(select(ChatThread).where(
            ChatThread.user_id == user.id,
            ChatThread.question_id == question_id,
        ))
        if thread is None:
            thread = ChatThread(user_id=user.id, question_id=question_id)
            session.add(thread)
            session.flush()
        user_message = ChatMessage(
            thread_id=thread.id,
            user_id=user.id,
            question_id=question_id,
            role='user',
            content=payload.content,
        )
        assistant_message = ChatMessage(
            thread_id=thread.id,
            user_id=user.id,
            question_id=question_id,
            role='assistant',
            content=output.content,
        )
        session.add_all((user_message, assistant_message))
        session.flush()
        result = ChatExchangeResponse(
            user_message=ChatMessageResponse.model_validate(user_message),
            assistant_message=ChatMessageResponse.model_validate(assistant_message),
            proposed_actions=output.proposed_actions,
        )
        session.commit()
        return result

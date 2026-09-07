from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from app.auth.models import User
from app.auth.passwords import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr


def get_session_factory(request: Request):
    return request.app.state.session_factory


def get_current_user(
    request: Request,
    session_factory=Depends(get_session_factory),
) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    with session_factory() as session:
        user = session.get(User, user_id)
        if not user or not user.is_active:
            request.session.clear()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        session.expunge(user)
        return user


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, request: Request, session_factory=Depends(get_session_factory)):
    normalized = payload.email.strip().lower()
    with session_factory() as session:
        user = session.scalar(select(User).where(User.email == normalized))
        if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        request.session.clear()
        request.session["user_id"] = user.id
        return UserResponse(id=user.id, email=user.email)


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]):
    return UserResponse(id=user.id, email=user.email)

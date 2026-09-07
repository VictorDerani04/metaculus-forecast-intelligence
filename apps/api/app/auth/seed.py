from sqlalchemy import select

from app.auth.models import User
from app.auth.passwords import hash_password


def seed_private_user(session_factory, email: str, password: str) -> User:
    normalized = email.strip().lower()
    with session_factory() as session:
        existing = session.scalar(select(User).where(User.email == normalized))
        if existing:
            return existing
        user = User(email=normalized, password_hash=hash_password(password), is_active=True)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

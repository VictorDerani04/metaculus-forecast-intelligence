from sqlalchemy import select

from app.auth.models import User
from app.auth.passwords import hash_password, verify_password


def seed_private_user(
    session_factory,
    email: str,
    password: str,
    *,
    synchronize_password: bool = False,
) -> User:
    normalized = email.strip().lower()
    with session_factory() as session:
        existing = session.scalar(select(User).where(User.email == normalized))
        if existing:
            if synchronize_password and not verify_password(password, existing.password_hash):
                existing.password_hash = hash_password(password)
                session.commit()
                session.refresh(existing)
            return existing
        user = User(email=normalized, password_hash=hash_password(password), is_active=True)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

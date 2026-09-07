import os

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.auth.routes import router as auth_router
from app.auth.seed import seed_private_user
from app.db.base import Base
from app.db.session import build_session_factory


def create_app(
    database_url: str | None = None,
    session_secret: str | None = None,
    seed_user: bool = True,
) -> FastAPI:
    database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///./forecast_intelligence.db")
    session_secret = session_secret or os.getenv("SESSION_SECRET", "dev-only-change-me")
    engine, session_factory = build_session_factory(database_url)
    Base.metadata.create_all(engine)

    app = FastAPI(title="Metaculus Forecast Intelligence")
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        session_cookie="session",
        same_site="lax",
        https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    )
    app.include_router(auth_router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    if seed_user:
        email = os.getenv("PRIVATE_USER_EMAIL")
        password = os.getenv("PRIVATE_USER_PASSWORD")
        if email and password:
            seed_private_user(session_factory, email, password)

    return app


app = create_app()

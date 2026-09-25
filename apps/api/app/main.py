import os
from sqlalchemy import text
from fastapi import HTTPException

from app.competitions import models as competition_models
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.auth.routes import router as auth_router
from app.auth.seed import seed_private_user
from app.competitions.routes import router as competitions_router
from app.forecasts.routes import router as forecasts_router
from app.forecasts.models import install_history_guards
from app.research.routes import router as research_router
from app.research.models import install_evidence_guards, install_research_schema_upgrades
from app.copilot.provider import UnavailableCopilotProvider
from app.copilot.routes import router as copilot_router
from app.models_lab.routes import router as models_router
from app.models_lab.models import install_model_guards
from app.analytics.routes import router as analytics_router
from app.monitoring.routes import router as monitoring_router
from app.monitoring.alert_routes import router as alerts_router
from app.notifications.routes import router as notifications_router
from app.audit.models import install_audit_guards, install_journal_guards
from app.audit import models as audit_models
from app.jobs import models as job_models
from app.monitoring import models as monitoring_models
from app.monitoring import alerts as alert_models
from app.notifications import models as notification_models
from app.monitoring.providers.live import build_live_provider_registry
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
    install_history_guards(engine)
    install_evidence_guards(engine)
    install_research_schema_upgrades(engine)
    install_model_guards(engine)
    install_audit_guards(engine)
    install_journal_guards(engine)
    monitoring_models.install_monitoring_schema_upgrades(engine)
    monitoring_models.install_monitoring_guards(engine)

    app = FastAPI(title="Metaculus Forecast Intelligence")
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.copilot_provider = UnavailableCopilotProvider()
    app.state.monitoring_providers = build_live_provider_registry()
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        session_cookie="session",
        same_site="lax",
        https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.getenv('WEB_ORIGIN', 'http://localhost:3000')],
        allow_credentials=True,
        allow_methods=['GET', 'POST', 'PUT'],
        allow_headers=['Content-Type'],
    )
    app.include_router(auth_router)
    app.include_router(competitions_router)
    app.include_router(forecasts_router)
    app.include_router(research_router)
    app.include_router(copilot_router)
    app.include_router(models_router)
    app.include_router(analytics_router)
    app.include_router(monitoring_router)
    app.include_router(alerts_router)
    app.include_router(notifications_router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        try:
            if app.state.engine is None:
                raise RuntimeError('engine unavailable')
            with app.state.engine.connect() as connection:
                connection.execute(text('SELECT 1'))
        except Exception:
            raise HTTPException(status_code=503, detail='Database is unavailable')
        return {"status": "ready"}

    if seed_user:
        email = os.getenv("PRIVATE_USER_EMAIL")
        password = os.getenv("PRIVATE_USER_PASSWORD")
        if email and password:
            seed_private_user(session_factory, email, password)

    return app


app = create_app()

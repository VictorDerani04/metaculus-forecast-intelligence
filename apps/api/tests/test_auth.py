from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.auth.seed import seed_private_user


def make_client(tmp_path):
    db_path = tmp_path / "auth.db"
    app = create_app(
        database_url=f"sqlite:///{db_path}",
        session_secret="test-session-secret",
        seed_user=False,
    )
    return app, TestClient(app)


def test_login_rejects_unknown_user(tmp_path):
    _, client = make_client(tmp_path)

    response = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_login_sets_session_for_seeded_user(tmp_path):
    app, client = make_client(tmp_path)
    seed_private_user(app.state.session_factory, "owner@example.com", "correct horse battery staple")

    response = client.post(
        "/auth/login",
        json={
            "email": "owner@example.com",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"
    assert "session=" in response.headers["set-cookie"]
    assert "httponly" in response.headers["set-cookie"].lower()

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "owner@example.com"
    assert me.json()["id"]


def test_me_requires_session(tmp_path):
    _, client = make_client(tmp_path)

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_production_startup_rejects_sqlite_and_default_session_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SESSION_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="PostgreSQL"):
        create_app(seed_user=False)


def test_production_rejects_sqlite_even_with_a_strong_secret(monkeypatch):
    from app.main import validate_production_configuration

    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        validate_production_configuration("sqlite:///release.db", "x" * 32)


def test_production_rejects_missing_session_secret(monkeypatch):
    from app.main import validate_production_configuration

    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        validate_production_configuration("postgresql+psycopg://host/db", None)


def test_production_rejects_blank_session_secret(monkeypatch):
    from app.main import validate_production_configuration

    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        validate_production_configuration("postgresql://host/db", "   ")


def test_production_rejects_default_session_secret(monkeypatch):
    from app.main import validate_production_configuration

    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        validate_production_configuration("postgresql://host/db", "dev-only-change-me")


def test_production_accepts_a_valid_postgresql_url_and_strong_secret(monkeypatch):
    from app.main import validate_production_configuration

    monkeypatch.setenv("APP_ENV", "production")
    validate_production_configuration("postgresql+psycopg://host/db", "x" * 32)


def test_production_cookie_is_always_secure(monkeypatch, tmp_path):
    import app.main as main
    from app.db.session import build_session_factory

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setattr(main, "build_session_factory", lambda _: build_session_factory(f"sqlite:///{tmp_path / 'cookie.db'}"))
    app = main.create_app(database_url="postgresql+psycopg://host/db", session_secret="x" * 32, seed_user=False)
    session = next(middleware for middleware in app.user_middleware if middleware.cls.__name__ == "SessionMiddleware")
    assert session.kwargs["https_only"] is True

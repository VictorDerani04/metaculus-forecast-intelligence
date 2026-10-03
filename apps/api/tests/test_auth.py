from fastapi.testclient import TestClient
import pytest
from base64 import b64encode
import json
from itsdangerous import TimestampSigner

from app.main import create_app
from app.auth.seed import seed_private_user


def test_root_env_loading_preserves_deployment_values(monkeypatch, tmp_path):
    from app.main import load_environment

    env_file = tmp_path / ".env"
    env_file.write_text("PRIVATE_USER_EMAIL=from-file@example.com\nSESSION_SECRET=from-file\n")
    monkeypatch.setenv("PRIVATE_USER_EMAIL", "from-process@example.com")
    monkeypatch.delenv("SESSION_SECRET", raising=False)

    load_environment(env_file)

    assert __import__("os").environ["PRIVATE_USER_EMAIL"] == "from-process@example.com"
    assert __import__("os").environ["SESSION_SECRET"] == "from-file"


def test_development_seed_sync_updates_the_configured_password(tmp_path):
    app, client = make_client(tmp_path)
    seed_private_user(app.state.session_factory, "owner@example.com", "old-password")

    seed_private_user(
        app.state.session_factory,
        "owner@example.com",
        "new-password",
        synchronize_password=True,
    )

    assert client.post("/auth/login", json={"email": "owner@example.com", "password": "old-password"}).status_code == 401
    assert client.post("/auth/login", json={"email": "owner@example.com", "password": "new-password"}).status_code == 200


def test_production_rejects_private_user_password_synchronization(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SYNC_PRIVATE_USER_PASSWORD", "true")

    with pytest.raises(RuntimeError, match="SYNC_PRIVATE_USER_PASSWORD"):
        create_app(
            database_url=f"sqlite:///{tmp_path / 'auth.db'}",
            session_secret="x" * 32,
            seed_user=False,
        )


def test_non_development_environment_rejects_private_user_password_synchronization(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("SYNC_PRIVATE_USER_PASSWORD", "true")

    with pytest.raises(RuntimeError, match="SYNC_PRIVATE_USER_PASSWORD"):
        create_app(
            database_url=f"sqlite:///{tmp_path / 'auth.db'}",
            session_secret="test-session-secret",
            seed_user=False,
        )


def test_session_expiry_is_explicit_and_configurable(monkeypatch, tmp_path):
    monkeypatch.setenv("SESSION_MAX_AGE_SECONDS", "3600")
    app, _ = make_client(tmp_path)
    session = next(middleware for middleware in app.user_middleware if middleware.cls.__name__ == "SessionMiddleware")

    assert session.kwargs["max_age"] == 3600


def test_expired_session_cookie_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("SESSION_MAX_AGE_SECONDS", "1")
    app, client = make_client(tmp_path)
    user = seed_private_user(app.state.session_factory, "owner@example.com", "correct horse battery staple")
    signer = TimestampSigner("test-session-secret")
    cookie = signer.sign(b64encode(json.dumps({"user_id": user.id}).encode())).decode()
    client.cookies.set("session", cookie)

    assert client.get("/auth/me").status_code == 200

    get_timestamp = TimestampSigner.get_timestamp
    monkeypatch.setattr(TimestampSigner, "get_timestamp", lambda self: get_timestamp(self) + 2)
    assert client.get("/auth/me").status_code == 401


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


def test_login_rejects_incorrect_password(tmp_path):
    app, client = make_client(tmp_path)
    seed_private_user(app.state.session_factory, "owner@example.com", "correct horse battery staple")

    response = client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "incorrect-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_seed_creates_a_new_configured_email_without_changing_existing_user(tmp_path):
    app, client = make_client(tmp_path)
    seed_private_user(app.state.session_factory, "first@example.com", "first-password")
    seed_private_user(app.state.session_factory, "second@example.com", "second-password")

    assert client.post("/auth/login", json={"email": "first@example.com", "password": "first-password"}).status_code == 200
    assert client.post("/auth/login", json={"email": "second@example.com", "password": "second-password"}).status_code == 200


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
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    assert "max-age=1209600" in response.headers["set-cookie"].lower()

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "owner@example.com"
    assert me.json()["id"]


def test_login_session_is_invalidated_by_logout(tmp_path):
    app, client = make_client(tmp_path)
    seed_private_user(app.state.session_factory, "owner@example.com", "correct horse battery staple")

    login_response = client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery staple"},
    )
    assert login_response.status_code == 200
    assert client.get("/auth/me").status_code == 200

    logout_response = client.post("/auth/logout")

    assert logout_response.status_code == 204
    assert "expires=thu, 01 jan 1970" in logout_response.headers["set-cookie"].lower()
    assert client.get("/auth/me").status_code == 401


def test_localhost_cors_allows_credentialed_login_requests(tmp_path):
    _, client = make_client(tmp_path)

    response = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"


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

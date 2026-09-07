from fastapi.testclient import TestClient

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

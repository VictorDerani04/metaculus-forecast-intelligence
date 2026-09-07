from fastapi.testclient import TestClient

from app.main import create_app
from app.auth.seed import seed_private_user


TEST_EMAIL = "owner@example.com"
TEST_PASSWORD = "correct horse battery staple"


def make_client(tmp_path):
    db_path = tmp_path / "competitions.db"
    app = create_app(
        database_url=f"sqlite:///{db_path}",
        session_secret="test-session-secret",
        seed_user=False,
    )
    return app, TestClient(app)


def login(app, client: TestClient) -> None:
    seed_private_user(
        app.state.session_factory,
        TEST_EMAIL,
        TEST_PASSWORD,
    )

    response = client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200


def test_competitions_require_authentication(tmp_path):
    _, client = make_client(tmp_path)

    response = client.get("/competitions")

    assert response.status_code == 401


def test_authenticated_user_can_list_competitions(tmp_path):
    app, client = make_client(tmp_path)

    login(app, client)

    response = client.get("/competitions")

    assert response.status_code == 200
    assert response.json() == []


def test_authenticated_user_can_create_and_list_competition(tmp_path):
    app, client = make_client(tmp_path)

    login(app, client)

    create_response = client.post(
        "/competitions",
        json={
            "name": "Metaculus Cup Fall 2026",
        },
    )

    assert create_response.status_code == 201

    created = create_response.json()
    assert created["id"]
    assert created["name"] == "Metaculus Cup Fall 2026"

    list_response = client.get("/competitions")

    assert list_response.status_code == 200
    assert list_response.json() == [
        {
             "id": created["id"],
            "name": "Metaculus Cup Fall 2026",
            "question_count": 0,
        }
    ]


def test_authenticated_user_can_create_and_list_questions_for_competition(tmp_path):
    app, client = make_client(tmp_path)

    login(app, client)

    competition_response = client.post(
        "/competitions",
        json={
            "name": "Metaculus Cup Fall 2026",
        },
    )
    assert competition_response.status_code == 201
    competition_id = competition_response.json()["id"]

    create_question_response = client.post(
        f"/competitions/{competition_id}/questions",
        json={
            "title": "Will event X occur before December 31, 2026?",
        },
    )

    assert create_question_response.status_code == 201

    created = create_question_response.json()
    assert created["id"]
    assert created["competition_id"] == competition_id
    assert created["title"] == "Will event X occur before December 31, 2026?"

    list_response = client.get(
        f"/competitions/{competition_id}/questions"
    )

    assert list_response.status_code == 200
    assert list_response.json() == [
        {
            "id": created["id"],
            "competition_id": competition_id,
            "title": "Will event X occur before December 31, 2026?",
        }
    ]


def test_user_cannot_access_another_users_competition_questions(tmp_path):
    app, owner_client = make_client(tmp_path)

    login(app, owner_client)

    competition_response = owner_client.post(
        "/competitions",
        json={"name": "Owner Competition"},
    )
    assert competition_response.status_code == 201
    competition_id = competition_response.json()["id"]

    other_client = TestClient(app)

    seed_private_user(
        app.state.session_factory,
        "other@example.com",
        "other-password",
    )

    login_response = other_client.post(
        "/auth/login",
        json={
            "email": "other@example.com",
            "password": "other-password",
        },
    )
    assert login_response.status_code == 200

    response = other_client.get(
        f"/competitions/{competition_id}/questions"
    )

    assert response.status_code == 404


def test_competition_list_includes_question_count(tmp_path):
    app, client = make_client(tmp_path)

    login(app, client)

    competition_response = client.post(
        "/competitions",
        json={"name": "Metaculus Cup Fall 2026"},
    )
    assert competition_response.status_code == 201
    competition_id = competition_response.json()["id"]

    question_response = client.post(
        f"/competitions/{competition_id}/questions",
        json={"title": "Will event X occur?"},
    )
    assert question_response.status_code == 201

    response = client.get("/competitions")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": competition_id,
            "name": "Metaculus Cup Fall 2026",
            "question_count": 1,
        }
    ]

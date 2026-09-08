from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.auth.seed import seed_private_user
from test_competitions import login, make_client


@pytest.fixture
def owned_question(tmp_path):
    app, client = make_client(tmp_path)
    login(app, client)
    competition = client.post('/competitions', json={'name': 'Forecast Cup'}).json()
    response = client.post(
        f"/competitions/{competition['id']}/questions",
        json={'title': 'Will event X occur?'},
    )
    assert response.status_code == 201
    return app, client, response.json()


def test_owner_can_record_a_human_forecast(owned_question):
    app, client, question = owned_question
    before = datetime.now(timezone.utc)
    response = client.post(f"/questions/{question['id']}/forecasts", json={
        'probability': 0.64, 'rationale': 'Official data supports this estimate.',
    })
    assert response.status_code == 201
    saved = response.json()
    assert saved['id']
    assert saved['question_id'] == question['id']
    assert saved['user_id'] == client.get('/auth/me').json()['id']
    assert saved['probability'] == 0.64
    assert saved['rationale'] == 'Official data supports this estimate.'
    assert before <= datetime.fromisoformat(saved['created_at']) <= datetime.now(timezone.utc)
    from app.forecasts.models import HumanForecast
    with app.state.session_factory() as session:
        record = session.get(HumanForecast, saved['id'])
        assert record.probability == 0.64
        assert record.rationale == saved['rationale']


@pytest.mark.parametrize('identity, expected', [('other', 404), ('anonymous', 401), ('missing', 404)])
def test_only_owner_can_submit_for_an_existing_question(owned_question, identity, expected):
    from sqlalchemy import func, select
    from app.forecasts.models import HumanForecast

    app, owner, question = owned_question
    client = TestClient(app) if identity != 'missing' else owner
    if identity == 'other':
        seed_private_user(app.state.session_factory, 'other@example.com', 'other-password')
        assert client.post('/auth/login', json={
            'email': 'other@example.com', 'password': 'other-password',
        }).status_code == 200
    question_id = 'missing-question' if identity == 'missing' else question['id']
    response = client.post(f'/questions/{question_id}/forecasts', json={'probability': 0.7})
    assert response.status_code == expected
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(HumanForecast.id))) == 0


@pytest.mark.parametrize('probability', [-0.01, 1.01, '0.64', True, False, None, 'NaN', 'Infinity'])
def test_invalid_probabilities_are_rejected_without_creating_history(owned_question, probability):
    from sqlalchemy import func, select
    from app.forecasts.models import HumanForecast

    app, client, question = owned_question
    response = client.post(f"/questions/{question['id']}/forecasts", json={'probability': probability})
    assert response.status_code == 422
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(HumanForecast.id))) == 0


@pytest.mark.parametrize('token', ['NaN', 'Infinity', '-Infinity'])
def test_nonfinite_json_number_returns_validation_error(owned_question, token):
    from sqlalchemy import func, select
    from app.forecasts.models import HumanForecast
    app, client, question = owned_question
    response = client.post(
        f"/questions/{question['id']}/forecasts",
        content='{"probability":' + token + '}',
        headers={'Content-Type': 'application/json'},
    )
    assert response.status_code == 422
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(HumanForecast.id))) == 0


def test_room_starts_with_distinct_unavailable_probabilities(owned_question):
    _, client, question = owned_question
    response = client.get(f"/questions/{question['id']}/room")
    assert response.status_code == 200
    room = response.json()
    assert room == {
        'question': {**question, 'source_url': None, 'resolution_criteria': None,
                     'question_type': None, 'close_at': None, 'resolve_at': None},
        'prior_probability': None,
        'model_probability': None,
        'human_forecast': None,
        'community_probability': None,
        'history': [],
    }


def test_second_forecast_appends_history_and_latest_is_derived(owned_question):
    from sqlalchemy import select
    from app.forecasts.models import HumanForecast

    app, client, question = owned_question
    url = f"/questions/{question['id']}/forecasts"
    first_response = client.post(url, json={'probability': 0, 'rationale': 'First assessment'})
    assert first_response.status_code == 201
    first = first_response.json()
    second_response = client.post(url, json={'probability': 1, 'rationale': 'New evidence'})
    assert second_response.status_code == 201
    second = second_response.json()
    assert first['id'] != second['id']
    room = client.get(f"/questions/{question['id']}/room").json()
    assert room['history'] == [first, second]
    assert room['human_forecast'] == second
    assert room['prior_probability'] is None
    assert room['model_probability'] is None
    assert room['community_probability'] is None
    with app.state.session_factory() as session:
        history = session.scalars(select(HumanForecast).order_by(HumanForecast.id)).all()
        assert [(row.probability, row.rationale) for row in history] == [(0, 'First assessment'), (1, 'New evidence')]


@pytest.mark.parametrize('community', [None, 0.0, 0.72])
def test_room_uses_stored_source_metadata_and_keeps_community_separate(owned_question, community):
    from app.competitions.models import QuestionSource
    app, client, question = owned_question
    with app.state.session_factory() as session:
        session.add(QuestionSource(
            question_id=question['id'], user_id=client.get('/auth/me').json()['id'],
            source_post_id=45262, source_url='https://www.metaculus.com/questions/45262/',
            resolution_criteria='Official resolution criteria.', question_type='binary',
            close_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
            resolve_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
            crowd_probability=community, source_payload={}, import_status='partial',
        ))
        session.commit()
    response = client.get(f"/questions/{question['id']}/room")
    assert response.status_code == 200
    room = response.json()
    assert room['question']['resolution_criteria'] == 'Official resolution criteria.'
    assert room['question']['source_url'] == 'https://www.metaculus.com/questions/45262/'
    assert room['question']['question_type'] == 'binary'
    assert datetime.fromisoformat(room['question']['close_at']).date().isoformat() == '2026-11-01'
    assert datetime.fromisoformat(room['question']['resolve_at']).date().isoformat() == '2026-12-01'
    assert room['community_probability'] == community
    assert room['human_forecast'] is None
    assert room['history'] == []


@pytest.mark.parametrize('operation', ['update', 'delete'])
def test_persisted_history_rejects_mutation_at_database_boundary(owned_question, operation):
    from sqlalchemy import delete, update
    from sqlalchemy.exc import DBAPIError
    from app.forecasts.models import HumanForecast

    app, client, question = owned_question
    first = client.post(f"/questions/{question['id']}/forecasts", json={
        'probability': 0.35, 'rationale': 'Original reasoning',
    }).json()
    statement = (update(HumanForecast).values(probability=0.9, rationale='Overwritten')
                 if operation == 'update' else delete(HumanForecast))
    with pytest.raises(DBAPIError, match='append-only'):
        with app.state.engine.begin() as connection:
            connection.execute(statement.where(HumanForecast.id == first['id']))
    room = client.get(f"/questions/{question['id']}/room").json()
    assert room['history'] == [first]


@pytest.mark.parametrize('identity,expected', [('other', 404), ('anonymous', 401), ('missing', 404)])
def test_forecast_room_enforces_read_ownership(owned_question, identity, expected):
    app, owner, question = owned_question
    assert owner.post(f"/questions/{question['id']}/forecasts", json={'probability': 0.63}).status_code == 201
    client = owner if identity == 'missing' else TestClient(app)
    if identity == 'other':
        seed_private_user(app.state.session_factory, 'other@example.com', 'other-password')
        client.post('/auth/login', json={'email': 'other@example.com', 'password': 'other-password'})
    question_id = 'missing-question' if identity == 'missing' else question['id']
    response = client.get(f'/questions/{question_id}/room')
    assert response.status_code == expected
    assert 'human_forecast' not in response.json()


def test_history_is_scoped_and_equal_timestamps_have_stable_order(owned_question):
    from app.forecasts.models import HumanForecast
    app, client, question = owned_question
    other_question = client.post(f"/competitions/{question['competition_id']}/questions", json={'title': 'Other target'}).json()
    user_id = client.get('/auth/me').json()['id']
    timestamp = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    with app.state.session_factory() as session:
        for target_id, probability in [(question['id'], 0.2), (other_question['id'], 0.99), (question['id'], 0.8)]:
            session.add(HumanForecast(question_id=target_id, user_id=user_id, probability=probability, created_at=timestamp))
            session.flush()
        session.commit()
    room = client.get(f"/questions/{question['id']}/room").json()
    assert [entry['probability'] for entry in room['history']] == [0.2, 0.8]
    assert room['human_forecast'] == room['history'][-1]
    assert room == client.get(f"/questions/{question['id']}/room").json()

def test_sqlite_replace_cannot_overwrite_history(owned_question):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    app, client, question = owned_question
    first = client.post(f"/questions/{question['id']}/forecasts", json={'probability': 0.35}).json()
    with pytest.raises(DBAPIError, match='append-only'):
        with app.state.engine.begin() as connection:
            connection.execute(text('INSERT OR REPLACE INTO human_forecasts (id, question_id, user_id, probability, rationale, created_at) VALUES (:id, :question_id, :user_id, 0.9, :rationale, :created_at)'), first)
    assert client.get(f"/questions/{question['id']}/room").json()['history'] == [first]

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, update
from sqlalchemy.exc import DBAPIError

from app.auth.seed import seed_private_user
from test_competitions import login, make_client


@pytest.fixture
def owned_question(tmp_path):
    app, client = make_client(tmp_path)
    login(app, client)
    competition = client.post('/competitions', json={'name': 'Decision Cup'}).json()
    question = client.post(
        f"/competitions/{competition['id']}/questions",
        json={'title': 'Will the event happen?'},
    ).json()
    return app, client, question


def test_decision_journal_captures_forecast_snapshot_and_is_append_only(owned_question):
    app, client, question = owned_question
    forecast = client.post(
        f"/questions/{question['id']}/forecasts",
        json={'probability': 0.64, 'rationale': 'Evidence supports this.'},
    ).json()

    response = client.post(
        f"/questions/{question['id']}/decisions",
        json={'rationale': 'I am committing to the current estimate.'},
    )

    assert response.status_code == 201
    decision = response.json()
    assert decision['question_id'] == question['id']
    assert decision['human_probability'] == forecast['probability']
    assert decision['rationale'] == 'I am committing to the current estimate.'
    assert decision['model_probability'] is None
    assert decision['crowd_probability'] is None
    assert client.get(f"/questions/{question['id']}/decisions").json() == [decision]

    from app.audit.models import DecisionJournal
    with app.state.engine.begin() as connection:
        with pytest.raises(DBAPIError, match='append-only'):
            connection.execute(
                update(DecisionJournal)
                .where(DecisionJournal.id == decision['id'])
                .values(rationale='rewritten')
            )
        with pytest.raises(DBAPIError, match='append-only'):
            connection.execute(
                delete(DecisionJournal).where(DecisionJournal.id == decision['id'])
            )


def test_decision_journal_requires_owner_and_preserves_distinct_probability_layers(owned_question):
    app, owner, question = owned_question
    seed_private_user(app.state.session_factory, 'other@example.com', 'other-password')
    other = TestClient(app)
    assert other.post('/auth/login', json={
        'email': 'other@example.com', 'password': 'other-password',
    }).status_code == 200

    assert other.post(
        f"/questions/{question['id']}/decisions",
        json={'rationale': 'Not mine.'},
    ).status_code == 404
    assert other.get(f"/questions/{question['id']}/decisions").status_code == 404
    assert other.get(f"/questions/{question['id']}/audit").status_code == 404


def test_audit_events_record_explicit_forecast_and_decision_actions_in_order(owned_question):
    app, client, question = owned_question
    client.post(
        f"/questions/{question['id']}/forecasts",
        json={'probability': 0.4, 'rationale': 'Initial estimate.'},
    )
    decision = client.post(
        f"/questions/{question['id']}/decisions",
        json={'rationale': 'Final decision for now.'},
    )
    assert decision.status_code == 201

    response = client.get(f"/questions/{question['id']}/audit")
    assert response.status_code == 200
    events = response.json()
    assert [event['action'] for event in events] == [
        'human_forecast_recorded',
        'decision_recorded',
    ]
    assert events[0]['entity_id']
    assert all(event['question_id'] == question['id'] for event in events)
    assert events[0]['created_at'] <= events[1]['created_at']
    from app.audit.models import AuditEvent
    with app.state.engine.begin() as connection:
        with pytest.raises(DBAPIError, match='append-only'):
            connection.execute(
                update(AuditEvent).where(AuditEvent.id == events[0]['id']).values(action='rewritten')
            )
        with pytest.raises(DBAPIError, match='append-only'):
            connection.execute(delete(AuditEvent).where(AuditEvent.id == events[0]['id']))

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.auth.seed import seed_private_user
from test_forecasts import owned_question


def add_candidate(client, question_id, **changes):
    payload = {'question_id': question_id, 'title': 'Official release',
               'summary': 'Reported output rose.', 'source_url': 'https://example.org/report',
               'source_name': 'Statistics office'}
    response = client.post('/research-items', json={**payload, **changes})
    assert response.status_code == 201
    return response.json()


def test_manual_creation_is_candidate_only(owned_question):
    _, client, question = owned_question
    before = client.get(f"/questions/{question['id']}/room").json()
    item = add_candidate(client, question['id'])
    assert item['status'] == 'candidate'
    assert item['user_id'] == client.get('/auth/me').json()['id']
    assert item['title'] == 'Official release'
    assert item['source_url'] == 'https://example.org/report'
    assert datetime.fromisoformat(item['created_at']).tzinfo is not None
    response = client.get(f"/questions/{question['id']}/research")
    assert response.status_code == 200
    assert response.json() == {'items': [item], 'evidence': []}
    assert client.get(f"/questions/{question['id']}/room").json() == before

@pytest.mark.parametrize('identity,expected', [('anonymous', 401), ('other', 404), ('missing', 404)])
@pytest.mark.parametrize('operation', ['create', 'list'])
def test_candidate_ownership(owned_question, identity, expected, operation):
    from sqlalchemy import func, select
    from app.research.models import ResearchItem
    app, owner, question = owned_question
    client = owner if identity == 'missing' else TestClient(app)
    if identity == 'other':
        seed_private_user(app.state.session_factory, 'other@example.com', 'other-password')
        client.post('/auth/login', json={'email': 'other@example.com', 'password': 'other-password'})
    question_id = 'missing' if identity == 'missing' else question['id']
    response = client.get(f'/questions/{question_id}/research') if operation == 'list' else client.post('/research-items', json={
        'question_id': question_id, 'title': 'Test', 'summary': 'Test', 'source_url': 'https://example.org/', 'source_name': 'Test',
    })
    assert response.status_code == expected
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(ResearchItem.id))) == 0

@pytest.mark.parametrize('changes', [
    {'title': ''}, {'title': '   '}, {'summary': ''}, {'source_name': ''},
    {'source_url': 'javascript:alert(1)'}, {'source_url': 'file:///secret'},
    {'source_url': 'not-a-url'}, {'status': 'approved'}, {'user_id': 'forged'},
])
def test_invalid_or_privileged_candidate_fields_are_rejected(owned_question, changes):
    _, client, question = owned_question
    response = client.post('/research-items', json={
        'question_id': question['id'], 'title': 'Title', 'summary': 'Summary',
        'source_url': 'https://example.org/', 'source_name': 'Source', **changes,
    })
    assert response.status_code == 422
    assert client.get(f"/questions/{question['id']}/research").json() == {'items': [], 'evidence': []}


def test_explicit_approval_records_evidence_provenance(owned_question):
    _, client, question = owned_question
    item = add_candidate(client, question['id'])
    start = datetime.now(timezone.utc)
    response = client.post(f"/research-items/{item['id']}/decision", json={'decision': 'approved'})
    assert response.status_code == 200
    data = client.get(f"/questions/{question['id']}/research").json()
    assert data['items'][0]['status'] == 'approved'
    assert len(data['evidence']) == 1
    evidence = data['evidence'][0]
    assert evidence['research_item_id'] == item['id']
    assert evidence['question_id'] == question['id']
    assert evidence['user_id'] == item['user_id']
    assert evidence['decision'] == 'approved'
    for field in ('title', 'summary', 'source_url', 'source_name'):
        assert evidence[field] == item[field]
    assert start <= datetime.fromisoformat(evidence['approved_at']) <= datetime.now(timezone.utc)


def test_approval_does_not_change_forecast_history_or_probability_layers(owned_question):
    _, client, question = owned_question
    assert client.post(f"/questions/{question['id']}/forecasts", json={
        'probability': 0.61, 'rationale': 'Independent human judgment',
    }).status_code == 201
    before = client.get(f"/questions/{question['id']}/room").json()
    item = add_candidate(client, question['id'])
    assert client.post(f"/research-items/{item['id']}/decision", json={'decision': 'approved'}).status_code == 200
    assert client.get(f"/questions/{question['id']}/room").json() == before


def test_populated_research_and_evidence_are_private(owned_question):
    app, owner, question = owned_question
    item = add_candidate(owner, question['id'])
    assert owner.post(f"/research-items/{item['id']}/decision", json={'decision': 'approved'}).status_code == 200
    seed_private_user(app.state.session_factory, 'other@example.com', 'other-password')
    stranger = TestClient(app)
    assert stranger.post('/auth/login', json={
        'email': 'other@example.com', 'password': 'other-password',
    }).status_code == 200
    response = stranger.get(f"/questions/{question['id']}/research")
    assert response.status_code == 404
    assert 'items' not in response.json()
    assert 'evidence' not in response.json()

@pytest.mark.parametrize('identity,expected', [('anonymous', 401), ('other', 404), ('missing', 404)])
@pytest.mark.parametrize('decision', ['approved', 'rejected'])
def test_only_owner_can_decide(owned_question, identity, expected, decision):
    app, owner, question = owned_question
    item = add_candidate(owner, question['id'])
    client = owner if identity == 'missing' else TestClient(app)
    if identity == 'other':
        seed_private_user(app.state.session_factory, 'other@example.com', 'other-password')
        client.post('/auth/login', json={'email': 'other@example.com', 'password': 'other-password'})
    item_id = 'missing' if identity == 'missing' else item['id']
    response = client.post(f'/research-items/{item_id}/decision', json={'decision': decision})
    assert response.status_code == expected
    assert owner.get(f"/questions/{question['id']}/research").json() == {'items': [item], 'evidence': []}

@pytest.mark.parametrize('decision', ['rejected', 'deferred'])
def test_nonapproval_preserves_candidate_without_eligible_evidence(owned_question, decision):
    from app.research.service import eligible_evidence
    app, client, question = owned_question
    item = add_candidate(client, question['id'])
    response = client.post(f"/research-items/{item['id']}/decision", json={'decision': decision})
    assert response.status_code == 200
    data = client.get(f"/questions/{question['id']}/research").json()
    assert data['items'][0]['status'] == decision
    assert data['evidence'] == []
    with app.state.session_factory() as session:
        assert eligible_evidence(session, question['id'], item['user_id']) == []


def test_eligible_evidence_defensively_filters_nonapproved_records(owned_question):
    from app.research.models import Evidence
    from app.research.service import eligible_evidence
    app, client, question = owned_question
    item = add_candidate(client, question['id'])
    with app.state.session_factory() as session:
        session.add(Evidence(
            research_item_id=item['id'], question_id=question['id'], user_id=item['user_id'],
            title=item['title'], summary=item['summary'], source_url=item['source_url'],
            source_name=item['source_name'], decision='rejected',
        ))
        session.commit()
        assert eligible_evidence(session, question['id'], item['user_id']) == []


def test_repeated_approval_creates_only_one_evidence_record(owned_question):
    _, client, question = owned_question
    item = add_candidate(client, question['id'])
    url = f"/research-items/{item['id']}/decision"
    assert client.post(url, json={'decision': 'approved'}).status_code == 200
    before = client.get(f"/questions/{question['id']}/research").json()
    assert client.post(url, json={'decision': 'approved'}).status_code == 200
    assert client.get(f"/questions/{question['id']}/research").json() == before


def test_simultaneous_approval_is_safe(owned_question):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    app, owner, question = owned_question
    item = add_candidate(owner, question['id'])
    barrier = Barrier(6)
    def approve(_):
        with TestClient(app, cookies=owner.cookies) as client:
            barrier.wait(timeout=10)
            return client.post(f"/research-items/{item['id']}/decision", json={'decision': 'approved'}).status_code
    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(approve, range(6)))
    assert all(code in (200, 409) for code in codes)
    assert len(owner.get(f"/questions/{question['id']}/research").json()['evidence']) == 1

@pytest.mark.parametrize('first,second', [('approved', 'rejected'), ('rejected', 'approved')])
def test_terminal_decision_cannot_be_reversed(owned_question, first, second):
    _, client, question = owned_question
    item = add_candidate(client, question['id'])
    url = f"/research-items/{item['id']}/decision"
    assert client.post(url, json={'decision': first}).status_code == 200
    before = client.get(f"/questions/{question['id']}/research").json()
    assert client.post(url, json={'decision': second}).status_code == 409
    assert client.get(f"/questions/{question['id']}/research").json() == before


@pytest.mark.parametrize('payload', [{'decision': 'candidate'}, {'decision': 'bogus'}, {'decision': 'approved', 'user_id': 'forged'}])
def test_invalid_decision_is_rejected(owned_question, payload):
    _, client, question = owned_question
    item = add_candidate(client, question['id'])
    assert client.post(f"/research-items/{item['id']}/decision", json=payload).status_code == 422
    assert client.get(f"/questions/{question['id']}/research").json() == {'items': [item], 'evidence': []}


def test_defer_then_approve_preserves_decision_audit(owned_question):
    _, client, question = owned_question
    item = add_candidate(client, question['id'])
    url = f"/research-items/{item['id']}/decision"
    for decision in ('deferred', 'approved'):
        assert client.post(url, json={'decision': decision}).status_code == 200
    item = client.get(f"/questions/{question['id']}/research").json()['items'][0]
    assert [entry['decision'] for entry in item['decisions']] == ['deferred', 'approved']
    assert all(entry['user_id'] == item['user_id'] for entry in item['decisions'])
    assert all(datetime.fromisoformat(entry['created_at']).tzinfo for entry in item['decisions'])

@pytest.mark.parametrize('decision', ['duplicate', 'superseded'])
def test_related_candidate_decision_retains_link_without_evidence(owned_question, decision):
    _, client, question = owned_question
    original = add_candidate(client, question['id'])
    item = add_candidate(client, question['id'], title='Related release')
    response = client.post(f"/research-items/{item['id']}/decision", json={
        'decision': decision, 'related_item_id': original['id'],
    })
    assert response.status_code == 200
    assert response.json()['decisions'][0]['related_item_id'] == original['id']
    assert client.get(f"/questions/{question['id']}/research").json()['evidence'] == []


def test_approval_records_dependencies_on_accepted_evidence(owned_question):
    _, client, question = owned_question
    original = add_candidate(client, question['id'])
    client.post(f"/research-items/{original['id']}/decision", json={'decision': 'approved'})
    evidence_id = client.get(f"/questions/{question['id']}/research").json()['evidence'][0]['id']
    item = add_candidate(client, question['id'], title='Dependent interpretation')
    response = client.post(f"/research-items/{item['id']}/decision", json={
        'decision': 'approved', 'dependency_evidence_ids': [evidence_id],
    })
    assert response.status_code == 200
    ledger = client.get(f"/questions/{question['id']}/research").json()['evidence']
    assert ledger[1]['dependency_evidence_ids'] == [evidence_id]


def test_approval_rejects_duplicate_dependency_ids(owned_question):
    _, client, question = owned_question
    original = add_candidate(client, question['id'])
    assert client.post(f"/research-items/{original['id']}/decision", json={'decision': 'approved'}).status_code == 200
    evidence_id = client.get(f"/questions/{question['id']}/research").json()['evidence'][0]['id']
    item = add_candidate(client, question['id'], title='Dependent interpretation')
    response = client.post(f"/research-items/{item['id']}/decision", json={
        'decision': 'approved', 'dependency_evidence_ids': [evidence_id, evidence_id],
    })
    assert response.status_code == 422
    data = client.get(f"/questions/{question['id']}/research").json()
    assert data['items'][1]['status'] == 'candidate'
    assert len(data['evidence']) == 1

@pytest.mark.parametrize('payload', [
    {'decision': 'duplicate'}, {'decision': 'superseded'},
    {'decision': 'rejected', 'related_item_id': 'anything'},
    {'decision': 'deferred', 'dependency_evidence_ids': ['anything']},
])
def test_incompatible_link_decisions_are_rejected(owned_question, payload):
    _, client, question = owned_question
    item = add_candidate(client, question['id'])
    assert client.post(f"/research-items/{item['id']}/decision", json=payload).status_code == 422


@pytest.mark.parametrize('target', ['self', 'missing', 'other_question', 'other_user'])
def test_related_candidate_must_belong_to_same_owned_question(owned_question, target):
    app, client, question = owned_question
    item = add_candidate(client, question['id'])
    related_id = item['id'] if target == 'self' else 'missing'
    if target in ('other_question', 'other_user'):
        other_question = client.post(f"/competitions/{question['competition_id']}/questions", json={'title': 'Other'}).json()
        other = add_candidate(client, other_question['id'])
        related_id = other['id']
        if target == 'other_user':
            from app.research.models import ResearchItem
            seed_private_user(app.state.session_factory, 'other@example.com', 'other-password')
            stranger = TestClient(app)
            stranger.post('/auth/login', json={'email': 'other@example.com', 'password': 'other-password'})
            with app.state.session_factory() as session:
                session.get(ResearchItem, related_id).user_id = stranger.get('/auth/me').json()['id']
                session.commit()
    response = client.post(f"/research-items/{item['id']}/decision", json={'decision': 'duplicate', 'related_item_id': related_id})
    assert response.status_code == (422 if target == 'self' else 404)
    assert client.get(f"/questions/{question['id']}/research").json()['items'][0]['status'] == 'candidate'


def test_unapproved_or_unowned_dependency_is_not_accepted(owned_question):
    _, client, question = owned_question
    item = add_candidate(client, question['id'])
    response = client.post(f"/research-items/{item['id']}/decision", json={'decision': 'approved', 'dependency_evidence_ids': [item['id']]})
    assert response.status_code == 404
    assert client.get(f"/questions/{question['id']}/research").json()['evidence'] == []


@pytest.mark.parametrize('evidence_decision,candidate_status', [
    ('rejected', 'approved'), ('approved', 'candidate'),
])
def test_dependency_requires_approved_evidence_from_an_approved_candidate(
    owned_question, evidence_decision, candidate_status,
):
    from app.research.models import Evidence, ResearchItem
    app, client, question = owned_question
    source = add_candidate(client, question['id'], title='Dependency source')
    with app.state.session_factory() as session:
        session.get(ResearchItem, source['id']).status = candidate_status
        session.add(Evidence(
            id='invalid-dependency', research_item_id=source['id'],
            question_id=question['id'], user_id=source['user_id'], title=source['title'],
            summary=source['summary'], source_url=source['source_url'],
            source_name=source['source_name'], decision=evidence_decision,
        ))
        session.commit()
    item = add_candidate(client, question['id'], title='Dependent item')
    response = client.post(f"/research-items/{item['id']}/decision", json={
        'decision': 'approved', 'dependency_evidence_ids': ['invalid-dependency'],
    })
    assert response.status_code == 404
    assert client.get(f"/questions/{question['id']}/research").json()['items'][1]['status'] == 'candidate'

@pytest.mark.parametrize('table', ['evidence', 'research_decisions'])
@pytest.mark.parametrize('operation', ['update', 'delete', 'replace'])
def test_accepted_evidence_and_decision_audit_are_immutable(owned_question, table, operation):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    app, client, question = owned_question
    item = add_candidate(client, question['id'])
    client.post(f"/research-items/{item['id']}/decision", json={'decision': 'approved'})
    before = client.get(f"/questions/{question['id']}/research").json()
    statement = {'update': f"UPDATE {table} SET user_id = 'tampered'",
                 'delete': f'DELETE FROM {table}',
                 'replace': f'INSERT OR REPLACE INTO {table} SELECT * FROM {table}'}[operation]
    with pytest.raises(DBAPIError, match='append-only'):
        with app.state.engine.begin() as connection:
            connection.execute(text(statement))
    assert client.get(f"/questions/{question['id']}/research").json() == before


@pytest.mark.parametrize('verb', ['INSERT', 'INSERT OR REPLACE'])
def test_database_cannot_accept_second_evidence_for_same_candidate(owned_question, verb):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    app, client, question = owned_question
    item = add_candidate(client, question['id'])
    client.post(f"/research-items/{item['id']}/decision", json={'decision': 'approved'})
    with pytest.raises(DBAPIError):
        with app.state.engine.begin() as connection:
            connection.execute(text(f"{verb} INTO evidence (id, research_item_id, question_id, user_id, title, summary, source_url, source_name, decision, approved_at, dependency_evidence_ids) SELECT 'different-id', research_item_id, question_id, user_id, title, summary, source_url, source_name, decision, approved_at, dependency_evidence_ids FROM evidence"))

@pytest.mark.parametrize('decision', ['approved', 'duplicate'])
def test_retry_cannot_silently_change_decision_links(owned_question, decision):
    _, client, question = owned_question
    targets = [add_candidate(client, question['id'], title=f'Target {n}') for n in range(2)]
    if decision == 'approved':
        for target in targets:
            client.post(f"/research-items/{target['id']}/decision", json={'decision': 'approved'})
        links = [row['id'] for row in client.get(f"/questions/{question['id']}/research").json()['evidence']]
        payloads = [{'decision': 'approved', 'dependency_evidence_ids': [link]} for link in links]
    else:
        payloads = [{'decision': 'duplicate', 'related_item_id': target['id']} for target in targets]
    item = add_candidate(client, question['id'])
    url = f"/research-items/{item['id']}/decision"
    assert client.post(url, json=payloads[0]).status_code == 200
    before = client.get(f"/questions/{question['id']}/research").json()
    assert client.post(url, json=payloads[0]).status_code == 200
    assert client.post(url, json=payloads[1]).status_code == 409
    assert client.get(f"/questions/{question['id']}/research").json() == before

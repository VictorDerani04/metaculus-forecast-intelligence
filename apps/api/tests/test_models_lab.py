from test_forecasts import owned_question
import pytest


def test_base_rate_runner_returns_the_configured_probability():
    from app.models_lab.runners import run_model

    result = run_model({'family': 'base_rate', 'parameters': {'probability': 0.42}})

    assert result.probability == 0.42


def test_bayesian_runner_uses_odds_conversion():
    from app.models_lab.runners import run_model
    result = run_model({'family': 'bayesian_likelihood_ratio', 'parameters': {
        'prior_probability': 0.5, 'likelihood_ratio': 3,
    }})
    assert result.probability == 0.75


def test_weighted_driver_runner_returns_weighted_mean():
    from app.models_lab.runners import run_model
    result = run_model({'family': 'weighted_driver', 'parameters': {
        'drivers': [{'probability': 0.2, 'weight': 1}, {'probability': 0.8, 'weight': 3}],
    }})
    assert result.probability == pytest.approx(0.65)


def test_scenario_tree_runner_returns_the_weighted_leaf_probability():
    from app.models_lab.runners import run_model

    result = run_model({'family': 'scenario_tree', 'parameters': {'scenarios': [
        {'weight': 0.25, 'probability': 0.2},
        {'weight': 0.75, 'probability': 0.8},
    ]}})

    assert result.probability == pytest.approx(0.65)


def test_seeded_monte_carlo_runner_is_deterministic_for_a_seed():
    from app.models_lab.runners import run_model

    spec = {'family': 'seeded_monte_carlo', 'parameters': {'probability': 0.37, 'trials': 100}}

    assert run_model(spec, seed=17).probability == run_model(spec, seed=17).probability


@pytest.mark.parametrize('spec', [
    {'family': 'base_rate', 'parameters': {'probability': float('nan')}},
    {'family': 'bayesian_likelihood_ratio', 'parameters': {'prior_probability': 0.5, 'likelihood_ratio': float('inf')}},
    {'family': 'weighted_driver', 'parameters': {'drivers': [{'probability': 0.5, 'weight': float('nan')}]}},
    {'family': 'scenario_tree', 'parameters': {'scenarios': [{'weight': 1, 'probability': float('inf')}]}},
    {'family': 'seeded_monte_carlo', 'parameters': {'probability': 0.2, 'trials': float('inf')}},
])
def test_runners_reject_nonfinite_numeric_parameters(spec):
    from app.models_lab.runners import run_model

    with pytest.raises(ValueError):
        run_model(spec, seed=1)


def test_draft_model_requires_explicit_approval_before_running(owned_question):
    _, client, question = owned_question
    created = client.post(f"/questions/{question['id']}/models", json={
        'family': 'base_rate', 'rationale': 'Reference class',
        'parameters': {'probability': 0.42}, 'assumptions': [], 'evidence_ids': [],
    })

    assert created.status_code == 201
    assert created.json()['status'] == 'draft'
    assert client.post(f"/models/{created.json()['id']}/run").status_code == 409


def test_explicit_approval_marks_a_draft_approved_without_running_it(owned_question):
    app, client, question = owned_question
    created = client.post(f"/questions/{question['id']}/models", json={
        'family': 'base_rate', 'rationale': 'Reference class',
        'parameters': {'probability': 0.42}, 'assumptions': [], 'evidence_ids': [],
    }).json()

    approved = client.post(f"/models/{created['id']}/activate")

    assert approved.status_code == 200
    assert approved.json()['status'] == 'approved'
    with app.state.session_factory() as session:
        from sqlalchemy import select
        from app.models_lab.models import ModelRun
        assert session.scalars(select(ModelRun)).all() == []


def test_approved_model_run_is_persisted(owned_question):
    _, client, question = owned_question
    created = client.post(f"/questions/{question['id']}/models", json={
        'family': 'base_rate', 'rationale': 'Reference class',
        'parameters': {'probability': 0.42}, 'assumptions': [], 'evidence_ids': [],
    }).json()
    assert client.post(f"/models/{created['id']}/activate").status_code == 200

    run = client.post(f"/models/{created['id']}/run")

    assert run.status_code == 201
    assert run.json()['probability'] == 0.42
    assert run.json()['model_spec_id'] == created['id']


def test_successful_run_updates_only_the_model_probability(owned_question):
    _, client, question = owned_question
    assert client.post(f"/questions/{question['id']}/forecasts", json={
        'probability': 0.62, 'rationale': 'Human judgment',
    }).status_code == 201
    created = client.post(f"/questions/{question['id']}/models", json={
        'family': 'base_rate', 'rationale': 'Reference class',
        'parameters': {'probability': 0.78}, 'assumptions': [], 'evidence_ids': [],
    }).json()
    assert client.post(f"/models/{created['id']}/activate").status_code == 200
    assert client.post(f"/models/{created['id']}/run").status_code == 201

    room = client.get(f"/questions/{question['id']}/room").json()

    assert room['model_probability'] == 0.78
    assert room['human_forecast']['probability'] == 0.62
    assert [record['probability'] for record in room['history']] == [0.62]
    assert room['prior_probability'] is None
    assert room['community_probability'] is None


def test_failed_run_does_not_replace_latest_successful_model_probability(owned_question, monkeypatch):
    _, client, question = owned_question
    created = client.post(f"/questions/{question['id']}/models", json={
        'family': 'base_rate', 'rationale': 'Reference class',
        'parameters': {'probability': 0.42}, 'assumptions': [], 'evidence_ids': [],
    }).json()
    assert client.post(f"/models/{created['id']}/activate").status_code == 200
    assert client.post(f"/models/{created['id']}/run").status_code == 201

    def fail_runner(*_args, **_kwargs):
        raise ValueError('invalid runtime input')
    monkeypatch.setattr('app.models_lab.service.run_model', fail_runner)

    failed = client.post(f"/models/{created['id']}/run")

    assert failed.status_code == 422
    assert client.get(f"/questions/{question['id']}/room").json()['model_probability'] == 0.42


def test_model_requires_unique_currently_approved_evidence_dependencies(owned_question):
    app, client, question = owned_question
    candidate = client.post('/research-items', json={
        'question_id': question['id'], 'title': 'Official release', 'summary': 'Output increased.',
        'source_url': 'https://example.org/release', 'source_name': 'Statistics office',
    }).json()
    assert client.post(f"/research-items/{candidate['id']}/decision", json={'decision': 'approved'}).status_code == 200
    evidence_id = client.get(f"/questions/{question['id']}/research").json()['evidence'][0]['id']
    payload = {'family': 'base_rate', 'rationale': 'Evidence-backed reference class',
               'parameters': {'probability': 0.42}, 'assumptions': [], 'evidence_ids': [evidence_id]}
    assert client.post(f"/questions/{question['id']}/models", json={**payload, 'evidence_ids': [evidence_id, evidence_id]}).status_code == 422
    model = client.post(f"/questions/{question['id']}/models", json=payload).json()
    assert client.post(f"/models/{model['id']}/activate").status_code == 200
    with app.state.session_factory() as session:
        from sqlalchemy import update
        from app.research.models import ResearchItem
        session.execute(update(ResearchItem).where(ResearchItem.id == candidate['id']).values(status='rejected'))
        session.commit()
    assert client.post(f"/models/{model['id']}/run").status_code == 422


def test_approved_model_is_versioned_and_runs_preserve_a_snapshot(owned_question):
    _, client, question = owned_question
    created = client.post(f"/questions/{question['id']}/models", json={
        'family': 'base_rate', 'rationale': 'First reference class',
        'parameters': {'probability': 0.42}, 'assumptions': ['Stable reference class'], 'evidence_ids': [],
    }).json()
    assert client.post(f"/models/{created['id']}/activate").status_code == 200
    run = client.post(f"/models/{created['id']}/run").json()
    replacement = client.post(f"/models/{created['id']}/versions", json={
        'family': 'base_rate', 'rationale': 'Updated reference class',
        'parameters': {'probability': 0.64}, 'assumptions': ['New data'], 'evidence_ids': [],
    })

    assert replacement.status_code == 201
    assert replacement.json()['version'] == 2
    assert replacement.json()['status'] == 'draft'
    assert run['model_version'] == 1
    assert run['spec_snapshot']['parameters'] == {'probability': 0.42}


@pytest.mark.parametrize('operation', ['read', 'approve', 'run'])
def test_model_operations_hide_other_users_models(owned_question, operation):
    from fastapi.testclient import TestClient
    from app.auth.seed import seed_private_user

    app, owner, question = owned_question
    created = owner.post(f"/questions/{question['id']}/models", json={
        'family': 'base_rate', 'rationale': 'Reference class',
        'parameters': {'probability': 0.42}, 'assumptions': [], 'evidence_ids': [],
    }).json()
    seed_private_user(app.state.session_factory, 'other@example.com', 'other-password')
    stranger = TestClient(app)
    assert stranger.post('/auth/login', json={'email': 'other@example.com', 'password': 'other-password'}).status_code == 200
    url = f"/models/{created['id']}" + ('' if operation == 'read' else f"/{'activate' if operation == 'approve' else 'run'}")
    response = stranger.get(url) if operation == 'read' else stranger.post(url)
    assert response.status_code == 404


@pytest.mark.parametrize('operation', ['spec', 'run'])
def test_approved_specs_and_model_runs_reject_database_mutation(owned_question, operation):
    from sqlalchemy import delete, update
    from sqlalchemy.exc import DBAPIError
    from app.models_lab.models import ModelRun, ModelSpec

    app, client, question = owned_question
    model = client.post(f"/questions/{question['id']}/models", json={
        'family': 'base_rate', 'rationale': 'Reference class',
        'parameters': {'probability': 0.42}, 'assumptions': [], 'evidence_ids': [],
    }).json()
    assert client.post(f"/models/{model['id']}/activate").status_code == 200
    run = client.post(f"/models/{model['id']}/run").json()
    statement = (update(ModelSpec).values(rationale='Overwritten').where(ModelSpec.id == model['id'])
                 if operation == 'spec' else delete(ModelRun).where(ModelRun.id == run['id']))
    with pytest.raises(DBAPIError, match='append-only|immutable'):
        with app.state.engine.begin() as connection:
            connection.execute(statement)


@pytest.mark.parametrize('parameters', [
    {}, {'probability': 1.01}, {'probability': '0.5'},
])
def test_model_creation_rejects_malformed_and_nonfinite_parameters(owned_question, parameters):
    _, client, question = owned_question
    response = client.post(f"/questions/{question['id']}/models", json={
        'family': 'base_rate', 'rationale': 'Reference class', 'parameters': parameters,
        'assumptions': [], 'evidence_ids': [],
    })
    assert response.status_code == 422


@pytest.mark.parametrize('token', ['NaN', 'Infinity'])
def test_model_creation_rejects_nonfinite_json_parameters(owned_question, token):
    _, client, question = owned_question
    response = client.post(f"/questions/{question['id']}/models", content=(
        '{"family":"base_rate","rationale":"Reference class","parameters":{"probability":' + token
        + '},"assumptions":[],"evidence_ids":[]}'
    ), headers={'Content-Type': 'application/json'})
    assert response.status_code == 422


def test_model_endpoints_require_authentication(owned_question):
    from fastapi.testclient import TestClient

    app, client, question = owned_question
    model = client.post(f"/questions/{question['id']}/models", json={
        'family': 'base_rate', 'rationale': 'Reference class', 'parameters': {'probability': 0.4},
        'assumptions': [], 'evidence_ids': [],
    }).json()
    anonymous = TestClient(app)
    assert anonymous.get(f"/questions/{question['id']}/models").status_code == 401
    assert anonymous.get(f"/models/{model['id']}").status_code == 401
    assert anonymous.post(f"/models/{model['id']}/activate").status_code == 401
    assert anonymous.post(f"/models/{model['id']}/run").status_code == 401

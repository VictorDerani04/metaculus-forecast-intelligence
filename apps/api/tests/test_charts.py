from datetime import datetime, timezone

import pytest

from app.forecasts.models import HumanForecast
from app.models_lab.models import ModelRun
from test_forecasts import owned_question


def test_probability_history_keeps_human_model_and_crowd_series_separate(owned_question):
    app, client, question = owned_question
    user_id = client.get('/auth/me').json()['id']
    with app.state.session_factory() as session:
        session.add_all([
            HumanForecast(
                question_id=question['id'], user_id=user_id, probability=0.4,
                rationale='first', created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            ModelRun(
                model_spec_id='missing-spec', question_id=question['id'], user_id=user_id,
                status='succeeded', probability=0.6, inputs={}, evidence_ids=[],
                model_version=2, spec_snapshot={},
                created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
        ])
        session.commit()

        from app.analytics.charts import build_probability_history
        result = build_probability_history(session, user_id, question['id'])

    assert result.model_version == 2
    assert len(result.human) == 1
    assert len(result.model) == 1
    assert result.human[0].probability == 0.4
    assert result.model[0].probability == 0.6
    assert result.crowd == []
    assert result.why_this_chart


def test_analysis_builders_expose_distribution_sensitivity_scenarios_and_map(owned_question):
    app, client, question = owned_question
    model = client.post(f"/questions/{question['id']}/models", json={
        'family': 'weighted_driver',
        'rationale': 'Compare two drivers',
        'parameters': {'drivers': [
            {'name': 'demand', 'probability': 0.2, 'weight': 1},
            {'name': 'supply', 'probability': 0.8, 'weight': 3},
        ]},
        'assumptions': [],
        'evidence_ids': [],
    }).json()
    assert client.post(f"/models/{model['id']}/activate").status_code == 200
    assert client.post(f"/models/{model['id']}/run").status_code == 201

    with app.state.session_factory() as session:
        from app.analytics.charts import (
            build_causal_model_map,
            build_distribution,
            build_scenario_analysis,
            build_sensitivity,
        )
        distribution = build_distribution(session, model['id'], client.get('/auth/me').json()['id'])
        sensitivity = build_sensitivity(session, model['id'], client.get('/auth/me').json()['id'])
        scenarios = build_scenario_analysis(session, model['id'], client.get('/auth/me').json()['id'])
        model_map = build_causal_model_map(session, model['id'], client.get('/auth/me').json()['id'])

    assert distribution.model_version == 1
    assert distribution.available is False
    assert sensitivity.impacts[0].name == 'supply'
    assert sensitivity.impacts[0].baseline == pytest.approx(0.65)
    assert scenarios.scenarios == []
    assert [node.kind for node in model_map.nodes] == ['outcome']
    assert model_map.edges == []


def test_analysis_endpoint_is_scoped_to_owned_question_and_model(owned_question):
    app, client, question = owned_question
    model = client.post(f"/questions/{question['id']}/models", json={
        'family': 'base_rate', 'rationale': 'Reference class',
        'parameters': {'probability': 0.42}, 'assumptions': [], 'evidence_ids': [],
    }).json()

    response = client.get(f"/questions/{question['id']}/analysis/{model['id']}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        'probability_history', 'distribution', 'sensitivity', 'evidence_impact',
        'scenarios', 'model_map',
    }
    assert body['probability_history']['human'] == []
    assert body['distribution']['available'] is False


def test_analysis_does_not_create_forecasts_or_model_runs(owned_question):
    from sqlalchemy import func, select
    from app.forecasts.models import HumanForecast
    from app.models_lab.models import ModelRun

    app, client, question = owned_question
    model = client.post(f"/questions/{question['id']}/models", json={
        'family': 'base_rate', 'rationale': 'Reference class',
        'parameters': {'probability': 0.42}, 'assumptions': [], 'evidence_ids': [],
    }).json()
    before = client.get(f"/questions/{question['id']}/room").json()
    assert client.get(f"/questions/{question['id']}/analysis/{model['id']}").status_code == 200
    assert client.get(f"/questions/{question['id']}/room").json() == before
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(HumanForecast.id))) == 0
        assert session.scalar(select(func.count(ModelRun.id))) == 0

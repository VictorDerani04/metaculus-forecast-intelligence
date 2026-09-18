from datetime import datetime, timezone

from test_forecasts import owned_question


def test_attention_priority_attributes_each_available_signal():
    from app.analytics.priority import attention_priority

    result = attention_priority({
        'resolve_at': datetime(2026, 9, 20, tzinfo=timezone.utc),
        'evaluated_at': datetime(2026, 9, 17, tzinfo=timezone.utc),
        'last_human_update': None,
        'last_model_run': None,
        'human_probability': None,
        'model_probability': 0.8,
        'crowd_probability': 0.2,
        'new_material_evidence': 2,
        'unresolved_alerts': 1,
        'sensitivity': 0.7,
        'research_value': 0.6,
    })

    assert result.score > 0
    assert {component.name for component in result.components} == {
        'deadline_proximity', 'forecast_staleness', 'material_evidence',
        'unresolved_alerts', 'human_crowd_divergence', 'human_model_divergence',
        'model_uncertainty_sensitivity', 'research_value', 'no_initial_forecast',
    }
    assert 'No initial human forecast' in result.reasons
    assert 'Deadline approaching' in result.reasons


def test_attention_questions_are_sorted_descending_and_owned(owned_question):
    app, client, question = owned_question
    response = client.get('/competitions/attention')

    assert response.status_code == 200
    assert response.json()[0]['question_id'] == question['id']
    assert response.json()[0]['priority']['score'] >= 0


def test_attention_calculation_is_read_only(owned_question):
    from sqlalchemy import func, select
    from app.forecasts.models import HumanForecast
    from app.models_lab.models import ModelRun

    app, client, question = owned_question
    before = client.get(f"/questions/{question['id']}/room").json()
    assert client.get('/competitions/attention').status_code == 200
    assert client.get(f"/questions/{question['id']}/room").json() == before
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(HumanForecast.id))) == 0
        assert session.scalar(select(func.count(ModelRun.id))) == 0


def test_attention_priority_normalizes_sqlite_naive_history_timestamps():
    from app.analytics.priority import attention_priority

    result = attention_priority({
        'evaluated_at': datetime(2026, 9, 17, tzinfo=timezone.utc),
        'last_human_update': datetime(2026, 9, 1),
        'human_probability': 0.5,
    })

    assert result.score > 0

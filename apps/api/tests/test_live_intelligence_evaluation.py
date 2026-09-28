import json
from pathlib import Path


def test_evaluation_corpus_is_varied_and_contains_required_failure_modes():
    from app.monitoring.evaluation import evaluate_corpus

    corpus = json.loads((Path(__file__).parent / 'fixtures' / 'live_intelligence_evaluation.json').read_text())
    result = evaluate_corpus(corpus)

    assert 8 <= result.question_count <= 15
    assert {'elections/politics', 'geopolitics', 'macroeconomics', 'financial markets', 'weather/climate', 'humanitarian crises', 'science/technology', 'sports'} <= set(result.domains)
    assert result.relevance.true_relevant == 8
    assert result.relevance.true_irrelevant == 2
    assert result.relevance.false_relevant == 0
    assert result.relevance.false_irrelevant == 0
    assert result.relevance.precision == 1.0
    assert result.relevance.recall == 1.0
    assert result.alerts.suppressed_duplicates == 1
    assert result.alerts.alerts == 4
    assert result.alerts.digests == 3
    assert result.missed_signals == ()


def test_evaluation_results_remain_inspectable_without_live_credentials():
    from app.monitoring.evaluation import evaluate_corpus

    result = evaluate_corpus([
        {'id': 'miss', 'domain': 'science/technology', 'question': 'Will X happen?', 'title': 'Important event', 'summary': 'Important event occurred.', 'source_url': 'https://example.test/x', 'source_name': 'Example', 'expected': {'relevant': True, 'materiality': 'critical', 'route': 'alert'}, 'observed': {'relevant': True, 'materiality': 'digest', 'route': 'digest', 'failure_stage': 'materiality classifier'}},
    ])

    assert result.missed_signals[0].case_id == 'miss'
    assert result.missed_signals[0].failure_stage == 'materiality classifier'
    assert result.cases[0].source_type == 'news_or_web'


def test_replay_harness_collects_real_pipeline_outcomes_and_duplicate_suppression(tmp_path):
    from sqlalchemy import func, select
    from app.monitoring.alerts import AlertEvent
    from app.monitoring.classification import FakeMaterialityClassifier, FakeRelevanceClassifier
    from app.monitoring.evaluation import evaluate_replay
    from app.monitoring.ingestion import ingest
    from app.monitoring.models import EventCluster, Finding, FindingEventLink, MonitoringRun
    from test_competitions import login, make_client

    app, client = make_client(tmp_path)
    login(app, client)
    competition = client.post('/competitions', json={'name': 'Evaluation'}).json()
    question = client.post(f"/competitions/{competition['id']}/questions", json={'title': 'Will Team A win the championship?'}).json()
    user_id = client.get('/auth/me').json()['id']
    corpus = json.loads((Path(__file__).parent / 'fixtures' / 'live_intelligence_evaluation.json').read_text())
    sports_cases = [case for case in corpus if case['id'].startswith('sports-')]

    def replay(case):
        with app.state.session_factory.begin() as session:
            run = MonitoringRun(user_id=user_id, question_id=question['id'], job_id=f"evaluation-{case['id']}")
            session.add(run)
            session.flush()
            ingest(session, user_id=user_id, question_id=question['id'], run_id=run.id, provider='web', next_cursor=case['id'], items=[{
                'external_id': case['id'], 'url': case['source_url'], 'title': case['title'], 'text': case['summary'], 'source_name': case['source_name'],
            }], relevance=FakeRelevanceClassifier(), materiality=FakeMaterialityClassifier())
            finding = session.scalar(select(Finding).where(Finding.monitoring_run_id == run.id))
            link = session.scalar(select(FindingEventLink).where(FindingEventLink.finding_id == finding.id))
            alert_created = session.scalar(select(func.count(AlertEvent.id)).where(AlertEvent.finding_id == finding.id)) == 1
            return {'relevant': finding.relevance_class == 'relevant', 'materiality': finding.materiality_class, 'route': 'alert' if alert_created else 'suppressed', 'source_type': finding.source_type, 'reliability': finding.source_reliability, 'cluster_id': link.event_cluster_id}

    result = evaluate_replay(sports_cases, replay)
    assert [case.route for case in result.cases] == ['alert', 'suppressed']
    assert result.alerts.suppressed_duplicates == 1
    assert result.cases[0].cluster_id == result.cases[1].cluster_id
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(EventCluster.id))) == 1


def test_acceptance_pipeline_stops_at_candidate_until_a_human_acts(tmp_path):
    from sqlalchemy import func, select
    from app.forecasts.models import HumanForecast
    from app.models_lab.models import ModelRun, ModelSpec
    from app.monitoring.classification import FakeMaterialityClassifier, FakeRelevanceClassifier
    from app.monitoring.ingestion import ingest
    from app.monitoring.models import MonitoringRun
    from app.research.models import Evidence, ResearchItem
    from test_competitions import login, make_client

    app, client = make_client(tmp_path)
    login(app, client)
    competition = client.post('/competitions', json={'name': 'Human boundary'}).json()
    question = client.post(f"/competitions/{competition['id']}/questions", json={'title': 'Will the launch occur?'}).json()
    user_id = client.get('/auth/me').json()['id']
    with app.state.session_factory.begin() as session:
        run = MonitoringRun(user_id=user_id, question_id=question['id'], job_id='acceptance-monitoring')
        session.add(run)
        session.flush()
        ingest(session, user_id=user_id, question_id=question['id'], run_id=run.id, provider='web', next_cursor='launch', items=[{
            'external_id': 'launch', 'url': 'https://agency.gov/launch', 'title': 'Agency confirms launch date', 'text': 'The agency confirmed the launch date.', 'source_name': 'Agency',
        }], relevance=FakeRelevanceClassifier(), materiality=FakeMaterialityClassifier())
        assert session.scalar(select(func.count(ResearchItem.id))) == 1
        assert session.scalar(select(ResearchItem.status)) == 'candidate'
        assert session.scalar(select(func.count(Evidence.id))) == 0
        assert session.scalar(select(func.count(ModelSpec.id))) == 0
        assert session.scalar(select(func.count(ModelRun.id))) == 0
        assert session.scalar(select(func.count(HumanForecast.id))) == 0

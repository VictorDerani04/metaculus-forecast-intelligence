def test_monitoring_modules_are_available():
    from app.jobs.models import BackgroundJob
    from app.monitoring.models import MonitoringConfig, MonitoringRun
    assert BackgroundJob.__tablename__ == 'background_jobs'
    assert MonitoringConfig.__tablename__ == 'monitoring_configs'
    assert MonitoringRun.__tablename__ == 'monitoring_runs'


def test_job_statuses_are_constrained_values():
    from app.jobs.models import JobStatus
    assert {status.value for status in JobStatus} == {'queued', 'running', 'succeeded', 'failed', 'retry_wait', 'cancelled'}


def test_monitoring_api_requires_enable_before_enqueuing(tmp_path):
    from test_competitions import login, make_client
    app, client = make_client(tmp_path); login(app, client)
    competition = client.post('/competitions', json={'name': 'Monitoring'}).json()
    question = client.post(f"/competitions/{competition['id']}/questions", json={'title': 'Will it happen?'}).json()
    path = f"/questions/{question['id']}/monitoring"
    assert client.get(path).json()['enabled'] is False
    assert client.post(f'{path}/run').status_code == 409
    assert client.post(f'{path}/enable', json={}).status_code == 200
    assert client.post(f'{path}/run').status_code == 202


def test_finding_normalization_is_deterministic_and_removes_tracking_parameters():
    from app.monitoring.normalization import canonicalize_url, fingerprint
    assert canonicalize_url('https://Example.com/a?utm_source=x&keep=1') == 'https://example.com/a?keep=1'
    assert fingerprint('provider', 'id', 'https://example.com/a', 'Title', 'Source', None) == fingerprint('provider', 'id', 'https://example.com/a', 'Title', 'Source', None)


def test_finding_normalization_rejects_unsupported_url_schemes():
    from app.monitoring.normalization import canonicalize_url
    assert canonicalize_url('file:///secret') is None


def test_ingestion_creates_one_unapproved_candidate_and_deduplicates(tmp_path):
    from test_competitions import login, make_client
    from app.monitoring.ingestion import ingest
    from app.monitoring.classification import FakeRelevanceClassifier, FakeMaterialityClassifier
    from app.monitoring.models import MonitoringRun
    app, client = make_client(tmp_path); login(app, client)
    competition = client.post('/competitions', json={'name': 'Pipeline'}).json()
    question = client.post(f"/competitions/{competition['id']}/questions", json={'title': 'Question'}).json()
    user_id = client.get('/auth/me').json()['id']
    with app.state.session_factory() as session:
        run = MonitoringRun(user_id=user_id, question_id=question['id'], job_id='job'); session.add(run); session.commit()
        item = {'external_id': 'x', 'url': 'https://example.com/a?utm_source=z', 'title': ' Item ', 'text': 'Summary', 'source_name': 'Example'}
        assert ingest(session, user_id=user_id, question_id=question['id'], run_id=run.id, provider='web', items=[item], next_cursor='next', relevance=FakeRelevanceClassifier(), materiality=FakeMaterialityClassifier())['candidates'] == 1
        session.commit()
    assert len(client.get(f"/questions/{question['id']}/research").json()['items']) == 1


def test_findings_are_owner_scoped(tmp_path):
    from test_competitions import login, make_client
    from app.auth.seed import seed_private_user
    from fastapi.testclient import TestClient
    app, owner = make_client(tmp_path); login(app, owner)
    competition = owner.post('/competitions', json={'name': 'Private'}).json()
    question = owner.post(f"/competitions/{competition['id']}/questions", json={'title': 'Private question'}).json()
    seed_private_user(app.state.session_factory, 'other@example.com', 'other-password')
    other = TestClient(app); other.post('/auth/login', json={'email': 'other@example.com', 'password': 'other-password'})
    assert other.get(f"/questions/{question['id']}/findings").status_code == 404


def test_classifier_failure_keeps_finding_but_does_not_advance_cursor_or_create_candidate(tmp_path):
    from sqlalchemy import select
    from test_competitions import login, make_client
    from app.monitoring.classification import FakeMaterialityClassifier
    from app.monitoring.ingestion import IngestionFailure, process_provider_result
    from app.monitoring.models import Finding, MonitoringRun, ProviderCursor
    app, client = make_client(tmp_path); login(app, client)
    competition = client.post('/competitions', json={'name': 'Pipeline'}).json()
    question = client.post(f"/competitions/{competition['id']}/questions", json={'title': 'Question'}).json(); user_id = client.get('/auth/me').json()['id']
    with app.state.session_factory.begin() as session:
        run = MonitoringRun(user_id=user_id, question_id=question['id'], job_id='classifier-job'); session.add(run); session.flush(); run_id = run.id
    class BrokenClassifier:
        def classify(self, question, finding): return {'relevant': True}
    item = {'external_id': 'x', 'url': 'https://example.com/a', 'title': 'Item', 'text': 'Summary', 'source_name': 'Example'}
    try:
        process_provider_result(app.state.session_factory, user_id=user_id, question_id=question['id'], run_id=run_id, provider='web', items=[item], next_cursor='next', question=None, relevance=BrokenClassifier(), materiality=FakeMaterialityClassifier())
    except IngestionFailure as exc:
        assert exc.code == 'classification_failure'
    else: assert False, 'classification failure must leave the provider retry-ready'
    with app.state.session_factory() as session:
        assert session.scalar(select(Finding).where(Finding.question_id == question['id'])).relevance_class == 'uncertain'
        assert session.scalar(select(ProviderCursor).where(ProviderCursor.question_id == question['id'])) is None
    assert client.get(f"/questions/{question['id']}/research").json()['items'] == []


def test_finding_persists_exact_bounded_classifier_provenance(tmp_path):
    from datetime import datetime, timezone
    from sqlalchemy import select
    from test_competitions import login, make_client
    from app.monitoring.classification import MaterialityResult, RelevanceResult
    from app.monitoring.ingestion import ingest
    from app.monitoring.models import Finding, MonitoringRun

    class Relevance:
        def classify(self, question, finding):
            return RelevanceResult('relevant', .8, 'Direct evidence.', .85, 'openai', 'gpt-4o-mini', datetime(2026, 9, 25, tzinfo=timezone.utc))
    class Materiality:
        def classify(self, question, finding):
            return MaterialityResult('material', .8, 'Meaningful update.', .9, 'down', 'openai', 'gpt-4o-mini', datetime(2026, 9, 25, tzinfo=timezone.utc))

    app, client = make_client(tmp_path); login(app, client)
    competition = client.post('/competitions', json={'name': 'Provenance'}).json(); question = client.post(f"/competitions/{competition['id']}/questions", json={'title': 'Question'}).json(); user_id = client.get('/auth/me').json()['id']
    with app.state.session_factory.begin() as session:
        run = MonitoringRun(user_id=user_id, question_id=question['id'], job_id='provenance-job'); session.add(run); session.flush()
        ingest(session, user_id=user_id, question_id=question['id'], run_id=run.id, provider='web', items=[{'external_id': 'p', 'url': 'https://example.com/p', 'title': 'Provenance', 'text': 'Evidence', 'source_name': 'Example'}], next_cursor='p', relevance=Relevance(), materiality=Materiality())
    with app.state.session_factory() as session:
        finding = session.scalar(select(Finding).where(Finding.question_id == question['id']))
        assert (finding.classifier_provider, finding.classifier_model, finding.relevance_confidence, finding.materiality_confidence, finding.materiality_direction, finding.classifier_schema_version) == ('openai', 'gpt-4o-mini', .85, .9, 'down', 'stage-3.2-v1')


def test_irrelevant_or_uncertain_relevance_cannot_route_a_materiality_alert(tmp_path):
    from sqlalchemy import func, select
    from test_competitions import login, make_client
    from app.monitoring.alerts import AlertEvent, DigestItem
    from app.monitoring.classification import FakeMaterialityClassifier, RelevanceResult
    from app.monitoring.ingestion import ingest
    from app.monitoring.models import Finding, MonitoringRun

    class Uncertain:
        def classify(self, question, finding): return RelevanceResult('uncertain', .3, 'Insufficient evidence.', .2)

    app, client = make_client(tmp_path); login(app, client)
    competition = client.post('/competitions', json={'name': 'Conservative'}).json(); question = client.post(f"/competitions/{competition['id']}/questions", json={'title': 'Question'}).json(); user_id = client.get('/auth/me').json()['id']
    with app.state.session_factory.begin() as session:
        run = MonitoringRun(user_id=user_id, question_id=question['id'], job_id='conservative-job'); session.add(run); session.flush()
        ingest(session, user_id=user_id, question_id=question['id'], run_id=run.id, provider='web', items=[{'external_id': 'u', 'url': 'https://example.com/u', 'title': 'Uncertain', 'text': 'Weak signal', 'source_name': 'Example'}], next_cursor='u', relevance=Uncertain(), materiality=FakeMaterialityClassifier())
    with app.state.session_factory() as session:
        finding = session.scalar(select(Finding).where(Finding.question_id == question['id']))
        assert finding.materiality_class == 'irrelevant'
        assert session.scalar(select(func.count(AlertEvent.id))) == 0
        assert session.scalar(select(func.count(DigestItem.id))) == 0


def test_retry_after_partial_provider_result_deduplicates_and_advances_once(tmp_path):
    from sqlalchemy import func, select
    from test_competitions import login, make_client
    from app.monitoring.classification import FakeMaterialityClassifier, FakeRelevanceClassifier
    from app.monitoring.ingestion import IngestionFailure, process_provider_result
    from app.monitoring.models import Finding, MonitoringRun, ProviderCursor
    from app.research.models import ResearchItem
    app, client = make_client(tmp_path); login(app, client)
    competition = client.post('/competitions', json={'name': 'Retry'}).json(); question = client.post(f"/competitions/{competition['id']}/questions", json={'title': 'Question'}).json(); user_id = client.get('/auth/me').json()['id']
    with app.state.session_factory.begin() as session:
        run = MonitoringRun(user_id=user_id, question_id=question['id'], job_id='retry-job'); session.add(run); session.flush(); run_id = run.id
    items = [
        {'external_id': 'one', 'url': 'https://example.com/1', 'title': 'One', 'text': 'One', 'source_name': 'Example'},
        {'external_id': 'two', 'url': 'https://example.com/2', 'title': 'Two', 'text': 'Two', 'source_name': 'Example'},
    ]
    class FailSecond:
        calls = 0
        def classify(self, question, finding):
            self.calls += 1
            if self.calls == 2: raise RuntimeError('not a secret')
            return FakeRelevanceClassifier().classify(question, finding)
    try:
        process_provider_result(app.state.session_factory, user_id=user_id, question_id=question['id'], run_id=run_id, provider='web', items=items, next_cursor='cursor-2', question=None, relevance=FailSecond(), materiality=FakeMaterialityClassifier())
    except IngestionFailure: pass
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(Finding.id))) == 2
        assert session.scalar(select(func.count(ResearchItem.id))) == 1
        assert session.scalar(select(ProviderCursor).where(ProviderCursor.question_id == question['id'])) is None
    counts = process_provider_result(app.state.session_factory, user_id=user_id, question_id=question['id'], run_id=run_id, provider='web', items=items, next_cursor='cursor-2', question=None, relevance=FakeRelevanceClassifier(), materiality=FakeMaterialityClassifier())
    assert counts == {'raw': 2, 'normalized': 0, 'duplicates': 2, 'relevant': 0, 'material': 0, 'candidates': 0}
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(Finding.id))) == 2
        assert session.scalar(select(func.count(ResearchItem.id))) == 1
        assert session.scalar(select(ProviderCursor.cursor_value).where(ProviderCursor.question_id == question['id'])) == 'cursor-2'


def test_worker_provider_failure_is_safe_retryable_and_later_success_is_truthful(tmp_path):
    from sqlalchemy import select
    from test_competitions import login, make_client
    from app.jobs.models import BackgroundJob, JobStatus
    from app.monitoring.models import MonitoringConfig, MonitoringRun, ProviderCursor, utcnow
    from app.monitoring.providers.base import ProviderFailure, ProviderResult
    from app.monitoring.worker import run_one_monitoring_job
    app, client = make_client(tmp_path); login(app, client)
    competition = client.post('/competitions', json={'name': 'Worker'}).json(); question = client.post(f"/competitions/{competition['id']}/questions", json={'title': 'Question'}).json()
    client.post(f"/questions/{question['id']}/monitoring/enable", json={}); queued = client.post(f"/questions/{question['id']}/monitoring/run").json()['job_id']
    class FailingProvider:
        def fetch(self, question, cursor): raise ProviderFailure('token=super-secret')
    run_one_monitoring_job(app.state.session_factory, {'web': FailingProvider()})
    with app.state.session_factory() as session:
        job = session.get(BackgroundJob, queued); run = session.scalar(select(MonitoringRun).where(MonitoringRun.job_id == queued)); config = session.scalar(select(MonitoringConfig).where(MonitoringConfig.question_id == question['id']))
        assert job.status == JobStatus.RETRY_WAIT.value and job.last_error_code == 'provider_failure'
        assert 'secret' not in (job.last_error_message + (run.safe_error_summary or ''))
        assert run.status == 'failed' and (run.providers_attempted, run.providers_succeeded, run.providers_failed) == (1, 0, 1)
        assert config.last_run_at is not None and config.last_success_at is None
        job.scheduled_for = utcnow(); session.commit()
    class SuccessProvider:
        def fetch(self, question, cursor): return ProviderResult(items=[], next_cursor='after-success')
    run_one_monitoring_job(app.state.session_factory, {'web': SuccessProvider()})
    with app.state.session_factory() as session:
        job = session.get(BackgroundJob, queued); config = session.scalar(select(MonitoringConfig).where(MonitoringConfig.question_id == question['id']))
        runs = session.scalars(select(MonitoringRun).where(MonitoringRun.job_id == queued).order_by(MonitoringRun.started_at)).all()
        assert job.status == JobStatus.SUCCEEDED.value and job.attempt_count == 2
        assert [run.status for run in runs] == ['failed', 'succeeded']
        assert config.last_success_at is not None
        assert session.scalar(select(ProviderCursor.cursor_value).where(ProviderCursor.question_id == question['id'])) == 'after-success'


def test_alert_and_digest_routing_lifecycle_and_owner_isolation(tmp_path):
    """Task 3 attention artifacts are exclusive, owned, and non-consequential."""
    from datetime import timezone
    from sqlalchemy import func, select
    from fastapi.testclient import TestClient
    from test_competitions import login, make_client
    from app.auth.seed import seed_private_user
    from app.monitoring.classification import FakeRelevanceClassifier, MaterialityResult
    from app.monitoring.ingestion import ingest
    from app.monitoring.models import MonitoringRun
    from app.monitoring.alerts import AlertEvent, DigestItem

    class RoutedMateriality:
        def classify(self, question, draft):
            return MaterialityResult('digest' if draft['title'] == 'Digest' else 'critical', .9, 'Persisted route')

    app, owner = make_client(tmp_path); login(app, owner)
    competition = owner.post('/competitions', json={'name': 'Attention'}).json()
    question = owner.post(f"/competitions/{competition['id']}/questions", json={'title': 'Question'}).json()
    user_id = owner.get('/auth/me').json()['id']
    with app.state.session_factory() as session:
        run = MonitoringRun(user_id=user_id, question_id=question['id'], job_id='attention-job'); session.add(run); session.flush()
        ingest(session, user_id=user_id, question_id=question['id'], run_id=run.id, provider='web', next_cursor='a',
               items=[{'external_id': 'alert', 'url': 'https://example.com/alert', 'title': 'Alert', 'text': 'A', 'source_name': 'Example'},
                      {'external_id': 'digest', 'url': 'https://example.com/digest', 'title': 'Digest', 'text': 'D', 'source_name': 'Example'}],
               relevance=FakeRelevanceClassifier(), materiality=RoutedMateriality())
        session.commit()
        assert session.scalar(select(func.count(AlertEvent.id))) == 1
        digest_item = session.scalar(select(DigestItem)); assert digest_item is not None
        digest_period_start = digest_item.eligible_at.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    alerts = owner.get('/alerts'); assert alerts.status_code == 200 and len(alerts.json()) == 1
    assert alerts.json()[0]['question_title'] == 'Question'
    alert_id = alerts.json()[0]['id']
    assert owner.post(f'/alerts/{alert_id}/seen').json()['status'] == 'seen'
    assert owner.post(f'/alerts/{alert_id}/seen').json()['status'] == 'seen'
    assert owner.post(f'/alerts/{alert_id}/dismiss').json()['status'] == 'dismissed'
    digest = owner.get('/digests'); assert digest.status_code == 200 and digest.json() == []
    from app.monitoring.alerts import generate_daily_digest
    with app.state.session_factory.begin() as session:
        from datetime import timedelta
        created = generate_daily_digest(session, user_id=user_id, period_start=digest_period_start, period_end=digest_period_start + timedelta(days=1))
        again = generate_daily_digest(session, user_id=user_id, period_start=digest_period_start, period_end=digest_period_start + timedelta(days=1))
        assert created.id == again.id
    digest = owner.get('/digests'); assert len(digest.json()) == 1
    detail = owner.get(f"/digests/{digest.json()[0]['id']}"); assert detail.status_code == 200 and [item['finding']['title'] for item in detail.json()['items']] == ['Digest']
    seed_private_user(app.state.session_factory, 'other@example.com', 'other-password')
    other = TestClient(app); other.post('/auth/login', json={'email': 'other@example.com', 'password': 'other-password'})
    assert other.get('/alerts').json() == []
    assert other.post(f'/alerts/{alert_id}/dismiss').status_code == 404
    assert other.get(f"/digests/{digest.json()[0]['id']}").status_code == 404


def test_task3_route_failure_keeps_cursor_unchanged_until_retry(tmp_path, monkeypatch):
    from sqlalchemy import func, select
    from test_competitions import login, make_client
    from app.monitoring.classification import FakeMaterialityClassifier, FakeRelevanceClassifier
    from app.monitoring.ingestion import process_provider_result
    from app.monitoring.models import Finding, MonitoringRun, ProviderCursor
    from app.monitoring.alerts import AlertEvent
    app, client = make_client(tmp_path); login(app, client)
    competition = client.post('/competitions', json={'name': 'Cursor'}).json(); question = client.post(f"/competitions/{competition['id']}/questions", json={'title': 'Question'}).json(); user_id = client.get('/auth/me').json()['id']
    with app.state.session_factory.begin() as session:
        run = MonitoringRun(user_id=user_id, question_id=question['id'], job_id='cursor-job'); session.add(run); session.flush(); run_id = run.id
    import app.monitoring.ingestion as ingestion
    monkeypatch.setattr(ingestion, 'route_finding', lambda session, finding: (_ for _ in ()).throw(RuntimeError('route persistence failed')))
    item = {'external_id': 'route', 'url': 'https://example.com/route', 'title': 'Route', 'text': 'A', 'source_name': 'Example'}
    try:
        process_provider_result(app.state.session_factory, user_id=user_id, question_id=question['id'], run_id=run_id, provider='web', items=[item], next_cursor='advanced', question=None, relevance=FakeRelevanceClassifier(), materiality=FakeMaterialityClassifier())
    except RuntimeError: pass
    with app.state.session_factory() as session:
        assert session.scalar(select(ProviderCursor).where(ProviderCursor.question_id == question['id'])) is None
        assert session.scalar(select(func.count(Finding.id))) == 0
    monkeypatch.undo()
    process_provider_result(app.state.session_factory, user_id=user_id, question_id=question['id'], run_id=run_id, provider='web', items=[item], next_cursor='advanced', question=None, relevance=FakeRelevanceClassifier(), materiality=FakeMaterialityClassifier())
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(Finding.id))) == 1
        assert session.scalar(select(func.count(AlertEvent.id))) == 1
        assert session.scalar(select(ProviderCursor.cursor_value).where(ProviderCursor.question_id == question['id'])) == 'advanced'

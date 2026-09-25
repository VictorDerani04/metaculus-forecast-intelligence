from datetime import datetime, timedelta, timezone


def test_adaptive_schedule_policy_and_explicit_interval_are_deterministic():
    from app.monitoring.policy import monitoring_interval_minutes

    now = datetime(2026, 9, 24, tzinfo=timezone.utc)
    assert monitoring_interval_minutes(None, now=now) == 720
    assert monitoring_interval_minutes(now + timedelta(days=90), now=now) == 360
    assert monitoring_interval_minutes(now + timedelta(days=30), now=now) == 180
    assert monitoring_interval_minutes(now + timedelta(days=7), now=now) == 60
    assert monitoring_interval_minutes(now + timedelta(days=6), now=now) == 60
    assert monitoring_interval_minutes(now + timedelta(days=3), explicit_interval_minutes=45, now=now) == 45


def test_recover_stale_jobs_respects_lease_and_retry_limit(tmp_path):
    from app.main import create_app
    from app.jobs.models import BackgroundJob, JobStatus
    from app.jobs.service import recover_stale_jobs

    app = create_app(f"sqlite:///{tmp_path / 'recovery.db'}", seed_user=False)
    now = datetime.now(timezone.utc)
    with app.state.session_factory.begin() as session:
        retryable = BackgroundJob(user_id='u', question_id=None, job_type='x', payload_json={}, idempotency_key='retry', status='running', attempt_count=1, max_attempts=3, started_at=now - timedelta(minutes=16), scheduled_for=now)
        exhausted = BackgroundJob(user_id='u', question_id=None, job_type='x', payload_json={}, idempotency_key='failed', status='running', attempt_count=3, max_attempts=3, started_at=now - timedelta(minutes=16), scheduled_for=now)
        fresh = BackgroundJob(user_id='u', question_id=None, job_type='x', payload_json={}, idempotency_key='fresh', status='running', attempt_count=1, max_attempts=3, started_at=now - timedelta(minutes=1), scheduled_for=now)
        session.add_all([retryable, exhausted, fresh])
    assert recover_stale_jobs(app.state.session_factory, now=now) == 2
    with app.state.session_factory() as session:
        jobs = {job.idempotency_key: job for job in session.query(BackgroundJob).all()}
        assert jobs['retry'].status == JobStatus.RETRY_WAIT.value
        assert jobs['retry'].last_error_code == 'lease_expired'
        assert jobs['failed'].status == JobStatus.FAILED.value
        assert jobs['fresh'].status == JobStatus.RUNNING.value


def test_ready_reports_database_failure_without_details(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app

    app = create_app(f"sqlite:///{tmp_path / 'ready.db'}", seed_user=False)
    assert TestClient(app).get('/ready').json() == {'status': 'ready'}
    app.state.engine.dispose()
    app.state.engine = None
    response = TestClient(app).get('/ready')
    assert response.status_code == 503
    assert response.json() == {'detail': 'Database is unavailable'}


def test_startup_additively_upgrades_existing_monitoring_configuration_table(tmp_path):
    from sqlalchemy import create_engine, inspect
    from app.monitoring.models import install_monitoring_schema_upgrades

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE monitoring_configs (id VARCHAR PRIMARY KEY)')
    install_monitoring_schema_upgrades(engine)
    assert 'adaptive_schedule_enabled' in {column['name'] for column in inspect(engine).get_columns('monitoring_configs')}

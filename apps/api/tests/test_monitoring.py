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

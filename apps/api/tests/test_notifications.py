from datetime import datetime, timezone


def _seed_attention(app, client):
    from test_competitions import login
    from app.monitoring.alerts import AlertEvent, Digest
    login(app, client)
    competition = client.post('/competitions', json={'name': 'Notifications'}).json()
    question = client.post(f"/competitions/{competition['id']}/questions", json={'title': 'Question'}).json()
    user_id = client.get('/auth/me').json()['id']
    with app.state.session_factory.begin() as session:
        alert = AlertEvent(user_id=user_id, question_id=question['id'], finding_id='finding-alert', severity='critical', reason='reason')
        digest = Digest(user_id=user_id, period_start=datetime(2026, 9, 24, tzinfo=timezone.utc), period_end=datetime(2026, 9, 25, tzinfo=timezone.utc))
        session.add_all([alert, digest]); session.flush()
        return user_id, alert.id, digest.id


def test_notification_preferences_and_attempt_history_are_owner_scoped(tmp_path):
    from fastapi.testclient import TestClient
    from test_competitions import make_client
    from app.auth.seed import seed_private_user
    app, owner = make_client(tmp_path); user_id, alert_id, _ = _seed_attention(app, owner)
    assert owner.get('/notification-preferences').json() == []
    saved = owner.put('/notification-preferences', json={'enabled': True, 'immediate_alerts_enabled': True, 'digest_enabled': False}).json()
    assert saved['user_id'] == user_id and saved['enabled'] is True
    seed_private_user(app.state.session_factory, 'other@example.com', 'other-password')
    other = TestClient(app); other.post('/auth/login', json={'email': 'other@example.com', 'password': 'other-password'})
    assert other.get('/notification-attempts').json() == []
    assert other.post(f'/alerts/{alert_id}/deliver').status_code == 404


def test_alert_and_digest_delivery_are_idempotent_and_do_not_acknowledge(tmp_path):
    from test_competitions import make_client
    from app.notifications.providers import FakeNotificationProvider
    from app.notifications.service import deliver_attempt
    app, client = make_client(tmp_path); _, alert_id, digest_id = _seed_attention(app, client)
    client.put('/notification-preferences', json={'enabled': True, 'immediate_alerts_enabled': True, 'digest_enabled': True})
    first = client.post(f'/alerts/{alert_id}/deliver'); assert first.status_code == 200
    again = client.post(f'/alerts/{alert_id}/deliver'); assert again.status_code == 200
    digest = client.post(f'/digests/{digest_id}/deliver'); assert digest.status_code == 200
    provider = FakeNotificationProvider()
    deliver_attempt(app.state.session_factory, first.json()['id'], {'fake': provider})
    deliver_attempt(app.state.session_factory, digest.json()['id'], {'fake': provider})
    deliver_attempt(app.state.session_factory, first.json()['id'], {'fake': provider})
    history = client.get('/notification-attempts').json()
    assert len(history) == 2
    assert {attempt['status'] for attempt in history} == {'succeeded'}
    assert client.get('/alerts').json()[0]['status'] == 'new'
    assert client.get(f'/digests/{digest_id}').status_code == 200


def test_disabled_preferences_prevent_delivery_and_safe_failures_retry(tmp_path):
    from test_competitions import make_client
    from app.notifications.providers import FakeNotificationProvider
    from app.notifications.service import deliver_attempt, schedule_alert_delivery
    app, client = make_client(tmp_path); user_id, alert_id, _ = _seed_attention(app, client)
    assert client.post(f'/alerts/{alert_id}/deliver').status_code == 409
    client.put('/notification-preferences', json={'enabled': True, 'immediate_alerts_enabled': True, 'digest_enabled': False})
    with app.state.session_factory.begin() as session:
        attempt = schedule_alert_delivery(session, user_id=user_id, alert_id=alert_id)
    result = deliver_attempt(app.state.session_factory, attempt.id, {'fake': FakeNotificationProvider(error_code='authentication_failure', error_message='token=secret')})
    assert result == attempt.id
    row = client.get('/notification-attempts').json()[0]
    assert row['status'] == 'retry_wait' and row['last_error_code'] == 'authentication_failure'
    assert 'secret' not in (row['last_error_message'] or '')

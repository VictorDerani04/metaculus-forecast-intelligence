import pytest

from app.integrations.metaculus.parser import parse_metaculus_url


def test_parse_metaculus_question_url_returns_post_id():
    post_id = parse_metaculus_url(
        "https://www.metaculus.com/questions/45262/"
        "what-vote-share-will-iotova-win-in-2026-bulgarian-presidential-election/"
    )

    assert post_id == 45262


@pytest.mark.parametrize('url', [
    'https://example.com/questions/45262/',
    'https://www.metaculus.com.evil.test/questions/45262/',
    'ftp://www.metaculus.com/questions/45262/',
    'https://user@www.metaculus.com/questions/45262/',
    'https://www.metaculus.com:8443/questions/45262/',
    'https://www.metaculus.com/notebooks/45262/',
    'https://www.metaculus.com/questions/0/',
    'https://www.metaculus.com/questions/-1/',
    'https://www.metaculus.com/questions/nope/',
    'not a URL',
    '',
])
def test_parse_rejects_invalid_question_urls(url):
    with pytest.raises(ValueError):
        parse_metaculus_url(url)


def test_client_maps_question_metadata_without_community_prediction():
    import httpx
    from app.integrations.metaculus.client import MetaculusClient

    payload = {
        'id': 45262,
        'title': 'Will event X occur?',
        'question': {
            'type': 'binary',
            'resolution_criteria': 'Resolves Yes if the official result confirms X.',
            'scheduled_close_time': '2026-11-01T00:00:00Z',
            'scheduled_resolve_time': '2026-12-01T00:00:00Z',
            'aggregations': {},
        },
    }
    def respond(request):
        assert str(request.url) == 'https://www.metaculus.com/api/posts/45262/'
        assert request.headers['Authorization'] == 'Token test-token'
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        data = MetaculusClient(token='test-token', http=http).fetch_post(45262)
    assert data.title == 'Will event X occur?'
    assert data.resolution_criteria == payload['question']['resolution_criteria']
    assert data.question_type == 'binary'
    assert data.close_at.isoformat() == '2026-11-01T00:00:00+00:00'
    assert data.resolve_at.isoformat() == '2026-12-01T00:00:00+00:00'
    assert data.crowd_probability is None
    assert data.source_payload == payload


@pytest.mark.parametrize('failure', [401, 403, 429, 503, 'timeout', 'invalid-json'])
def test_client_provider_failures_have_safe_unavailable_contract(failure):
    import httpx
    from app.integrations.metaculus.client import MetaculusClient, MetaculusUnavailable

    def respond(request):
        if failure == 'timeout':
            raise httpx.ReadTimeout('secret provider details', request=request)
        if failure == 'invalid-json':
            return httpx.Response(200, text='<html>secret provider details</html>')
        return httpx.Response(failure, text='secret provider details')

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        with pytest.raises(MetaculusUnavailable) as error:
            MetaculusClient(token='test-token', http=http).fetch_post(45262)
    assert 'secret' not in str(error.value)


def test_client_without_token_does_not_request_provider():
    import httpx
    from app.integrations.metaculus.client import MetaculusClient, MetaculusUnavailable

    def forbidden(request):
        pytest.fail('Unauthenticated provider request')

    with httpx.Client(transport=httpx.MockTransport(forbidden)) as http:
        with pytest.raises(MetaculusUnavailable):
            MetaculusClient(token='', http=http).fetch_post(45262)


def test_client_preserves_partial_data_when_optional_fields_are_malformed():
    import httpx
    from app.integrations.metaculus.client import MetaculusClient

    payload = {'id': 45262, 'title': 'Keep this question', 'question': {
        'resolution_criteria': ['unexpected'],
        'scheduled_close_time': 'not-a-date',
        'scheduled_resolve_time': None,
    }}
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as http:
        data = MetaculusClient(token='test-token', http=http).fetch_post(45262)
    assert data.title == 'Keep this question'
    assert data.resolution_criteria is None
    assert data.close_at is None
    assert data.resolve_at is None
    assert data.crowd_probability is None
    assert data.source_payload == payload


@pytest.mark.parametrize('payload', [[], None, 'bad', {'id': 999, 'title': 'Wrong post'}, {'id': 45262, 'question': []}])
def test_client_rejects_unusable_or_mismatched_source_payload(payload):
    import httpx
    from app.integrations.metaculus.client import MetaculusClient, MetaculusUnavailable
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as http:
        with pytest.raises(MetaculusUnavailable):
            MetaculusClient(token='test-token', http=http).fetch_post(45262)


def test_import_persists_source_metadata_in_owned_competition(tmp_path):
    from datetime import datetime, timezone
    from sqlalchemy import select
    from test_competitions import make_client, login
    from app.competitions.models import QuestionSource
    from app.integrations.metaculus.dependencies import get_metaculus_client
    from app.integrations.metaculus.schemas import MetaculusQuestionData

    class Source:
        def fetch_post(self, post_id):
            assert post_id == 45262
            return MetaculusQuestionData(
                title='Imported question', resolution_criteria='Official results.',
                question_type='binary', close_at='2026-11-01T00:00:00Z',
                resolve_at='2026-12-01T00:00:00Z', source_payload={'id': 45262},
            )

    app, client = make_client(tmp_path)
    app.dependency_overrides[get_metaculus_client] = lambda: Source()
    login(app, client)
    competition = client.post('/competitions', json={'name': 'Cup'}).json()
    response = client.post(f"/competitions/{competition['id']}/questions/import", json={
        'url': 'https://www.metaculus.com/questions/45262/example/?tracking=yes',
    })
    assert response.status_code == 201
    result = response.json()
    assert result['title'] == 'Imported question'
    assert result['source_post_id'] == 45262
    assert result['source_url'] == 'https://www.metaculus.com/questions/45262/'
    assert result['crowd_probability'] is None
    assert result['import_status'] == 'imported'
    assert result['resolution_criteria'] == 'Official results.'
    with app.state.session_factory() as session:
        source = session.scalar(select(QuestionSource).where(QuestionSource.question_id == result['id']))
        assert source.user_id == client.get('/auth/me').json()['id']
        assert source.source_payload == {'id': 45262}
        assert source.close_at.replace(tzinfo=timezone.utc) == datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert client.get(f"/competitions/{competition['id']}/questions").json()[0]['title'] == 'Imported question'
    assert client.get('/competitions').json()[0]['question_count'] == 1


def test_unavailable_import_returns_manual_fallback_without_creating_question(tmp_path):
    from test_competitions import make_client, login
    from app.integrations.metaculus.dependencies import get_metaculus_client
    from app.integrations.metaculus.client import MetaculusUnavailable

    class Unavailable:
        def fetch_post(self, post_id):
            raise MetaculusUnavailable('sensitive upstream error')

    app, client = make_client(tmp_path)
    app.dependency_overrides[get_metaculus_client] = lambda: Unavailable()
    login(app, client)
    competition_id = client.post('/competitions', json={'name': 'Cup'}).json()['id']
    response = client.post(f'/competitions/{competition_id}/questions/import', json={
        'url': 'https://www.metaculus.com/questions/45262/',
    })
    assert response.status_code == 409
    detail = response.json()['detail']
    assert detail['code'] == 'manual_entry_required'
    assert 'sensitive' not in detail['message']
    assert client.get(f'/competitions/{competition_id}/questions').json() == []


def test_manual_fallback_saves_user_details_and_source_without_provider_request(tmp_path):
    from sqlalchemy import select
    from test_competitions import make_client, login
    from app.competitions.models import QuestionSource
    from app.integrations.metaculus.dependencies import get_metaculus_client

    class Forbidden:
        def fetch_post(self, post_id):
            pytest.fail('Manual entry must not call provider')

    app, client = make_client(tmp_path)
    app.dependency_overrides[get_metaculus_client] = lambda: Forbidden()
    login(app, client)
    competition_id = client.post('/competitions', json={'name': 'Cup'}).json()['id']
    response = client.post(f'/competitions/{competition_id}/questions/import', json={
        'url': 'https://metaculus.com/questions/45262/',
        'manual_details': {'title': 'Manually entered title', 'resolution_criteria': 'My entered criteria'},
    })
    assert response.status_code == 201
    result = response.json()
    assert result['import_status'] == 'manual'
    assert result['title'] == 'Manually entered title'
    assert result['resolution_criteria'] == 'My entered criteria'
    assert result['crowd_probability'] is None
    with app.state.session_factory() as session:
        source = session.scalar(select(QuestionSource).where(QuestionSource.question_id == result['id']))
        assert source.source_payload == {}
        assert source.source_post_id == 45262


@pytest.mark.parametrize('title', ['Known title', None])
def test_partial_import_preserves_question_without_optional_enrichment(tmp_path, title):
    from test_competitions import make_client, login
    from app.integrations.metaculus.dependencies import get_metaculus_client
    from app.integrations.metaculus.schemas import MetaculusQuestionData

    class Partial:
        def fetch_post(self, post_id):
            return MetaculusQuestionData(title=title, source_payload={'id': post_id})

    app, client = make_client(tmp_path)
    app.dependency_overrides[get_metaculus_client] = lambda: Partial()
    login(app, client)
    competition_id = client.post('/competitions', json={'name': 'Cup'}).json()['id']
    response = client.post(f'/competitions/{competition_id}/questions/import', json={
        'url': 'https://www.metaculus.com/questions/45262/',
    })
    assert response.status_code == 201
    assert response.json()['title'] == (title or 'Metaculus question 45262')
    assert response.json()['import_status'] == 'partial'
    assert response.json()['crowd_probability'] is None


def test_invalid_import_url_is_validation_error_and_does_not_fetch(tmp_path):
    from test_competitions import make_client, login
    from app.integrations.metaculus.dependencies import get_metaculus_client

    class Forbidden:
        def fetch_post(self, post_id):
            pytest.fail('Invalid URL must not reach provider')

    app, client = make_client(tmp_path)
    app.dependency_overrides[get_metaculus_client] = lambda: Forbidden()
    login(app, client)
    competition_id = client.post('/competitions', json={'name': 'Cup'}).json()['id']
    response = client.post(f'/competitions/{competition_id}/questions/import', json={'url': 'https://evil.test/questions/45262/'})
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'invalid_url'
    assert client.get(f'/competitions/{competition_id}/questions').json() == []


@pytest.mark.parametrize('title', ['', '   ', 'x' * 501])
def test_manual_import_rejects_unusable_title(tmp_path, title):
    from test_competitions import make_client, login
    app, client = make_client(tmp_path)
    login(app, client)
    competition_id = client.post('/competitions', json={'name': 'Cup'}).json()['id']
    response = client.post(f'/competitions/{competition_id}/questions/import', json={
        'url': 'https://www.metaculus.com/questions/45262/',
        'manual_details': {'title': title},
    })
    assert response.status_code == 422
    assert client.get(f'/competitions/{competition_id}/questions').json() == []


@pytest.mark.parametrize('identity,expected', [('anonymous', 401), ('other', 404)])
def test_import_enforces_ownership_before_fetching(tmp_path, identity, expected):
    from fastapi.testclient import TestClient
    from app.auth.seed import seed_private_user
    from test_competitions import make_client, login
    from app.integrations.metaculus.dependencies import get_metaculus_client

    class Forbidden:
        def fetch_post(self, post_id):
            pytest.fail('Unauthorized user reached provider')

    app, owner = make_client(tmp_path)
    app.dependency_overrides[get_metaculus_client] = lambda: Forbidden()
    login(app, owner)
    competition_id = owner.post('/competitions', json={'name': 'Private'}).json()['id']
    client = TestClient(app)
    if identity == 'other':
        seed_private_user(app.state.session_factory, 'other@example.com', 'other-password')
        assert client.post('/auth/login', json={'email': 'other@example.com', 'password': 'other-password'}).status_code == 200
    for manual in [None, {'title': 'Unauthorized'}]:
        response = client.post(f'/competitions/{competition_id}/questions/import', json={
            'url': 'https://www.metaculus.com/questions/45262/', 'manual_details': manual,
        })
        assert response.status_code == expected
    assert owner.get(f'/competitions/{competition_id}/questions').json() == []


@pytest.mark.parametrize('kind,centers,expected', [
    ('binary', [0.72], 0.72), ('binary', [0.0], 0.0),
    ('numeric', [0.72], None), ('binary', [1.2], None),
    ('binary', [True], None), ('binary', [], None),
])
def test_client_reads_only_valid_binary_community_probability(kind, centers, expected):
    import httpx
    from app.integrations.metaculus.client import MetaculusClient
    payload = {'id': 45262, 'title': 'Question', 'question': {
        'type': kind, 'aggregations': {'recency_weighted': {'latest': {'centers': centers}}},
    }}
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as http:
        data = MetaculusClient(token='test-token', http=http).fetch_post(45262)
    assert data.crowd_probability == expected


def test_oversized_post_id_is_rejected_before_manual_persistence(tmp_path):
    from test_competitions import make_client, login
    app, client = make_client(tmp_path)
    login(app, client)
    competition_id = client.post('/competitions', json={'name': 'Cup'}).json()['id']
    response = client.post(f'/competitions/{competition_id}/questions/import', json={
        'url': 'https://www.metaculus.com/questions/2147483648/',
        'manual_details': {'title': 'Must not be created'},
    })
    assert response.status_code == 422
    assert client.get(f'/competitions/{competition_id}/questions').json() == []


@pytest.mark.parametrize('origin,status', [('http://localhost:3000', 200), ('https://untrusted.example', 400)])
def test_browser_import_preflight_only_allows_configured_web_origin(tmp_path, monkeypatch, origin, status):
    from test_competitions import make_client
    monkeypatch.setenv('WEB_ORIGIN', 'http://localhost:3000')
    _, client = make_client(tmp_path)
    response = client.options('/competitions/cup/questions/import', headers={
        'Origin': origin, 'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type',
    })
    assert response.status_code == status
    if status == 200:
        assert response.headers['access-control-allow-origin'] == origin
        assert response.headers['access-control-allow-credentials'] == 'true'
    else:
        assert 'access-control-allow-origin' not in response.headers


def test_client_retains_raw_oversized_text_without_exceeding_database_limits():
    import httpx
    from app.integrations.metaculus.client import MetaculusClient
    payload = {'id': 45262, 'title': 'x' * 501, 'question': {'type': 'x' * 101}}
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as http:
        data = MetaculusClient(token='test-token', http=http).fetch_post(45262)
    assert data.title is None
    assert data.question_type is None
    assert data.source_payload == payload

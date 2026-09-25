from datetime import datetime, timezone
import json

import httpx
import pytest


def test_live_web_provider_maps_safe_provenance_and_deterministic_query():
    from app.monitoring.providers.live import TavilyWebSearchProvider
    from app.monitoring.providers.base import QuestionContext

    captured = {}
    def respond(request):
        captured['url'], captured['json'] = str(request.url), json.loads(request.content)
        return httpx.Response(200, json={'results': [{'url': 'https://example.test/report?utm_source=x', 'title': ' Report ', 'content': ' A finding ', 'published_date': '2026-09-25T00:00:00Z'}]})
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        result = TavilyWebSearchProvider(api_key='secret', http=http).fetch(QuestionContext('q', 'Will inflation fall by 2027?', 'Inflation is the criterion'))
    assert captured['url'] == 'https://api.tavily.com/search'
    assert captured['json']['query'] == 'Will inflation fall by 2027?'
    assert result.items == [{'external_id': None, 'url': 'https://example.test/report?utm_source=x', 'title': 'Report', 'text': 'A finding', 'source_name': 'Tavily web search', 'published_at': datetime(2026, 9, 25, tzinfo=timezone.utc), 'metadata': {'query': 'Will inflation fall by 2027?', 'rank': 1}}]


def test_live_registry_is_allowlisted_and_requires_an_explicit_key():
    from app.monitoring.providers.live import build_live_provider_registry
    assert build_live_provider_registry({}) == {}
    assert set(build_live_provider_registry({'WEB_SEARCH_API_KEY': 'test-key'})) == {'web'}


def test_application_exposes_only_configured_live_provider_registry(tmp_path, monkeypatch):
    from app.main import create_app
    monkeypatch.setenv('WEB_SEARCH_API_KEY', 'test-key')
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}", seed_user=False)
    assert set(app.state.monitoring_providers) == {'web'}


@pytest.mark.parametrize(('status', 'code'), [(401, 'provider_authentication_failure'), (429, 'rate_limited'), (503, 'provider_unavailable')])
def test_live_web_provider_maps_http_failures_to_safe_codes(status, code):
    from app.monitoring.providers.live import TavilyWebSearchProvider
    from app.monitoring.providers.base import ProviderFailure, QuestionContext
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status, text='secret body'))) as http:
        with pytest.raises(ProviderFailure, match=code): TavilyWebSearchProvider(api_key='secret', http=http).fetch(QuestionContext('q', 'Question', None))

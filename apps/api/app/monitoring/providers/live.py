"""Application-owned fixed-endpoint live search provider."""
import json
import os
from datetime import datetime

import httpx

from app.monitoring.normalization import normalize_text
from app.monitoring.providers.base import ProviderFailure, ProviderResult, QuestionContext

TAVILY_ENDPOINT = 'https://api.tavily.com/search'


def build_query(question: QuestionContext) -> str:
    return normalize_text(question.title)[:500]


def _published(value):
    if not isinstance(value, str): return None
    try: return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError: return None


class TavilyWebSearchProvider:
    provider_name = 'web'
    def __init__(self, *, api_key: str, http: httpx.Client | None = None, timeout_seconds: float = 10):
        self._api_key, self._http, self._timeout = api_key, http, timeout_seconds

    def fetch(self, question: QuestionContext, cursor=None) -> ProviderResult:
        query = build_query(question)
        try:
            if self._http:
                response = self._http.post(TAVILY_ENDPOINT, json={'api_key': self._api_key, 'query': query, 'max_results': 5}, timeout=self._timeout)
            else:
                with httpx.Client(timeout=self._timeout, follow_redirects=False) as http:
                    response = http.post(TAVILY_ENDPOINT, json={'api_key': self._api_key, 'query': query, 'max_results': 5})
        except httpx.TimeoutException as exc: raise ProviderFailure('provider_timeout') from exc
        except httpx.HTTPError as exc: raise ProviderFailure('provider_unavailable') from exc
        if response.status_code in {401, 403}: raise ProviderFailure('provider_authentication_failure')
        if response.status_code == 429: raise ProviderFailure('rate_limited')
        if response.status_code >= 500: raise ProviderFailure('provider_unavailable')
        if response.status_code >= 400: raise ProviderFailure('provider_failure')
        try: results = response.json().get('results', [])
        except (ValueError, AttributeError) as exc: raise ProviderFailure('malformed_provider_response') from exc
        if not isinstance(results, list): raise ProviderFailure('malformed_provider_response')
        items = []
        for rank, result in enumerate(results[:5], 1):
            if not isinstance(result, dict) or not isinstance(result.get('url'), str): continue
            items.append({'external_id': result.get('id') if isinstance(result.get('id'), str) else None, 'url': result['url'], 'title': normalize_text(result.get('title')) or 'Untitled result', 'text': normalize_text(result.get('content')), 'source_name': 'Tavily web search', 'published_at': _published(result.get('published_date')), 'metadata': {'query': query, 'rank': rank}})
        return ProviderResult(items=items, provider_metadata={'query': query, 'pagination': 'stateless'})


def build_live_provider_registry(environ=None):
    environ = os.environ if environ is None else environ
    key = environ.get('WEB_SEARCH_API_KEY')
    return {'web': TavilyWebSearchProvider(api_key=key, timeout_seconds=float(environ.get('WEB_SEARCH_TIMEOUT_SECONDS', '10')))} if key else {}

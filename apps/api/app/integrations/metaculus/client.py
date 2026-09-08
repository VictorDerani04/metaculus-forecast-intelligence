import httpx

from app.integrations.metaculus.schemas import MetaculusQuestionData


class MetaculusUnavailable(Exception):
    """Source data is unavailable; manual entry remains possible."""


class MetaculusClient:
    def __init__(self, *, token: str, http: httpx.Client):
        self.token = token
        self.http = http

    def fetch_post(self, post_id: int) -> MetaculusQuestionData:
        if not self.token.strip():
            raise MetaculusUnavailable('Live import unavailable. Enter question details manually.')
        try:
            response = self.http.get(
                f'https://www.metaculus.com/api/posts/{post_id}/',
                headers={'Authorization': f'Token {self.token}'},
                timeout=10,
                follow_redirects=False,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MetaculusUnavailable('Live import unavailable. Enter question details manually.') from exc
        if not isinstance(payload, dict) or payload.get('id', post_id) != post_id:
            raise MetaculusUnavailable('Live import returned unusable question data.')
        question = payload.get('question')
        if question is None:
            question = {}
        if not isinstance(question, dict):
            raise MetaculusUnavailable('Live import returned unusable question data.')
        return MetaculusQuestionData(
            title=payload.get('title'),
            resolution_criteria=question.get('resolution_criteria'),
            question_type=question.get('type'),
            close_at=question.get('scheduled_close_time'),
            resolve_at=question.get('scheduled_resolve_time'),
            crowd_probability=binary_community_probability(question),
            source_payload=payload,
        )


def binary_community_probability(question: dict) -> float | None:
    if question.get('type') != 'binary':
        return None
    value = question
    for key in ('aggregations', 'recency_weighted', 'latest', 'centers'):
        value = value.get(key) if isinstance(value, dict) else None
    if isinstance(value, list) and len(value) == 1:
        probability = value[0]
        if type(probability) in (int, float) and 0 <= probability <= 1:
            return float(probability)
    return None

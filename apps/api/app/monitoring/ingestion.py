"""Persistence boundary for untrusted provider observations."""
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy import select

from app.monitoring.classification import MaterialityResult, RelevanceResult, validate_materiality, validate_relevance
from app.monitoring.models import Finding, ProviderCursor, RawFinding
from app.monitoring.normalization import canonicalize_url, fingerprint, normalize_text
from app.research.models import ResearchItem
from app.monitoring.alerts import route_finding
from app.monitoring.source_intelligence_service import attach_to_event_cluster


@dataclass
class IngestionFailure(Exception):
    code: str
    counts: dict[str, int]


def empty_counts():
    return {'raw': 0, 'normalized': 0, 'duplicates': 0, 'relevant': 0, 'material': 0, 'candidates': 0}


def _draft(item, provider):
    url = canonicalize_url(item.get('url'))
    title = normalize_text(item.get('title')) or 'Untitled finding'
    source = normalize_text(item.get('source_name')) or 'Unknown source'
    published_at = item.get('published_at')
    return {'url': url, 'title': title, 'summary': normalize_text(item.get('text')), 'source_name': source,
            'fingerprint': fingerprint(provider, item.get('external_id'), url, title, source, published_at), 'published_at': published_at}


def _classify(question, draft, relevance, materiality):
    try:
        if hasattr(relevance, 'classify_both'):
            pair = relevance.classify_both(question, draft)
            rel, mat = validate_relevance(pair[0]), validate_materiality(pair[1])
        else:
            rel, mat = validate_relevance(relevance.classify(question, draft)), validate_materiality(materiality.classify(question, draft))
        # Materiality is meaningful only after relevance is established. Persist this
        # conservative routing result rather than letting contradictory output alert.
        if rel.relevance_class != 'relevant':
            mat = MaterialityResult('irrelevant', 0, 'Relevance is not established.', mat.confidence, 'neutral', mat.provider, mat.model, mat.classified_at, mat.schema_version)
        return rel, mat, None
    except Exception:
        # Preserve reviewable data but never derive a candidate from malformed AI output.
        return RelevanceResult('uncertain', 0, 'Classification unavailable'), MaterialityResult('irrelevant', 0, 'Classification unavailable'), 'classification_failure'


def ingest_item(session, *, user_id, question_id, run_id, provider, item, question, relevance, materiality):
    """Persist one item atomically; classifier calls have no database transaction."""
    counts = empty_counts(); draft = _draft(item, provider)
    rel, mat, failure = _classify(question, draft, relevance, materiality)
    raw = RawFinding(user_id=user_id, question_id=question_id, monitoring_run_id=run_id, provider=provider,
                     external_id=item.get('external_id'), source_url=item.get('url'), raw_title=item.get('title'),
                     raw_text=item.get('text'), published_at=draft['published_at'], raw_metadata_json={})
    session.add(raw); session.flush(); counts['raw'] = 1
    existing = session.scalar(select(Finding).where(Finding.user_id == user_id, Finding.question_id == question_id,
                                                     Finding.content_fingerprint == draft['fingerprint']))
    if existing is not None:
        counts['duplicates'] = 1
        return counts, failure
    finding = Finding(user_id=user_id, question_id=question_id, monitoring_run_id=run_id, raw_finding_id=raw.id,
                      provider=provider, provider_external_id=item.get('external_id'), source_url=item.get('url'),
                      canonical_url=draft['url'], title=draft['title'], summary=draft['summary'], source_name=draft['source_name'],
                      source_domain=urlsplit(draft['url']).netloc if draft['url'] else None, published_at=draft['published_at'],
                      content_fingerprint=draft['fingerprint'], relevance_class=rel.relevance_class, relevance_score=rel.score,
                      relevance_confidence=rel.confidence, relevance_reason=rel.reason, materiality_class=mat.materiality_class,
                      materiality_score=mat.score, materiality_confidence=mat.confidence, materiality_direction=mat.direction,
                      materiality_reason=mat.reason, classifier_provider=rel.provider, classifier_model=rel.model,
                      classified_at=rel.classified_at, classifier_schema_version=rel.schema_version)
    session.add(finding); session.flush(); counts['normalized'] = 1
    attach_to_event_cluster(session, finding)
    route_finding(session, finding); session.flush()
    if rel.relevance_class == 'relevant': counts['relevant'] = 1
    if mat.materiality_class in {'material', 'critical'}: counts['material'] = 1
    if rel.relevance_class == 'relevant' and mat.materiality_class in {'material', 'critical'}:
        session.add(ResearchItem(user_id=user_id, question_id=question_id, title=draft['title'], summary=draft['summary'],
                                 source_url=draft['url'] or '', source_name=draft['source_name'], origin='monitoring',
                                 monitoring_run_id=run_id, finding_id=finding.id, provider=provider,
                                 materiality_score=mat.score, materiality_class=mat.materiality_class,
                                 classification_reason=f'{rel.reason}\n{mat.reason}'))
        session.flush(); counts['candidates'] = 1
    return counts, failure


def advance_cursor(session, *, user_id, question_id, provider, next_cursor):
    cursor = session.scalar(select(ProviderCursor).where(ProviderCursor.user_id == user_id,
        ProviderCursor.question_id == question_id, ProviderCursor.provider == provider))
    if cursor is None:
        cursor = ProviderCursor(user_id=user_id, question_id=question_id, provider=provider); session.add(cursor)
    cursor.cursor_value = next_cursor


def current_cursor(session_factory, *, user_id, question_id, provider):
    with session_factory() as session:
        return session.scalar(select(ProviderCursor.cursor_value).where(ProviderCursor.user_id == user_id,
            ProviderCursor.question_id == question_id, ProviderCursor.provider == provider))


def process_provider_result(session_factory, *, user_id, question_id, run_id, provider, items, next_cursor, question, relevance, materiality):
    """Commit each safe item, then move its cursor only after the complete result."""
    total = empty_counts()
    for item in items:
        with session_factory.begin() as session:
            counts, failure = ingest_item(session, user_id=user_id, question_id=question_id, run_id=run_id, provider=provider,
                                          item=item, question=question, relevance=relevance, materiality=materiality)
        for key, value in counts.items(): total[key] += value
        if failure: raise IngestionFailure(failure, total)
    with session_factory.begin() as session:
        advance_cursor(session, user_id=user_id, question_id=question_id, provider=provider, next_cursor=next_cursor)
    return total


def ingest(session, *, user_id, question_id, run_id, provider, items, next_cursor, relevance, materiality):
    """Compatibility helper for direct unit callers."""
    total = empty_counts()
    for item in items:
        counts, failure = ingest_item(session, user_id=user_id, question_id=question_id, run_id=run_id, provider=provider,
                                      item=item, question=None, relevance=relevance, materiality=materiality)
        for key, value in counts.items(): total[key] += value
        if failure: raise IngestionFailure(failure, total)
    advance_cursor(session, user_id=user_id, question_id=question_id, provider=provider, next_cursor=next_cursor)
    return total

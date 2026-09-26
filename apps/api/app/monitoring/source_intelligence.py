"""Conservative, deterministic source and event intelligence for untrusted findings.

This module deliberately does not infer political leaning or truth.  It records a
bounded source descriptor and only joins findings when their wording strongly
indicates the same underlying development.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from urllib.parse import urlsplit


OFFICIAL_DOMAINS = frozenset({'cdc.gov', 'who.int', 'un.org', 'gov.uk', 'whitehouse.gov'})
WIRE_DOMAINS = frozenset({'reuters.com', 'apnews.com', 'afp.com', 'bloomberg.com'})
HIGH_RELIABILITY_DOMAINS = OFFICIAL_DOMAINS | WIRE_DOMAINS
STOP_WORDS = frozenset({'a', 'an', 'the', 'and', 'or', 'for', 'to', 'of', 'in', 'on', 'at', 'by', 'with', 'from', 'that', 'this', 'is', 'are', 'was', 'were', 'reports', 'report', 'says', 'say'})


@dataclass(frozen=True)
class SourceAssessment:
    normalized_source: str | None
    source_type: str
    reliability_level: str
    reliability_reason: str


@dataclass(frozen=True)
class ClusterCandidate:
    question_id: str
    title: str
    summary: str
    normalized_source: str | None
    source_type: str
    published_at: datetime | None


@dataclass(frozen=True)
class ClusterMatch:
    matched: bool
    score: float
    reason: str


def _registrable_domain(value: str | None) -> str | None:
    if not value:
        return None
    host = urlsplit(value).hostname if '://' in value else value.split('/')[0]
    if not host:
        return None
    host = host.lower().strip('. ')
    return host[4:] if host.startswith('www.') else host


def assess_source(source_url: str | None, source_name: str | None) -> SourceAssessment:
    """Return a bounded descriptor; publisher text is data and never instructions."""
    domain = _registrable_domain(source_url)
    if domain in OFFICIAL_DOMAINS or (domain and (domain.endswith('.gov') or '.gob.' in domain)):
        return SourceAssessment(domain, 'official', 'high', 'Official sources are authoritative about their own actions only.')
    if domain in WIRE_DOMAINS:
        return SourceAssessment(domain, 'wire_service', 'high', 'Established wire service; still requires corroboration for claims.')
    if domain:
        return SourceAssessment(domain, 'news_or_web', 'unknown', 'No bounded reliability assessment is available for this source.')
    return SourceAssessment(None, 'unknown', 'unknown', 'Source identity is ambiguous.')


def _tokens(*values: str) -> set[str]:
    words = re.findall(r"[a-z0-9]{2,}", ' '.join(values).lower())
    normalized = set()
    for word in words:
        if word in STOP_WORDS:
            continue
        if word.endswith('ed') and len(word) > 4:
            word = word[:-2]
        elif word.endswith('es') and len(word) > 4:
            word = word[:-2]
        elif word.endswith('s') and len(word) > 3:
            word = word[:-1]
        normalized.add(word)
    return normalized


def cluster_match(existing: ClusterCandidate, incoming: ClusterCandidate) -> ClusterMatch:
    """Match only same-question, high-overlap reports; false merges are worse."""
    if existing.question_id != incoming.question_id:
        return ClusterMatch(False, 0, 'Question boundary differs.')
    title_a, title_b = _tokens(existing.title), _tokens(incoming.title)
    detail_a, detail_b = _tokens(existing.summary), _tokens(incoming.summary)
    title_union = title_a | title_b
    title_score = len(title_a & title_b) / len(title_union) if title_union else 0
    detail_overlap = len(detail_a & detail_b)
    # At least three matching substantive title terms and corroborating detail are
    # required. This intentionally leaves ambiguous topical reports separate.
    matched = title_score >= .60 and len(title_a & title_b) >= 3 and detail_overlap >= 2
    return ClusterMatch(matched, round(title_score, 3), 'High title and detail overlap.' if matched else 'Insufficient same-event evidence.')


def syndicated_origin(title: str, source_name: str, normalized_source: str | None) -> str | None:
    """Recognize a small deterministic wire byline set, never an LLM guess."""
    text = f'{title} {source_name}'.lower()
    for domain, marker in (('reuters.com', 'reuters'), ('apnews.com', 'associated press'), ('afp.com', 'afp')):
        if marker in text:
            return domain
    return normalized_source

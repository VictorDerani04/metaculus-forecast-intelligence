import hashlib
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'}

def normalize_text(value: str | None) -> str:
    return ' '.join((value or '').split())

def canonicalize_url(value: str | None) -> str | None:
    if not value: return None
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {'http', 'https'} or not parsed.netloc: return None
    query = urlencode([(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in TRACKING], doseq=True)
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or '/', query, ''))

def fingerprint(provider, external_id, canonical_url, title, source_name, published_at: datetime | None) -> str:
    parts = [normalize_text(str(x)).lower() for x in (provider, external_id or '', canonical_url or '', title, source_name)]
    parts.append(published_at.isoformat() if published_at else '')
    return hashlib.sha256('\x1f'.join(parts).encode()).hexdigest()

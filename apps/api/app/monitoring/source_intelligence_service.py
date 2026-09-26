"""Persistence and corroboration for conservative event clusters."""
from datetime import timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.monitoring.models import EventCluster, Finding, FindingEventLink, utcnow
from app.monitoring.source_intelligence import ClusterCandidate, assess_source, cluster_match, syndicated_origin


def get_owned_event_cluster(session: Session, *, user_id: str, question_id: str, event_cluster_id: str) -> EventCluster:
    """Return a cluster only within its owner and question boundary."""
    cluster = session.scalar(select(EventCluster).where(
        EventCluster.id == event_cluster_id,
        EventCluster.user_id == user_id,
        EventCluster.question_id == question_id,
    ))
    if cluster is None:
        raise HTTPException(status_code=404, detail='Event cluster not found')
    return cluster


def _candidate(finding: Finding) -> ClusterCandidate:
    return ClusterCandidate(finding.question_id, finding.title, finding.summary, finding.normalized_source or finding.source_domain, finding.source_type, finding.published_at)


def _refresh_corroboration(session: Session, cluster: EventCluster) -> None:
    findings = session.scalars(select(Finding).join(FindingEventLink, FindingEventLink.finding_id == Finding.id).where(FindingEventLink.event_cluster_id == cluster.id, Finding.user_id == cluster.user_id, Finding.question_id == cluster.question_id)).all()
    sources = {finding.normalized_source or finding.source_domain for finding in findings if finding.normalized_source or finding.source_domain}
    origins = {finding.reporting_origin or finding.normalized_source or finding.source_domain for finding in findings if finding.reporting_origin or finding.normalized_source or finding.source_domain}
    cluster.total_findings = len(findings)
    cluster.unique_normalized_sources = len(sources)
    cluster.independent_source_count = len(origins)
    cluster.primary_source_present = any(finding.source_type == 'official' for finding in findings)
    cluster.wire_service_present = any(finding.source_type == 'wire_service' for finding in findings)
    cluster.high_reliability_source_count = len({finding.normalized_source for finding in findings if finding.source_reliability == 'high' and finding.normalized_source})
    timestamps = [finding.discovered_at.replace(tzinfo=timezone.utc) if finding.discovered_at.tzinfo is None else finding.discovered_at for finding in findings]
    if timestamps:
        cluster.first_seen_at, cluster.last_seen_at = min(timestamps), max(timestamps)


def attach_to_event_cluster(session: Session, finding: Finding) -> EventCluster:
    """Link a finding to at most one same-owner/same-question cluster."""
    existing_link = session.scalar(select(FindingEventLink).where(FindingEventLink.finding_id == finding.id, FindingEventLink.user_id == finding.user_id, FindingEventLink.question_id == finding.question_id))
    if existing_link:
        return session.get(EventCluster, existing_link.event_cluster_id)
    assessment = assess_source(finding.canonical_url or finding.source_url, finding.source_name)
    finding.normalized_source = assessment.normalized_source
    finding.source_type = assessment.source_type
    finding.source_reliability = assessment.reliability_level
    finding.source_reliability_reason = assessment.reliability_reason
    finding.reporting_origin = syndicated_origin(finding.title, finding.source_name, assessment.normalized_source)
    candidate = _candidate(finding)
    matched_cluster, matched = None, None
    clusters = session.scalars(select(EventCluster).where(EventCluster.user_id == finding.user_id, EventCluster.question_id == finding.question_id).order_by(EventCluster.last_seen_at.desc())).all()
    for cluster in clusters:
        exemplar = session.scalar(select(Finding).join(FindingEventLink, FindingEventLink.finding_id == Finding.id).where(FindingEventLink.event_cluster_id == cluster.id).order_by(Finding.discovered_at.asc()))
        if exemplar:
            result = cluster_match(_candidate(exemplar), candidate)
            if result.matched:
                matched_cluster, matched = cluster, result
                break
    if matched_cluster is None:
        matched_cluster = EventCluster(user_id=finding.user_id, question_id=finding.question_id, canonical_summary=finding.title, first_seen_at=finding.discovered_at, last_seen_at=finding.discovered_at)
        session.add(matched_cluster); session.flush()
        matched_score, matched_reason = 1.0, 'Initial event cluster finding.'
    else:
        matched_score, matched_reason = matched.score, matched.reason
    session.add(FindingEventLink(user_id=finding.user_id, question_id=finding.question_id, finding_id=finding.id, event_cluster_id=matched_cluster.id, match_score=matched_score, match_reason=matched_reason))
    session.flush()
    _refresh_corroboration(session, matched_cluster)
    return matched_cluster

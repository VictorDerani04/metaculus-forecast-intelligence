from sqlalchemy.orm import Session

from app.audit.models import AuditEvent


def record_audit(
    session: Session,
    *,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    question_id: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        user_id=user_id,
        question_id=question_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=metadata or {},
    )
    session.add(event)
    return event

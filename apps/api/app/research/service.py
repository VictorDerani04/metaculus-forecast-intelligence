from fastapi import HTTPException
from app.forecasts.service import get_owned_question
from sqlalchemy import select, update
from app.research.models import ResearchItem, Evidence, ResearchDecision
from app.research.schemas import CandidateResponse, EvidenceResponse


def create_candidate(session, user_id, payload):
    get_owned_question(session, payload.question_id, user_id)
    item = ResearchItem(user_id=user_id, **payload.model_dump())
    session.add(item)
    session.commit()
    return CandidateResponse.model_validate(item)


def research_for_question(session, question_id, user_id):
    get_owned_question(session, question_id, user_id)
    items = session.scalars(select(ResearchItem).where(
        ResearchItem.question_id == question_id, ResearchItem.user_id == user_id,
    ).order_by(ResearchItem.created_at, ResearchItem.id)).all()
    return {'items': [CandidateResponse.model_validate(item) for item in items], 'evidence': eligible_evidence(session, question_id, user_id)}


def eligible_evidence(session, question_id, user_id):
    get_owned_question(session, question_id, user_id)
    records = session.scalars(select(Evidence).where(
        Evidence.question_id == question_id, Evidence.user_id == user_id,
        Evidence.decision == 'approved',
    ).order_by(Evidence.approved_at, Evidence.id)).all()
    return [EvidenceResponse.model_validate(record) for record in records]


def decide_candidate(session, item_id, user_id, payload):
    item = session.get(ResearchItem, item_id)
    if item is None or item.user_id != user_id:
        raise HTTPException(status_code=404, detail='Research item not found')
    get_owned_question(session, item.question_id, user_id)
    if payload.related_item_id:
        if payload.related_item_id == item.id:
            raise HTTPException(status_code=422, detail='A candidate cannot reference itself')
        related = session.get(ResearchItem, payload.related_item_id)
        if related is None or related.user_id != user_id or related.question_id != item.question_id:
            raise HTTPException(status_code=404, detail='Related research item not found')
    for evidence_id in payload.dependency_evidence_ids:
        dependency = session.get(Evidence, evidence_id)
        dependency_item = session.get(ResearchItem, dependency.research_item_id) if dependency else None
        if (dependency is None or dependency.decision != 'approved'
                or dependency.user_id != user_id or dependency.question_id != item.question_id
                or dependency_item is None or dependency_item.status != 'approved'
                or dependency_item.user_id != user_id or dependency_item.question_id != item.question_id):
            raise HTTPException(status_code=404, detail='Evidence dependency not found')
    if item.status == payload.decision:
        original = session.scalar(select(ResearchDecision).where(
            ResearchDecision.research_item_id == item.id,
        ).order_by(ResearchDecision.id.desc()))
        evidence = session.scalar(select(Evidence).where(Evidence.research_item_id == item.id))
        if (original is None or original.related_item_id != payload.related_item_id
                or (evidence is not None and evidence.dependency_evidence_ids != payload.dependency_evidence_ids)):
            raise HTTPException(status_code=409, detail='Decision links differ from the recorded decision')
        return CandidateResponse.model_validate(item)
    if item.status not in ('candidate', 'deferred'):
        raise HTTPException(status_code=409, detail='Research decision is final')
    changed = session.execute(update(ResearchItem).where(
        ResearchItem.id == item.id, ResearchItem.status == item.status,
    ).values(status=payload.decision))
    if changed.rowcount != 1:
        session.rollback()
        raise HTTPException(status_code=409, detail='Research decision changed; refresh and retry')
    session.add(ResearchDecision(research_item_id=item.id, user_id=user_id, decision=payload.decision, related_item_id=payload.related_item_id))
    if payload.decision == 'approved':
        evidence = Evidence(dependency_evidence_ids=payload.dependency_evidence_ids, research_item_id=item.id, question_id=item.question_id, user_id=user_id,
                            **{field: getattr(item, field) for field in ('title', 'summary', 'source_url', 'source_name')})
        session.add(evidence)
    session.commit()
    return CandidateResponse.model_validate(item)

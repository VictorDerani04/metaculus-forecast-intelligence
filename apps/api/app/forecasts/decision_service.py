from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from app.audit.service import record_audit
from app.competitions.models import Question, QuestionSource
from app.forecasts.models import HumanForecast
from app.forecasts.schemas import DecisionCreate, DecisionResponse
from app.forecasts.service import get_owned_question
from app.models_lab.models import ModelRun, ModelSpec
from app.research.models import Evidence


def create_decision(session: Session, question_id: str, user_id: str, payload: DecisionCreate) -> DecisionResponse:
    question = get_owned_question(session, question_id, user_id)
    human = session.scalar(select(HumanForecast).where(
        HumanForecast.question_id == question_id,
        HumanForecast.user_id == user_id,
    ).order_by(HumanForecast.created_at.desc(), HumanForecast.id.desc()))
    source = session.scalar(select(QuestionSource).where(
        QuestionSource.question_id == question_id,
        QuestionSource.user_id == user_id,
    ))
    model = session.scalar(select(ModelRun).where(
        ModelRun.question_id == question_id,
        ModelRun.user_id == user_id,
        ModelRun.status == 'succeeded',
    ).order_by(ModelRun.created_at.desc(), ModelRun.id.desc()))
    evidence_ids = [
        evidence.id for evidence in session.scalars(select(Evidence).where(
            Evidence.question_id == question_id,
            Evidence.user_id == user_id,
            Evidence.decision == 'approved',
        ).order_by(Evidence.approved_at, Evidence.id)).all()
    ]
    model_spec_id = model.model_spec_id if model else None
    decision = DecisionResponse.from_snapshot(
        user_id=user_id,
        question=question,
        human=human,
        source=source,
        model=model,
        evidence_ids=evidence_ids,
        rationale=payload.rationale,
    )
    from app.audit.models import DecisionJournal
    record = DecisionJournal(
        id=decision.id,
        user_id=user_id,
        question_id=question_id,
        human_probability=decision.human_probability,
        rationale=payload.rationale,
        prior_probability=decision.prior_probability,
        model_probability=decision.model_probability,
        crowd_probability=decision.crowd_probability,
        evidence_ids=evidence_ids,
        model_spec_id=model_spec_id,
        model_run_id=model.id if model else None,
        competition_id=question.competition_id,
    )
    session.add(record)
    record_audit(
        session, user_id=user_id, question_id=question_id, action='decision_recorded',
        entity_type='decision_journal', entity_id=record.id,
        metadata={'human_probability': decision.human_probability, 'evidence_ids': evidence_ids},
    )
    session.commit()
    session.refresh(record)
    return DecisionResponse.model_validate(record)


def list_decisions(session: Session, question_id: str, user_id: str) -> list[DecisionResponse]:
    get_owned_question(session, question_id, user_id)
    from app.audit.models import DecisionJournal
    return [DecisionResponse.model_validate(record) for record in session.scalars(
        select(DecisionJournal).where(
            DecisionJournal.question_id == question_id,
            DecisionJournal.user_id == user_id,
        ).order_by(DecisionJournal.created_at, DecisionJournal.id)
    ).all()]


def list_audit(session: Session, question_id: str, user_id: str) -> list[AuditEvent]:
    get_owned_question(session, question_id, user_id)
    return session.scalars(select(AuditEvent).where(
        AuditEvent.question_id == question_id,
        AuditEvent.user_id == user_id,
    ).order_by(AuditEvent.created_at, AuditEvent.id)).all()

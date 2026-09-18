from copy import deepcopy
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.forecasts.service import get_owned_question
from app.models_lab.models import ModelRun, ModelSpec
from app.models_lab.runners import run_model
from app.models_lab.schemas import ModelRunResponse, ModelSpecCreate, ModelSpecResponse
from app.research.models import Evidence


def validate_evidence_dependencies(session: Session, evidence_ids: list[str], question_id: str, user_id: str) -> None:
    if len(evidence_ids) != len(set(evidence_ids)):
        raise HTTPException(status_code=422, detail='Evidence dependencies must be unique')
    from app.research.models import ResearchItem
    for evidence_id in evidence_ids:
        evidence = session.get(Evidence, evidence_id)
        item = session.get(ResearchItem, evidence.research_item_id) if evidence else None
        if (evidence is None or evidence.decision != 'approved'
                or evidence.user_id != user_id or evidence.question_id != question_id
                or item is None or item.status != 'approved'
                or item.user_id != user_id or item.question_id != question_id):
            raise HTTPException(status_code=404, detail='Evidence dependency not found')

def create_model(session: Session, question_id: str, user_id: str, payload: ModelSpecCreate) -> ModelSpecResponse:
    get_owned_question(session, question_id, user_id)
    validate_evidence_dependencies(session, payload.evidence_ids, question_id, user_id)
    spec = ModelSpec(question_id=question_id, user_id=user_id, **payload.model_dump())
    session.add(spec)
    session.flush()
    from app.audit.service import record_audit
    record_audit(session, user_id=user_id, question_id=question_id, action='model_created',
                 entity_type='model_spec', entity_id=spec.id,
                 metadata={'family': spec.family, 'version': spec.version})
    session.commit()
    return ModelSpecResponse.model_validate(spec)


def create_model_version(session: Session, model_id: str, user_id: str, payload: ModelSpecCreate) -> ModelSpecResponse:
    original = owned_model(session, model_id, user_id)
    if original.status != 'approved':
        raise HTTPException(status_code=409, detail='Only approved models can be versioned')
    validate_evidence_dependencies(session, payload.evidence_ids, original.question_id, user_id)
    root_id = original.source_model_id or original.id
    latest_version = session.scalar(select(func.max(ModelSpec.version)).where(
        ModelSpec.user_id == user_id,
        ModelSpec.question_id == original.question_id,
        (ModelSpec.id == root_id) | (ModelSpec.source_model_id == root_id),
    )) or original.version
    spec = ModelSpec(question_id=original.question_id, user_id=user_id, source_model_id=root_id,
                     version=latest_version + 1, **payload.model_dump())
    session.add(spec); session.commit()
    return ModelSpecResponse.model_validate(spec)

def owned_model(session: Session, model_id: str, user_id: str) -> ModelSpec:
    spec = session.get(ModelSpec, model_id)
    if spec is None or spec.user_id != user_id:
        raise HTTPException(status_code=404, detail='Model not found')
    get_owned_question(session, spec.question_id, user_id)
    return spec

def approve_model(session: Session, model_id: str, user_id: str) -> ModelSpecResponse:
    spec = owned_model(session, model_id, user_id)
    if spec.status == 'draft':
        spec.status = 'approved'
        spec.approved_at = datetime.now(timezone.utc)
        from app.audit.service import record_audit
        record_audit(session, user_id=user_id, question_id=spec.question_id, action='model_approved',
                     entity_type='model_spec', entity_id=spec.id,
                     metadata={'version': spec.version})
        session.commit()
    return ModelSpecResponse.model_validate(spec)


def list_models(session: Session, question_id: str, user_id: str) -> list[ModelSpecResponse]:
    get_owned_question(session, question_id, user_id)
    return [ModelSpecResponse.model_validate(spec) for spec in session.scalars(select(ModelSpec).where(
        ModelSpec.question_id == question_id, ModelSpec.user_id == user_id,
    ).order_by(ModelSpec.created_at, ModelSpec.id)).all()]


def get_model(session: Session, model_id: str, user_id: str) -> ModelSpecResponse:
    return ModelSpecResponse.model_validate(owned_model(session, model_id, user_id))

def run_approved_model(session: Session, model_id: str, user_id: str) -> ModelRunResponse:
    spec = owned_model(session, model_id, user_id)
    if spec.status != 'approved':
        raise HTTPException(status_code=409, detail='Model must be approved before running')
    try:
        validate_evidence_dependencies(session, spec.evidence_ids, spec.question_id, user_id)
        result = run_model({'family': spec.family, 'parameters': spec.parameters})
    except (HTTPException, ValueError) as exc:
        failed_run = ModelRun(
            model_spec_id=spec.id, user_id=user_id, question_id=spec.question_id,
            status='failed', probability=None, inputs=deepcopy(spec.parameters), evidence_ids=deepcopy(spec.evidence_ids),
            model_version=spec.version, spec_snapshot=spec_snapshot(spec))
        session.add(failed_run)
        session.flush()
        from app.audit.service import record_audit
        record_audit(session, user_id=user_id, question_id=spec.question_id, action='model_run_failed',
                     entity_type='model_run', entity_id=failed_run.id, metadata={'model_spec_id': spec.id})
        session.commit()
        raise HTTPException(status_code=422, detail='Model run failed') from None
    run = ModelRun(model_spec_id=spec.id, user_id=user_id, question_id=spec.question_id,
                   probability=result.probability, inputs=deepcopy(spec.parameters), evidence_ids=deepcopy(spec.evidence_ids),
                   model_version=spec.version, spec_snapshot=spec_snapshot(spec))
    session.add(run)
    session.flush()
    from app.audit.service import record_audit
    record_audit(session, user_id=user_id, question_id=spec.question_id, action='model_run_succeeded',
                 entity_type='model_run', entity_id=run.id, metadata={'model_spec_id': spec.id})
    session.commit()
    return ModelRunResponse.model_validate(run)


def spec_snapshot(spec: ModelSpec) -> dict:
    return {'id': spec.id, 'version': spec.version, 'family': spec.family, 'rationale': spec.rationale,
            'parameters': deepcopy(spec.parameters), 'assumptions': deepcopy(spec.assumptions),
            'evidence_ids': deepcopy(spec.evidence_ids), 'source_model_id': spec.source_model_id}

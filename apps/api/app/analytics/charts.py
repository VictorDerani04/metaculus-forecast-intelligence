from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.competitions.models import QuestionSource
from app.forecasts.models import HumanForecast
from app.forecasts.service import get_owned_question
from app.models_lab.models import ModelRun
from app.models_lab.models import ModelSpec
from app.models_lab.runners import run_model
from app.models_lab.service import owned_model
from app.research.service import eligible_evidence


class ProbabilityPoint(BaseModel):
    timestamp: datetime
    probability: float


class ProbabilityHistory(BaseModel):
    model_version: int | None
    generated_at: datetime
    why_this_chart: str
    human: list[ProbabilityPoint]
    model: list[ProbabilityPoint]
    crowd: list[ProbabilityPoint]


class ChartMetadata(BaseModel):
    model_version: int | None
    generated_at: datetime
    why_this_chart: str


class DistributionAnalysis(ChartMetadata):
    available: bool
    probability: float | None
    values: list[float]
    unavailable_reason: str | None


class SensitivityImpact(BaseModel):
    name: str
    baseline: float
    downside: float
    upside: float
    impact: float


class SensitivityAnalysis(ChartMetadata):
    impacts: list[SensitivityImpact]


class ScenarioOutcome(BaseModel):
    name: str
    weight: float
    probability: float


class ScenarioAnalysis(ChartMetadata):
    scenarios: list[ScenarioOutcome]


class EvidenceImpact(BaseModel):
    evidence_id: str
    title: str
    summary: str
    dependency_warning: bool


class EvidenceImpactAnalysis(ChartMetadata):
    evidence: list[EvidenceImpact]


class MapNode(BaseModel):
    id: str
    kind: str
    label: str


class MapEdge(BaseModel):
    source: str
    target: str
    relationship: str


class CausalModelMap(ChartMetadata):
    nodes: list[MapNode]
    edges: list[MapEdge]


class AnalysisResponse(BaseModel):
    probability_history: ProbabilityHistory
    distribution: DistributionAnalysis
    sensitivity: SensitivityAnalysis
    evidence_impact: EvidenceImpactAnalysis
    scenarios: ScenarioAnalysis
    model_map: CausalModelMap


def build_probability_history(
    session: Session, user_id: str, question_id: str,
) -> ProbabilityHistory:
    get_owned_question(session, question_id, user_id)
    human = session.scalars(select(HumanForecast).where(
        HumanForecast.question_id == question_id,
        HumanForecast.user_id == user_id,
    ).order_by(HumanForecast.created_at, HumanForecast.id)).all()
    model = session.scalars(select(ModelRun).where(
        ModelRun.question_id == question_id,
        ModelRun.user_id == user_id,
        ModelRun.status == 'succeeded',
    ).order_by(ModelRun.created_at, ModelRun.id)).all()
    source = session.scalar(select(QuestionSource).where(
        QuestionSource.question_id == question_id,
        QuestionSource.user_id == user_id,
    ))
    latest_version = model[-1].model_version if model else None
    return ProbabilityHistory(
        model_version=latest_version,
        generated_at=datetime.now(timezone.utc),
        why_this_chart='Compare the human, model, and community probability series without combining them.',
        human=[
            ProbabilityPoint(timestamp=item.created_at, probability=item.probability)
            for item in human
        ],
        model=[
            ProbabilityPoint(timestamp=item.created_at, probability=item.probability)
            for item in model
        ],
        crowd=(
            [ProbabilityPoint(timestamp=source.created_at if hasattr(source, 'created_at') else datetime.now(timezone.utc),
                              probability=source.crowd_probability)]
            if source and source.crowd_probability is not None else []
        ),
    )


def _model_context(
    session: Session, model_id: str, user_id: str,
) -> tuple[ModelSpec, ModelRun | None]:
    spec = owned_model(session, model_id, user_id)
    run = session.scalar(select(ModelRun).where(
        ModelRun.model_spec_id == spec.id,
        ModelRun.user_id == user_id,
        ModelRun.question_id == spec.question_id,
        ModelRun.status == 'succeeded',
    ).order_by(ModelRun.created_at.desc(), ModelRun.id.desc()))
    return spec, run


def _metadata(spec: ModelSpec, why: str) -> dict:
    return {
        'model_version': spec.version,
        'generated_at': datetime.now(timezone.utc),
        'why_this_chart': why,
    }


def build_distribution(session: Session, model_id: str, user_id: str) -> DistributionAnalysis:
    spec, run = _model_context(session, model_id, user_id)
    metadata = _metadata(spec, 'Show uncertainty only when the approved runner provides a distribution.')
    if run is None:
        return DistributionAnalysis(
            **metadata, available=False, probability=None, values=[],
            unavailable_reason='No successful model run is available.',
        )
    distribution = run.spec_snapshot.get('distribution')
    if not isinstance(distribution, list):
        return DistributionAnalysis(
            **metadata, available=False, probability=run.probability, values=[],
            unavailable_reason='This model runner does not provide a distribution.',
        )
    return DistributionAnalysis(
        **metadata, available=True, probability=run.probability,
        values=[float(value) for value in distribution], unavailable_reason=None,
    )


def build_sensitivity(session: Session, model_id: str, user_id: str) -> SensitivityAnalysis:
    spec, run = _model_context(session, model_id, user_id)
    metadata = _metadata(spec, 'Compare temporary driver perturbations with the approved model baseline.')
    if run is None or spec.family != 'weighted_driver':
        return SensitivityAnalysis(**metadata, impacts=[])
    drivers = spec.parameters.get('drivers', [])
    baseline = run_model({'family': spec.family, 'parameters': spec.parameters}).probability
    impacts = []
    for index, driver in enumerate(drivers):
        name = str(driver.get('name', f'driver_{index + 1}'))
        changed = [dict(item) for item in drivers]
        for position, value in ((0, 0.0), (1, 1.0)):
            changed[index] = {**changed[index], 'probability': value}
            result = run_model({'family': spec.family, 'parameters': {'drivers': changed}})
            if position == 0:
                downside = result.probability
            else:
                upside = result.probability
        impacts.append(SensitivityImpact(
            name=name, baseline=baseline, downside=downside, upside=upside,
            impact=abs(upside - downside),
        ))
    impacts.sort(key=lambda item: item.impact, reverse=True)
    return SensitivityAnalysis(**metadata, impacts=impacts)


def build_scenario_analysis(session: Session, model_id: str, user_id: str) -> ScenarioAnalysis:
    spec, _ = _model_context(session, model_id, user_id)
    metadata = _metadata(spec, 'Compare explicitly specified scenario outcomes without changing the approved run.')
    if spec.family != 'scenario_tree':
        return ScenarioAnalysis(**metadata, scenarios=[])
    return ScenarioAnalysis(**metadata, scenarios=[
        ScenarioOutcome(
            name=str(item.get('name', f'scenario_{index + 1}')),
            weight=float(item['weight']),
            probability=float(item['probability']),
        )
        for index, item in enumerate(spec.parameters.get('scenarios', []))
    ])


def build_evidence_impact(session: Session, model_id: str, user_id: str) -> EvidenceImpactAnalysis:
    spec, _ = _model_context(session, model_id, user_id)
    metadata = _metadata(spec, 'Show approved evidence provenance and dependency warnings for this model.')
    evidence = eligible_evidence(session, spec.question_id, user_id)
    evidence_by_id = {item.id: item for item in evidence}
    return EvidenceImpactAnalysis(**metadata, evidence=[
        EvidenceImpact(
            evidence_id=item.id, title=item.title, summary=item.summary,
            dependency_warning=any(dependency in evidence_by_id for dependency in item.dependency_evidence_ids),
        )
        for item in evidence if item.id in spec.evidence_ids
    ])


def build_causal_model_map(session: Session, model_id: str, user_id: str) -> CausalModelMap:
    spec, _ = _model_context(session, model_id, user_id)
    metadata = _metadata(spec, 'Show explicit approved evidence-to-question relationships; no causal edges are inferred from text.')
    evidence = eligible_evidence(session, spec.question_id, user_id)
    selected = [item for item in evidence if item.id in spec.evidence_ids]
    outcome_id = f'question:{spec.question_id}'
    return CausalModelMap(
        **metadata,
        nodes=[MapNode(id=outcome_id, kind='outcome', label='Target question')] + [
            MapNode(id=item.id, kind='evidence', label=item.title) for item in selected
        ],
        edges=[
            MapEdge(source=item.id, target=outcome_id, relationship='approved evidence')
            for item in selected
        ],
    )

from datetime import datetime, timezone
from math import ceil

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.competitions.models import Question, QuestionSource
from app.forecasts.models import HumanForecast
from app.models_lab.models import ModelRun
from app.research.models import Evidence, ResearchItem


SIGNAL_NAMES = (
    'deadline_proximity',
    'forecast_staleness',
    'material_evidence',
    'unresolved_alerts',
    'human_crowd_divergence',
    'human_model_divergence',
    'model_uncertainty_sensitivity',
    'research_value',
    'no_initial_forecast',
)


class PriorityComponent(BaseModel):
    name: str
    value: float
    contribution: float


class AttentionPriority(BaseModel):
    score: float
    components: list[PriorityComponent]
    reasons: list[str]


class AttentionQuestion(BaseModel):
    question_id: str
    title: str
    competition_id: str
    priority: AttentionPriority
    human_probability: float | None
    model_probability: float | None
    crowd_probability: float | None
    resolve_at: datetime | None


def _normalized(value: object) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _days_since(value: datetime | None, evaluated_at: datetime) -> float | None:
    if value is None:
        return None
    return max(0.0, (evaluated_at - value).total_seconds() / 86400)


def attention_priority(question_state: dict) -> AttentionPriority:
    evaluated_at = question_state.get('evaluated_at') or datetime.now(timezone.utc)
    resolve_at = question_state.get('resolve_at')
    days_until_resolution = (
        max(0.0, (resolve_at - evaluated_at).total_seconds() / 86400)
        if resolve_at else None
    )
    deadline = 0.0 if days_until_resolution is None else _normalized(
        1 - days_until_resolution / 30
    )
    last_human = question_state.get('last_human_update')
    staleness = 0.0 if last_human is None else _normalized(
        (_days_since(last_human, evaluated_at) or 0) / 30
    )
    human = question_state.get('human_probability')
    crowd = question_state.get('crowd_probability')
    model = question_state.get('model_probability')
    crowd_divergence = 0.0 if human is None or crowd is None else _normalized(abs(human - crowd))
    model_divergence = 0.0 if human is None or model is None else _normalized(abs(human - model))
    values = {
        'deadline_proximity': deadline,
        'forecast_staleness': staleness,
        'material_evidence': _normalized(question_state.get('new_material_evidence', 0) / 3),
        'unresolved_alerts': _normalized(question_state.get('unresolved_alerts', 0) / 3),
        'human_crowd_divergence': crowd_divergence,
        'human_model_divergence': model_divergence,
        'model_uncertainty_sensitivity': _normalized(question_state.get('sensitivity', 0)),
        'research_value': _normalized(question_state.get('research_value', 0)),
        'no_initial_forecast': 1.0 if human is None else 0.0,
    }
    components = [
        PriorityComponent(name=name, value=value, contribution=value / len(values) * 100)
        for name, value in values.items()
    ]
    reasons = []
    if deadline >= 0.5:
        reasons.append('Deadline approaching')
    if staleness >= 0.5:
        reasons.append('Forecast is stale')
    if values['material_evidence'] > 0:
        reasons.append('New material evidence')
    if values['unresolved_alerts'] > 0:
        reasons.append('Unresolved alerts')
    if crowd_divergence >= 0.1:
        reasons.append('Human and crowd probabilities diverge')
    if model_divergence >= 0.1:
        reasons.append('Human and model probabilities diverge')
    if values['model_uncertainty_sensitivity'] > 0:
        reasons.append('Model uncertainty or sensitivity')
    if values['research_value'] > 0:
        reasons.append('Additional research may be valuable')
    if values['no_initial_forecast']:
        reasons.append('No initial human forecast')
    return AttentionPriority(
        score=round(sum(component.contribution for component in components), 4),
        components=components,
        reasons=reasons,
    )


def question_attention(
    session: Session, user_id: str, question_id: str,
    *, evaluated_at: datetime | None = None,
) -> AttentionQuestion:
    from app.forecasts.service import get_owned_question
    question = get_owned_question(session, question_id, user_id)
    source = session.scalar(select(QuestionSource).where(
        QuestionSource.question_id == question_id,
        QuestionSource.user_id == user_id,
    ))
    human = session.scalar(select(HumanForecast).where(
        HumanForecast.question_id == question_id,
        HumanForecast.user_id == user_id,
    ).order_by(HumanForecast.created_at.desc(), HumanForecast.id.desc()))
    model = session.scalar(select(ModelRun).where(
        ModelRun.question_id == question_id,
        ModelRun.user_id == user_id,
        ModelRun.status == 'succeeded',
    ).order_by(ModelRun.created_at.desc(), ModelRun.id.desc()))
    last_human_at = human.created_at if human else None
    latest_evidence = session.scalar(select(Evidence).where(
        Evidence.question_id == question_id,
        Evidence.user_id == user_id,
        Evidence.decision == 'approved',
    ).order_by(Evidence.approved_at.desc(), Evidence.id.desc()))
    candidate_count = session.query(ResearchItem).filter(
        ResearchItem.question_id == question_id,
        ResearchItem.user_id == user_id,
        ResearchItem.status.in_(['candidate', 'deferred']),
    ).count()
    state = {
        'resolve_at': source.resolve_at if source else None,
        'evaluated_at': evaluated_at or datetime.now(timezone.utc),
        'last_human_update': last_human_at,
        'human_probability': human.probability if human else None,
        'model_probability': model.probability if model else None,
        'crowd_probability': source.crowd_probability if source else None,
        'new_material_evidence': 1 if latest_evidence and (
            last_human_at is None or latest_evidence.approved_at > last_human_at
        ) else 0,
        'unresolved_alerts': candidate_count,
        'sensitivity': 0,
        'research_value': 1 if candidate_count else 0,
    }
    return AttentionQuestion(
        question_id=question.id,
        title=question.title,
        competition_id=question.competition_id,
        priority=attention_priority(state),
        human_probability=state['human_probability'],
        model_probability=state['model_probability'],
        crowd_probability=state['crowd_probability'],
        resolve_at=state['resolve_at'],
    )


def list_attention_questions(
    session: Session, user_id: str, *, evaluated_at: datetime | None = None,
) -> list[AttentionQuestion]:
    from app.competitions.models import Competition
    questions = session.scalars(select(Question).join(Competition).where(
        Competition.user_id == user_id,
    )).all()
    result = [
        question_attention(session, user_id, question.id, evaluated_at=evaluated_at)
        for question in questions
    ]
    return sorted(result, key=lambda item: (-item.priority.score, item.question_id))

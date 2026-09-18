from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.auth.models import User
from app.auth.routes import get_current_user
from app.analytics.charts import (
    AnalysisResponse,
    build_causal_model_map,
    build_distribution,
    build_evidence_impact,
    build_probability_history,
    build_scenario_analysis,
    build_sensitivity,
)
from app.forecasts.service import get_owned_question
from app.models_lab.service import owned_model


router = APIRouter(tags=['analytics'])


@router.get(
    '/questions/{question_id}/analysis/{model_id}',
    response_model=AnalysisResponse,
)
def analysis(
    question_id: str,
    model_id: str,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    with request.app.state.session_factory() as session:
        get_owned_question(session, question_id, user.id)
        model = owned_model(session, model_id, user.id)
        if model.question_id != question_id:
            get_owned_question(session, 'missing-question', user.id)
        return AnalysisResponse(
            probability_history=build_probability_history(session, user.id, question_id),
            distribution=build_distribution(session, model_id, user.id),
            sensitivity=build_sensitivity(session, model_id, user.id),
            evidence_impact=build_evidence_impact(session, model_id, user.id),
            scenarios=build_scenario_analysis(session, model_id, user.id),
            model_map=build_causal_model_map(session, model_id, user.id),
        )

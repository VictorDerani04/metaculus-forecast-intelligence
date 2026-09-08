from typing import Protocol

from sqlalchemy.orm import Session

from app.competitions.models import Question, QuestionSource
from app.competitions.schemas import ImportedQuestionResponse, ManualQuestionDetails
from app.integrations.metaculus.parser import parse_metaculus_url
from app.integrations.metaculus.schemas import MetaculusQuestionData


class QuestionProvider(Protocol):
    def fetch_post(self, post_id: int) -> MetaculusQuestionData: ...


def import_question(
    session: Session,
    *,
    competition_id: str,
    user_id: str,
    url: str,
    provider: QuestionProvider,
    manual_details: ManualQuestionDetails | None = None,
) -> ImportedQuestionResponse:
    post_id = parse_metaculus_url(url)
    data = (
        MetaculusQuestionData(**manual_details.model_dump())
        if manual_details else provider.fetch_post(post_id)
    )
    has_metadata = all((
        data.title, data.resolution_criteria, data.question_type,
        data.close_at, data.resolve_at,
    ))
    import_status = 'imported' if has_metadata else 'partial'
    question = Question(
        competition_id=competition_id,
        title=data.title or f'Metaculus question {post_id}',
    )
    session.add(question)
    session.flush()
    source = QuestionSource(
        question_id=question.id,
        user_id=user_id,
        source_post_id=post_id,
        source_url=f'https://www.metaculus.com/questions/{post_id}/',
        import_status='manual' if manual_details else import_status,
        **data.model_dump(exclude={'title'}),
    )
    session.add(source)
    session.flush()
    result = ImportedQuestionResponse(
        id=question.id,
        competition_id=competition_id,
        title=question.title,
        source_post_id=post_id,
        source_url=source.source_url,
        import_status=source.import_status,
        **data.model_dump(exclude={'title', 'source_payload'}),
    )
    session.commit()
    return result

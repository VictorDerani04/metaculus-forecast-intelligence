"""Runtime-only PostgreSQL proof for the queue's SKIP LOCKED claim behavior."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest


POSTGRES_URL = os.getenv('POSTGRES_TEST_DATABASE_URL', '')
pytestmark = pytest.mark.skipif(not POSTGRES_URL.startswith('postgresql'), reason='set POSTGRES_TEST_DATABASE_URL to run PostgreSQL runtime verification')


def test_postgresql_concurrent_claimers_claim_distinct_jobs():
    # app.main is the authoritative composition root: its explicit domain imports
    # register the complete metadata graph before schema creation.
    from app import main as application
    from app.auth.models import User
    from app.db.base import Base
    from app.db.session import build_session_factory
    from app.jobs.models import BackgroundJob
    from app.jobs.service import claim_next_job

    assert application.competition_models.Question.__tablename__ == 'questions'
    engine, session_factory = build_session_factory(POSTGRES_URL)
    Base.metadata.create_all(engine)
    unique = f'postgres-claim-{datetime.now(timezone.utc).timestamp()}'
    with session_factory.begin() as session:
        user = User(email=f'{unique}@example.test', password_hash='not-a-password')
        session.add(user); session.flush()
        session.add_all([
            BackgroundJob(user_id=user.id, question_id=None, job_type='runtime_probe', payload_json={}, idempotency_key=f'{unique}-one', scheduled_for=datetime.now(timezone.utc)),
            BackgroundJob(user_id=user.id, question_id=None, job_type='runtime_probe', payload_json={}, idempotency_key=f'{unique}-two', scheduled_for=datetime.now(timezone.utc)),
        ])
    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(pool.map(lambda _: claim_next_job(session_factory, job_types=('runtime_probe',)), range(2)))
    assert all(claimed)
    assert len({job.id for job in claimed}) == 2


def test_postgresql_event_cluster_schema_enforces_owner_and_question_scope():
    from sqlalchemy import inspect
    from app.main import create_app

    app = create_app(
        database_url=POSTGRES_URL,
        session_secret='postgres-source-intelligence-test',
        seed_user=False,
    )
    inspector = inspect(app.state.engine)
    foreign_key_columns = {
        tuple(sorted(foreign_key['constrained_columns']))
        for foreign_key in inspector.get_foreign_keys('finding_event_links')
    }
    assert ('finding_id', 'question_id', 'user_id') in foreign_key_columns
    assert ('event_cluster_id', 'question_id', 'user_id') in foreign_key_columns

# Stage 2 Task 1: Monitoring Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the safe, persistent monitoring infrastructure required for Stage 2 Task 1 without implementing external research processing or consequential forecasting actions.

**Architecture:** Add a focused `monitoring` domain for configurations, runs, provider contracts, scheduling, and HTTP routes, plus a generic `jobs` domain for persistent job state and claim logic. The FastAPI application supplies a fixed, application-controlled provider registry; a scheduler only enqueues idempotent jobs, while a worker claims and executes them outside long database transactions. A small client panel consumes only monitoring status and history APIs.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Pydantic, pytest, SQLite test database, PostgreSQL-compatible SQLAlchemy query path, Next.js, React, TypeScript, Vitest, React Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-20-stage-2-autonomous-monitoring-architecture.md`

## Global Constraints

- Implement Stage 2 Task 1 only; do not add real web/news providers, findings, deduplication, classifiers, candidates, alerts, digests, notification delivery, adaptive scheduling, or automatic Metaculus refresh.
- Keep Stage 2 a modular monolith; do not add Redis, Celery, or a microservice split.
- Persist jobs in PostgreSQL-compatible tables and isolate PostgreSQL `FOR UPDATE SKIP LOCKED` logic from deterministic SQLite tests.
- Monitoring is explicitly user-enabled per owned question; no question is monitored merely because it exists.
- Every monitoring-owned record must be user-scoped; cross-user and cross-question access returns the existing not-found semantics.
- Provider registration is allowlisted in application code. External text/data is never executable or application instruction.
- Providers and workers cannot approve evidence, mutate Human Final Forecasts, mutate/run ModelSpecs, write DecisionJournal entries, or submit forecasts to Metaculus.
- Do not hold database transactions open during provider execution.
- Audit only explicit enable, disable, and manual-run actions; operational execution is represented by `MonitoringRun` and `BackgroundJob`.
- Use `py`, `npm.cmd`, and `npx.cmd` on Windows. Do not track generated artifacts or local databases.
- Do not commit, push, merge, rebase, reset, clean, or stage changes. Leave Task 1 work unstaged for review.

## Review Focus

- A second scheduler invocation racing the first must not enqueue another active job for the same config and schedule window; Task 3 pins this with a unique idempotency key and repeated invocation test.
- A provider exception containing secret-like text must not store that raw text in a job or run error; Task 4 pins safe error-code/message mapping.
- A worker retry after a provider failure must update `last_run_at` but only update `last_success_at` after a later success; Task 4 pins both timestamps.
- A user who owns neither the question nor its config must not read status/history, enable/disable, or enqueue manual work; Task 5 pins each endpoint.
- A PostgreSQL dialect must use the `SKIP LOCKED` claim query while SQLite retains a deterministic atomic fallback; Task 2 pins generated statements/claim behavior without claiming live PostgreSQL concurrency verification.

---

## File Structure

- `apps/api/app/jobs/models.py` — `BackgroundJob` persistence model, lifecycle constants, idempotency key, and timestamps.
- `apps/api/app/jobs/service.py` — enqueue, safe transition, retry-ready failure, and dialect-specific job claim functions.
- `apps/api/app/monitoring/models.py` — `MonitoringConfig` and `MonitoringRun` persistence models, indexes, and constraints.
- `apps/api/app/monitoring/schemas.py` — validated configuration input and API response contracts.
- `apps/api/app/monitoring/providers/base.py` — typed question context, provider result, and provider protocol.
- `apps/api/app/monitoring/providers/fake.py` — deterministic fake provider used only by tests and injected application test state.
- `apps/api/app/monitoring/service.py` — owned config/status/history, enable/disable/manual enqueue, and audit integration.
- `apps/api/app/monitoring/scheduler.py` — due-config selection and idempotent monitor-job enqueueing.
- `apps/api/app/monitoring/worker.py` — claim-one orchestration, short transaction boundaries, provider execution, and run/config/job completion.
- `apps/api/app/monitoring/routes.py` — question-scoped monitoring endpoints.
- `apps/api/app/main.py` — module imports/router registration and fixed provider-registry default.
- `apps/api/tests/test_monitoring.py` — backend model, scheduler, worker, ownership, safety, and API coverage.
- `apps/web/lib/api.ts` — monitoring client types and endpoint calls.
- `apps/web/components/monitoring-panel.tsx` — minimal Forecast Room monitoring panel.
- `apps/web/components/forecast-room.tsx` — renders the panel without redesigning the room.
- `apps/web/tests/monitoring-panel.test.tsx` — panel behavior and client integration tests.

### Task 1: Persistent monitoring and job models

**Files:**
- Create: `apps/api/app/jobs/__init__.py`
- Create: `apps/api/app/jobs/models.py`
- Create: `apps/api/app/monitoring/__init__.py`
- Create: `apps/api/app/monitoring/models.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_monitoring.py`

**Interfaces:**
- Produces `BackgroundJob(user_id, job_type, question_id, payload_json, idempotency_key, status, attempt_count, max_attempts, scheduled_for, started_at, finished_at, last_error_code, last_error_message)`.
- Produces `MonitoringConfig(user_id, question_id, enabled, metaculus_refresh_enabled, web_monitoring_enabled, news_monitoring_enabled, monitoring_interval_minutes, materiality_threshold, digest_threshold, last_run_at, last_success_at, next_run_at)`.
- Produces `MonitoringRun(user_id, question_id, job_id, status, provider/counter fields, safe_error_summary)`.
- Consumes the existing `Base` metadata and `Question`/`User` foreign keys.

- [ ] **Step 1: Write failing persistence and constraint tests**

```python
def test_monitoring_config_is_unique_per_owned_question(session, user, question):
    session.add_all([
        MonitoringConfig(user_id=user.id, question_id=question.id),
        MonitoringConfig(user_id=user.id, question_id=question.id),
    ])
    with pytest.raises(IntegrityError):
        session.commit()

def test_background_job_defaults_to_queued_with_retry_ready_fields(session, user, question):
    job = BackgroundJob(user_id=user.id, question_id=question.id,
                        job_type='monitor_question', payload_json={'config_id': 'c'},
                        idempotency_key='config:c:window:2026-09-20T12:00:00Z')
    session.add(job); session.commit()
    assert (job.status, job.attempt_count, job.max_attempts) == ('queued', 0, 3)
```

- [ ] **Step 2: Run the focused tests to verify RED**

Run: `py -m pytest apps/api/tests/test_monitoring.py -k "unique or defaults" -v`

Expected: FAIL because monitoring and jobs modules do not yet exist.

- [ ] **Step 3: Implement the minimal SQLAlchemy models**

```python
class BackgroundJob(Base):
    __tablename__ = 'background_jobs'
    __table_args__ = (UniqueConstraint('idempotency_key', name='uq_background_jobs_idempotency_key'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    question_id: Mapped[str | None] = mapped_column(ForeignKey('questions.id'), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='queued', nullable=False)

class MonitoringConfig(Base):
    __tablename__ = 'monitoring_configs'
    __table_args__ = (UniqueConstraint('user_id', 'question_id', name='uq_monitoring_config_user_question'),)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey('questions.id'), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    monitoring_interval_minutes: Mapped[int] = mapped_column(Integer, default=360, nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Import the models before `Base.metadata.create_all()` in `create_app`, exactly as the existing domain model imports do. Give `MonitoringRun` all specified counters with zero defaults; do not add finding records.

- [ ] **Step 4: Run model tests to verify GREEN**

Run: `py -m pytest apps/api/tests/test_monitoring.py -k "unique or defaults" -v`

Expected: PASS.

- [ ] **Step 5: Extend RED coverage for lifecycle and validation boundaries**

```python
def test_monitoring_config_rejects_invalid_interval_and_thresholds(client, question_id):
    assert client.post(f'/questions/{question_id}/monitoring/enable', json={
        'monitoring_interval_minutes': 0, 'materiality_threshold': 1.1,
    }).status_code == 422

def test_monitoring_run_has_zero_task_one_finding_counters(session, run):
    assert run.raw_items_seen == run.normalized_findings == run.candidates_created == 0
```

- [ ] **Step 6: Implement only model-level defaults needed by the tests**

Use positive interval and inclusive `0.0..1.0` threshold validation in a later schema; retain zero counters and nullable safe error fields in the model.

- [ ] **Step 7: Run the focused model suite**

Run: `py -m pytest apps/api/tests/test_monitoring.py -k "unique or defaults or invalid or counters" -v`

Expected: PASS.

- [ ] **Step 8: Leave changes unstaged**

Run: `git status --short`

Expected: only the new monitoring/job source and test files plus this implementation plan; do not run `git add` or `git commit`.

### Task 2: Job repository and typed provider boundary

**Files:**
- Create: `apps/api/app/jobs/service.py`
- Create: `apps/api/app/monitoring/providers/__init__.py`
- Create: `apps/api/app/monitoring/providers/base.py`
- Create: `apps/api/app/monitoring/providers/fake.py`
- Test: `apps/api/tests/test_monitoring.py`

**Interfaces:**
- Consumes `BackgroundJob` from Task 1.
- Produces `enqueue_job(session, *, user_id: str, question_id: str, job_type: str, payload_json: dict, scheduled_for: datetime, idempotency_key: str) -> BackgroundJob`.
- Produces `claim_next_job(session_factory) -> ClaimedJob | None`; PostgreSQL path queries queued/retry-wait due jobs with `with_for_update(skip_locked=True)`, while SQLite uses deterministic conditional state transition.
- Produces `QuestionContext(question_id: str, title: str, resolution_criteria: str | None)` and `ProviderResult(items: list[dict], next_cursor: str | None, rate_limit_metadata: dict, provider_metadata: dict)`.
- Produces `MonitoringProvider` protocol with `provider_name` and `fetch(question: QuestionContext, cursor: None) -> ProviderResult`.

- [ ] **Step 1: Write failing claim and provider substitution tests**

```python
def test_claim_next_job_marks_one_due_job_running(session_factory, queued_job):
    claimed = claim_next_job(session_factory)
    assert claimed and claimed.status == 'running'
    assert claimed.attempt_count == 1

def test_fake_provider_can_return_result_or_raise():
    assert FakeMonitoringProvider(items=[{'title': 'fixture'}]).fetch(CONTEXT, None).items
    with pytest.raises(ProviderFailure):
        FakeMonitoringProvider(error_code='provider_unavailable').fetch(CONTEXT, None)
```

- [ ] **Step 2: Run focused tests to verify RED**

Run: `py -m pytest apps/api/tests/test_monitoring.py -k "claim_next_job or fake_provider" -v`

Expected: FAIL because the repository functions and provider contract do not exist.

- [ ] **Step 3: Implement narrow repository and provider contracts**

```python
def claim_next_job(session_factory: sessionmaker) -> BackgroundJob | None:
    with session_factory.begin() as session:
        query = select(BackgroundJob).where(
            BackgroundJob.status.in_(['queued', 'retry_wait']),
            BackgroundJob.scheduled_for <= utcnow(),
        ).order_by(BackgroundJob.scheduled_for, BackgroundJob.created_at).limit(1)
        if session.bind.dialect.name == 'postgresql':
            query = query.with_for_update(skip_locked=True)
        job = session.scalar(query)
        if job is not None:
            job.status, job.started_at, job.attempt_count = 'running', utcnow(), job.attempt_count + 1
        return job
```

For SQLite, make selection and transition in one short transaction and document that this is deterministic test behavior, not PostgreSQL concurrency verification. `FakeMonitoringProvider` must be test-only and return fixed data or raise a typed `ProviderFailure`; it must not fetch the network.

- [ ] **Step 4: Run claim/provider tests to verify GREEN**

Run: `py -m pytest apps/api/tests/test_monitoring.py -k "claim_next_job or fake_provider" -v`

Expected: PASS.

- [ ] **Step 5: Add RED coverage for retry eligibility and PostgreSQL query readiness**

```python
def test_cancelled_and_future_jobs_are_not_claimed(session_factory, cancelled_job, future_job):
    assert claim_next_job(session_factory) is None

def test_postgresql_claim_statement_uses_skip_locked(postgres_bound_session):
    from sqlalchemy.dialects import postgresql
    statement = build_claim_query('postgresql', now=datetime(2026, 9, 20, tzinfo=timezone.utc))
    assert 'FOR UPDATE SKIP LOCKED' in str(statement.compile(dialect=postgresql.dialect()))
```

- [ ] **Step 6: Implement retry eligibility and a testable claim-query builder**

Keep raw SQL out of business services. Factor `build_claim_query(dialect_name, now)` so the PostgreSQL test compiles a query without connecting to a running PostgreSQL instance.

- [ ] **Step 7: Run focused repository tests**

Run: `py -m pytest apps/api/tests/test_monitoring.py -k "claim or provider" -v`

Expected: PASS.

- [ ] **Step 8: Leave changes unstaged**

Run: `git diff --check`

Expected: no whitespace errors; do not stage or commit.

### Task 3: Configuration service and idempotent scheduler

**Files:**
- Create: `apps/api/app/monitoring/schemas.py`
- Create: `apps/api/app/monitoring/service.py`
- Create: `apps/api/app/monitoring/scheduler.py`
- Test: `apps/api/tests/test_monitoring.py`

**Interfaces:**
- Consumes Tasks 1–2 models and `enqueue_job`.
- Produces `enable_monitoring(session, *, user_id: str, question_id: str, settings: MonitoringEnable) -> MonitoringConfig`.
- Produces `disable_monitoring(session, *, user_id: str, question_id: str) -> MonitoringConfig`.
- Produces `enqueue_manual_run(session, *, user_id: str, question_id: str) -> BackgroundJob`.
- Produces `enqueue_due_monitoring_jobs(session, now: datetime) -> list[BackgroundJob]`.
- Produces response schemas `MonitoringStatusResponse`, `MonitoringRunResponse`, and validated `MonitoringEnable`.

- [ ] **Step 1: Write failing config and scheduler tests**

```python
def test_enable_creates_explicit_config_and_manual_run_enqueues_job(session, user, question):
    config = enable_monitoring(session, user_id=user.id, question_id=question.id, settings=MonitoringEnable())
    job = enqueue_manual_run(session, user_id=user.id, question_id=question.id)
    assert config.enabled and job.job_type == 'monitor_question'

def test_scheduler_enqueues_once_for_due_enabled_config(session, due_config, now):
    assert len(enqueue_due_monitoring_jobs(session, now)) == 1
    assert enqueue_due_monitoring_jobs(session, now) == []
```

- [ ] **Step 2: Run config/scheduler tests to verify RED**

Run: `py -m pytest apps/api/tests/test_monitoring.py -k "enable or scheduler" -v`

Expected: FAIL because configuration and scheduler services do not exist.

- [ ] **Step 3: Implement owned configuration service and deterministic scheduling**

```python
def schedule_key(config_id: str, scheduled_for: datetime) -> str:
    return f'monitor_question:{config_id}:{scheduled_for.astimezone(timezone.utc).isoformat()}'

def enqueue_due_monitoring_jobs(session: Session, now: datetime) -> list[BackgroundJob]:
    configs = session.scalars(select(MonitoringConfig).where(
        MonitoringConfig.enabled.is_(True), MonitoringConfig.next_run_at <= now,
    )).all()
    return [enqueue_job(
        session, user_id=config.user_id, question_id=config.question_id,
        job_type='monitor_question', payload_json={'config_id': config.id},
        scheduled_for=config.next_run_at, idempotency_key=schedule_key(config.id, config.next_run_at),
    ) for config in configs]
```

Call existing `get_owned_question` before configuration reads/writes. Set the first `next_run_at` on explicit enable; update it only after a worker cycle. Catch the unique idempotency constraint in `enqueue_job` and return the existing job rather than making a duplicate.

- [ ] **Step 4: Run config/scheduler tests to verify GREEN**

Run: `py -m pytest apps/api/tests/test_monitoring.py -k "enable or scheduler" -v`

Expected: PASS.

- [ ] **Step 5: Add RED coverage for disabled/not-due and manual idempotency**

```python
def test_scheduler_ignores_disabled_and_not_due_configs(session, disabled_config, future_config, now):
    assert enqueue_due_monitoring_jobs(session, now) == []

def test_repeated_manual_run_reuses_active_job(session, user, question):
    assert enqueue_manual_run(session, user_id=user.id, question_id=question.id).id == \
           enqueue_manual_run(session, user_id=user.id, question_id=question.id).id
```

- [ ] **Step 6: Implement only the required active-job/manual idempotency policy**

Use a manual idempotency key based on config ID plus a stable active-run marker; once the job is terminal, a subsequent explicit manual run receives a new UUID-backed key. Do not implement adaptive scheduling.

- [ ] **Step 7: Run focused scheduler suite**

Run: `py -m pytest apps/api/tests/test_monitoring.py -k "scheduler or manual" -v`

Expected: PASS.

- [ ] **Step 8: Leave changes unstaged**

Run: `git status --short`

Expected: Task 1 source/tests/plan only; do not stage or commit.

### Task 4: Worker execution and safe failure lifecycle

**Files:**
- Create: `apps/api/app/monitoring/worker.py`
- Modify: `apps/api/app/jobs/service.py`
- Modify: `apps/api/app/monitoring/service.py`
- Test: `apps/api/tests/test_monitoring.py`

**Interfaces:**
- Consumes `claim_next_job`, `MonitoringProvider`, `MonitoringConfig`, `MonitoringRun`, and `QuestionContext`.
- Produces `run_one_monitoring_job(session_factory, providers: Mapping[str, MonitoringProvider]) -> str | None`.
- Produces terminal job status `succeeded` or `retry_wait`/`failed`, completed run status, safe counters, config last-run timestamps, and a next due time.

- [ ] **Step 1: Write failing worker success and safety tests**

```python
def test_worker_claims_job_invokes_provider_and_records_success(app, queued_job, fake_provider):
    assert run_one_monitoring_job(app.state.session_factory, {'fake': fake_provider}) == queued_job.id
    run = load_run(app, queued_job.id)
    assert (run.status, run.providers_attempted, run.providers_succeeded) == ('succeeded', 1, 1)
    assert load_job(app, queued_job.id).status == 'succeeded'

def test_worker_does_not_mutate_consequential_domain_records(app, queued_job, fake_provider):
    run_one_monitoring_job(app.state.session_factory, {'fake': fake_provider})
    assert counts(app, HumanForecast, Evidence, ModelSpec, ModelRun, DecisionJournal) == (0, 0, 0, 0, 0)
```

- [ ] **Step 2: Run worker success tests to verify RED**

Run: `py -m pytest apps/api/tests/test_monitoring.py -k "worker and success or consequential" -v`

Expected: FAIL because worker orchestration does not exist.

- [ ] **Step 3: Implement short-transaction worker orchestration**

```python
def run_one_monitoring_job(session_factory, providers):
    job = claim_next_job(session_factory)                 # commits running state
    if job is None: return None
    run_id, context, enabled_names = start_run_and_load_context(session_factory, job.id)
    outcomes = [provider.fetch(context, None) for name, provider in allowlisted(providers, enabled_names)]
    finish_success(session_factory, job.id, run_id, outcomes)  # short persistence transaction
    return job.id
```

The provider selection is derived solely from enabled config flags and the fixed registry keys, not job payload or provider-returned data. Count successful providers and raw items but leave all Task 2/3 counters at zero. Do not retain provider items.

- [ ] **Step 4: Run worker success tests to verify GREEN**

Run: `py -m pytest apps/api/tests/test_monitoring.py -k "worker and success or consequential" -v`

Expected: PASS.

- [ ] **Step 5: Write failing error and retry timestamp tests**

```python
def test_provider_failure_records_safe_retry_state_and_no_raw_secret(app, queued_job):
    run_one_monitoring_job(app.state.session_factory, {'fake': FakeMonitoringProvider(error_message='token=secret')})
    assert load_job(app, queued_job.id).status == 'retry_wait'
    assert 'secret' not in (load_job(app, queued_job.id).last_error_message or '')

def test_last_success_changes_only_after_successful_provider_cycle(app, queued_job):
    run_one_monitoring_job(app.state.session_factory, {'fake': FakeMonitoringProvider(error_code='provider_unavailable')})
    failed_config = load_config(app, queued_job.question_id)
    assert failed_config.last_run_at is not None and failed_config.last_success_at is None
    make_job_retry_due(app, queued_job.id)
    run_one_monitoring_job(app.state.session_factory, {'fake': FakeMonitoringProvider(items=[])})
    succeeded_config = load_config(app, queued_job.question_id)
    assert succeeded_config.last_success_at is not None
```

- [ ] **Step 6: Implement typed safe failures and retry-ready transitions**

Map `ProviderFailure`, malformed payload, missing config/question, and unknown exception to fixed safe codes/messages. Increment attempts; if below `max_attempts`, set `retry_wait` and `scheduled_for` to a small fixed retry delay, otherwise set `failed`. Always set `last_run_at`; set `last_success_at` and advance `next_run_at` only on success.

- [ ] **Step 7: Run focused worker suite**

Run: `py -m pytest apps/api/tests/test_monitoring.py -k "worker or provider_failure or last_success" -v`

Expected: PASS.

- [ ] **Step 8: Leave changes unstaged**

Run: `git diff --check`

Expected: no whitespace errors; do not stage or commit.

### Task 5: Monitoring HTTP API, audit actions, and backend ownership coverage

**Files:**
- Create: `apps/api/app/monitoring/routes.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/monitoring/service.py`
- Test: `apps/api/tests/test_monitoring.py`

**Interfaces:**
- Produces `GET /questions/{id}/monitoring`, `POST /questions/{id}/monitoring/enable`, `POST /questions/{id}/monitoring/disable`, `POST /questions/{id}/monitoring/run`, and `GET /questions/{id}/monitoring/runs`.
- Consumes authenticated `User`, request session factory, and monitoring service functions.
- Produces audit action names `monitoring_enabled`, `monitoring_disabled`, and `monitoring_manual_run` only for explicit human requests.

- [ ] **Step 1: Write failing endpoint and audit tests**

```python
def test_monitoring_api_enable_status_disable_and_manual_enqueue(client, question_id):
    assert client.post(f'/questions/{question_id}/monitoring/enable', json={}).status_code == 200
    assert client.get(f'/questions/{question_id}/monitoring').json()['enabled'] is True
    assert client.post(f'/questions/{question_id}/monitoring/run').status_code == 202
    assert client.post(f'/questions/{question_id}/monitoring/disable').json()['enabled'] is False

def test_other_user_cannot_read_or_mutate_monitoring(client_as_other, question_id):
    for method, path in [('get', 'monitoring'), ('post', 'monitoring/enable'), ('post', 'monitoring/run'), ('get', 'monitoring/runs')]:
        assert getattr(client_as_other, method)(f'/questions/{question_id}/{path}', json={} if method == 'post' else None).status_code == 404
```

- [ ] **Step 2: Run API tests to verify RED**

Run: `py -m pytest apps/api/tests/test_monitoring.py -k "monitoring_api or other_user" -v`

Expected: FAIL with endpoint not found.

- [ ] **Step 3: Implement routes and minimal service response mapping**

```python
@router.post('/{question_id}/monitoring/run', status_code=202)
def monitor_now(question_id: str, request: Request, user: CurrentUser):
    with request.app.state.session_factory() as session:
        job = enqueue_manual_run(session, user_id=user.id, question_id=question_id)
        record_audit(session, user_id=user.id, question_id=question_id,
                     action='monitoring_manual_run', entity_type='background_job', entity_id=job.id)
        session.commit()
        return {'job_id': job.id, 'status': job.status}
```

Use `get_owned_question` before each route action and order runs newest-first. Return nullable timestamps and the latest safe error exactly as stored; do not expose payloads or raw exception messages.

- [ ] **Step 4: Run API/audit tests to verify GREEN**

Run: `py -m pytest apps/api/tests/test_monitoring.py -k "monitoring_api or other_user or audit" -v`

Expected: PASS.

- [ ] **Step 5: Add RED coverage for run-history isolation and disabled manual behavior**

```python
def test_other_user_cannot_read_run_history(client_as_other, question_id):
    assert client_as_other.get(f'/questions/{question_id}/monitoring/runs').status_code == 404

def test_manual_run_requires_explicitly_enabled_monitoring(client, question_id):
    assert client.post(f'/questions/{question_id}/monitoring/run').status_code == 409
```

- [ ] **Step 6: Implement only documented status/error semantics**

Use a stable 409 detail for a disabled/missing configuration; do not implicitly enable it. Confirm audit history contains only explicit actions and no worker-created audit event.

- [ ] **Step 7: Run all monitoring backend tests**

Run: `py -m pytest apps/api/tests/test_monitoring.py -v`

Expected: PASS.

- [ ] **Step 8: Leave changes unstaged**

Run: `git status --short`

Expected: Task 1 source/tests/plan files only; do not stage or commit.

### Task 6: Forecast Room monitoring panel and frontend client coverage

**Files:**
- Modify: `apps/web/lib/api.ts`
- Create: `apps/web/components/monitoring-panel.tsx`
- Modify: `apps/web/components/forecast-room.tsx`
- Create: `apps/web/tests/monitoring-panel.test.tsx`

**Interfaces:**
- Consumes `MonitoringStatus` and `MonitoringRun` API responses.
- Produces `getMonitoring(questionId)`, `enableMonitoring(questionId, settings)`, `disableMonitoring(questionId)`, `monitorNow(questionId)`, and `getMonitoringRuns(questionId)`.
- Produces `<MonitoringPanel questionId={questionId} />`, displaying status, last/next check, latest run/safe error, and enable/disable/manual controls.

- [ ] **Step 1: Write failing disabled/never-run panel test**

```tsx
it('shows a truthful disabled, never-run state and enables monitoring', async () => {
  mockFetchMonitoring({enabled: false, last_run_at: null, next_run_at: null, latest_run: null});
  render(<MonitoringPanel questionId="q1" />);
  expect(await screen.findByText('Monitoring is disabled')).toBeInTheDocument();
  expect(screen.getByText('Never checked')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: 'Enable monitoring'}));
  expect(await screen.findByText('Monitoring is enabled')).toBeInTheDocument();
});
```

- [ ] **Step 2: Run panel test to verify RED**

Run: `npm.cmd test -- --run tests/monitoring-panel.test.tsx`

Expected: FAIL because the panel and API client functions do not exist.

- [ ] **Step 3: Implement typed client calls and minimal panel**

```tsx
export function MonitoringPanel({questionId}: {questionId: string}) {
  const [status, setStatus] = useState<MonitoringStatus | null>(null);
  const [pending, setPending] = useState<'enable' | 'disable' | 'run' | null>(null);
  // load status; render truthful empty/loading/error states; reload after a successful action
}
```

Match existing `fetch` credentials and error handling. Disable all action controls during an in-flight action, preserve the prior visible state on API failure, and show a retryable safe error. Add the panel alongside existing Forecast Room sections without changing their ordering or behavior.

- [ ] **Step 4: Run panel test to verify GREEN**

Run: `npm.cmd test -- --run tests/monitoring-panel.test.tsx`

Expected: PASS.

- [ ] **Step 5: Add RED coverage for enabled/latest-run/error/pending states**

```tsx
it('shows latest run and safe error and blocks duplicate monitor-now requests', async () => {
  mockFetchMonitoring({enabled: true, last_run_at: '2026-09-20T12:00:00Z',
    next_run_at: '2026-09-20T13:00:00Z', latest_run: {status: 'retry_wait', safe_error_summary: 'Provider unavailable'}});
  render(<MonitoringPanel questionId="q1" />);
  expect(await screen.findByText('Provider unavailable')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: 'Monitor now'}));
  expect(screen.getByRole('button', {name: 'Monitoring…'})).toBeDisabled();
});
```

- [ ] **Step 6: Implement action transitions and testable formatting**

Render ISO timestamps in a consistent readable form, distinguish queued manual work from completed run state, and make failed API actions retryable. Do not render findings, alerts, or digests.

- [ ] **Step 7: Run the monitoring frontend suite**

Run: `npm.cmd test -- --run tests/monitoring-panel.test.tsx`

Expected: PASS.

- [ ] **Step 8: Leave changes unstaged**

Run: `git diff --check`

Expected: no whitespace errors; do not stage or commit.

### Task 7: Regression, security pass, and final verification

**Files:**
- Modify only if a regression test exposes a Task 1 defect; otherwise no source changes.
- Test: backend, frontend, typecheck, build, and existing Playwright suite.

**Interfaces:**
- Consumes all Task 1 APIs and UI.
- Produces verification evidence only; no PostgreSQL live-concurrency claim without a running PostgreSQL verification environment.

- [ ] **Step 1: Run all backend tests**

Run: `py -m pytest`

Expected: PASS; record the collected/pass count and fix only Task 1 regressions with a new focused RED test first.

- [ ] **Step 2: Run all frontend tests**

Run: `npm.cmd test`

Expected: PASS; record the test count/files.

- [ ] **Step 3: Run type checking and production build**

Run: `npm.cmd run typecheck`

Expected: PASS.

Run: `npm.cmd run build`

Expected: PASS.

- [ ] **Step 4: Run existing Private Core end-to-end acceptance**

Run: `npm.cmd run e2e`

Expected: PASS. If the repository uses a different script, run its established Playwright command with `npx.cmd`.

- [ ] **Step 5: Perform a focused security/scope inspection**

Run: `rg -n "eval\(|exec\(|subprocess|os\.system|importlib|requests\.|httpx\.|Evidence\(|HumanForecast\(|ModelRun\(|DecisionJournal\(" apps/api/app/jobs apps/api/app/monitoring`

Expected: no executable/provider-controlled behavior, no network provider, and no consequential-domain mutation from the new modules. Inspect error mapping to confirm payloads/raw exception text are not exposed.

- [ ] **Step 6: Run final repository hygiene checks**

Run: `git diff --check`

Expected: PASS.

Run: `git status --short`

Expected: only intended Task 1 source, tests, and plan files; all remain unstaged.

Run: `git diff --stat`

Expected: report the final Task 1 change summary without committing.

## Self-Review

- Spec coverage: Task 1 maps config, job persistence/claim readiness, scheduler, typed provider/fake, worker/run lifecycle, manual/API/audit paths, Forecast Room UI, ownership, safety, and verification to Tasks 1–7. It intentionally excludes Stage 2 Tasks 2–5.
- Placeholder scan: no deferred implementation markers are used; the intentional deferrals are explicit scope constraints from the authoritative spec.
- Type consistency: `BackgroundJob` and provider interfaces are produced before scheduler/worker use; route and UI types consume the schemas produced by the monitoring service.
- Review focus: the five highest-risk untested conditions are each assigned to Tasks 2–5 with an explicit test step.

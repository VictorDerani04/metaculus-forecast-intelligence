# Private Competition Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first deployable standalone Metaculus Forecast Intelligence application: authenticated private dashboard, URL/manual question import, Forecast Rooms, human forecasts, evidence approval, natural-language Copilot, transparent models, visualizations, and immutable decision history.

**Architecture:** A Next.js/TypeScript frontend talks only to a FastAPI backend. FastAPI owns authorization and PostgreSQL persistence and exposes explicit domain APIs; Python model runners are deterministic and versioned. External Metaculus and AI providers sit behind adapters so access limitations or provider changes do not leak into the core domain.

**Tech Stack:** Next.js, React, TypeScript, FastAPI, Python, PostgreSQL, SQLAlchemy/Alembic, Pydantic, pytest, Vitest/React Testing Library, Playwright, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-05-metaculus-forecast-intelligence-design.md`

## Global Constraints
- This is a new standalone product; do not import or depend on Forecasting Academy code or data.
- Natural language is the primary AI interaction.
- Human approval is required to approve evidence, activate a model, and change the final forecast.
- Prior, model probability, human forecast, and community forecast remain distinct.
- Candidate research cannot affect a model.
- All user-owned domain records carry `user_id` and authorization is enforced server-side.
- Model specs/runs and forecast updates are versioned/auditable.
- V1 is private with no public signup.
- Metaculus access must use an adapter and degrade gracefully when fields/community prediction are unavailable.
- External research content is untrusted data, never system instruction.
- TDD: no production behavior before a failing test.

---

## File Structure

`apps/web/` — Next.js UI, routes, components and browser tests.  
`apps/api/app/main.py` — FastAPI composition root.  
`apps/api/app/auth/` — private-user authentication and authorization.  
`apps/api/app/db/` — SQLAlchemy session/base and Alembic migrations.  
`apps/api/app/competitions/` — competition/question portfolio APIs.  
`apps/api/app/integrations/metaculus/` — Metaculus URL parsing/import adapter.  
`apps/api/app/forecasts/` — Forecast Room, human forecast and decision journal.  
`apps/api/app/research/` — candidate research and evidence approval.  
`apps/api/app/copilot/` — forecast-scoped chat/context and provider adapter.  
`apps/api/app/models_lab/` — model specs, activation and deterministic runners.  
`apps/api/app/analytics/` — chart data and dashboard priority metrics.  
`tests/e2e/` — full acceptance path.

---

### Task 1: Repository, runtime and authenticated private shell

**Files:**
- Create: `docker-compose.yml`, `.env.example`, `apps/api/pyproject.toml`, `apps/api/app/main.py`, `apps/api/app/db/base.py`, `apps/api/app/db/session.py`, `apps/api/app/auth/models.py`, `apps/api/app/auth/routes.py`, `apps/api/tests/test_auth.py`
- Create: `apps/web/package.json`, `apps/web/app/layout.tsx`, `apps/web/app/page.tsx`, `apps/web/app/login/page.tsx`, `apps/web/lib/api.ts`, `apps/web/tests/login.test.tsx`

**Interfaces:**
- Produces `GET /health -> {"status":"ok"}`.
- Produces `POST /auth/login` with private-user credentials and an HttpOnly session.
- Produces `GET /auth/me -> {id,email}`.
- Produces PostgreSQL `users(id,email,password_hash,is_active,created_at)`.

- [ ] Write `test_login_rejects_unknown_user`, `test_login_sets_session_for_seeded_user`, and `test_me_requires_session` before auth code.
- [ ] Run `pytest apps/api/tests/test_auth.py -v`; verify RED because routes/models do not exist.
- [ ] Implement SQLAlchemy user model, password verification, signed session/cookie dependency, `/health`, `/auth/login`, `/auth/me`; seed one private user from environment without a signup endpoint.
- [ ] Run the auth tests; verify GREEN.
- [ ] Write React tests that unauthenticated root redirects/shows login and authenticated shell renders “Forecast Intelligence”.
- [ ] Run `npm test -- login.test.tsx`; verify RED.
- [ ] Implement private Next.js shell and API client; verify GREEN.
- [ ] Run backend + frontend suites and commit `feat: create authenticated private app shell`.

### Task 2: Multi-user-ready competition and question domain

**Files:**
- Create: `apps/api/app/competitions/models.py`, `schemas.py`, `service.py`, `routes.py`, `apps/api/tests/test_questions.py`
- Create: `apps/web/app/dashboard/page.tsx`, `apps/web/components/question-table.tsx`, `apps/web/tests/dashboard.test.tsx`

**Interfaces:**
- `Competition(user_id,name,slug,status)`.
- `Question(user_id,competition_id,source,source_post_id,source_url,title,resolution_criteria,question_type,close_at,resolve_at,status,source_payload)`.
- `POST /questions/manual`, `GET /questions`, `GET /questions/{id}`; all queries scoped to authenticated `user_id`.

- [ ] Write API tests proving user A cannot read user B's question and manual creation preserves resolution criteria.
- [ ] Verify RED.
- [ ] Implement models/migration/service/routes with server-side ownership filters.
- [ ] Verify GREEN.
- [ ] Write dashboard component tests for title, deadline and empty state; verify RED.
- [ ] Implement dashboard table; verify GREEN and commit `feat: add private competition portfolio`.

### Task 3: Metaculus URL import adapter with graceful fallback

**Files:**
- Create: `apps/api/app/integrations/metaculus/client.py`, `parser.py`, `schemas.py`, `apps/api/tests/test_metaculus_import.py`
- Modify: `apps/api/app/competitions/routes.py`
- Create: `apps/web/components/import-question.tsx`, `apps/web/tests/import-question.test.tsx`

**Interfaces:**
- `parse_metaculus_url(url) -> post_id`.
- `MetaculusClient.fetch_post(post_id) -> MetaculusQuestionData`.
- `POST /questions/import {"url":...}` creates a source-backed question.
- Missing optional community prediction is `null`, never an error or fabricated number.

- [ ] Write fixture-based tests for URL parsing, imported criteria/dates, unavailable crowd data, provider/auth failure, and malformed URL.
- [ ] Verify RED without network calls.
- [ ] Implement adapter and route with injectable HTTP client; map only supported source fields and retain raw source payload.
- [ ] Verify GREEN.
- [ ] Test UI import success and fallback-to-manual state; verify RED then implement.
- [ ] Verify full suites and commit `feat: import Metaculus questions by URL`.

### Task 4: Forecast Room and immutable human forecast history

**Files:**
- Create: `apps/api/app/forecasts/models.py`, `schemas.py`, `service.py`, `routes.py`, `apps/api/tests/test_forecasts.py`
- Create: `apps/web/app/questions/[id]/page.tsx`, `components/probability-strip.tsx`, `components/forecast-editor.tsx`, `apps/web/tests/forecast-room.test.tsx`

**Interfaces:**
- `HumanForecast(id,user_id,question_id,probability,rationale,created_at)` is append-only.
- `CrowdObservation(...)` is separate.
- `GET /questions/{id}/room`; `POST /questions/{id}/forecasts`.
- Probability strip renders Prior / Model / Human / Crowd independently.

- [ ] Write tests for 0–1 probability validation, append-only updates, ownership and null crowd.
- [ ] Verify RED; implement persistence/API; verify GREEN.
- [ ] Write UI tests proving model/crowd values cannot overwrite human editor.
- [ ] Verify RED; implement Forecast Room and strip; verify GREEN.
- [ ] Commit `feat: add forecast room and human forecast journal`.

### Task 5: Research Inbox and human-approved Evidence Ledger

**Files:**
- Create: `apps/api/app/research/models.py`, `schemas.py`, `service.py`, `routes.py`, `apps/api/tests/test_evidence.py`
- Create: `apps/web/components/research-inbox.tsx`, `evidence-ledger.tsx`, `apps/web/tests/evidence.test.tsx`

**Interfaces:**
- `ResearchItem.status ∈ candidate|approved|rejected|deferred|duplicate|superseded`.
- `Evidence` references the approved candidate and records approval/provenance.
- `POST /research-items`, `POST /research-items/{id}/decision`.
- `eligible_evidence(question_id,user_id)` returns approved evidence only.

- [ ] Write tests proving candidate/deferred/rejected items are excluded from `eligible_evidence`.
- [ ] Verify RED.
- [ ] Implement records, decisions, immutable approval provenance and correlation/dependency links.
- [ ] Verify GREEN.
- [ ] Test Approve/Reject/Defer/Duplicate UI; implement after RED.
- [ ] Commit `feat: add controlled evidence approval`.

### Task 6: Forecast-scoped natural-language Copilot

**Files:**
- Create: `apps/api/app/copilot/context.py`, `provider.py`, `schemas.py`, `routes.py`, `apps/api/tests/test_copilot.py`
- Create: `apps/web/components/copilot-chat.tsx`, `apps/web/tests/copilot.test.tsx`

**Interfaces:**
- `build_forecast_context(user_id,question_id)` returns authorized question, criteria, forecast history, crowd observations, drivers, approved evidence, candidate research summaries, active model metadata and recent chat.
- `POST /questions/{id}/chat` stores user/assistant messages.
- Provider output may propose actions but cannot execute `approve_evidence`, `activate_model`, or `set_human_forecast`.

- [ ] Write tests for context scoping, untrusted research delimiting, persistence and forbidden automatic state changes.
- [ ] Verify RED.
- [ ] Implement context builder, provider interface and action proposal schema; verify GREEN.
- [ ] Write natural-language chat UI tests; implement after RED.
- [ ] Commit `feat: add forecast scoped model copilot`.

### Task 7: Model specs, approval and transparent local runners

**Files:**
- Create: `apps/api/app/models_lab/models.py`, `schemas.py`, `service.py`, `runners.py`, `apps/api/tests/test_models_lab.py`
- Create: `apps/web/app/questions/[id]/model-lab/page.tsx`, `components/model-card.tsx`, `apps/web/tests/model-lab.test.tsx`

**Interfaces:**
- Versioned `ModelSpec` stores family/rationale/inputs/assumptions/evidence_ids/dependencies.
- `POST /questions/{id}/models`, `POST /models/{id}/activate`, `POST /models/{id}/run`.
- `run_model(spec, seed=None) -> ModelRunResult(probability,distribution,trace,warnings,sensitivity_inputs)`.
- Initial families: base-rate, Bayesian likelihood-ratio, weighted-driver, scenario tree, seeded Monte Carlo.
- Runner rejects non-approved evidence IDs.

- [ ] Write numerical and authorization tests first, including Bayesian odds conversion and deterministic seeded Monte Carlo.
- [ ] Verify RED.
- [ ] Implement model/version tables and runners; verify GREEN.
- [ ] Test that proposed models require explicit Activate action; implement UI after RED.
- [ ] Commit `feat: add transparent versioned model lab`.

### Task 8: Visual analysis and causal Model Map

**Files:**
- Create: `apps/api/app/analytics/charts.py`, `apps/api/tests/test_charts.py`
- Create: `apps/web/components/charts/probability-history.tsx`, `distribution.tsx`, `sensitivity.tsx`, `evidence-impact.tsx`, `scenario-chart.tsx`, `model-map.tsx`, `apps/web/tests/charts.test.tsx`

**Interfaces:**
- Chart-data endpoints/builders always include `model_version`, `generated_at`, and `why_this_chart`.
- Required outputs: probability history, distribution, tornado sensitivity, evidence impact, scenarios, causal nodes/edges.

- [ ] Write chart-data tests for provenance and separate human/model/crowd series; verify RED.
- [ ] Implement chart builders; verify GREEN.
- [ ] Write component tests for labels, provenance and “Why this chart?”; implement after RED.
- [ ] Commit `feat: visualize model uncertainty and drivers`.

### Task 9: Attention Priority dashboard

**Files:**
- Create: `apps/api/app/analytics/priority.py`, `apps/api/tests/test_priority.py`
- Modify: `apps/api/app/competitions/routes.py`, `apps/web/components/question-table.tsx`
- Create: `apps/web/components/priority-explanation.tsx`

**Interfaces:**
- `attention_priority(question_state) -> {score,components,reasons}`.
- Components: deadline proximity, staleness, material evidence, unresolved alerts, human/crowd divergence, human/model divergence, uncertainty/sensitivity, research value, no-initial-forecast.
- Dashboard default sort is descending priority.

- [ ] Write deterministic priority tests and reason attribution; verify RED.
- [ ] Implement normalized component scoring and endpoint projection; verify GREEN.
- [ ] Test default UI ordering and “Why?” explanation; implement after RED.
- [ ] Commit `feat: prioritize forecasting attention`.

### Task 10: Decision journal, audit log and end-to-end private core

**Files:**
- Create: `apps/api/app/audit/models.py`, `apps/api/app/forecasts/decision_service.py`, `apps/api/tests/test_decision_journal.py`
- Modify forecast/model/evidence services to append audit events.
- Create: `apps/web/components/update-comparison.tsx`
- Create: `tests/e2e/private-core.spec.ts`

**Interfaces:**
- Audit events are append-only.
- Human forecast update may reference model version/evidence set but is never generated by model activation.
- Material human/model divergence requests rationale.
- E2E path: login → import/manual question → prior/human forecast → candidate research → approve evidence → chat → model proposal → activate/run → inspect chart → human update → history.

- [ ] Write API tests for immutable audit trail and human/model separation; verify RED.
- [ ] Implement decision/audit service; verify GREEN.
- [ ] Write Playwright acceptance test; verify RED.
- [ ] Complete UI wiring until acceptance test passes.
- [ ] Run `pytest`, frontend unit tests, TypeScript checks, production build and Playwright suite.
- [ ] Commit `feat: complete private forecasting core`.

---

## Stage 2 Follow-on Plan Boundary

Autonomous monitoring workers, immediate material alerts, daily digests, source deduplication/correlation, periodic Metaculus refresh and notification delivery are deliberately a separate implementation plan. Stage 1 creates the research/evidence and alert-compatible domain contracts they consume, while Stage 2 introduces scheduled external side effects.

## Acceptance Gate

Stage 1 is complete only when a real browser can execute:
**Sign in → import/create question → Forecast Room → record human forecast → add candidate research → approve evidence → converse naturally with Copilot → create/approve/run transparent model → inspect probability/model charts → compare Prior/Model/Human/Crowd → record human update → inspect immutable history**, with server-side user isolation throughout.

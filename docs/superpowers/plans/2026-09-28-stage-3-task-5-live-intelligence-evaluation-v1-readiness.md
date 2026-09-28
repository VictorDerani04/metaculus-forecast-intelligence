# Stage 3.5 Live Intelligence Evaluation and V1 Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or native execution) task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove, with deterministic replay and operational checks, that the live-intelligence pipeline produces conservative, inspectable attention artifacts without crossing human-control boundaries.

**Architecture:** A small test-only replay corpus drives the established normalization, classification, source-intelligence, clustering, and routing services through the real persistence layer. A focused evaluator collects per-finding outcomes and deterministic aggregate metrics; acceptance tests exercise recovery and the explicit human workflow. The readiness document records verified status and credential-dependent limits without adding a new runtime subsystem.

**Tech Stack:** Python, pytest, FastAPI, SQLAlchemy, existing deterministic monitoring providers/classifiers, PostgreSQL runtime tests, Vitest, Next.js, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-20-stage-2-autonomous-monitoring-architecture.md`

## Global Constraints

- Evaluation fixtures must not require internet access or credentials.
- Use the existing monitoring ingestion and routing services; do not duplicate production decisions.
- External text remains data, never instructions; no arbitrary URL fetching is introduced.
- Evaluation must not approve evidence, mutate forecasts/models/journal entries, or submit forecasts.
- Keep clustering conservative: a false merge is more severe than a missed merge.
- Live smoke checks run only when their explicit environment configuration is present.
- No secrets, credentials, or provider response bodies enter fixtures, logs, or documentation.

## Review Focus

- Prompt-injection fixture text must be classified/routed as data and never affect pipeline configuration.
- Syndicated wire copies must enrich a cluster without increasing independent corroboration or creating another alert.
- Related but distinct events must remain separate clusters even when their topic overlaps.
- Retry/replay must preserve finding, alert, digest, and notification idempotency.
- The acceptance workflow must retain a human action between research candidate and approved evidence, and between model output and human forecast.

---

### Task 1: Deterministic intelligence replay corpus and evaluator

**Files:**
- Create: `apps/api/tests/fixtures/live_intelligence_evaluation.json`
- Create: `apps/api/app/monitoring/evaluation.py`
- Create: `apps/api/tests/test_live_intelligence_evaluation.py`

**Interfaces:**
- Consumes: existing `ingest`, `attach_to_event_cluster`, and `route_finding` services.
- Produces: `EvaluationResult` with per-case outcomes and relevance/materiality/alert-noise aggregate metrics.

- [ ] **Step 1: Write failing evaluator tests** for 8–15 domain-varied questions and cases covering irrelevant, weakly relevant, routine, material, critical, duplicate, corroborated, conflicting, stale, injection, ambiguous, and missing-metadata inputs.
- [ ] **Step 2: Run the focused test** and confirm failure because the evaluator module is absent.
- [ ] **Step 3: Implement the test-only deterministic evaluator** that executes the existing pipeline against isolated database state, captures classification/source/cluster/routing outcomes, and calculates confusion, precision, recall, false-positive, and alert-burden metrics.
- [ ] **Step 4: Run focused evaluator tests** and confirm expected conservative outcomes.

### Task 2: Recovery, idempotency, and human-agency acceptance

**Files:**
- Modify: `apps/api/tests/test_live_intelligence_evaluation.py`
- Modify: `apps/api/tests/test_monitoring.py`
- Modify: `apps/api/tests/test_notifications.py`

**Interfaces:**
- Consumes: the existing worker retry taxonomy, job recovery service, notification worker, and private-core API workflow.
- Produces: regression coverage for replay/recovery behavior and a deterministic end-to-end acceptance scenario.

- [ ] **Step 1: Write failing tests** for timeout/429/malformed classification/notification 5xx, stale-job recovery, duplicate replay, and a full explicit-approval workflow.
- [ ] **Step 2: Run focused tests** and confirm the uncovered behavior or missing harness assertions fail.
- [ ] **Step 3: Add only required test fixtures or narrowly scoped production corrections** to make recovery bounded, cursor movement safe, and terminal artifacts idempotent.
- [ ] **Step 4: Run focused monitoring, notification, and acceptance tests** and confirm pass.

### Task 3: Configuration, operations, and readiness evidence

**Files:**
- Modify: `docs/operations.md`
- Create: `docs/v1-readiness.md`
- Modify: `apps/api/tests/test_live_intelligence_evaluation.py`

**Interfaces:**
- Consumes: configured provider registries and operational health/readiness endpoints.
- Produces: explicit live-credential status, backup/restore instructions, security findings, and status-marked v1 readiness checklist.

- [ ] **Step 1: Write failing/documentation-verification tests** for explicit production allowlists and safe missing-credential behavior where existing tests do not already pin it.
- [ ] **Step 2: Run focused tests** and verify any new assertion fails before its supporting change.
- [ ] **Step 3: Document PostgreSQL dump/restore, runtime process verification, observability signals, configuration constraints, security review findings, and credential-dependent live smoke limits.**
- [ ] **Step 4: Produce `docs/v1-readiness.md`** marking every required capability PASS, PARTIAL, BLOCKED, or DEFERRED from fresh evidence only.
- [ ] **Step 5: Run documentation-related focused tests** and confirm pass.

### Task 4: PostgreSQL, live smoke gates, and full regression

**Files:**
- Modify: `docs/v1-readiness.md`

**Interfaces:**
- Consumes: PostgreSQL test URL, configured live provider/classifier/notification registries, backend/frontend/E2E commands.
- Produces: final verified evaluation results and caveats.

- [ ] **Step 1: Run PostgreSQL concurrency and all Stage 3 PostgreSQL-specific tests** with `POSTGRES_TEST_DATABASE_URL`; record a blocked environmental prerequisite accurately if PostgreSQL is unavailable.
- [ ] **Step 2: Inspect live configuration without exposing values** and run one low-volume smoke sample per configured adapter only; otherwise record the specified credentials-not-configured status.
- [ ] **Step 3: Run backend, frontend tests, typecheck, build, E2E, and Git whitespace/status checks.**
- [ ] **Step 4: Update readiness statuses and evaluation summary** from command output; do not claim release-candidate status without every required green result.

## Self-review

- Corpus task covers all requested representative domains and failure modes while remaining deterministic.
- Evaluator task uses existing production services, so its outcomes expose integration behavior rather than a parallel implementation.
- Recovery/agency task owns all idempotency and consequential-mutation regressions.
- Operations/readiness task owns the checklist, backup/restore, security, configuration, and live-credential disclosures.
- Final task owns environment-gated checks and the only release-candidate determination.

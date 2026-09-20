# Metaculus Forecast Intelligence — Stage 2 Architecture Specification v1.0

**Status:** Proposed architecture baseline  
**Date:** 2026-09-20  
**Private Core v1 baseline:** `00081f4 feat: complete private core with decision journal audit and e2e`  
**Scope:** Stage 2 autonomous monitoring, alerting, digesting, and production-readiness foundation  
**Audience:** Engineering / Codex / Copilot implementation agents  
**Architecture style:** Modular monolith with separate scheduler and worker processes

---

## 1. Purpose

Private Core v1 established the human-controlled forecasting workflow:

```text
Question
   ↓
Research Inbox
   ↓ explicit approval
Evidence Ledger
   ↓
Model Workspace
   ↓ explicit approval + run
Model Probability
   ↓
Human Final Forecast
   ↓
Decision Journal / Audit
```

Stage 2 adds an autonomous observation and attention layer around that system.

The objective is to continuously observe external information sources, identify developments relevant to active forecasting questions, organize and prioritize those developments, and notify the user without silently changing approved evidence, model state, or the Human Final Forecast.

The autonomous boundary ends at:

```text
ResearchCandidate
AlertEvent
DigestItem
```

Consequential transitions remain human-controlled.

---

## 2. Architectural Invariants

The following invariants are mandatory throughout Stage 2.

1. Human Final Forecast changes only through explicit human action.
2. AI-discovered information never becomes approved Evidence automatically.
3. Research discoveries enter the system as candidates.
4. Evidence approval remains explicit.
5. Model approval remains explicit.
6. Model execution remains explicit.
7. Copilot remains advisory-only.
8. Analysis remains read-only.
9. Attention Priority remains read-only.
10. No autonomous Metaculus forecast submission exists.
11. External content is always treated as untrusted data.
12. Autonomous processing may notify, classify, summarize, and recommend, but it may not make consequential forecasting decisions on behalf of the user.

The core trust boundary is:

```text
UNTRUSTED EXTERNAL CONTENT
          ↓
Normalization
          ↓
Classification
          ↓
Research Candidate / Alert / Digest
          ↓
        HUMAN
          ↓
Consequential action
```

No direct path from untrusted external content to consequential state is permitted.

---

## 3. Architecture Style

Stage 2 remains a modular monolith.

Do not split the application into independent microservices unless future scaling requirements demonstrate a concrete need.

Use one codebase and one primary PostgreSQL database, with separate runtime processes for API, scheduling, monitoring work, and later notification delivery.

```text
┌──────────────────────────────────────────────┐
│          Metaculus Forecast Intelligence    │
│                                              │
│  Next.js Web                                 │
│        │                                     │
│        ▼                                     │
│  FastAPI Application                        │
│        │                                     │
│        ├──────── PostgreSQL                  │
│        │                                     │
│        └──── Job creation / control          │
│                                              │
│  Scheduler                                  │
│        │                                     │
│        └──── creates due jobs                │
│                                              │
│  Monitoring Worker                          │
│        │                                     │
│        ├──── External providers              │
│        └──── PostgreSQL                      │
│                                              │
│  Notification Worker [later Stage 2]         │
│        │                                     │
│        └──── Email / push / other channels   │
└──────────────────────────────────────────────┘
```

All processes share the same domain modules and data model.

---

## 4. Technology Baseline

Retain the existing stack:

### Frontend
- Next.js
- React
- TypeScript

### Backend
- Python
- FastAPI

### Database
- PostgreSQL

### Modeling
- NumPy
- pandas
- SciPy
- statsmodels
- scikit-learn where appropriate

### Testing
- pytest
- Vitest / React Testing Library
- Playwright

### Deployment
- Docker
- Docker Compose
- Cloud-portable runtime

### Background Execution

Stage 2 introduces persistent background jobs.

Initial recommendation:

- PostgreSQL-backed job queue
- Dedicated Python worker process
- Separate scheduler process
- Row claiming via `FOR UPDATE SKIP LOCKED`

Do not introduce Redis/Celery in Stage 2 v1 unless the implementation plan identifies a demonstrated requirement.

This choice minimizes infrastructure while preserving:
- persistence
- retries
- crash recovery
- transactional job creation
- concurrency safety
- straightforward local development

The job interface must remain replaceable so a later queue implementation can migrate to Redis, SQS, Temporal, or another system without rewriting domain services.

---

## 5. Stage 2 Module Layout

Recommended backend structure:

```text
apps/api/app/

    auth/
    competitions/
    questions/
    forecasts/
    research/
    models_lab/
    analytics/
    audit/

    monitoring/
        models.py
        schemas.py
        service.py
        scheduler.py
        worker.py
        routes.py

        providers/
            base.py
            metaculus.py
            web_search.py
            news.py

        normalization/
            normalizer.py

        dedup/
            fingerprints.py
            service.py

        classification/
            relevance.py
            materiality.py

    alerts/
        models.py
        schemas.py
        service.py
        routes.py

    digests/
        models.py
        schemas.py
        service.py
        routes.py

    jobs/
        models.py
        service.py
        worker.py

    notifications/          # later Stage 2
        service.py
        providers/
            email.py
            push.py
```

The architecture is domain-oriented rather than provider-oriented.

Correct:

```text
MonitoringService
      ↓
MonitoringProvider interface
      ↓
Concrete Provider Adapter
```

Avoid embedding vendor-specific logic directly into business workflows.

---

## 6. Monitoring Configuration

Monitoring is explicitly enabled per question.

A question does not become monitored merely because it exists.

Conceptual model:

```text
MonitoringConfig

id
user_id
question_id

enabled

metaculus_refresh_enabled
web_monitoring_enabled
news_monitoring_enabled

monitoring_interval_minutes

materiality_threshold
digest_threshold

last_run_at
last_success_at
next_run_at

created_at
updated_at
```

### Requirements

- Unique active configuration per `(user_id, question_id)`.
- All configuration is user-owned.
- Enable/disable actions are explicit.
- Scheduling policy must be stored independently from worker implementation.
- Monitoring configuration changes may be written to the existing audit trail where appropriate.

---

## 7. Persistent Background Jobs

A generic persistent job system coordinates asynchronous execution.

Conceptual model:

```text
BackgroundJob

id
user_id

job_type

question_id nullable

status
    queued
    running
    succeeded
    failed
    retry_wait
    cancelled

payload_json

attempt_count
max_attempts

scheduled_for
started_at
finished_at

last_error_code
last_error_message

created_at
updated_at
```

### Initial Job Types

```text
monitor_question
refresh_metaculus
classify_finding
build_daily_digest
deliver_notification
```

The scheduler never performs domain work directly.

Flow:

```text
Scheduler
   ↓
BackgroundJob
   ↓
Worker
   ↓
Domain Service
```

### Requirements

- Worker claiming must be concurrency-safe.
- A job may be retried safely.
- Failed jobs must preserve safe error metadata.
- No secrets may be persisted in job error messages.
- Job payloads may reference IDs but must not carry unnecessary sensitive data.

---

## 8. Monitoring Runs

`BackgroundJob` is infrastructure state.

`MonitoringRun` is domain state describing what happened while observing a question.

Conceptual model:

```text
MonitoringRun

id
user_id
question_id

job_id

started_at
completed_at

status

providers_attempted
providers_succeeded
providers_failed

raw_items_seen
normalized_findings
duplicates_removed
relevant_findings
material_findings
digest_findings
candidates_created

safe_error_summary
```

### Requirements

- Every manual or scheduled monitoring execution creates one run.
- Monitoring run history is queryable by question.
- Run records are immutable after completion except for tightly controlled lifecycle transitions while the run is active.
- Failure of one provider must not corrupt the entire run.
- Partial success semantics must be explicit and testable.

---

## 9. Provider Abstraction

All external acquisition happens through provider adapters.

Conceptual contract:

```python
class MonitoringProvider(Protocol):
    provider_name: str

    async def fetch(
        question: QuestionContext,
        cursor: ProviderCursor | None,
    ) -> ProviderResult:
        ...
```

`ProviderResult` should contain:

```text
items
next_cursor
rate_limit_metadata
provider_metadata
```

### Initial Providers

- `MetaculusProvider`
- `WebSearchProvider`
- `NewsProvider`

### Future Providers

Potential later providers include:
- RSS
- GDELT
- Google News
- financial APIs
- government feeds
- election data
- weather
- sports
- prediction-market feeds

No provider may directly create:
- Evidence
- Human Forecasts
- ModelSpecs
- ModelRuns
- DecisionJournal entries

Providers return observations only.

---

## 10. Provider Cursors

Each `(user, question, provider)` may persist acquisition state.

Conceptual model:

```text
ProviderCursor

user_id
question_id
provider

cursor_value
last_seen_timestamp
last_seen_external_id

updated_at
```

Purpose:
- avoid repeatedly scanning historical results
- reduce API cost
- support incremental polling
- improve idempotency

Provider cursor changes must occur only after successful persistence of the related acquisition results.

---

## 11. Raw Findings and Normalized Findings

Separate provider payloads from application-domain findings.

### Raw Finding

```text
RawFinding

provider
external_id
url
raw_title
raw_text
published_at
retrieved_at
raw_metadata
```

### Normalized Finding

```text
Finding

id
user_id
question_id

provider
source_url
canonical_url

title
summary

published_at
discovered_at

source_name
source_domain

content_fingerprint

relevance_score
relevance_class

materiality_score
materiality_class

status

raw_finding_id
```

### Requirements

- External payloads remain untrusted.
- Raw provider data must never be interpreted as application instructions.
- Business logic operates on normalized, validated structures.
- Raw payload retention should be minimal and justified by provenance/debugging needs.

---

## 12. Exact Deduplication

Deduplication occurs before ResearchCandidate creation.

Pipeline:

```text
Raw Finding
    ↓
Normalize URL/title/text
    ↓
Generate deterministic fingerprints
    ↓
Exact duplicate?
    ├── yes → attach observation to existing finding
    └── no  → continue
```

Potential exact fingerprint inputs:

```text
canonical URL
provider external ID
normalized headline
normalized source
publication timestamp bucket
content hash
```

### Requirements

- Exact duplicate protection must not depend solely on an LLM.
- Database uniqueness constraints should enforce deduplication where possible.
- Worker retries must not create duplicate findings, candidates, alerts, or digest items.

---

## 13. Event Correlation

Event correlation is distinct from exact deduplication.

Multiple publishers may report the same real-world event using different language.

Future conceptual model:

```text
EventCluster

id
question_id
canonical_summary
first_seen_at
last_seen_at
finding_count
```

with:

```text
FindingEventLink
```

Stage 2 v1 should establish interfaces that allow this later, but sophisticated semantic event clustering is not part of the first implementation task.

Exact deduplication must be correct before near-duplicate clustering is introduced.

---

## 14. Relevance Engine

The relevance engine answers:

> Is this finding relevant to resolving this forecasting question?

Input context may include:

```text
question title
question description
resolution criteria
resolution date
known entities
current approved evidence
```

Expected output:

```text
Relevant
Irrelevant
Uncertain
```

plus:

```text
reason
confidence
```

### Requirements

- Structured output only.
- AI output must be schema validated.
- External finding text is untrusted.
- Relevance classification cannot approve evidence or alter forecast/model state.
- Failure to classify should preserve the finding for retry or review rather than silently discarding it.

---

## 15. Materiality Engine

Relevance does not imply urgency.

Materiality answers:

> How much could this development matter for the forecast?

Recommended representation:

```text
materiality_score: 0.0–1.0

materiality_class:
    irrelevant
    digest
    material
    critical
```

Illustrative threshold mapping only:

```text
0.04 → irrelevant
0.32 → digest
0.76 → immediate alert
0.97 → critical
```

Exact thresholds must be configurable and implemented explicitly.

### Requirements

- Preserve both score and class.
- Preserve structured justification.
- Classification may propose urgency, but may not perform consequential actions.
- AI classification must be validated before use.
- Classification failure must be observable and retryable.

---

## 16. ResearchCandidate Integration

The Stage 2 monitoring pipeline ends in ResearchCandidate for information that may become evidence.

```text
External Finding
      ↓
Relevant Finding
      ↓
Monitoring Candidate
      ↓
ResearchCandidate
      ↓
USER REVIEW
      ↓
Approve Evidence
      ↓
Evidence Ledger
```

Monitoring may automatically create `ResearchCandidate`.

Monitoring may never automatically create approved `Evidence`.

ResearchCandidate provenance should include:

```text
origin = monitoring
monitoring_run_id
finding_id
provider
source_url
materiality_score
materiality_class
classification_reason
```

Existing Task 5 evidence approval rules remain unchanged.

---

## 17. Alert Architecture

An alert is an internal domain event, not a delivery attempt.

Conceptual model:

```text
AlertEvent

id

user_id
question_id
finding_id
research_candidate_id

severity
reason

created_at

status
    new
    seen
    dismissed

delivery_required
```

### Requirements

- Alerts are idempotent by finding/question.
- Alert creation does not imply notification delivery.
- Alert reads and status updates are user-scoped.
- Alert creation never alters forecast/model/evidence state.

Later delivery model:

```text
NotificationAttempt

alert_event_id
channel
provider
status
attempted_at
error
```

---

## 18. Digest Architecture

Lower-priority findings accumulate as digest items.

Conceptual model:

```text
DigestItem

id
user_id
question_id
finding_id

eligible_at
included_in_digest_id nullable

created_at
```

and:

```text
Digest

id
user_id

period_start
period_end

status

generated_at
delivered_at
```

Generation and delivery remain separate concerns.

Initial Stage 2 should support digest eligibility and later digest assembly before adding external notification delivery.

---

## 19. Scheduled Metaculus Refresh

Metaculus refresh is implemented as a provider/job workflow.

```text
Scheduler
   ↓
refresh_metaculus job
   ↓
Metaculus Adapter
   ↓
Question metadata refresh
```

Potential permitted updates:

```text
question status
resolution state
resolution timestamp
community prediction
external metadata
```

Must never overwrite:

```text
Prior/Base Rate
Model Probability
Human Final Forecast
```

Community prediction remains nullable when unavailable.

The existing Task 3 Metaculus adapter should be reused rather than duplicated.

---

## 20. Scheduling Policy

Scheduling policy is independent from workers.

Recommended initial adaptive policy:

```text
Long horizon (>90 days)
    every 12 hours

Medium horizon (30–90 days)
    every 6 hours

Short horizon (7–30 days)
    every 3 hours

Near resolution (<7 days)
    hourly
```

These are initial defaults, not hard-coded architectural constants.

Later, Task 9 Attention Priority may inform monitoring frequency:

```text
Attention Priority ↑
        ↓
Monitoring Frequency ↑
```

This optimization should be added only after baseline scheduling is reliable.

---

## 21. Failure Taxonomy

External monitoring failures are normal operational states.

Recommended classifications:

```text
ProviderTimeout
ProviderUnavailable
RateLimited
AuthenticationFailure
MalformedResponse
ClassificationFailure
DatabaseFailure
UnknownFailure
```

Retry policy:

```text
temporary error
     ↓
retry with backoff

permanent configuration error
     ↓
stop retrying
     ↓
surface warning
```

Initial backoff example:

```text
1 minute
5 minutes
15 minutes
1 hour
```

Failures must:
- remain auditable
- expose safe user-facing error information
- never leak secrets
- never partially approve evidence
- never mutate forecasts or model state

---

## 22. Idempotency

Every autonomous workflow must assume it can execute more than once.

Common duplicate execution causes:
- worker crash after persistence
- scheduler duplication
- provider retry
- network retry
- process restart

The following must be safe under retry:

```text
job creation
job execution
finding ingestion
candidate creation
alert creation
digest insertion
```

Database uniqueness constraints should be preferred over in-memory duplicate checks.

---

## 23. Transaction Boundaries

Never hold database transactions open during external network operations.

Incorrect:

```text
BEGIN
    fetch provider
    call AI classifier
    wait
COMMIT
```

Correct:

```text
fetch provider
    ↓
normalize
    ↓
classify
    ↓
BEGIN
persist
deduplicate
create candidate/event
COMMIT
```

Transactions should be short and centered on database state transitions.

---

## 24. AI Orchestration

AI may assist with:
- relevance classification
- materiality classification
- summarization
- query generation
- later event correlation

Expected structured output conceptually:

```text
MonitoringClassification

relevant: boolean
relevance_reason: string

materiality_score: number
materiality_reason: string

suggested_alert_level:
    none
    digest
    immediate
```

### Rules

- AI output is advisory to application logic.
- Output must be schema validated.
- The service code decides allowed actions.
- AI cannot return executable commands.
- AI cannot approve evidence.
- AI cannot run models.
- AI cannot change forecasts.
- AI cannot submit to Metaculus.

---

## 25. Prompt-Injection Boundary

Stage 2 substantially increases prompt-injection risk.

All external content must be represented explicitly as untrusted data.

```text
SYSTEM INSTRUCTIONS
        │ trusted
        ▼
AI Classifier
        ▲
        │ untrusted
        │
External Article
```

External content must never be concatenated into trusted system instructions.

Provider or article text may not:
- alter system policy
- call arbitrary tools
- approve evidence
- activate models
- run models
- modify forecasts
- record human decisions
- submit forecasts

---

## 26. SSRF Protection

Monitoring can introduce arbitrary URLs.

Any direct URL retrieval capability must block:
- `localhost`
- `127.0.0.1`
- private IPv4/IPv6 ranges
- link-local ranges
- cloud metadata endpoints
- internal hostnames
- `file://`
- unsupported protocols such as `ftp://`

Prefer provider APIs that return content directly rather than arbitrary server-side URL fetching.

URL canonicalization and validation must occur before any direct fetch.

---

## 27. API Surface

Proposed Stage 2 API surface:

```text
GET    /questions/{id}/monitoring
POST   /questions/{id}/monitoring/enable
POST   /questions/{id}/monitoring/disable

POST   /questions/{id}/monitoring/run
GET    /questions/{id}/monitoring/runs

GET    /questions/{id}/findings

GET    /alerts
POST   /alerts/{id}/seen
POST   /alerts/{id}/dismiss

GET    /digests
GET    /digests/{id}
```

Manual `monitor now` is required even when scheduling is enabled.

All endpoints inherit existing authentication and ownership semantics.

---

## 28. Frontend Integration

Do not redesign the application.

Add monitoring to the existing Forecast Room.

Conceptual structure:

```text
Forecast Room

Probability Strip
Human Forecast
Research Inbox
Evidence Ledger
Copilot
Model Workspace
Analysis
Decision Journal

─────────────────────────

Monitoring

Status
● Active

Last checked
18 minutes ago

Next check
42 minutes

Latest result
6 sources checked
2 new findings
1 material development

[ Monitor now ]
```

Later, global alert visibility may be added to the Attention Dashboard.

Monitoring UI must provide:
- truthful empty states
- loading state
- retryable errors
- explicit enable/disable
- manual run action
- last run status
- latest error if relevant

---

## 29. Observability

Initial operational observability must include:

```text
structured logs
job state
monitoring run history
provider latency
provider errors
findings per run
duplicates per run
candidates per run
alerts per run
digest items per run
```

Do not add Prometheus/Grafana until operational requirements justify them.

Database history plus structured logs are sufficient for Stage 2 v1.

---

## 30. Database Relationship Overview

```text
User
 │
 ├── Competition
 │     │
 │     └── Question
 │           │
 │           ├── MonitoringConfig
 │           ├── MonitoringRun
 │           ├── ProviderCursor
 │           ├── Finding
 │           │      │
 │           │      ├── ResearchCandidate
 │           │      ├── AlertEvent
 │           │      └── DigestItem
 │           │
 │           ├── Evidence
 │           ├── ModelSpec
 │           ├── ModelRun
 │           ├── HumanForecast
 │           └── DecisionJournal
 │
 └── BackgroundJob
```

Every user-owned Stage 2 entity must carry `user_id` either directly or through a guaranteed ownership relationship.

---

# 31. Stage 2 Implementation Roadmap

Stage 2 is divided into five implementation tasks.

## Stage 2 — Task 1: Monitoring Infrastructure

### Deliverables

```text
MonitoringConfig
MonitoringRun
BackgroundJob
Scheduler
Worker
Provider interfaces
Manual "Monitor now"
```

Real news/web providers are not required yet.

Deterministic fake providers should be used for tests.

### Acceptance Criteria

- Monitoring can be enabled and disabled per owned question.
- A manual run creates a persistent monitoring job.
- Scheduler can identify due monitoring configurations and enqueue jobs idempotently.
- Worker can claim queued jobs safely.
- Worker executes a provider abstraction, not provider-specific business logic.
- MonitoringRun records execution outcome.
- Failed jobs are retryable and preserve safe errors.
- Re-running the same scheduled interval does not create duplicate work.
- No HumanForecast, Evidence, ModelSpec, ModelRun, or DecisionJournal state changes.
- All ownership and privacy tests pass.
- Full Private Core regression and Playwright acceptance remain green.

## Stage 2 — Task 2: External Research Pipeline

### Deliverables

```text
Web/news provider adapters
Finding normalization
Canonicalization
Deterministic fingerprints
Exact deduplication
Relevance classification
Materiality classification
ResearchCandidate creation
```

### Acceptance Criteria

- Provider results normalize into typed Finding records.
- Duplicate findings do not create duplicate candidates.
- Classification output is schema validated.
- External content remains untrusted.
- Relevant findings can create ResearchCandidate records.
- ResearchCandidate always begins unapproved.
- Evidence is never auto-created.
- Irrelevant findings do not flood the Research Inbox.
- Materiality classification is transparent and retained.
- Provider and classification errors are retryable.
- No consequential forecast/model mutation occurs.

## Stage 2 — Task 3: Alert and Digest Engine

### Deliverables

```text
AlertEvent
DigestItem
Severity logic
Alert UI
Daily digest generation
```

### Acceptance Criteria

- Material findings create idempotent AlertEvents.
- Lower-priority findings create DigestItems.
- Alert generation and notification delivery are separate.
- Alerts support new/seen/dismissed state.
- Digest generation is deterministic for a period.
- No duplicate alert/digest entries under retry.
- Alert/digest data is user-owned.
- Forecast and evidence approval state remains unchanged.

## Stage 2 — Task 4: Notification Delivery

### Deliverables

```text
NotificationProvider interface
Email delivery
NotificationAttempt
Retry/backoff
Delivery status
Notification preferences
```

### Acceptance Criteria

- Delivery is downstream from internal AlertEvent/Digest state.
- Provider failures do not lose domain alerts.
- Delivery attempts are persisted.
- Retry is idempotent.
- Notification preferences are user-controlled.
- Secrets stay server-side.
- No delivery provider can alter forecast/evidence/model state.

## Stage 2 — Task 5: Reliability and Production Readiness

### Deliverables

```text
Adaptive scheduling
Provider backoff
Rate limiting
Worker recovery
PostgreSQL concurrency verification
Operational monitoring
Full Stage 2 E2E
Security review
Deployment verification
```

### Acceptance Criteria

- Concurrent workers do not double-claim jobs.
- PostgreSQL runtime behavior is tested.
- Rate limits and retries behave safely.
- Scheduler restarts do not lose due work.
- Worker crashes recover without duplicate consequential records.
- Stage 2 E2E passes.
- Private Core Playwright acceptance still passes.
- Security review covers SSRF, prompt injection, secrets, ownership, and provider isolation.
- Deployment instructions are reproducible.

---

## 32. Cross-Task Testing Requirements

Every Stage 2 task must preserve Private Core v1 behavior.

Backend:
```text
py -m pytest
```

Frontend:
```text
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
```

E2E:
Run the existing Private Core Playwright suite.

Git hygiene:
```text
git diff --check
git status --short
git diff --stat
```

Generated artifacts must remain untracked:
- `node_modules`
- `.next`
- `__pycache__`
- `*.pyc`
- `.pytest_cache`
- `.venv`
- Playwright reports
- test-results
- browser caches
- local SQLite databases

---

## 33. Security Acceptance Criteria

Before Stage 2 is considered complete, the implementation must demonstrate:

- No cross-user monitoring access.
- No cross-question finding leakage.
- No provider text interpreted as instructions.
- No arbitrary code execution from provider or AI output.
- No `eval`/`exec` path for external content.
- No arbitrary dynamic imports controlled by external data.
- No shell execution controlled by external data.
- SSRF protections for any direct URL fetch capability.
- Secrets remain server-side.
- AI outputs are schema validated.
- External information cannot auto-approve Evidence.
- External information cannot auto-run or auto-activate models.
- External information cannot change Human Final Forecast.
- External information cannot create human DecisionJournal entries.
- No autonomous Metaculus submission.

---

## 34. Explicitly Out of Scope for Stage 2 v1

Stage 2 v1 does not autonomously:

```text
change Human Final Forecast
approve Evidence
reject approved Evidence
activate models
run models automatically
record human Decision Journal entries
submit forecasts to Metaculus
```

These boundaries require a separate future architecture review if they are ever reconsidered.

---

## 35. Architectural Decisions Frozen by v1.0

### ADR-S2-001 — Modular Monolith

Stage 2 remains a modular monolith with separate runtime processes.

No microservices split in Stage 2 v1.

### ADR-S2-002 — PostgreSQL Job Queue

Use a PostgreSQL-backed persistent job queue initially.

Do not introduce Redis/Celery without a demonstrated requirement and explicit architecture revision.

### ADR-S2-003 — Human Consequential Gates

Autonomous workflows terminate at:

```text
ResearchCandidate
AlertEvent
DigestItem
```

They do not cross directly into Evidence, model execution, Human Final Forecast, or DecisionJournal state.

### ADR-S2-004 — Provider Abstraction

External systems are accessed through adapters behind application-owned interfaces.

No provider owns business workflow.

### ADR-S2-005 — Untrusted External Content

All web/news/provider text is untrusted data.

No external content can become application instructions.

### ADR-S2-006 — Idempotent Autonomous Work

Jobs, findings, candidates, alerts, and digest records must be safe under retries.

### ADR-S2-007 — Generation Separate from Delivery

Alert/digest generation is distinct from notification delivery.

---

## 36. Definition of Stage 2 Completion

Stage 2 is complete only when all five Stage 2 tasks are implemented and verified.

Completion requires:

1. Persistent scheduler/worker infrastructure.
2. External research ingestion.
3. Normalization and exact deduplication.
4. Relevance/materiality classification.
5. Monitoring-origin ResearchCandidate creation.
6. Internal immediate alerts.
7. Digest generation.
8. Notification delivery with retries.
9. PostgreSQL concurrency verification.
10. Full Stage 2 security review.
11. Stage 2 browser E2E.
12. Private Core v1 regression remains fully green.

Until all twelve conditions are met, reports should describe Stage 2 as in progress rather than complete.

---

## 37. Final Architecture

```text
                         ┌──────────────────────┐
                         │    External World    │
                         │                      │
                         │ Web / News / APIs    │
                         │ Metaculus            │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │  Provider Adapters   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Monitoring Worker    │
                         │                      │
                         │ fetch                │
                         │ normalize            │
                         │ deduplicate          │
                         │ classify             │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      Findings        │
                         └──────────┬───────────┘
                                    │
                        ┌───────────┴────────────┐
                        │                        │
                        ▼                        ▼
                ResearchCandidate          Alert / Digest
                        │                        │
                        │                        ▼
                        │               Notification Worker
                        │
                        ▼
                 HUMAN APPROVAL
                        │
                        ▼
                 Evidence Ledger
                        │
                        ▼
                   Model Lab
                        │
                 explicit run
                        │
                        ▼
                Model Probability
                        │
                        ▼
                    HUMAN
                        │
                        ▼
              Human Final Forecast
                        │
                        ▼
                Decision Journal
```

Infrastructure:

```text
Scheduler
    ↓
PostgreSQL Job Queue
    ↓
Monitoring Worker(s)

             PostgreSQL

Questions
Forecasts
Evidence
Models
Analytics
MonitoringConfig
MonitoringRuns
ProviderCursors
BackgroundJobs
Findings
Alerts
Digests
NotificationAttempts
Audit
```

---

## 38. Baseline Statement

This document is intended to become the authoritative architecture baseline for Stage 2 of Metaculus Forecast Intelligence.

Implementation agents should:

1. read this specification first;
2. preserve Private Core v1 invariants;
3. implement Stage 2 task-by-task;
4. use strict TDD;
5. avoid architecture expansion outside the current task;
6. never weaken human approval boundaries;
7. report gaps rather than silently changing architecture.

Any material departure from ADR-S2-001 through ADR-S2-007 requires an explicit architecture revision before implementation.

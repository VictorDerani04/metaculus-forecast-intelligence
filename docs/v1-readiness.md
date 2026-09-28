# V1.0 Readiness

**Evaluation date:** 2026-09-28  
**Scope:** Stage 3.5 deterministic replay, regression, configuration, and local-runtime evaluation.  A status reflects executed evidence only; it is not a production deployment certification.

| Capability | Status | Evidence / limitation |
|---|---|---|
| Auth | PASS | Owner-scoped API regression coverage. |
| Dashboard | PASS | Web tests, typecheck, and production build pass. |
| Question import | PASS | Existing API regression coverage. |
| Forecast Room | PASS | Human forecasts are append-only and explicit. |
| Research Inbox | PASS | Monitoring creates candidate research only. |
| Evidence Ledger | PASS | Approval is explicit and evidence is separated from candidates. |
| Copilot | PASS | Advisory context tests preserve evidence/probability boundaries. |
| Model framework | PASS | Model approval/run are explicit; runs are append-only. |
| Visual analysis | PASS | Existing analysis regression coverage. |
| Attention priority | PASS | Existing priority regression coverage. |
| Decision journal | PASS | Existing audit regression coverage. |
| Monitoring scheduler | PASS | Persistent scheduling and deadline cadence are covered by regression tests. |
| Monitoring worker | PASS | Persistent worker, lease recovery, retry/backoff, and safe provider failure paths are covered. |
| Live research adapter | PASS | Allowlisted fixed-endpoint adapter is covered offline; live credentials are not configured. |
| Live AI classifier | PASS | Fixed-endpoint, allowlisted structured adapter is covered offline; live credentials are not configured. |
| Source intelligence | PASS | Deterministic source/corroboration and conservative cluster replay pass. |
| Alerts | PASS | Material/critical routing and cluster duplicate suppression pass. |
| Digests | PASS | Digest routing and persistence/retry coverage pass. |
| Real notification adapter | PASS | Fixed Resend endpoint, configured-destination-only delivery, escaping, idempotency, and safe failures are covered offline. |
| Notifications | PASS | Alert/digest attempt persistence and duplicate-safe delivery paths pass; live delivery remains credential-deferred. |
| PostgreSQL concurrency | PASS | Current local PostgreSQL runtime verification: 2 passed. |
| Retries/recovery | PASS | Provider, classifier, notification, stale-job, and duplicate-replay tests pass. |
| Health/readiness | PASS | `/health` and safe DB `/ready` behavior are covered. |
| Security | PASS | Fixed endpoints, redirect control, bounded model output, escaped email, allowlists, owner scopes, and human boundaries are covered by Stage 3 tests. |
| Backup/restore | PASS | Local Docker dump/restore drill restored 27 public tables, then removed only the temporary restore database and dump. |
| Operations documentation | PASS | Local process, configuration, recovery, and exact Docker drill commands are documented. |
| E2E | PASS | Playwright deterministic private-core acceptance workflow passed. |
| Deterministic v1 acceptance scenario | PASS | Pipeline replay confirms candidate-only ResearchItem creation, source intelligence, clustering, suppression, and no autonomous crossing of human boundaries. |
| Full backend regression | PASS | 264 passed, 2 skipped (the PostgreSQL-only tests are executed separately against the local service). |
| Frontend tests | PASS | 20 files / 53 tests passed. |
| Frontend typecheck | PASS | `tsc --noEmit` passed. |
| Frontend production build | PASS | `next build` passed. |
| Live research credential status | DEFERRED | NOT EXECUTED — CREDENTIALS NOT CONFIGURED. |
| Live AI credential status | DEFERRED | NOT EXECUTED — CREDENTIALS NOT CONFIGURED. |
| Live notification credential status | DEFERRED | NOT EXECUTED — CREDENTIALS NOT CONFIGURED. |
| Live credential status | DEFERRED | No live research, AI, or notification credentials were available during this evaluation. |

## Deterministic evaluation findings

`apps/api/tests/fixtures/live_intelligence_evaluation.json` contains ten
inspectable cases across politics, geopolitics, macroeconomics, markets,
weather, humanitarian events, science/technology, and sports.  The evaluator
calculates relevance precision, recall, false-positive rate, alert/digest
counts, duplicate suppression, source identity, reliability label, cluster ID,
and missed-signal stage.  Its deterministic baseline has 8 true-relevant, 2
true-irrelevant, 0 false-relevant, 0 false-irrelevant, precision 1.0, recall
1.0, four alerts, three digests, and one suppressed syndicated duplicate.

This corpus is a regression detector, not a forecast-truth score.  It includes
noise, routine and material updates, a critical-resolution event, syndication,
corroboration, ambiguity, missing metadata, and prompt-injection text.  The
replay test executes the established persisted ingestion, source intelligence,
clustering, and routing path for the syndicated pair.

## Live evaluations

LIVE RESEARCH EVALUATION: NOT EXECUTED — CREDENTIALS NOT CONFIGURED.

LIVE AI EVALUATION: NOT EXECUTED — CREDENTIALS NOT CONFIGURED.

LIVE NOTIFICATION EVALUATION: NOT EXECUTED — CREDENTIALS NOT CONFIGURED.

No live check should be inferred from deterministic fake-provider tests.  The
three production adapters require explicit environment-only configuration and
are absent when credentials are missing.

## Security and human agency

The reviewed live adapters use fixed HTTPS endpoints, disabled redirects, and
environment-only allowlists; there is no request-controlled direct URL fetch
surface.  Provider/model content is bounded untrusted data, never system
instructions.  Email rendering escapes content and destinations are server
configuration only.  Errors are safe-code summaries and tests prevent secret
material from persistence or output.

The deterministic acceptance test proves the monitoring path creates a
ResearchItem in `candidate` status but creates no Evidence, ModelSpec,
ModelRun, or HumanForecast.  Notifications do not acknowledge alerts.  The
existing explicit evidence/model/forecast routes remain the only paths across
those consequential boundaries.

## Operational checklist

- Scheduler and monitoring worker use the persistent job queue and bounded
  backoff; notification work is independently persistent and observable.
- `/health` indicates process liveness; `/ready` performs a safe database
  probe without exposing connection errors.
- Logs contain IDs, counts, statuses, and safe failure codes, enabling checks
  for scheduler/worker activity, queued jobs, last monitoring success,
  provider failures, notification retries, and database health.
- PostgreSQL dump and restore commands are in `docs/operations.md`.

## Release-candidate determination

**V1.0 RELEASE CANDIDATE: YES.**

The required credential-free regression, local PostgreSQL proof, deterministic
acceptance coverage, and backup/restore drill all passed. Live provider smoke
tests remain explicitly deferred because credentials are absent; this is not a
release blocker because the adapters, safe configuration behavior, and
credential-free contract/integration paths are covered.

No live credential is required for this determination if adapters remain fully
implemented/tested and their absence is disclosed, but credential-free status
does not replace the required local regression and PostgreSQL evidence.

# Stage 2 Task 5 — Reliability and Production Readiness

## Scope and invariants

Harden the existing modular-monolith, PostgreSQL-backed queue without changing the
human approval boundary.  Workers only create monitoring, research, attention, and
delivery records; they never approve evidence, run models, modify forecasts, or
write Decision Journal entries.

## Execution plan

1. Add centralized UTC scheduling and retry policy helpers.  Deadline-based cadence
   applies only to configurations without an explicit user interval; disabled
   monitoring remains disabled.
2. Make scheduler scans restart safe through existing schedule-window idempotency;
   add stale-running lease recovery with bounded retry transitions.
3. Use the generic PostgreSQL-aware claim path for both monitoring and notification
   workers, and make notification attempt/job outcomes agree after transient and
   permanent provider failures.
4. Add provider-safe error classification, deterministic staged backoff, concise
   JSON structured operational logs, and internal queue/monitoring status.
5. Extend health with database readiness checks; keep startup additive and
   non-destructive.
6. Pin the above with focused SQLite tests and a PostgreSQL runtime concurrency
   suite that starts two independent claimers against Docker PostgreSQL.
7. Verify backend, frontend, E2E, local services, security boundaries, schema, and
   documentation.  Generated reports and databases are removed only after use.

## Operational notes

`DATABASE_URL` selects PostgreSQL in deployed environments.  The fake notification
provider is a deterministic test/local dependency and must be supplied explicitly
to a worker; it is not a live delivery integration.  All persisted timestamps use
UTC-aware values; comparisons normalize legacy SQLite values to UTC.

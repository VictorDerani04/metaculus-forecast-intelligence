# Metaculus Forecast Intelligence v1.0.0

**Release date:** 2026-09-28

## Architecture and supported capabilities

V1 is a private, single-user FastAPI and PostgreSQL application with a Next.js
frontend. It supports owned competition/question tracking, explicit human
forecasts, candidate research and human-approved evidence, advisory Copilot
context, versioned transparent models, audit/history, monitoring, source
intelligence, event clustering/corroboration, alerts, digests, and configured
notification delivery.

The production processes are the API, frontend, scheduler, monitoring worker,
and notification worker. Workers use persistent jobs, leases, bounded retry,
and structured safe-error logging. See `operations.md` for startup, recovery,
and worker invocation details.

## Required production configuration

Set `APP_ENV=production`, a PostgreSQL `DATABASE_URL`, a unique non-placeholder
`SESSION_SECRET` of at least 32 characters, `COOKIE_SECURE=true`, one private
owner email/password, and the exact `WEB_ORIGIN`. Production startup rejects a
SQLite or malformed PostgreSQL URL, missing/blank/default/short session secrets,
and forces Secure session cookies. `.env.example` lists all variable names; do
not commit secrets.

Live integrations are optional server-side configuration: Tavily research uses
`WEB_SEARCH_API_KEY`; OpenAI-compatible classification requires
`AI_CLASSIFIER_PROVIDER=openai` and `OPENAI_API_KEY`; Resend delivery requires
`NOTIFICATION_PROVIDER=resend`, sender/destination, and API key. All use fixed
allowlisted endpoints and bounded timeouts. Missing credentials safely disable
the corresponding production adapter. LIVE RESEARCH, LIVE AI, and LIVE
NOTIFICATION smoke tests were NOT EXECUTED — CREDENTIALS NOT CONFIGURED.

## Operational verification

`/health` reports process liveness and `/ready` performs a safe database probe.
The local Docker PostgreSQL backup/restore drill documented in `operations.md`
restored 27 public tables into a temporary database and removed only the
temporary database and dump afterward.

Release-gate verification passed: 265 backend tests, 2 expected PostgreSQL skips
in the default suite, 53 frontend tests, TypeScript check, production build, one
Playwright E2E scenario, and 2 PostgreSQL concurrency tests. The
deterministic evaluation corpus is a diagnostic regression detector, not a
statistically representative live-performance measure.

## Human-control guarantees and limitations

The system never autonomously approves Evidence, changes a Human Final
Forecast, runs a model, writes a Decision Journal entry, or submits to
Metaculus. Monitoring creates candidate research and attention artifacts only.

V1 is private/single-user; it has no public signup or multi-user collaboration.
Live provider credentials require manual deployment configuration and are not
included in this release. Notification idempotency is provider-assisted: a
crash after an external send cannot claim universal exactly-once delivery.

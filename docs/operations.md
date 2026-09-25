# Stage 2 operations

## Local processes

Start PostgreSQL with `docker compose up -d postgres`, then set
`DATABASE_URL=postgresql+psycopg://forecast:forecast@localhost:5432/forecast_intelligence`.
Start the API from `apps/api` with `py -m uvicorn app.main:app --reload`; start the
web app from `apps/web` with `npm.cmd run dev`.

The scheduler calls `enqueue_due_monitoring_jobs(session, now)` periodically. A
worker calls `recover_stale_jobs(session_factory)` at startup and then invokes
`run_one_configured_monitoring_job(app)` or `run_one_notification_job` with the
application-owned registries. Provider calls happen outside database transactions.

`GET /health` confirms process liveness. `GET /ready` runs a safe database probe and
returns `503` with a generic error if the database cannot be used. Logs are JSON
events and intentionally contain IDs, status, counts, and safe error codes only.

## Safety and configuration

Use environment variables for `DATABASE_URL`, `SESSION_SECRET`, `WEB_ORIGIN`,
`COOKIE_SECURE`, `PRIVATE_USER_EMAIL`, and `PRIVATE_USER_PASSWORD`. Do not use the
fake notification provider for a real delivery channel: it is a deterministic local
adapter that must be explicitly passed to a notification worker. Missing or
unallowlisted providers fail without sending anything.

Monitoring is only enabled by an owner. With no explicit interval it uses deadline
cadence: >90 days 12h, 30–90 days 6h, 7–30 days 3h, and <=7 days hourly. An explicit
interval remains user-owned. Worker leases expire after 15 minutes and use bounded
1m/5m/15m/1h backoff; retries stop at `max_attempts`.

Set `WEB_SEARCH_API_KEY` to enable the allowlisted Tavily web-search adapter. It
uses the fixed HTTPS endpoint `https://api.tavily.com/search`, a 10-second default
timeout (`WEB_SEARCH_TIMEOUT_SECONDS`), bounded results, and no redirects. Without
the key, the live provider is absent; fake providers remain deterministic test-only
dependencies. There is no arbitrary URL-fetch endpoint.

To enable live AI attention classification, set all of
`AI_CLASSIFIER_PROVIDER=openai`, `OPENAI_API_KEY`, and optionally the allowlisted
`AI_CLASSIFIER_MODEL=gpt-4o-mini` plus `AI_CLASSIFIER_TIMEOUT_SECONDS` (1–60,
default 10). The classifier has a fixed OpenAI-compatible HTTPS endpoint and a
fixed model allowlist; user input and provider content cannot select providers,
models, prompts, tools, or URLs. Without this explicit configuration the live
classifier is unavailable and processing a nonempty live provider result retries
without routing it. Deterministic fake classifiers are test/offline-E2E
dependencies only and are never the production default. Persisted Finding audit
data contains bounded classifications, confidence, direction, timestamp, provider,
model, and schema version; it never contains keys, raw prompts, raw provider
responses, or reasoning traces.

## Verification

Run API tests with `py -m pytest` (or the project virtual environment), web tests
with `npm.cmd test`, typecheck with `npm.cmd run typecheck`, build with
`npm.cmd run build`, and browser tests at repository root with `npm.cmd run e2e`.
For the mandatory PostgreSQL proof, start Compose and run:

`POSTGRES_TEST_DATABASE_URL=postgresql+psycopg://forecast:forecast@localhost:5432/forecast_intelligence py -m pytest apps/api/tests/test_postgres_concurrency.py -q`

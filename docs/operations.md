# Stage 2 operations

## Local processes

Start PostgreSQL with `docker compose up -d postgres`, then set
`DATABASE_URL=postgresql+psycopg://forecast:forecast@localhost:5432/forecast_intelligence`.
Start the API from `apps/api` with `py -m uvicorn app.main:app --reload`; start the
web app from `apps/web` with `npm.cmd run dev`.

## Production configuration and process startup

Set `APP_ENV=production`, a PostgreSQL `DATABASE_URL`, a strong
`SESSION_SECRET`, `COOKIE_SECURE=true`, private owner credentials, and the exact
HTTPS `WEB_ORIGIN`. Production startup rejects SQLite and the default
development session secret. There is no public signup. Keep all secrets in the
deployment environment; `.env.example` contains names and safe example values
only.

Start the API with `py -m uvicorn app.main:app --host 0.0.0.0 --port 8000` and
the frontend with `npm.cmd run start`. Run the scheduler loop, monitoring
worker, and notification worker as separate long-lived processes that call the
application-owned scheduler/worker entry points described below. They need no
source edits or request-provided provider configuration; missing live-provider
credentials leave the corresponding registry empty and jobs fail safely.

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

## Source intelligence safety

Findings receive a normalized source identity, bounded source type, and a
conservative reliability label. These labels are not universal truth scores and
do not use political ideology. Official sources are authoritative only for
their own announcements and actions. Unknown or ambiguous identity stays
`unknown`, never upgraded by a classifier.

Event clustering is deterministic, user- and question-scoped, and requires
high overlap in both headline and detail. Ambiguous reports remain separate.
Clusters preserve every finding link and corroboration counts; recognized wire
bylines share a reporting origin so syndicated copies do not add independent
confirmation. Later same-event copies enrich corroboration without creating a
duplicate alert or digest item.

Security review: provider and AI text (names, headlines, snippets, and
metadata) is bounded data, never an instruction. No content selects a prompt,
model, URL, tool, or command. Live acquisition uses fixed HTTPS endpoints with
no arbitrary URL fetch or redirects, so there is no direct SSRF surface. Keys
remain environment-only, safe errors omit headers and bodies, raw HTML is not
rendered, and no eval, exec, subprocess, dynamic import, or unsafe
deserialization path handles provider content. Cluster reads and writes filter
both `user_id` and `question_id`.

## Production notification email

Real delivery is disabled unless `NOTIFICATION_PROVIDER=resend` and all of
`NOTIFICATION_FROM_EMAIL`, `NOTIFICATION_TO_EMAIL`, and
`NOTIFICATION_API_KEY` are configured server-side. The configured destination
is private v1.0 configuration, never a request parameter or frontend value.
The adapter uses the fixed Resend HTTPS endpoint, a 1–30 second timeout,
escaped HTML plus text fallback, and the `NotificationAttempt` idempotency key.
Missing or invalid configuration leaves the production registry empty and
delivery fails safely. `fake` is a test dependency, not a production registry
selection. Start the normal background worker with the configured application
registry; it claims `deliver_notification` jobs and obeys the existing
bounded 1/5/15/60-minute retry policy for timeout, rate-limit, transport, and
5xx failures. Authentication, destination, and malformed provider response
failures are recorded without credentials or provider response bodies.

For a low-volume smoke test, configure a verified private destination, create
one test alert or digest, run one notification worker job, and check that the
attempt has an external message ID while the alert remains unacknowledged.
Never put credentials in source, request bodies, or logs. Disable live delivery
by unsetting `NOTIFICATION_PROVIDER`. Provider-level idempotency limits the
crash-after-send window because success is persisted after the provider call;
without an external provider guarantee, exactly-once delivery cannot be
claimed.

## Verification

Run API tests with `py -m pytest` (or the project virtual environment), web tests
with `npm.cmd test`, typecheck with `npm.cmd run typecheck`, build with
`npm.cmd run build`, and browser tests at repository root with `npm.cmd run e2e`.
For the mandatory PostgreSQL proof, start Compose and run:

`POSTGRES_TEST_DATABASE_URL=postgresql+psycopg://forecast:forecast@localhost:5432/forecast_intelligence py -m pytest apps/api/tests/test_postgres_concurrency.py -q`

## PostgreSQL backup and recovery

Use a PostgreSQL client with the same host, database, and role as the running
application.  Do not place a password in a shell history; provide it through a
local credential mechanism such as `PGPASSWORD` for the one command or a
protected `.pgpass` file.

Create a compressed, portable dump:

`pg_dump --format=custom --no-owner --file forecast_intelligence.dump forecast_intelligence`

Restore only into a deliberately created empty recovery database, never over
the running application database:

`createdb forecast_intelligence_recovery`

`pg_restore --clean --if-exists --no-owner --dbname forecast_intelligence_recovery forecast_intelligence.dump`

Verify the restored database with a read-only health query before any recovery
decision.  Production backup schedules, retention, encryption, and off-host
storage remain deployment responsibilities; this repository documents the
safe local dump/restore procedure but does not operate a backup service.

### Local Docker drill (executed 2026-09-28)

The following commands were exercised against the local Compose container. They
create and remove only `forecast_intelligence_restore_test`; the primary
`forecast_intelligence` database is never reset or overwritten:

`docker exec metaculus-forecast-intelligence-postgres-1 pg_dump -U forecast --format=custom --no-owner --file /tmp/stage35-forecast-intelligence.dump forecast_intelligence`

`docker exec metaculus-forecast-intelligence-postgres-1 createdb -U forecast forecast_intelligence_restore_test`

`docker exec metaculus-forecast-intelligence-postgres-1 pg_restore -U forecast --no-owner --dbname forecast_intelligence_restore_test /tmp/stage35-forecast-intelligence.dump`

`docker exec metaculus-forecast-intelligence-postgres-1 psql -U forecast -d forecast_intelligence_restore_test -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';"`

The restored schema contained 27 public tables. After verification, clean up
only the temporary artifacts:

`docker exec metaculus-forecast-intelligence-postgres-1 dropdb -U forecast forecast_intelligence_restore_test`

`docker exec metaculus-forecast-intelligence-postgres-1 rm -f /tmp/stage35-forecast-intelligence.dump`

# Stage 3.3 Source Intelligence Implementation Plan

> Historical checkpoint: this document records the implemented Stage 3.3
> behavior and its verification. It is not authorization to change the feature.

**Goal:** Preserve conservative, deterministic source intelligence and
event-level corroboration for monitoring findings without changing human
forecasting, approval, or external-submission workflows.

**Architecture:** Source assessment is a deterministic transformation of a
finding URL and bounded publisher metadata. Persistence attaches each Finding
to at most one user- and question-scoped EventCluster, then refreshes cluster
corroboration counts. Alert routing recognizes links already belonging to the
same cluster so later copies enrich the event instead of creating duplicate
attention.

**Tech stack:** Python, FastAPI, SQLAlchemy, SQLite test databases, and
PostgreSQL runtime verification.

## Implemented behavior

### Source identity and reliability

- A source URL is normalized to a lowercase hostname with a leading `www.`
  removed. A missing or unparsable host remains `None`.
- Source types are bounded to `official`, `wire_service`, `news_or_web`, and
  `unknown`.
- Reliability is deliberately conservative: recognized official and wire
  domains receive `high`; all other recognized domains and ambiguous identities
  receive `unknown`. No political or universal truth score is inferred.
- Official status means only that the source is authoritative about its own
  announcements and actions. A recognized wire source still requires
  corroboration for claims.
- `Finding` persists normalized source, source type, reliability level and
  reason, and a reporting origin. Wire bylines are recognized only through the
  small deterministic Reuters, Associated Press, and AFP marker set.

### Event clustering and corroboration

- `EventCluster` stores its user and question owner, canonical summary,
  timestamps, total findings, normalized-source count, independent-source
  count, official/wire presence, and high-reliability-source count.
- `FindingEventLink` records a Finding-to-cluster link, the bounded match score,
  and the match reason. One Finding can be linked only once.
- A report may join an existing cluster only within the same question and user.
  The deterministic matcher requires at least 60% title-token overlap, at least
  three common substantive title tokens, and at least two common summary tokens.
  Ambiguous or merely related reports remain separate.
- Corroboration counts distinct normalized sources and distinct reporting
  origins. A syndicated wire copy sharing a recognized reporting origin does
  not become a new independent source.
- When a material or critical finding is routed, an earlier alert from the same
  user-scoped cluster suppresses a duplicate alert; a distinct question retains
  its own alert even for a same-looking event.

### Ownership, schema, and compatibility

- Cluster lookup filters `id`, `user_id`, and `question_id`, returning the
  existing 404-style not-found behavior for an out-of-scope cluster.
- The link table has composite foreign keys from `(finding_id, user_id,
  question_id)` to Finding and from `(event_cluster_id, user_id, question_id)`
  to EventCluster. Corresponding composite unique constraints on the parent
  tables make those ownership and question boundaries enforceable by
  PostgreSQL.
- Startup keeps compatibility upgrades additive. For PostgreSQL it adds the
  required composite unique and foreign-key constraints when absent; it also
  adds new Finding source-intelligence columns where necessary.

### Safety and human agency

- Provider text, source names, headlines, summaries, and metadata are data,
  never instructions. They cannot select a prompt, model, URL, tool, or
  command.
- The feature does not fetch arbitrary URLs, create or approve Evidence,
  approve ResearchItems, mutate a Human Final Forecast or ModelSpec, initiate
  ModelRuns, alter a DecisionJournal, or submit to Metaculus.
- Source intelligence augments finding provenance and attention routing only;
  probability layers and approved evidence remain separate.

## Evaluation and verification strategy

- Unit and service tests cover bounded source assessment, deterministic
  same-event matching, prompt-injection content, persisted provenance,
  corroboration totals, syndicated-copy independence, and duplicate alert
  suppression.
- Isolation tests prove that a user cannot read or enrich another user's
  cluster, source/corroboration data remains private, same-looking events from
  different questions use separate clusters, and question-scoped duplicate
  suppression does not suppress the other question.
- Schema tests assert the composite ownership/question foreign-key structure.
- PostgreSQL runtime tests verify additive EventCluster constraints and the
  existing concurrent `SKIP LOCKED` job claimer behavior.

## Final verification expectations

- `py -m pytest` completes without a backend stall and passes the private-core
  probability/evidence separation regression.
- With `POSTGRES_TEST_DATABASE_URL` configured, run
  `py -m pytest apps/api/tests/test_postgres_concurrency.py -q` and confirm
  both the EventCluster scope-constraint test and `SKIP LOCKED` regression
  pass.
- Preserve already-green frontend test, typecheck, build, and E2E results when
  no frontend or API-contract change is made.
- Before handoff, run `git diff --check`, `git status --short`, and
  `git diff --stat`; do not stage or commit the checkpoint.

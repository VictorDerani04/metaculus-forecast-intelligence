# Stage 2 Task 2: External Research Pipeline Implementation Plan

**Goal:** Persist, normalize, exactly deduplicate, classify, and expose monitoring discoveries as human-reviewable ResearchItems without crossing any consequential approval boundary.

**Spec:** `docs/superpowers/specs/2026-09-20-stage-2-autonomous-monitoring-architecture.md`

## Constraints

- Task 2 ends at persisted Findings and unapproved `ResearchItem` candidates; it creates no Evidence, alerts, digests, forecasts, model activity, or journal entries.
- Provider text is untrusted data and is neither executed nor passed as instructions. No arbitrary URL retrieval is added.
- Use database uniqueness for provider cursors and exact-finding identity. Keep Task 1 claim architecture unchanged.
- Candidate policy: only relevant findings with `material` or `critical` materiality create one monitoring-origin ResearchItem. All other classifications remain inspectable Findings.
- Leave all work unstaged and uncommitted.

## Tasks

1. Add `RawFinding`, `Finding`, and `ProviderCursor` models plus enum-backed classification/status fields and database uniqueness constraints. Write RED tests for ownership, cursor uniqueness, exact identity, and unapproved candidate provenance.
2. Add pure normalization helpers: whitespace/domain/timestamp normalization, HTTP(S)-only conservative URL canonicalization, SHA-256 fingerprinting, and typed relevance/materiality contracts. RED tests cover tracking URLs, rejected schemes, deterministic fingerprints, malformed outputs, and fake classifiers.
3. Add an ingestion service that persists raw observations, normalizes and deduplicates them transactionally, creates eligible unapproved `ResearchItem`s once, and advances a cursor only after persistence. RED tests cover retry/idempotency/counter behavior.
4. Extend the worker to invoke the ingestion service after provider fetches, preserve short transaction boundaries, and record truthful monitoring counters/failures. Test no consequential mutations.
5. Add owned, read-only `GET /questions/{id}/findings` and only a compact monitoring summary UI if it can expose truthful counts without redesigning the Research Inbox.
6. Run complete backend/frontend/type/build/E2E suites, security scan, and git hygiene. Report live providers and PostgreSQL runtime as deferred/not verified when applicable.

## Review Focus

- Tracking-parameter URL variants must converge without over-canonicalizing different resources.
- A crash or retry cannot advance cursors or duplicate candidates before a successful database transaction.
- Classifier failures preserve raw/normalized findings for review rather than silently dropping them.
- Provider and finding reads remain strictly user/question scoped.
- Worker code cannot invoke any consequential service; only `ResearchItem` creation is allowed.

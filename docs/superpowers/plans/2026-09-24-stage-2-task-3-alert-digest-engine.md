# Stage 2 Task 3: Alert and Digest Engine

## Goal
Route persisted Task 2 Findings deterministically into idempotent internal AlertEvents or DigestItems, assemble UTC daily Digests, and expose owner-scoped review UI without delivery or consequential forecast actions.

## Tasks
1. Add AlertEvent, DigestItem, and Digest models with database uniqueness, additive compatibility upgrades, and ownership constraints.
2. Add routing and digest services: `digest` findings become DigestItems; `material`/`critical` become alerts; all routing runs in the finding persistence transaction before cursor advancement.
3. Add owner-scoped alert lifecycle and digest APIs; audit only explicit alert state actions.
4. Add compact alert/digest components and API clients.
5. Add RED/GREEN coverage for routing, retry/idempotency, cursor rollback, lifecycle, digest periods/ownership, safety, and UI states; run full regressions and security scan.

## Decisions
- UTC period is `[00:00, 24:00)` and a `(user_id, period_start, period_end)` unique key makes generation idempotent.
- Routing is exclusive: irrelevant/uncertain do nothing; digest creates DigestItem; material/critical create AlertEvent.
- No notification delivery, provider fetch, model, evidence, forecast, or journal mutation is in scope.

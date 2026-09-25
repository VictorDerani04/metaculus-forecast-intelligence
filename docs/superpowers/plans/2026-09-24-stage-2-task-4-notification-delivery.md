# Stage 2 Task 4: Notification Delivery

## Goal
Deliver existing AlertEvents and generated Digests through an application-controlled
provider boundary without changing their attention semantics or any consequential
forecasting state.

## Plan
1. Add NotificationPreference and NotificationAttempt persistence, with source XOR,
   owner/source consistency, lifecycle fields, and idempotency constraints.
2. Add a typed allowlisted provider interface and deterministic fake provider.
3. Add a delivery service that respects preferences, queues BackgroundJobs, invokes
   providers outside database transactions, records safe results, and uses
   retry_wait after safe failures.
4. Add owner-scoped preference, history, and explicit alert/digest delivery APIs.
5. Add compact preference/history UI, API client functions, and RED/GREEN coverage.
6. Verify safety, full backend/frontend/E2E regressions, and repository hygiene.

## Decisions
- Only the in-process deterministic fake provider is implemented; no credentials,
  real recipients, or real delivery integration are introduced.
- Provider registry keys are application-owned and fixed. API callers never choose
  arbitrary providers or recipients.
- A successful logical source/channel/provider delivery is idempotent. Failures
  transition the same attempt to retry_wait; a later explicit delivery retries it.
- Digest delivered_at is updated only after a successful provider result. Alert
  lifecycle remains independent from delivery.

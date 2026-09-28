# Stage 3.4 Real Notification Delivery Implementation Plan

**Goal:** Send existing alert and digest attempts through an allowlisted production email provider without altering attention or forecasting state.

**Architecture:** Keep `NotificationAttempt` as the database idempotency record and use a fixed Resend HTTPS endpoint when explicit server configuration is complete. Rendering is application-owned HTML/text, and the provider receives the attempt idempotency key.

## Tasks

1. Add a fixed-endpoint `EmailNotificationProvider`, environment-only registry, and safe failure mapping.
2. Render escaped alert and digest text/HTML payloads and route configured email attempts through the existing worker lifecycle.
3. Preserve owner-scoped preferences, application/provider idempotency, retry backoff, and delivery-versus-acknowledgment separation.
4. Add contract, rendering, ownership, PostgreSQL, full backend, frontend, browser, and operations verification.

## Constraints

- No request-provided recipients, provider selection, credentials, or URLs.
- No automatic approval, evidence creation, forecast/model/journal mutation, or Metaculus submission.
- Provider errors and API payloads are secret-safe; templates escape untrusted text.

# Authentication Hardening Design

**Goal:** Make the existing FastAPI session-cookie sign-in flow deterministic for local development while retaining production-safe configuration and credentials.

## Decisions

- The API loads only the repository-root `.env` when present, without overriding already supplied process environment variables. Deployment variables therefore remain authoritative.
- Development seed reconciliation is opt-in through `SYNC_PRIVATE_USER_PASSWORD=true` and is rejected outside development. It may only update the configured seed account identified by its normalized email.
- Production startup can seed a missing configured user but never changes an existing user's password.
- Session expiration is an explicit `SESSION_MAX_AGE_SECONDS` configuration value. Login, current-user, and logout continue to use Starlette's signed `HttpOnly`, `SameSite=Lax` session cookie.
- The frontend classifies expected authentication, API-unavailable, server-configuration, and unexpected failures without showing backend internals. The form prevents concurrent submissions.

## Scope

The change adds environment loading, safe seed synchronization, a logout endpoint/client action, tests for the complete cookie lifecycle and settings, login error feedback, and root-level local-start instructions. It does not introduce another authentication provider or change ownership/authorization architecture.

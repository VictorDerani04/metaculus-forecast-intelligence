# Authentication Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make local sign-in configuration deterministic and prove the complete session lifecycle.

**Architecture:** Keep FastAPI session cookies and the existing private seeded user. Load root configuration without overriding deployment variables, use an explicit development-only synchronization switch, and surface safe typed frontend errors.

**Tech Stack:** FastAPI, Starlette sessions/CORS, SQLAlchemy, pytest, Next.js, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-03-authentication-hardening-design.md`

## Global Constraints

- Keep process environment values higher priority than `.env` values.
- Never synchronize an existing production password.
- Keep credentials and secrets out of source and logs.
- Preserve the existing FastAPI session-cookie architecture.

## Review Focus

- Production must reject password synchronization even when the environment flag is set.
- Login failures must not expose backend detail.
- A cookie must persist through a page refresh and be invalid after logout.
- Cross-origin localhost requests must include credentials and receive the exact configured origin.
- A changed development seed password must affect only the configured account.

### Task 1: Backend configuration and seed behavior

**Files:** `apps/api/app/main.py`, `apps/api/app/auth/seed.py`, `apps/api/tests/test_auth.py`, `.env.example`

- [ ] Add failing tests for root `.env` precedence, explicit expiry, and development-only seed password synchronization.
- [ ] Run the targeted tests and observe the expected failures.
- [ ] Implement deterministic root `.env` loading, explicit session age, and gated seed reconciliation.
- [ ] Re-run targeted backend tests.

### Task 2: Complete backend session lifecycle

**Files:** `apps/api/app/auth/routes.py`, `apps/api/tests/test_auth.py`

- [ ] Add a failing login → me → logout → me integration test and cookie/CORS assertions.
- [ ] Run it and observe failure because logout is absent.
- [ ] Add the minimal logout endpoint and verify session clearing.
- [ ] Re-run targeted tests.

### Task 3: Safe frontend authentication feedback

**Files:** `apps/web/lib/api.ts`, `apps/web/app/login/page.tsx`, `apps/web/tests/api.test.ts`, `apps/web/tests/login-page.test.tsx`, `apps/web/tests/login-integration.test.tsx`

- [ ] Add failing API-client and form tests for classified failures and in-flight disabling.
- [ ] Run web tests and observe expected failures.
- [ ] Implement safe error classification and accessible feedback.
- [ ] Re-run targeted web tests.

### Task 4: Browser proof and documentation

**Files:** `tests/e2e/private-core.spec.ts`, `docs/operations.md`, `.env.example`

- [ ] Extend browser coverage for refresh, logout, and the unauthenticated state.
- [ ] Run the browser test and observe the missing logout behavior.
- [ ] Update root-start instructions, credential synchronization/reset guidance, and 401 troubleshooting.
- [ ] Run the API, web, typecheck, build, and E2E quality checks.

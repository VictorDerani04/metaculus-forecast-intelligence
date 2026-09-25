# Stage 3.1 Live Research Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an allowlisted, configured live web-search adapter that feeds the existing monitoring ingestion pipeline.

**Architecture:** A Tavily-compatible HTTPS adapter accepts only application-owned question context, creates bounded provenance-bearing result dictionaries, and exposes safe `ProviderFailure` codes. The provider registry maps logical `web` to this adapter only when explicit configuration exists; deterministic fakes remain test-only.

**Tech Stack:** FastAPI, SQLAlchemy, httpx, pytest MockTransport.

**Spec:** `docs/superpowers/specs/2026-09-20-stage-2-autonomous-monitoring-architecture.md`

### Task 1: Provider contract and registry

**Files:** Create `apps/api/app/monitoring/providers/live.py`, modify `apps/api/app/monitoring/providers/__init__.py`, test `apps/api/tests/test_live_provider.py`.

- [ ] Write MockTransport tests for success, empty responses, malformed payloads, 401, 429, timeout, and 5xx.
- [ ] Implement deterministic query construction, bounded result mapping, and safe failure codes.
- [ ] Build an environment-only allowlisted registry; missing credentials omit the live adapter.
- [ ] Run focused tests and the backend regression.

### Task 2: Operational integration

**Files:** Modify `apps/api/app/monitoring/worker.py`, `docs/operations.md`.

- [ ] Treat rate limiting as retryable in the existing worker failure taxonomy.
- [ ] Document fixed HTTPS endpoint, environment variables, fake-provider behavior, and credential-free smoke-test limitation.
- [ ] Run full API, web, browser, PostgreSQL, and diff verification.

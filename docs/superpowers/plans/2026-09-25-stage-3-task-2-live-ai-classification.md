# Stage 3.2 Live AI Classification Implementation Plan

**Goal:** Add a configured, structured-output AI classifier while preserving fake classifiers and Task 2 routing.

**Architecture:** An OpenAI-compatible fixed endpoint adapter builds a bounded untrusted-content payload, validates strict JSON into existing domain result types, and is selected only through an environment allowlist. Failures return safe retryable codes; persisted Finding fields remain the routing record.

### Tasks

1. Add RED contract tests for structured relevance/materiality, injection delimiters, malformed output, and HTTP failure mapping.
2. Implement a fixed-endpoint OpenAI-compatible adapter and strict bounded schemas; retain fakes.
3. Add an allowlisted environment registry and worker wiring; document missing-credential behavior.
4. Run backend, frontend, browser, PostgreSQL, and diff verification.

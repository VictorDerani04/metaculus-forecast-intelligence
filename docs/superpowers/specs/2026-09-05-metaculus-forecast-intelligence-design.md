# Metaculus Forecast Intelligence — Product & Architecture Design

**Status:** Design baseline for user review  
**Date:** 2026-09-05  
**Product:** Private-first hosted forecasting intelligence application  
**Initial competition:** Metaculus Cup Fall 2026  
**Relationship to Forecasting Academy:** None. This is a new standalone product and does not reuse the Academy product, UI, state, or curriculum.

---

## 1. Product Goal

Build a private hosted web application that helps a human forecaster perform better in forecasting competitions by combining:

- question portfolio management,
- autonomous web/news monitoring,
- human-approved evidence,
- persistent natural-language AI collaboration,
- transparent quantitative modeling,
- probabilistic visualization,
- forecast decision journaling,
- attention prioritization,
- and post-resolution performance analysis.

The AI is a forecasting copilot, not an autonomous entrant. The final forecast always remains a human decision.

---

## 2. Core Product Rules

1. **Natural language is the primary interface.**
   The user should be able to talk to the system as they would talk to an expert forecasting analyst.

2. **Human approval controls consequential state.**
   AI may discover, summarize, classify, recommend, model, simulate, challenge, and alert.
   It may not silently:
   - approve evidence,
   - activate a model,
   - overwrite model assumptions,
   - or change the user's final forecast.

3. **Candidate research is not model evidence.**
   Research discovered by the AI enters a Research Inbox first.

4. **Four probability layers remain distinct.**
   The product always distinguishes:
   - Prior / Base Rate
   - Model Probability
   - Human Final Forecast
   - Metaculus Community Forecast, when available

5. **Every model is inspectable and versioned.**
   No black-box percentage. The user can inspect assumptions, inputs, formulas/logic, uncertainty, dependencies, provenance, sensitivity, model version, and change attribution.

6. **Every forecast change is auditable.**
   The system retains immutable forecast/update history.

7. **Single-user behavior in v1, multi-user architecture from day one.**
   Every user-owned domain object is scoped by `user_id`.

---

## 3. User Experience

### 3.1 Primary Navigation

The v1 application has five main areas:

1. **Competition Dashboard**
2. **Forecast Room**
3. **Research Inbox**
4. **Model Lab**
5. **Performance**

The application also provides a global AI command/chat surface that understands the user's current context.

### 3.2 Natural-Language Interaction

Examples of valid requests:

- “Research this question and tell me the most important variables.”
- “Find historical situations similar to this one.”
- “What model would you use here?”
- “Build the Bayesian model you recommended.”
- “Show me what would need to happen for this to reach 70%.”
- “Which assumption matters most?”
- “Why did the model move from 43% to 51%?”
- “The crowd is at 38% and I’m at 55%. Investigate why.”
- “Something about this model feels too dependent on polls. Check it.”
- “Which three questions deserve my attention today?”

The AI is context-aware. Inside a Forecast Room it can access permitted context for that forecast without requiring the user to restate it.

---

## 4. Metaculus Integration

### 4.1 Primary Import Flow

The user pastes a Metaculus question URL.

The system attempts to import, where technically and contractually permitted:

- question/post identifier,
- title/question text,
- resolution criteria,
- question type,
- close date,
- resolution date,
- outcome options/range/scaling,
- current user prediction if accessible,
- current Community Prediction if accessible,
- project/tournament metadata,
- relevant staff comments or updates if accessible.

The imported source record is kept separate from the application's analytical layer.

### 4.2 Fallback

If a field is unavailable:

- show it as unavailable rather than fabricating it,
- allow manual entry,
- preserve provenance,
- and do not block creation of the Forecast Room.

The product must work even when Community Prediction is unavailable.

### 4.3 Refresh

Imported fields that may change are refreshed periodically where access permits.

Historical snapshots are retained so the system can compare:

- Human Forecast
- Model Probability
- Community Forecast

over time.

### 4.4 Compliance Boundary

Metaculus integration is implemented through an adapter rather than being embedded throughout the product. The adapter must obey the current API authentication requirements, access restrictions, throttling, and Terms of Use.

No architecture decision assumes unrestricted access to Community Prediction.

---

## 5. Competition Dashboard

The Competition Dashboard is the morning command center.

Each active question should show at minimum:

- question title,
- close/deadline date,
- human probability,
- latest active-model probability,
- Community Prediction if available,
- human-vs-model divergence,
- human-vs-crowd divergence,
- last human update,
- last model run,
- new candidate research count,
- unresolved material alert count,
- forecast staleness,
- model uncertainty/sensitivity indicator,
- Attention Priority score.

### 5.1 Attention Priority

The system ranks questions using a transparent priority model that can include:

- deadline proximity,
- forecast staleness,
- material new evidence,
- unresolved alerts,
- human-crowd disagreement,
- human-model disagreement,
- model uncertainty,
- model sensitivity,
- expected value of additional research,
- and whether the question has never received an initial forecast.

The user can ask the AI why a question ranks highly.

---

## 6. Forecast Room

A Forecast Room is the complete workspace for one competition question.

It contains:

- imported Metaculus question and resolution criteria,
- human forecast,
- prior/base rate,
- crowd observation/history if available,
- active model,
- model history,
- causal drivers,
- research monitoring profile,
- Research Inbox for the question,
- Approved Evidence Ledger,
- scenarios,
- visual analysis,
- AI chat,
- change-my-mind conditions,
- decision journal,
- deadline/status,
- and post-resolution analysis.

### 6.1 Persistent Context

AI context is assembled from structured application data rather than relying only on chat history.

The AI should know, subject to authorization:

- the exact question,
- current resolution criteria,
- prior,
- user's forecast/update history,
- crowd observations,
- causal drivers,
- approved evidence,
- candidate evidence,
- active model and prior model versions,
- assumptions,
- prior model runs,
- charts,
- user notes,
- and relevant recent chat.

---

## 7. Autonomous Research & Monitoring

### 7.1 Monitoring Agent

Every active Forecast Room can have an autonomous monitoring profile containing:

- entities,
- causal drivers,
- search terms,
- official sources,
- indicators,
- geography,
- domains/topics,
- known data releases,
- and user-defined change-my-mind triggers.

The monitoring system can search public information proactively.

### 7.2 Research Candidate

Every discovered item starts as candidate research, with:

- title,
- URL/source,
- publisher/organization,
- publication timestamp,
- retrieval timestamp,
- source type,
- source credibility assessment,
- summary,
- novelty assessment,
- relevance assessment,
- likely direction of impact,
- likely magnitude,
- affected causal drivers,
- duplicate/correlation grouping,
- AI reasoning,
- and citations/provenance.

### 7.3 Evidence Approval States

Candidate research supports:

- **Approve**
- **Reject**
- **Defer**
- **Duplicate / Correlated**
- **Superseded**

Only **Approved** evidence may become an input to the active forecasting model.

### 7.4 Hybrid Alerts

Two delivery modes:

**Immediate alert**
- only for material/critical developments,
- explains why the item matters,
- identifies affected drivers,
- estimates likely direction/magnitude,
- and may show a counterfactual model-impact estimate without changing the active model.

**Daily intelligence digest**
- consolidates lower-priority relevant developments,
- deduplicates repeated coverage of the same underlying event,
- groups correlated information,
- and prioritizes what deserves review.

---

## 8. Evidence Ledger

Approved Evidence is immutable historical evidence with explicit provenance.

Each record stores:

- evidence ID,
- forecast ID,
- user ID,
- source/reference,
- original candidate research ID,
- approval timestamp,
- user decision,
- summary,
- causal drivers affected,
- direction,
- estimated strength,
- model-input mapping,
- dependency/correlation links,
- supersession links,
- and notes.

Evidence does not automatically change a model when approved. It only becomes eligible for model use.

---

## 9. Model Copilot

### 9.1 Authority

The AI may:

- decompose a question,
- identify reference classes/base rates,
- identify causal drivers,
- inspect available data,
- ask for missing information,
- recommend model families,
- propose 2–3 alternatives,
- explain trade-offs,
- recommend one,
- create an editable model specification,
- run approved or proposed models,
- test assumptions,
- detect double-counting,
- perform sensitivity/scenario analysis,
- compare human/model/crowd probabilities,
- and recommend high-value research.

The AI may not activate a proposed model without user approval.

### 9.2 Modeling Hierarchy

Default escalation:

**Base rate → simple Bayesian/driver model → scenario model → statistical model → simulation → ensemble**

The AI must prefer the simplest model justified by the evidence.

It may explicitly conclude:

> There is not enough information to justify a formal model yet.

### 9.3 Candidate Families

Initial model families:

- base-rate/reference-class,
- Bayesian likelihood-ratio updating,
- weighted causal-driver scorecard,
- conditional/scenario trees,
- Monte Carlo simulation,
- regression/classification,
- time series,
- survival/time-to-event/hazard,
- market-implied/base-rate approaches,
- ensembles/hybrids.

The initial implementation does not need every advanced family on day one, but the model contract must support them.

---

## 10. Model Specification & Versioning

A Model Spec includes:

- ID/version/parent version,
- forecast target,
- family,
- rationale,
- variables,
- units,
- evidence/input provenance,
- formulas or executable logic reference,
- priors,
- coefficients/weights,
- ranges/distributions,
- dependencies/correlations,
- scenarios,
- assumptions,
- validation/calibration metadata,
- warnings,
- created-by identity,
- timestamps.

A Model Run records:

- model version,
- exact inputs,
- approved evidence references,
- output probability/distribution,
- uncertainty interval,
- sensitivity output,
- warnings,
- reproducibility seed when relevant,
- runtime metadata,
- timestamp.

Model runs are never overwritten.

---

## 11. Model Lab

Three principal panels:

### Panel A — AI Model Copilot
Natural-language collaboration.

### Panel B — Model & Assumptions
Structured editable representation of the model, variables, evidence links, distributions, assumptions, coefficients, scenarios, and warnings.

### Panel C — Visual Analysis
Automatically selected visualizations tied to the active model version.

The user can edit the structured model directly or by natural language.

---

## 12. Visualization System

Required v1 visualization types:

1. **Probability History**
   - human
   - model
   - crowd
   - evidence/update annotations

2. **Probability / Outcome Distribution**
   - central estimate
   - uncertainty/tails
   - intervals

3. **Sensitivity / Tornado Chart**
   - identifies assumptions and drivers with greatest effect

4. **Evidence Impact**
   - approved evidence grouped by direction/magnitude
   - dependency/double-counting warnings

5. **Scenario Comparison**
   - pessimistic
   - base
   - optimistic
   - custom

6. **Causal Model Map**
   - evidence → variables/drivers → intermediate states → target event
   - correlation/dependency edges

Conditional visualizations include:

- time-series charts,
- Monte Carlo histograms/CDFs,
- scatterplots,
- regression diagnostics,
- calibration plots,
- conditional trees,
- survival/hazard curves,
- residual charts,
- driver-contribution charts.

Every AI-selected visualization exposes:

- “Why this chart?”
- source/model version
- assumptions represented
- timestamp

---

## 13. Forecast Update Workflow

1. New information is discovered or entered.
2. AI analyzes relevance and expected impact.
3. User approves/rejects/defers/correlates it.
4. Approved evidence enters the ledger.
5. Copilot identifies affected drivers/model inputs.
6. AI proposes an updated model version if warranted.
7. User reviews and approves model activation.
8. Model runs.
9. System shows old vs. new model probability and change attribution.
10. User independently sets or retains the Human Final Forecast.
11. If human/model differ materially, system requests a short rationale.
12. Immutable decision/update history is appended.

No step automatically changes the final human forecast.

---

## 14. Performance & Learning Analytics

The Performance area tracks:

- question coverage,
- time-to-first-forecast,
- stale forecast count,
- forecast/update cadence,
- question scores where available,
- Brier/log-score diagnostics where applicable,
- calibration,
- model-vs-human accuracy,
- model-vs-crowd comparisons where available,
- human override value,
- performance by domain,
- performance by model family,
- evidence source performance,
- probability movement attribution,
- research effort/value-of-information indicators,
- and postmortems.

This product does not include the Forecasting Academy curriculum.

---

## 15. Technical Architecture

### 15.1 Recommended Stack

**Frontend**
- Next.js
- React
- TypeScript
- charting/visualization library selected during implementation
- responsive desktop-first UI

**Backend API**
- Python
- FastAPI
- typed request/response contracts

**Database**
- PostgreSQL

**Modeling**
- Python
- NumPy
- pandas
- SciPy
- statsmodels / scikit-learn as needed
- optional probabilistic libraries later

**AI Orchestration**
- server-side LLM integration
- structured tool/function interfaces
- retrieval of forecast-scoped context
- explicit authorization boundary

**Background Work**
- job/worker system for monitoring, refresh, alerting, model tasks, digests

**Hosting**
- cloud-portable containerized deployment
- private production instance for v1

### 15.2 Service Boundaries

Logical modules:

- Auth/User
- Competition
- Metaculus Adapter
- Forecast
- Research/Monitoring
- Evidence
- AI Copilot
- Modeling
- Visualization Data
- Alerts/Digests
- Performance
- Audit

These may begin in one deployable backend, with module boundaries preventing later rewrite.

---

## 16. Multi-User-Ready Data Ownership

Even in single-user v1, user-owned tables contain `user_id`.

Examples:

- users
- competitions
- questions
- forecast_rooms
- human_forecasts
- forecast_updates
- monitoring_profiles
- research_items
- evidence
- evidence_dependencies
- causal_drivers
- model_specs
- model_versions
- model_runs
- scenarios
- crowd_observations
- chat_threads
- chat_messages
- alerts
- digests
- decision_journal
- postmortems

Authorization is enforced server-side, not only in the UI.

---

## 17. Authentication & Private Deployment

V1 behavior:

- one primary authorized human user,
- real authentication,
- no public signup,
- private production deployment.

The schema and authorization model must allow later:

- multiple accounts,
- account signup/invitations,
- per-user private forecasts,
- team/workspace sharing if desired,
- subscription/commercial layers if the product later evolves.

---

## 18. Security & Reliability

Minimum requirements:

- secrets only server-side,
- encrypted transport,
- hashed/managed credentials,
- authorization checks on every user-owned resource,
- audit logging for consequential actions,
- safe rendering of external research content,
- protection against prompt injection from retrieved web content,
- source provenance on AI research,
- retry/backoff for external integrations,
- idempotent background jobs,
- database backups,
- health checks,
- structured application logs.

External research is untrusted data, never system instruction.

---

## 19. Staged Delivery

### Stage 1 — Private Competition Core
- authentication,
- standalone Competition Dashboard,
- URL/manual question creation,
- Forecast Room,
- human forecast history,
- crowd snapshots when available,
- manual research/evidence,
- natural-language AI Copilot,
- model-spec contract,
- first transparent model engines,
- visualizations,
- decision journal,
- PostgreSQL persistence.

### Stage 2 — Autonomous Intelligence
- continuous research monitoring,
- hybrid alerting,
- daily digest,
- deduplication/correlation,
- automated Metaculus refresh where permitted,
- model-impact previews,
- monitoring profiles.

### Stage 3 — Advanced Modeling & Analytics
- advanced statistical/time-series/hazard models,
- richer ensembles,
- deeper validation,
- performance analytics,
- source/model-family evaluation,
- value-of-information tooling.

### Stage 4 — Multi-User Productization
- signup/invitations,
- account isolation,
- team/workspace options,
- operational/admin tooling,
- optional commercialization.

---

## 20. Initial Acceptance Criteria

A successful private v1 can demonstrate this complete workflow:

1. Sign in.
2. Paste a Metaculus question URL or manually create a question.
3. Open its Forecast Room.
4. Establish a prior/base rate.
5. Enter or discover candidate research.
6. Review and approve evidence.
7. Ask the Model Copilot which model to use.
8. Compare 2–3 model proposals.
9. Approve/build the selected model.
10. Run the model.
11. Inspect probability distribution, Model Map, sensitivity, scenarios, and history.
12. Compare Prior / Model / Human / Crowd.
13. Record a final human forecast with rationale.
14. Receive later relevant alerts.
15. Approve new evidence.
16. Re-run/update the model.
17. Inspect exactly why probability changed.
18. Retain or change the human forecast.
19. Review the full immutable history.
20. View portfolio priorities from the Competition Dashboard.

---

## 21. Explicit Non-Goals for v1

- Forecasting Academy curriculum or training exercises
- autonomous submission of forecasts to Metaculus
- automatic evidence approval
- automatic human-forecast changes
- unrestricted scraping that bypasses Metaculus access rules
- public social features
- multi-user signup UX
- fully autonomous forecasting bot behavior

---

## 22. Product Principle

The system should make the user a better-informed, more disciplined human forecaster.

It is not designed to replace judgment with a single AI probability. It is designed to make evidence, assumptions, models, uncertainty, disagreements, updates, and decisions visible and auditable.

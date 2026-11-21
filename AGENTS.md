# Amaanat - Binding Architectural & Agent Directives

> **STATUS**: PROTOTYPE ONLY (Hackathon Prototype, Not an Official Service)  
> **Source of Truth**: `docs/BLUEPRINT.md`  
> **Target Optimization**: `docs/RUBRICS.md`  

All agents and contributors working in this repository MUST strictly abide by these binding rules. No exceptions.

---

## 1. Absolute Human Supremacy & Fail-Closed Safety
- **AI never approves money or rejects a person.**
- The platform supports exactly **three exits**:
  1. `AUTO` (Approve onto a reversible hold, e.g., 60-second hold).
  2. `ASK` (Request one specific, cheap piece of missing evidence / clarification).
  3. `HUMAN` (Escalate to a human officer with an attached case hand-off packet).
- **Every exception, unhandled error, low confidence, or edge condition fails closed to `HUMAN`.**
- There is NO silent path and NO auto-rejection path.

---

## 2. Universal Consent Gateway
- **Every personal-data read goes through ONE consent-gate function (`verify_consent(...)`) that checks consent directly from the database at read time.**
- **No caching of consent decisions.** If a user withdraws consent, the very next request must immediately return `403 Forbidden`.
- Every consent check and consent withdrawal is logged in the tamper-evident audit trail.

---

## 3. Data-Driven, Versioned, Immutable Rules
- **Rules, thresholds, cost weights, required documents, and reason texts are data in versioned, immutable rule sets.**
- **No hard-coded numbers** (e.g. no hard-coded `0.80` or `0.95` magic numbers in business logic).
- All thresholds must be derived from the stated cost model and statistical risk bounds.
- When an admin updates a rule set, a new immutable version is published. Historic decisions must permanently link to the exact rule set version used at the time of evaluation.

---

## 4. Uncompromising Prototype Labelling
- **Every screen, dashboard, API header, and exported report must visibly show a `PROTOTYPE` label.**
- The user must never be misled into believing this is an official government service.
- Synthetic and mocked data only: **No real personal data (no real CNIC, real phone number, or real bank account), ever.**

---

## 5. Automated Verification & Test Integrity
- **Every module ships with automated tests.**
- Tests must be executed and their output confirmed before declaring a module or task "done".
- **Never delete or weaken a test to make it pass.** If a test fails, fix the underlying code or align the test with the specification in `docs/BLUEPRINT.md`.

---

## 6. Zero Metric Invention
- **Never invent or hard-code evaluation metrics.**
- Any accuracy, false-positive, false-alarm, or operational number shown in the UI, API, or README **must originate directly from an execution of our own evaluation harness (`/eval`)**.

---

## 7. Post-Commit Tamper-Evident Audit Logging
- **Write the audit entry only AFTER the request's database transaction is committed.**
- Audit entries must be hash-chained (`sha256(prev_hash + entry_data)`), append-only, and tamper-evident.
- If an operation fails or rolls back, a failure audit entry should reflect the outcome accordingly without corrupting the cryptographic hash chain.

---

## 8. Dual-Database Compatibility (Postgres & SQLite)
- **Production uses PostgreSQL; automated unit tests run on SQLite via `DATABASE_URL`.**
- All database models, queries, and Alembic migrations must work seamlessly on both PostgreSQL and SQLite (e.g., use JSON compatible serialization, generic UUID/DateTime representations, and avoid dialect-specific non-portable SQL).

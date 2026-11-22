# Project Amaanat (امانت)

> ⚠️ **PROTOTYPE ONLY**: Amaanat is a hackathon prototype developed for Hagrid's Hackathon (Coder's Cup '26, ACM FAST-NUCES Karachi). It is **not** an official government service. All identity, payment, telco, and data services are fully mocked. No real personal data is ever used.

---

## Mission
> *"We help a low-literacy citizen, alone or through a community helper on a shared phone, claim a mock government relief grant even though they cannot read the forms, have a weak signal, and are surrounded by fake 'relief payment' messages."*

---

## Core Principles & Guardrails (from `AGENTS.md`)
1. **AI Proposes, Rules Decide, Humans Own Risky Cases**: No AI model ever approves money or rejects a citizen.
2. **Three Exits Only**: Every claim terminates in `AUTO` (approved onto reversible hold), `ASK` (targeted single-question next-best evidence), or `HUMAN` (escalated with full context packet).
3. **Universal Consent Gate**: Every personal data read passes a runtime database check; withdrawal is instantaneous (immediate 403).
4. **Data-Driven Rules**: Thresholds, cost models, and policies are versioned immutable records.
5. **Offline-First Resilience**: Voice-and-icon interface, indexedDB local queue, and idempotent sync.
6. **Auditable & Explainable**: Dual-view decisions (Urdu plain explanation for citizens, cryptographic hash-chained trace for auditors).

---

## Monorepo Layout
```
/
├── api/             # FastAPI backend (Pydantic v2, SQLAlchemy 2, Alembic, pytest)
├── worker/          # Background worker (Postgres/async task processing, hold releases)
├── mocks/           # Standalone mock services (NADRA CNIC, Raast Payouts, Telco SMS)
├── web/             # Frontend PWA (React + TypeScript + Vite, Tailwind CSS)
├── eval/            # Evaluation harness, benchmark datasets & metrics calculation
├── docs/            # Problem Statement, Blueprint, and Rubrics
├── docker-compose.yml # Unified multi-container environment
├── AGENTS.md        # Binding architectural rules for agents and developers
└── README.md
```

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (optional for local multi-container run)

### Backend Setup (Windows & POSIX)
```powershell
# 1. Create and activate Python virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run automated tests (uses in-memory SQLite by default)
pytest
```

### Frontend Setup
```powershell
cd web
npm install
npm run dev
```

### Full Local Development (`scripts/dev.ps1`)
Runs the standalone public rail mocks (NADRA, Raast, Telco SMS), the FastAPI backend server, and the Vite frontend simultaneously:
```powershell
.\scripts\dev.ps1
```

### Seeded Credentials (Tenant `prd`)
Password for all demo accounts: `Demo@12345`
- Citizen: `citizen@prd.test`
- Helper: `helper@prd.test`
- Officer: `officer@prd.test`
- Admin: `admin@prd.test`
- Auditor: `auditor@prd.test`

---

## Evaluation & Limitations

### Evaluation Harness (`/eval`)
The evaluation harness (`eval/harness.py`) executes non-parametric isotonic calibration and risk-bounded threshold optimization over a 3,000-case synthetic dataset with exact Clopper-Pearson 95% binomial bounds.

### Known Limitations
1. **Simulated vs. Real Scorers in Batch Evaluation**:
   - `eval/harness.py` computes batch performance across 3,000 cases using **simulated component scores** derived from dataset metadata (income, family size, card clarity, and identity match) to allow fast, reproducible statistical calibration.
   - The **REAL AI scorers** (`RealIdentityResolver`, `RealDocumentReader`, OpenCV ELA/QR decoders, and anomaly rules) are executed during live claim evaluations (`POST /cases/{id}/evaluate`) and thoroughly verified in `api/tests/test_module6_ai_and_forensics.py`.
2. **Synthetic Data**: All CNICs, IBANs, phone numbers, and names are generated synthetically for Hagrid's Hackathon 2026. No real citizen data is ever collected or processed.
3. **Card Forgery Scope**: Document forensics (ELA, glare, blur, and boundary checks) are tuned to detect common alterations and QR tampering on standard Pakistani CNIC layouts.
4. **Urdu Model Nuances**: Dialectical variants in Roman-Urdu and spoken Urdu may occasionally require human officer review (failing closed).


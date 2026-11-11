# Data Assist (ClearData)

**Turn messy, ambiguous company spreadsheets into clean, auditable, stakeholder-ready analyses and interactive reports.**

Data Assist (working app name **ClearData**) is a full-stack data quality and stakeholder analytics platform built with **Next.js**, **FastAPI**, **Polars**, and **SQLAlchemy**. Teams upload raw CSV, TSV, or multi-sheet Excel files, automatically profile anomalies, and generate verified executive briefings, charts, spreadsheets, and boardroom-ready presentations—where **every reported number traces directly back to its source rows**.

---

## Why Data Assist?

Analysts spend most of their week fighting messy exports before they can present a single number to leadership. Traditional BI dashboards silently drop bad rows or hide mixed currencies (`$1,250` vs `€850`), while generic AI summaries frequently hallucinate figures.

ClearData enforces five core engineering principles:

1. **Immutable Raw Data:** Uploaded files and ingested source rows (`rows.raw_json`) are never overwritten. Versioned overlays (`cell_values` + `dataset_versions`) track effective values separately.
2. **Deterministic First, AI Second:** Exact Python/Polars logic handles ingestion, header detection, anomaly profiling, statistics, and guardrails; LLMs are reserved for narrative synthesis over verified metrics.
3. **Zero Silent Guessing:** Ambiguous dates (`01/15/2024` vs `MM/DD` vs `DD/MM`), mixed currency symbols, invalid numeric strings, and mixed rating scales (`5/5` vs `9/10` vs `"Satisfied"`) are flagged as explicit **Data Quality Caveats** instead of silently coerced.
4. **Verified AI Narratives:** Every numeric metric and ISO date cited by the LLM (`mock`, `openai`, `anthropic`, or `gemini`) is checked by a backend verifier before earning a **Backend-Verified Narrative** badge.
5. **Click-Through Source Row Lineage:** Click any KPI, chart bar/slice, or summary table row to open the **Source Row Lineage Drawer** and inspect the exact contributing (or excluded) source rows and raw-vs-effective diffs.

---

## Key Features (Implemented)

- **Workspaces & Role-Based Access Control (RBAC):** JWT authentication + bcrypt hashing with workspace roles (`admin`, `steward`, `stakeholder`, `contributor`).
- **Multi-Format Ingestion & Auto-Profiling:** Parses CSV, TSV (including UTF-8 BOM & semicolon delimiters), and multi-sheet `.xlsx` workbooks (auto-skipping title banner rows) using Polars and `openpyxl`.
- **Deterministic Issue Detection:** Surfaces missing values, null-like strings (`N/A`, `null`, `-`), numeric/date type violations, ambiguous date formats, leading/trailing whitespace, casing/label variants, and duplicate rows.
- **Virtualized Dataset Explorer:** High-speed TanStack Table v9 + `@tanstack/react-virtual` grid with server-side numeric-aware sorting, cursor pagination, search filtering, Column Profile Sidebar, and severity-tinted Issue Focus mode.
- **Stakeholder Analysis Engine:** Computes dataset readiness score (`0–100`), ranked KPI measures (`sum`, `mean`, `median`, `min`, `max`, `Q1`/`Q3`/`IQR`), safe exclusions for unparseable/mixed-scale columns, unambiguous time-series, categorical segment breakdowns, and pairwise Pearson correlations.
- **Interactive Report Builder & Presentation Mode:**
  - Auto-recommends curated templates (`Executive Sales`, `Survey Insights`, `Inventory Summary`, `General Summary`).
  - Add, edit, reorder, or remove blocks (`narrative`, `kpi`, `bar_chart`, `line_chart`, `area_chart`, `pie_chart`, `summary_table`, `data_quality`) and regenerate narratives on demand.
  - Toggle **Presentation View** (clean stakeholder read-only mode) or **Print / Save as PDF**.
  - **Export `.xlsx` Workbook:** Multi-sheet Excel export (*Executive Summary*, *Metrics & Charts Data*, *Source Data Audit*) with Excel formula-injection sanitization.

> **Roadmap Note:** Core Foundation (Phase 0), Dataset Ingestion/Profiling/Explorer (Phase 1), and Stakeholder Analysis & Interactive Report Builder (early Phase 3) are live today. Automated rule-engine cleaning transforms, low-confidence AI review queues (Phase 2), and comment/approval workflows (Phase 4) are specified in [`BUILD_PLAN.md`](BUILD_PLAN.md).

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS |
| **Grid & Charts** | TanStack Table v9 (`@tanstack/react-virtual`), Recharts |
| **Backend API** | Python 3.11, FastAPI, Pydantic v2 |
| **Data Engine** | Polars columnar engine, `openpyxl` (Excel import & `.xlsx` export) |
| **Database & ORM** | SQLAlchemy 2.0, Alembic migrations (local SQLite default or PostgreSQL 16) |
| **Background Jobs** | Unified queue (`JOBS_INLINE=true` in local dev, or Redis + RQ) |
| **AI Providers** | Swappable `LLMClient`: `mock` (offline deterministic), `openai`, `anthropic`, `gemini` |
| **Auth & Security** | JWT Bearer tokens, `bcrypt`, workspace/project/dataset/report RBAC |

---

## Quick Start for Public Demo (2 Minutes, No Docker Required)

The quickest way to run and demo Data Assist locally uses native Python + Node.js with automatic SQLite initialization and pre-seeded demo credentials.

### Prerequisites
- **Python 3.11** (`python --version`)
- **Node.js 20+** & **npm** (`node --version`)
- *(Optional)* **Docker & Docker Compose** for containerized PostgreSQL + Redis setup

### 1. Clone the Repository
```bash
git clone https://github.com/Tofuwho/Data-Assist.git
cd Data-Assist
```

### 2. Start the Backend API (Terminal 1)
By default in `development` mode, the API uses local SQLite (`apps/api/cleardata.db`), automatically runs Alembic migrations on startup, and seeds demo accounts if the database is empty.

**Windows (PowerShell):**
```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**macOS / Linux:**
```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

API endpoints & interactive docs:
- Health check: `http://localhost:8000/api/v1/health`
- Swagger / OpenAPI UI: `http://localhost:8000/api/v1/docs`

### 3. Start the Frontend Web App (Terminal 2)
```bash
cd apps/web
npm install
npm run dev
```

Open **[http://localhost:3000](http://localhost:3000)** in your browser.

---

## Public Demo Walkthrough

### Step 1 — Sign In (Pre-Seeded Local Dev Accounts)
When `ENVIRONMENT=development` and the database has no users, ClearData automatically seeds two demo accounts:

| Role | Email | Password | Seeded Workspace(s) |
|---|---|---|---|
| **Admin** | `admin@cleardata.io` | `Password123!` | `Acme Operations` (`admin`) |
| **Steward** | `steward@cleardata.io` | `Password123!` | `Global Data Office` (`admin`), `Acme Operations` (`steward`) |

- On `http://localhost:3000`, click **Quickfill Admin** (or **Quickfill Steward**) and then **Sign In**.
- Or switch to **Create Account** to register your own user and workspace.

### Step 2 — Upload Sample Messy Datasets (`fixtures/`)
Create a new project (e.g., `Q1 Executive Review`), open it, and upload any of the sample files in [`fixtures/`](fixtures):

1. **`fixtures/messy_sales.csv`** *(Recommended first demo)*:
   - Contains mixed currencies (`$1,250.00`, `3400 USD`, `€850.00`, `invalid_amount`), mixed date notations (`2024-01-15`, `01/15/2024`, `16-Jan-2024`), inconsistent region casing (`NY`, `New York`, `N.Y.`), and missing fields.
2. **`fixtures/survey_results.csv`**:
   - Contains mixed rating scales (`5/5`, `9/10`, `"Satisfied"`, `4`, `"Very Satisfied"`) and department variants (`eng`, `Engineering`, `MARKETING`).
3. **`fixtures/inventory.xlsx`**:
   - Multi-sheet Excel workbook (`Warehouse_North`, `Warehouse_South`) with leading title banner rows before the table headers.

### Step 3 — Inspect Data Quality in Dataset Explorer
1. Wait a moment for the dataset status badge to switch to **Ready**.
2. Click **Explore Dataset** to open the virtualized data grid.
3. Click the **`Date`** or **`Amount`** column header to open the **Column Profile Sidebar** (distributions, top values, format breakdown, and ambiguity flags).
4. Click an anomaly in the **Issues** panel (for example `type_violation`, `mixed_formats`, or `label_variants`) to filter and highlight affected rows/cells.

### Step 4 — Generate & Audit a Stakeholder Report
1. Click **Generate Stakeholder Report** inside Dataset Explorer (or **Analyze** from the Project page).
2. Choose **Auto-Recommend (Smart Template)** (or select `Executive Sales & Revenue Brief`, `Survey & Feedback Insights`, `Inventory & Operations Summary`, or `General Stakeholder Summary`) and click **Generate Report**.
3. Review:
   - **Executive Briefing:** Grounded narrative with **Backend-Verified Narrative** citation badge.
   - **KPIs & Charts:** Totals alongside explicit counts of any excluded unparseable rows (`__excluded__`), plus **Data Quality & Methodology Caveats**.
   - **Click-Through Lineage:** Click any KPI card, bar/slice in a chart, or summary row to open the **Source Row Lineage** drawer and inspect exact underlying rows.
4. Click **Add Block** to customize metrics or chart types, switch to **Presentation View** for stakeholder readout, and click **Export XLSX** or **Print / PDF** to share.

---

## How to Test (Automated & Manual Verification)

### Backend Tests & Linting (`apps/api`)
Activate the backend virtual environment first (`.\.venv\Scripts\Activate.ps1` on Windows or `source .venv/bin/activate` on macOS/Linux):

```bash
cd apps/api

# 1. Lint & import order check
ruff check .

# 2. Run the full test suite (42 tests across 11 suites)
pytest
```

> **Test Database Behavior:** `pytest` automatically connects to PostgreSQL when `DATABASE_URL` points to a reachable Postgres server (matching GitHub Actions CI), or gracefully falls back to in-memory SQLite with `PRAGMA foreign_keys=ON` for zero-setup offline testing.

#### What the Backend Test Suites Cover
- [`test_auth_and_workspaces.py`](apps/api/tests/test_auth_and_workspaces.py) — registration, login, wrong-password `401`, `/auth/me`, workspace & project RBAC.
- [`test_startup_seed.py`](apps/api/tests/test_startup_seed.py) — default SQLite config fallback, production `SECRET_KEY` startup guard, and idempotent dev demo user seeding.
- [`test_models.py`](apps/api/tests/test_models.py) — schema relationships, JSON column fidelity, cascading deletes.
- [`test_ingest.py`](apps/api/tests/test_ingest.py) — CSV/TSV/multi-sheet `.xlsx` ingestion, BOM/semicolon handling, duplicate headers, bounded upload limit (`413`), and dataset/job RBAC guards.
- [`test_profiling.py`](apps/api/tests/test_profiling.py) & [`test_detectors.py`](apps/api/tests/test_detectors.py) — column statistics, identifier vs number disambiguation, null-like tokens, ambiguous dates, duplicate rows.
- [`test_dataset_api.py`](apps/api/tests/test_dataset_api.py) — cursor pagination, numeric-aware sorting, search filter, issue filtering, contributor RBAC stub.
- [`test_analysis_unit.py`](apps/api/tests/test_analysis_unit.py) & [`test_analysis_and_reports.py`](apps/api/tests/test_analysis_and_reports.py) — analysis metrics across all 3 fixtures, mixed-scale/currency safety, ambiguous date exclusion, hallucination catching in `verify_narrative_numbers`, version-locked `CellValue` overlay lineage, report CRUD, multi-sheet `.xlsx` export with formula sanitization, and report RBAC.
- [`test_jobs.py`](apps/api/tests/test_jobs.py) & [`test_health.py`](apps/api/tests/test_health.py) — inline & RQ queue dispatch + `/api/v1/health`.

### Frontend Checks (`apps/web`)
```bash
cd apps/web

# 1. ESLint check
npm run lint

# 2. TypeScript type check
npx tsc --noEmit

# 3. Production build check (stop `npm run dev` first so `.next` is not shared)
npm run build
```

### Live Smoke Verification Checklist (Public Demo QA)
If verifying a deployed or local demo instance end-to-end:
1. Confirm `GET /api/v1/health` returns `{"status": "healthy"}`.
2. Confirm sign-in works with `admin@cleardata.io` / `Password123!` and a newly registered account creates its own default workspace.
3. Upload `fixtures/messy_sales.csv`, verify status becomes `Ready`, and inspect `Date` / `Amount` profiles + issues.
4. Generate a Stakeholder Report (`auto` template), click a chart bar to verify **Source Row Lineage** opens with exact source rows, switch to **Presentation View**, and download `.xlsx`.

---

## Optional Configuration & Docker Compose

### Customizing `.env` (PostgreSQL or Real AI Providers)
Copy `.env.example` to `.env` in the repository root if you want to enable a real LLM provider (`openai`, `anthropic`, or `gemini`) or point the backend to PostgreSQL:

```bash
cp .env.example .env
```

Key environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | `development`, `test`, or `production` (demo seeding only runs in `development`) |
| `SECRET_KEY` | dev-only default | JWT signing secret; API refuses to boot outside `development`/`test` if unset, default, or `< 32` chars |
| `DATABASE_URL` | `sqlite:///.../apps/api/cleardata.db` | Database connection string (`sqlite:///...` or `postgresql://...`) |
| `JOBS_INLINE` | `true` | `true` runs ingestion/profiling synchronously in-process; `false` uses Redis + RQ |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL when `JOBS_INLINE=false` |
| `LLM_PROVIDER` | `mock` | `mock` (offline), `openai`, `anthropic`, or `gemini` |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | `""` | API key for the selected `LLM_PROVIDER` |
| `LLM_MODEL` | `gpt-4o-mini` | Model identifier passed to external LLM provider |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | Backend API base URL used by the Next.js frontend |

### Alternative: Docker Compose
If Docker & Docker Compose are installed:

```bash
docker compose up --build
```

This launches **PostgreSQL 16**, **Redis 7**, the **FastAPI API** (`:8000`), and **Next.js** (`:3000`). To run database migrations or an RQ worker inside the container:

```bash
docker compose exec api alembic upgrade head
docker compose exec api rq worker cleardata
```

---

## Repository Structure

```text
Data-Assist/
├── apps/
│   ├── api/
│   │   ├── alembic/             # Database schema migrations
│   │   ├── app/
│   │   │   ├── config.py        # Settings (.env resolution & SQLite/Postgres config)
│   │   │   ├── main.py          # FastAPI app, CORS, error formatting, lifespan seed
│   │   │   ├── models/          # SQLAlchemy 2.0 domain models & session setup
│   │   │   ├── routers/         # auth, workspaces, datasets, jobs, reports
│   │   │   ├── schemas/         # Pydantic v2 validation schemas
│   │   │   ├── services/
│   │   │   │   ├── ingest/      # CSV/TSV/Excel ingestion & banner detection
│   │   │   │   ├── profiling/   # Column profiling & deterministic issue detectors
│   │   │   │   ├── analysis/    # Quantitative analyzer & versioned overlay resolver
│   │   │   │   ├── ai/          # Swappable LLMClient & numeric grounding verifier
│   │   │   │   └── reports/     # Block evaluator, row lineage & XLSX exporter
│   │   │   └── workers/         # Inline + Redis/RQ queue abstraction
│   │   └── tests/               # 11 Pytest unit & API integration suites (42 tests)
│   └── web/
│       └── src/
│           ├── app/             # Next.js App Router pages (Home, Project, Explorer, Report)
│           ├── components/      # AuthCard, DatasetGrid, ReportBlockCard, LineageDrawer, etc.
│           ├── context/         # AuthContext & workspace session management
│           └── lib/             # Typed API client & formatters
├── fixtures/                    # Sample messy datasets for demos & automated tests
├── .github/workflows/ci.yml     # CI pipeline (Postgres 16 + Redis + Ruff + Pytest + Next build)
├── BUILD_PLAN.md                # Full architecture & product specification
├── PROGRESS.md                  # Engineering progress log
└── docker-compose.yml           # Multi-service container setup
```

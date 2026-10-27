# ClearData

ClearData is an intelligent data cleaning and reporting platform that transforms ambiguous, messy company datasets (CSV, TSV, Excel) into clean, auditable, and trustworthy reports. Teams can profile issues, review rule-based and AI-assisted fixes, collaborate across roles, and publish verified reports.

---

## Core Principles

1. **Raw Data is Immutable:** Uploaded files and ingested source rows (`rows.raw_json`) are never modified. All transformations produce versioned change overlays (`cell_values` and `dataset_versions`).
2. **Every Change is Traceable:** Every edit records who or what made it (rule, AI, human), when, previous value, new value, reason, and confidence.
3. **Deterministic Rules First, AI Second:** Code-level deterministic transforms (casing, trimming, regex date parsing) resolve predictable inconsistencies; LLMs are queried only for genuine semantic ambiguity.
4. **Human in the Loop:** Low-confidence AI suggestions are never auto-applied; they are routed to a human review queue.
5. **Auditable Lineage:** Every KPI and chart number traces back to specific source rows and transformations.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS |
| **Grid & Charts** | TanStack Table (virtualized), Recharts |
| **Backend API** | Python 3.11, FastAPI, Pydantic v2 |
| **Data Engine** | Polars columnar processing (openpyxl for Excel) |
| **Database** | PostgreSQL 16, SQLAlchemy 2.0, Alembic migrations |
| **Background Workers** | In-process synchronous queue (`JOBS_INLINE=true`) or Redis + RQ |
| **Storage** | Local file storage abstraction (S3-compatible interface ready) |
| **Auth & Security** | JWT sessions, bcrypt password hashing, Role-Based Access Control |

---

## Getting Started

### Prerequisites
- **Python 3.11** (`python --version`)
- **Node.js 20+** and `npm` (`node --version`)
- *(Optional)* **Docker & Docker Compose** for containerized workflows

---

### Path A: Native Local Development (No Docker Required)

This workflow is optimized for native Windows, macOS, and Linux developer environments without requiring a local Docker daemon or Redis instance.

#### 1. Configure Environment
```bash
# Copy environment configuration
cp .env.example .env
```
Ensure `JOBS_INLINE=true` in `.env` to execute background profiling and ingestion tasks synchronously in-process.

#### 2. Start Backend API
```bash
cd apps/api

# Create and activate Python 3.11 virtual environment
python -m venv .venv

# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
# By default, uses SQLite (sqlite:///./cleardata.db) or local PostgreSQL if configured:
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The API is live at `http://127.0.0.1:8000` (interactive documentation at `http://127.0.0.1:8000/docs`).

#### 3. Start Frontend
```bash
cd apps/web

# Install dependencies
npm install

# Start Next.js development server
npm run dev
```
Open `http://localhost:3000` in your browser.

---

### Path B: Containerized Development (Docker Compose)

For environments with Docker and Docker Compose installed:

```bash
# Build and start all services (PostgreSQL, Redis, API, and Next.js)
docker compose up --build
```

To run a dedicated RQ worker inside Docker or Linux/WSL:
```bash
docker compose exec api rq worker cleardata
```

---

## Running Tests & Quality Checks

### Backend Checks
```bash
cd apps/api

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run Ruff linter and code formatting checks
ruff check .

# Run test suite (auto-detects PostgreSQL in CI; uses SQLite fallback locally if Postgres is unreachable)
pytest
```

### Frontend Checks
```bash
cd apps/web

# Run ESLint
npm run lint

# Run Next.js production build verification
npm run build
```

---

## Environment Variables Reference

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | Runtime environment (`development`, `test`, `production`) |
| `SECRET_KEY` | *(dev key)* | Secret key for signing JWT auth tokens |
| `DATABASE_URL` | `postgresql://...` | Connection string for PostgreSQL (or `sqlite:///./cleardata.db`) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis instance for job queue & caching |
| `JOBS_INLINE` | `true` | When `true`, background jobs execute in-process synchronously |
| `STORAGE_BACKEND`| `local` | `local` for disk storage or `s3` for object store |
| `LOCAL_STORAGE_PATH`| `./storage` | Directory where uploaded raw files are preserved |
| `LLM_PROVIDER` | `mock` | AI engine (`mock`, `openai`, `anthropic`, `gemini`) |
| `NEXT_PUBLIC_API_URL`| `http://localhost:8000/api/v1` | Backend API URL for frontend |

---

## Monorepo Layout

```
/
├── apps/
│   ├── web/                # Next.js frontend (App Router, Tailwind, UI)
│   └── api/                # FastAPI backend service
│       ├── app/
│       │   ├── config.py   # Settings loaded from environment
│       │   ├── main.py     # FastAPI application factory & routes
│       │   ├── models/     # SQLAlchemy domain models & database session
│       │   ├── routers/    # Auth, Workspaces, Projects, Datasets endpoints
│       │   ├── schemas/    # Pydantic v2 validation contracts
│       │   ├── services/   # Ingest, Profiling, Cleaning, and AI services
│       │   └── workers/    # Unified queue abstraction (inline & RQ)
│       ├── alembic/        # Database schema migrations
│       └── tests/          # Pytest test suites & fixtures
├── fixtures/               # Sample messy datasets for test coverage
├── .github/workflows/      # GitHub Actions CI workflow
├── docker-compose.yml      # Multi-service container orchestration
├── BUILD_PLAN.md           # Master product specification & roadmap
├── NEXT_STEPS.md           # Agent task execution checklist
└── PROGRESS.md             # Implementation progress log
```

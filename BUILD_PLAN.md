# BUILD_PLAN.md — ClearData (working name)

> Instructions for a coding agent. Read this whole file before writing code. Work phase by phase, task by task. Do not skip ahead.

## 0. Mission

Build a web app that takes **ambiguous, messy company data** (CSV/Excel uploads) and turns it into **clean, readable, trustworthy reports**. Teams must be able to **review and fix data, collaborate with stakeholders, and publish approved reports**.

**Core principles (never violate):**
1. **Raw data is immutable.** Never overwrite an uploaded file or original rows. Cleaning is stored as versioned, reversible changes.
2. **Every change is traceable:** who/what made it (AI, rule, or human), when, before/after, and why.
3. **Deterministic rules first, AI second.** Use code rules for what can be solved exactly. Call the LLM only for genuine ambiguity.
4. **AI never silently applies low-confidence changes.** They go to a human review queue.
5. **Every number in a report traces back to source rows.**

## 1. Working rules for the agent

- Work in small tasks. One task = one commit with a clear message (`feat:`, `fix:`, `chore:`, `test:`).
- After each task: run lint, type checks, and tests. Do not move on while anything fails.
- Write tests for all cleaning logic (unit tests with fixture CSVs in `/fixtures`).
- Keep a `PROGRESS.md` log: task done, decisions made, open questions.
- If a requirement is unclear or you want to deviate from the stack below, **stop and ask** instead of guessing.
- No secrets in code. Use `.env` and provide `.env.example`.
- Prefer boring, well-documented libraries. Do not add a dependency without a reason noted in `PROGRESS.md`.

## 2. Tech stack (fixed unless told otherwise)

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router) + TypeScript + Tailwind |
| Data grid | TanStack Table (virtualized) |
| Charts | Recharts |
| Backend API | Python 3.11 + FastAPI |
| Data processing | Polars (pandas allowed where needed) |
| Database | PostgreSQL + SQLAlchemy + Alembic migrations |
| Queue / workers | Redis + RQ (or Celery) |
| File storage | Local disk in dev, S3-compatible interface in prod |
| Auth | Email/password with JWT sessions (SSO later) |
| Realtime | WebSockets (FastAPI) for comments and job status |
| AI | LLM provider behind an interface (`LLMClient`), swappable |
| Infra | Docker Compose for local dev; GitHub Actions for CI |

## 3. Repository structure

```
/
├── apps/
│   ├── web/                # Next.js frontend
│   └── api/                # FastAPI backend
│       ├── app/
│       │   ├── routers/
│       │   ├── models/
│       │   ├── schemas/
│       │   ├── services/
│       │   │   ├── ingest/
│       │   │   ├── profiling/
│       │   │   ├── cleaning/     # rule engine + transforms
│       │   │   ├── ai/           # LLMClient, prompts, cache
│       │   │   └── reports/
│       │   └── workers/
│       └── tests/
├── fixtures/               # messy sample CSVs for tests
├── docker-compose.yml
├── .github/workflows/ci.yml
├── BUILD_PLAN.md
└── PROGRESS.md
```

## 4. Data model

Create with Alembic migrations.

- `users` (id, email, password_hash, name)
- `workspaces` (id, name) and `memberships` (user_id, workspace_id, role: `admin | steward | stakeholder | contributor`)
- `projects` (id, workspace_id, name)
- `datasets` (id, project_id, name, source_type, raw_file_path)
- `dataset_versions` (id, dataset_id, version_number, created_by, note) — each applied batch of changes creates a new version
- `columns` (id, dataset_id, name, inferred_type, semantic_hint, stats_json)
- `rows` (id, dataset_id, row_index, raw_json) — **raw_json is never modified**
- `cell_values` (dataset_version_id, row_id, column_id, value) — cleaned values per version
- `rules` (id, workspace_id, name, column_pattern, transform_type, config_json, scope) — reusable
- `changes` (id, dataset_version_id, row_id, column_id, before, after, source: `rule | ai | human`, rule_id nullable, confidence nullable, reason, status: `pending | accepted | rejected | reverted`)
- `issues` (id, dataset_id, type, severity, column_id, row_ids, status, assignee_id, description)
- `reports` (id, project_id, dataset_version_id, title, status: `draft | in_review | approved | published`, layout_json)
- `comments` (id, target_type: `cell | issue | report | report_block`, target_id, author_id, body, parent_id, resolved)
- `approvals` (id, report_id, reviewer_id, decision, note)
- `audit_log` (id, workspace_id, actor_id, action, payload_json, created_at)

## 5. Phases and tasks

### Phase 0 — Foundation
- [x] **0.1** Scaffold monorepo, Docker Compose (api, web, postgres, redis), `.env.example`.
- [x] **0.2** CI workflow: lint, type check, tests for both apps.
- [x] **0.3** Alembic setup and initial migration with the tables above.
- [x] **0.4** Auth (register, login, JWT), workspace creation, role-based permission dependency in FastAPI.
- [x] **0.5** Frontend shell: login, workspace switcher, project list.

**Done when:** `docker compose up` runs everything, a user can sign up, create a workspace and a project, and CI is green.

### Phase 1 — Ingest and profiling (MVP core)
- [ ] **1.1** File upload endpoint (CSV, XLSX). Store raw file untouched. Parse into `rows.raw_json` and `columns`. Handle encodings, delimiters, header detection, multiple Excel sheets.
- [ ] **1.2** Profiling job (async worker): per column compute inferred type, null %, distinct count, top values, min/max, format patterns (e.g., date formats mixed), and write `stats_json`.
- [ ] **1.3** Issue detection (deterministic): missing values, exact and near duplicates, mixed formats in one column, outliers, inconsistent casing/whitespace, values that violate inferred type.
- [ ] **1.4** Frontend: dataset page with virtualized grid, column profile sidebar, issues list with counts and severity.

**Done when:** uploading `fixtures/messy_sales.csv` shows the grid, correct column profiles, and a list of detected issues, with tests covering each detector.

### Phase 2 — Cleaning engine and review queue
- [ ] **2.1** Rule engine: transform types — `trim`, `case`, `parse_date(format)`, `parse_number/currency`, `map_values(dict)`, `fill_missing(strategy)`, `dedupe(keys)`, `split/merge columns`. Each transform is a pure function with tests.
- [ ] **2.2** Apply a rule → produces `changes` (status `pending` or `accepted`) and a new `dataset_version`. Support **undo/revert** per change and per version.
- [ ] **2.3** AI interpretation service (see section 6): groups distinct ambiguous values, asks the LLM for a proposed standardization with confidence and reason. Cache results by (column semantic hint + value set hash).
- [ ] **2.4** Confidence policy: `>= 0.9` → can be bulk-accepted by user in one click; `< 0.9` → goes to review queue. Nothing is auto-applied without a user action in MVP.
- [ ] **2.5** Review queue UI: grouped suggestions ("14 values → 'New York'"), accept / edit / reject, bulk actions, shows before/after samples.
- [ ] **2.6** Inline cell editing in the grid (creates a `human` change). Bulk find-and-replace.
- [ ] **2.7** Save a fix as a reusable **rule** and apply it to future uploads in the same project.
- [ ] **2.8** Version history UI with diff view and revert.

**Done when:** a messy fixture can be taken from raw to clean using suggestions and manual fixes, every change appears in history with its source, and any change can be reverted.

### Phase 3 — Reporting
- [ ] **3.1** Report builder: choose a dataset version, add blocks (KPI card, bar/line/pie chart, table, text). Aggregations computed server-side from `cell_values`.
- [ ] **3.2** Click-through lineage: clicking a chart value or KPI shows the underlying rows and the changes applied to them.
- [ ] **3.3** AI-written summary block (see section 6) that only cites numbers computed by the backend.
- [ ] **3.4** Report templates (monthly sales, survey results, inventory). Start with two.
- [ ] **3.5** Export: PDF and XLSX. Shareable read-only link with expiry.

**Done when:** a cleaned dataset yields a report with charts, a generated summary whose numbers match the data, working lineage, and a PDF export.

### Phase 4 — Collaboration
- [ ] **4.1** Comments on cells, issues, report blocks; threads, @mentions, resolve.
- [ ] **4.2** Issue assignment and **clarification requests** ("Is Q3 fiscal or calendar?") sent to a contributor; their answer can generate a rule.
- [ ] **4.3** Notifications (in-app first, email later).
- [ ] **4.4** Approval workflow: draft → in_review → approved → published; stakeholders can approve or request changes; publishing locks the dataset version used.
- [ ] **4.5** Permissions enforced end to end: stakeholders can view/comment/approve but not edit data; contributors only see assigned items.
- [ ] **4.6** Audit log page for admins.
- [ ] **4.7** Realtime updates via WebSocket for comments and job status.

**Done when:** two users in different roles can complete the full loop: steward cleans data, stakeholder comments and requests a change, steward fixes it, stakeholder approves, report is published.

### Phase 5 — Hardening
- [ ] **5.1** Large file handling (streaming parse, chunked processing, row limits with clear errors).
- [ ] **5.2** Rate limiting, input validation, upload size/type limits, XSS/CSRF review.
- [ ] **5.3** Observability: structured logs, error tracking, job failure visibility in UI.
- [ ] **5.4** E2E tests (Playwright) for the main loop.
- [ ] **5.5** Docs: README, setup guide, architecture diagram.

## 6. AI layer specification

**Interface**
```python
class LLMClient(Protocol):
    def complete_json(self, system: str, user: str, schema: dict) -> dict: ...
```

**Interpretation task** — send only *distinct values* of a column (plus a few sample rows for context), never the full dataset. Expected JSON response:

```json
{
  "column_meaning": "US state or city",
  "suggestions": [
    {
      "source_values": ["NY", "N.Y.", "new york"],
      "proposed_value": "New York",
      "confidence": 0.95,
      "reason": "Common abbreviations and casing variants of the same place"
    }
  ],
  "unresolved": [
    { "value": "NJ?", "question": "Is this New Jersey?" }
  ]
}
```

**Rules for prompts**
- Instruct the model to return **only JSON** matching the schema; validate it and retry once on failure.
- Instruct it to put anything uncertain in `unresolved` rather than guessing.
- Never include personal data beyond what is needed; allow workspace-level setting to disable AI.
- Log prompt hash, model, and token usage for cost tracking.

**Summary task** — backend computes all metrics first, then passes a JSON of verified numbers. The model may only describe those numbers. After generation, validate that every number in the text appears in the supplied metrics; otherwise regenerate or flag.

## 7. API conventions

- REST under `/api/v1`, JSON, Pydantic schemas for all requests/responses.
- Long operations (parse, profile, AI interpret, export) run as background jobs; return `job_id`; frontend polls or listens on WebSocket.
- Pagination for rows (cursor-based) and changes.
- Consistent error format: `{ "error": { "code": "...", "message": "..." } }`.

## 8. Test fixtures to create first

Create in `/fixtures` before building detectors:
1. `messy_sales.csv` — mixed date formats, currency symbols, duplicate customers, inconsistent region names, blank cells.
2. `survey_results.csv` — free-text answers with spelling variants, mixed scales.
3. `inventory.xlsx` — multiple sheets, merged header cells, mixed units (kg/lbs).

## 9. Definition of done (MVP = Phases 0–3 + 4.1, 4.4)

- [ ] A user can upload a messy file and see profiling and issues.
- [ ] Cleaning via rules, AI suggestions, and manual edits works with full history and undo.
- [ ] A report can be built, traced to source rows, exported, and shared.
- [ ] A second user can comment and approve.
- [ ] CI passes; README explains setup in under 10 minutes.

## 10. First instruction to the agent

Start with **Phase 0, Task 0.1**. Create the scaffold, confirm it runs with `docker compose up`, record it in `PROGRESS.md`, and then continue task by task. Ask me before choosing a niche-specific template or changing the stack.

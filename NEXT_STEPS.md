# NEXT_STEPS.md — Continue ClearData from Phase 1

> Instructions for the coding agent. `BUILD_PLAN.md` is still the source of truth for the stack, data model, principles, and AI spec. **This file tells you what to do next.** Read `BUILD_PLAN.md`, `PROGRESS.md`, and this file fully before touching code.

## 1. Where the project stands

Per `PROGRESS.md`, **Phase 0 (Foundation) is complete**:

- Monorepo scaffold (`apps/web` Next.js, `apps/api` FastAPI), Dockerfiles, `docker-compose.yml`, `.env.example`
- CI workflow in `.github/workflows/ci.yml`
- 16 SQLAlchemy models + initial Alembic migration
- JWT auth, workspaces, projects, and `require_workspace_role(...)` RBAC with integration tests
- Frontend shell: login, workspace switcher, project list
- Fixtures: `fixtures/messy_sales.csv`, `fixtures/survey_results.csv`, `fixtures/inventory.xlsx`

**Next up: Phase 1 (Ingest and profiling).** But first, clear the pre-flight items below, because they affect everything that follows.

## 2. Pre-flight checks (do these before Phase 1, one commit each)

These come from gaps and risks visible in `PROGRESS.md`. Verify each against the actual code; if it's already fine, note that in `PROGRESS.md` and move on.

- [x] **P.1 — Confirm CI is green on the latest `master` commit.** Check the Actions tab or run the same commands locally (Ruff, Pytest with Postgres and Redis available, ESLint, `npm run build`). Fix anything red.
- [x] **P.2 — Python version mismatch.** The plan specified Python 3.12; local dev used 3.11. Pick one version and make `apps/api/Dockerfile`, the CI workflow, and the local venv all use it. Document it in the README.
- [x] **P.3 — Docker Compose was never run.** The dev host has no Docker daemon, so `docker-compose.yml` is unverified. Do not assume it works. Either run it (if Docker is available now) or add a **no-Docker local dev path** documented in the README: local Postgres + Redis (or a hosted dev instance), `uvicorn` for the API, `npm run dev` for the web app. Whichever path you use, record it in `PROGRESS.md`.
- [x] **P.4 — Test database.** Check what the tests run against. If they use SQLite while production uses PostgreSQL, switch tests that touch JSON columns, constraints, or migrations to PostgreSQL (CI already provides it). SQLite hides real bugs here.
- [ ] **P.5 — Background jobs on Windows.** The plan uses Redis + RQ, and RQ's default worker relies on `fork`, which does not work on native Windows. Resolve this now:
  - Add a settings flag `JOBS_INLINE=true` that runs jobs synchronously in-process (for local dev and tests), and `false` to enqueue to Redis.
  - Put all job entry points behind one function: `enqueue(job_fn, *args)`. Nothing else should import RQ directly.
  - Document how to run the real worker (in Docker/WSL) in the README.
- [ ] **P.6 — README.** Add a root `README.md`: what the app is, how to run it (both paths), how to run tests, env vars.

Commit each as `chore: ...` and log them under a "Pre-flight" heading in `PROGRESS.md`.

## 3. Working protocol (unchanged, restated)

- One task = one commit (`feat:`, `fix:`, `test:`, `chore:`). Lint, type check, and tests pass before moving on.
- After each task, append to `PROGRESS.md` using the same format as before: **Status**, **Decisions Made**, **Notes / Observations**.
- Add tests for every detector and parser using the files in `/fixtures`. Add more fixtures when you find an edge case.
- **Raw data stays immutable.** Never write to `rows.raw_json` after ingest.
- Do not add dependencies without noting why in `PROGRESS.md`.
- **Stop and ask me** if: a requirement is ambiguous, you want to deviate from the stack, a task needs more than about a day of work and could be split differently, or tests can't be made to pass for a reason you don't understand.

## 4. Phase 1 — Ingest and profiling

Goal: upload a messy file, see it in a grid, see column profiles, and see a list of detected issues.

### Task 1.1 — File upload and parsing

**Backend**
- `POST /api/v1/projects/{project_id}/datasets` (multipart upload). Roles allowed: `admin`, `steward`.
- Validate extension and size (`.csv`, `.tsv`, `.xlsx`; configurable max size via env, default 25 MB). Reject others with the standard error format.
- Save the original file unchanged via a `FileStorage` interface (local disk implementation now; S3-compatible later). Store the path in `datasets.raw_file_path`.
- Create the `datasets` row immediately with a `status` of `processing`, enqueue a parse job, and return `{ dataset_id, job_id }`. (Add a `status` column via a new Alembic migration if it doesn't exist: `processing | ready | failed`, plus `error_message`.)
- **Parse job** (`services/ingest/`):
  - CSV/TSV: detect encoding (try UTF-8, then UTF-8-BOM, then fall back with `charset-normalizer`), detect delimiter, handle quoted newlines, ragged rows, and duplicate header names (suffix `_2`, `_3`).
  - XLSX: read with `openpyxl`/Polars. If multiple sheets, create **one dataset per sheet** named `<file> — <sheet>` (or accept a `sheet` parameter; choose one and document it). Handle merged header cells by forward-filling, and detect the real header row when there are title rows above it.
  - Read everything as **strings first**; do not let the parser coerce types. Keep original values exactly as they appear. Type inference happens in profiling, not here.
  - Write `columns` (name, position) and `rows` (`row_index`, `raw_json`) in batches (e.g., 5,000 rows per insert), not one by one.
  - Create `dataset_versions` version 1 with note "Original import".
  - On failure, set `status=failed` with a readable message.
- Tests: each fixture parses to the expected row/column counts; a file with a BOM, a semicolon-delimited file, and a file with duplicate headers all parse correctly.

**Done when:** uploading each of the three fixtures creates a `ready` dataset with correct rows and columns, and the original file on disk is byte-identical to the upload.

### Task 1.2 — Profiling job

- After a successful parse, enqueue a profiling job (chain it from the parse job).
- For each column compute and store in `columns.stats_json`:
  - `inferred_type`: one of `integer`, `decimal`, `currency`, `percentage`, `date`, `datetime`, `boolean`, `email`, `phone`, `category`, `free_text`, `mixed`. Use pattern-based detection on a sample plus full-column pass for counts.
  - `null_count` / `null_pct` (treat empty strings, whitespace-only, and `N/A`, `NA`, `null`, `none`, `-`, `n/a`, `#N/A` as null-like, but count them separately as `null_like_count`)
  - `distinct_count`, `top_values` (top 10 with counts)
  - For numerics: min, max, mean, median
  - For text: min/max length, % with leading/trailing whitespace, case distribution (upper/lower/title/mixed)
  - For dates: detected formats with counts (e.g., `{"%m/%d/%Y": 120, "%d-%b-%y": 35}`), min/max when parseable
  - `format_patterns`: generalized shape of values (e.g., `99/99/9999`, `AAA-999`) with counts
  - `semantic_hint` (nullable): best-effort guess from the column name plus values (e.g., `email`, `date`, `region`, `amount`, `customer_name`). Keep this simple and rule-based for now.
- Also store dataset-level stats on the dataset (row count, column count, overall completeness %).
- Tests: expected inferred types and key stats on each fixture, including the mixed-date-format column in `messy_sales.csv`.

**Done when:** `GET /api/v1/datasets/{id}/columns` returns accurate profiles for all fixtures.

### Task 1.3 — Issue detection (deterministic)

Implement detectors in `services/profiling/detectors/`, one module each, all returning a common `DetectedIssue` shape and all writing to `issues`:

| Detector | Issue type | Severity rule |
|---|---|---|
| Missing values | `missing_values` | high if >20% null, medium 5–20%, low below |
| Exact duplicate rows | `duplicate_rows` | medium |
| Near-duplicate rows/values | `near_duplicates` | medium (use normalized keys + a fuzzy ratio, e.g., `rapidfuzz`; configurable threshold) |
| Mixed formats in a column | `mixed_formats` | high for dates and numbers |
| Inconsistent casing/whitespace | `inconsistent_text` | low |
| Type violations (value doesn't fit the column's dominant type) | `type_violation` | medium |
| Numeric outliers | `outliers` | low (IQR method; only flag, never change) |
| Inconsistent category labels (same thing, different spelling) | `label_variants` | medium (cluster by normalized form + fuzzy match) |

Each issue stores: `type`, `severity`, `column_id` (nullable), `row_ids` (cap the stored list at e.g. 1,000 and also store `affected_count`), `description` (plain English, e.g., "Column `order_date` mixes 3 date formats"), and a `details_json` with examples (add column if needed). Re-running detection for a dataset must **replace** previous auto-detected issues without touching issues a human created or resolved.

- Tests: at least one fixture-based test per detector, plus a "clean" fixture that should produce zero issues.

**Done when:** `GET /api/v1/datasets/{id}/issues` returns a sensible, non-noisy list for each fixture. Review the output with me before moving on if the issue lists look noisy (too many low-value issues).

### Task 1.4 — Dataset API for the frontend

- `GET /api/v1/projects/{project_id}/datasets` (list with status and stats)
- `GET /api/v1/datasets/{id}` (metadata, status, dataset stats)
- `GET /api/v1/datasets/{id}/rows?cursor=&limit=&sort=&filter=` — cursor-based pagination, default limit 100, max 500; basic sorting by a column and a simple "contains" filter
- `GET /api/v1/datasets/{id}/columns`
- `GET /api/v1/datasets/{id}/issues?severity=&type=&column_id=`
- `GET /api/v1/jobs/{job_id}` for status polling
- All endpoints enforce workspace membership. Contributors may only see datasets they are assigned to (stub this check now; full assignment comes in Phase 4).
- Tests for pagination boundaries, permissions, and 404s.

### Task 1.5 — Frontend: upload and dataset list

- On the project page, add an **Upload** button (steward/admin only) with drag-and-drop, file type/size validation, and an upload progress state.
- Show datasets in a list with status badges (`processing`, `ready`, `failed`), row/column counts, and completeness %.
- Poll job status until done; show a clear error message on failure.

### Task 1.6 — Frontend: dataset page (grid, profiles, issues)

Route: `/projects/[projectId]/datasets/[datasetId]`

- **Grid**: virtualized (TanStack Table + a virtualizer), infinite scroll via the cursor API, sticky header, column resizing, and cell highlighting for cells that belong to an issue. Read-only for now.
- **Column profile panel** (right sidebar, opens on column header click): inferred type, null %, distinct count, top values, detected formats, and a small distribution chart.
- **Issues panel**: grouped by severity, filterable by type and column. Clicking an issue scrolls/filters the grid to the affected rows and highlights them.
- **Summary bar**: row count, column count, completeness %, issue counts by severity.
- Empty, loading, and error states for every panel.
- Keep the existing visual style from Task 0.5; don't redesign it.

**Done when (Phase 1 complete):** I can sign in, create a project, upload `messy_sales.csv`, see it processed, scroll the grid, open a column profile showing the mixed date formats, and click an issue to see the affected rows highlighted. All tests, lint, and CI pass. Record a short "how to demo this" section in `PROGRESS.md`.

## 5. Things to watch for (decisions to make deliberately)

- **`cell_values` size.** Storing a full copy of every cell per version will explode in size. When you reach Phase 2, store only **changed cells** as an overlay on top of the previous version (or the raw rows) and resolve values by reading the latest version that touched each cell. Propose the design to me in `PROGRESS.md` before implementing it.
- **Large files.** Parse and profile in streaming/chunked fashion; don't load a whole 25 MB file into per-row Python dicts if Polars can do it columnar. Note measured timings for the largest fixture you can generate (try 100k rows) in `PROGRESS.md`.
- **Type inference false positives.** ZIP codes, phone numbers, and IDs look like integers but must not be treated as numbers. Prefer `category` or `identifier` when values have leading zeros or fixed length.
- **Ambiguous dates** (`03/04/2025`). Never silently pick MM/DD vs DD/MM. Record the ambiguity in the profile and surface it as an issue; resolution is a Phase 2 concern.

## 6. After Phase 1

Do **not** start Phase 2 automatically. When Phase 1 is done:
1. Update `PROGRESS.md`.
2. Summarize what's built, what's deferred, and any problems.
3. Propose the cell-version storage design (section 5, first bullet) and wait for my go-ahead.

Phase 2 preview, for planning only: rule engine (`trim`, `case`, `parse_date`, `parse_number`, `map_values`, `fill_missing`, `dedupe`), apply-rule-creates-changes-and-version, AI interpretation service with confidence thresholds, review queue UI, inline editing, saved rules, version history with revert.

## 7. First instruction to the agent

Start with **Pre-flight P.1**. Work through P.1 to P.6, then Task 1.1. Log every step in `PROGRESS.md`. Ask me before moving past any "stop and ask" condition.

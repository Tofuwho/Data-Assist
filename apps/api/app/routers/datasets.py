from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.database import get_db
from app.models.entities import (
    CellValue,
    ColumnModel,
    Dataset,
    DatasetVersion,
    Issue,
    Membership,
    Project,
    RowModel,
)
from app.routers.deps import require_dataset_role, require_project_role
from app.schemas.dataset import (
    ColumnResponse,
    DatasetItemSummary,
    DatasetResponse,
    DatasetUploadResponse,
    IssueCounts,
    IssueResponse,
    JobStatusResponse,
    RowItemResponse,
    RowPageResponse,
)
from app.schemas.workspace import ProjectResponse
from app.services.ingest import inspect_xlsx_sheets, parse_and_persist_dataset
from app.services.profiling import profile_dataset
from app.services.profiling.profiler import (
    parse_currency_value,
    parse_numeric_value,
    parse_percentage_value,
)
from app.services.storage import get_storage
from app.workers import enqueue

router = APIRouter(tags=["Datasets"])

ALLOWED_EXTENSIONS = {".csv", ".tsv", ".xlsx"}


def _get_issue_counts_map(db: Session, dataset_ids: list[str]) -> dict[str, IssueCounts]:
    """Batch-fetch open/in_review issue counts grouped by severity for datasets."""
    counts_map: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}
    )
    if not dataset_ids:
        return {}

    rows = (
        db.query(Issue.dataset_id, Issue.severity, func.count(Issue.id))
        .filter(Issue.dataset_id.in_(dataset_ids), Issue.status.in_(["open", "in_review"]))
        .group_by(Issue.dataset_id, Issue.severity)
        .all()
    )
    for ds_id, sev, cnt in rows:
        counts_map[ds_id]["total"] += cnt
        if sev in counts_map[ds_id]:
            counts_map[ds_id][sev] += cnt

    return {ds_id: IssueCounts(**counts_map[ds_id]) for ds_id in dataset_ids}


def _serialize_dataset(ds: Dataset, issue_counts: IssueCounts) -> DatasetResponse:
    return DatasetResponse(
        id=ds.id,
        project_id=ds.project_id,
        name=ds.name,
        source_type=ds.source_type,
        status=ds.status,
        error_message=ds.error_message,
        stats_json=ds.stats_json,
        issue_counts=issue_counts,
        created_at=ds.created_at,
        updated_at=ds.updated_at,
    )


def _resolve_cell_overlays(
    db: Session,
    dataset_id: str,
    version_id: str | None,
    row_ids: list[str] | None = None,
) -> tuple[str | None, dict[str, dict[str, Any]]]:
    """Resolve effective cell value overlays up to target dataset version."""
    versions = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_number.asc())
        .all()
    )
    if not versions:
        return None, {}

    target_version = versions[-1]
    if version_id:
        match = next((v for v in versions if v.id == version_id), None)
        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset version {version_id} not found",
            )
        target_version = match

    applicable_version_ids = [v.id for v in versions if v.version_number <= target_version.version_number]
    if len(applicable_version_ids) <= 1 and not db.query(CellValue.id).filter(
        CellValue.dataset_version_id == target_version.id
    ).first():
        return target_version.id, {}

    cols_by_id = {
        c.id: c.name
        for c in db.query(ColumnModel.id, ColumnModel.name).filter(ColumnModel.dataset_id == dataset_id).all()
    }
    version_rank = {v.id: v.version_number for v in versions}

    cv_query = db.query(CellValue).filter(CellValue.dataset_version_id.in_(applicable_version_ids))
    if row_ids is not None:
        if not row_ids:
            return target_version.id, {}
        cv_query = cv_query.filter(CellValue.row_id.in_(row_ids))

    cells = cv_query.all()
    cells.sort(key=lambda c: version_rank.get(c.dataset_version_id, 0))

    overlays: dict[str, dict[str, Any]] = defaultdict(dict)
    for cell in cells:
        col_name = cols_by_id.get(cell.column_id)
        if col_name:
            overlays[cell.row_id][col_name] = cell.value

    return target_version.id, overlays


def _sort_key_for_value(val: Any, inferred_type: str | None) -> tuple[int, Any]:
    """Numeric-aware sort key placing empty/missing values consistently at the end."""
    s = "" if val is None else str(val).strip()
    if s == "":
        return (1, "")
    if inferred_type in ("integer", "decimal", "currency", "percentage"):
        if inferred_type == "currency":
            c = parse_currency_value(s)
            if c is not None:
                return (0, c)
        if inferred_type == "percentage":
            p = parse_percentage_value(s)
            if p is not None:
                return (0, p)
        _, num = parse_numeric_value(s)
        if num is not None:
            return (0, num)
        return (1, s.lower())
    return (0, s.lower())


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    project_and_membership: Annotated[
        tuple[Project, Membership],
        Depends(require_project_role(["admin", "steward", "stakeholder", "contributor"])),
    ],
):
    """Retrieve metadata for a single project."""
    project, _ = project_and_membership
    return ProjectResponse.model_validate(project)


@router.post(
    "/projects/{project_id}/datasets",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_dataset(
    project_id: str,
    project_and_membership: Annotated[
        tuple[Project, Membership],
        Depends(require_project_role(["admin", "steward"])),
    ],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
):
    """Upload a raw dataset file (.csv, .tsv, .xlsx), validate format/size, and enqueue parsing."""
    project, membership = project_and_membership

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a valid filename",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    chunk_size = 1024 * 1024
    chunks: list[bytes] = []
    total_size = 0
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB",
            )
        chunks.append(chunk)
    content = b"".join(chunks)

    storage = get_storage()
    stored_path = storage.save(file.filename, content)

    base_name = Path(file.filename).stem

    if ext == ".xlsx":
        try:
            sheets = inspect_xlsx_sheets(content)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Corrupt or invalid Excel file: {exc}",
            ) from exc

        if len(sheets) > 1:
            dataset_summaries: list[DatasetItemSummary] = []
            primary_dataset_id = ""
            primary_job_id = ""

            for idx, sheet_name in enumerate(sheets):
                sheet_dataset_name = f"{base_name} — {sheet_name}"
                ds = Dataset(
                    project_id=project.id,
                    name=sheet_dataset_name,
                    source_type="xlsx",
                    raw_file_path=stored_path,
                    status="processing",
                )
                db.add(ds)
                db.flush()

                job = enqueue(
                    parse_and_persist_dataset,
                    dataset_id=ds.id,
                    file_path=stored_path,
                    created_by=membership.user_id,
                    sheet_name=sheet_name,
                )

                if idx == 0:
                    primary_dataset_id = ds.id
                    primary_job_id = job.id

                dataset_summaries.append(
                    DatasetItemSummary(
                        dataset_id=ds.id,
                        name=ds.name,
                        job_id=job.id,
                    )
                )

            db.commit()
            return DatasetUploadResponse(
                dataset_id=primary_dataset_id,
                job_id=primary_job_id,
                name=f"{file.filename} ({len(sheets)} sheets)",
                status="processing",
                datasets=dataset_summaries,
            )

    ds = Dataset(
        project_id=project.id,
        name=file.filename,
        source_type="xlsx" if ext == ".xlsx" else "csv",
        raw_file_path=stored_path,
        status="processing",
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    job = enqueue(
        parse_and_persist_dataset,
        dataset_id=ds.id,
        file_path=stored_path,
        created_by=membership.user_id,
    )

    return DatasetUploadResponse(
        dataset_id=ds.id,
        job_id=job.id,
        name=ds.name,
        status="processing",
    )


@router.get("/projects/{project_id}/datasets", response_model=list[DatasetResponse])
def list_project_datasets(
    project_id: str,
    project_and_membership: Annotated[
        tuple[Project, Membership],
        Depends(require_project_role(["admin", "steward", "stakeholder", "contributor"])),
    ],
    db: Annotated[Session, Depends(get_db)],
):
    """List datasets in a project with status, profiling stats, and issue counts."""
    project, membership = project_and_membership
    query = db.query(Dataset).filter(Dataset.project_id == project.id)

    # Contributor stub: only show datasets with at least one issue assigned to them
    if membership.role == "contributor":
        assigned_ds_ids = [
            row[0]
            for row in db.query(Issue.dataset_id)
            .filter(Issue.assignee_id == membership.user_id)
            .distinct()
            .all()
        ]
        if not assigned_ds_ids:
            return []
        query = query.filter(Dataset.id.in_(assigned_ds_ids))

    datasets = query.order_by(Dataset.created_at.desc()).all()
    counts_map = _get_issue_counts_map(db, [d.id for d in datasets])
    return [_serialize_dataset(d, counts_map.get(d.id, IssueCounts())) for d in datasets]


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
def get_dataset(
    dataset_id: str,
    dataset_ctx: Annotated[
        tuple[Dataset, Project, Membership],
        Depends(require_dataset_role(["admin", "steward", "stakeholder", "contributor"])),
    ],
    db: Annotated[Session, Depends(get_db)],
):
    """Retrieve metadata, status, profiling stats, and issue counts for a dataset."""
    dataset, _, _ = dataset_ctx
    counts_map = _get_issue_counts_map(db, [dataset.id])
    return _serialize_dataset(dataset, counts_map.get(dataset.id, IssueCounts()))


@router.get("/datasets/{dataset_id}/columns", response_model=list[ColumnResponse])
def get_dataset_columns(
    dataset_id: str,
    dataset_ctx: Annotated[
        tuple[Dataset, Project, Membership],
        Depends(require_dataset_role(["admin", "steward", "stakeholder", "contributor"])),
    ],
    db: Annotated[Session, Depends(get_db)],
):
    """Retrieve ordered columns and their statistical profiles for a dataset."""
    dataset, _, _ = dataset_ctx
    columns = (
        db.query(ColumnModel)
        .filter(ColumnModel.dataset_id == dataset.id)
        .order_by(ColumnModel.position)
        .all()
    )
    return columns


@router.get("/datasets/{dataset_id}/rows", response_model=RowPageResponse)
def get_dataset_rows(
    dataset_id: str,
    dataset_ctx: Annotated[
        tuple[Dataset, Project, Membership],
        Depends(require_dataset_role(["admin", "steward", "stakeholder", "contributor"])),
    ],
    db: Annotated[Session, Depends(get_db)],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    sort: Annotated[str | None, Query()] = None,
    sort_dir: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
    filter_text: Annotated[str | None, Query(alias="filter")] = None,
    issue_id: Annotated[str | None, Query()] = None,
    version_id: Annotated[str | None, Query()] = None,
):
    """Retrieve cursor-paginated dataset rows with optional sorting, filtering, and issue focus."""
    dataset, _, _ = dataset_ctx

    issue_row_ids: list[str] | None = None
    if issue_id:
        issue = db.query(Issue).filter(Issue.id == issue_id, Issue.dataset_id == dataset.id).first()
        if not issue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Issue {issue_id} not found for dataset {dataset_id}",
            )
        issue_row_ids = list(issue.row_ids or [])

    base_query = db.query(RowModel).filter(RowModel.dataset_id == dataset.id)
    if issue_row_ids is not None:
        if not issue_row_ids:
            return RowPageResponse(
                dataset_id=dataset.id,
                version_id=version_id,
                total_count=0,
                limit=limit,
                next_cursor=None,
                has_more=False,
                items=[],
            )
        base_query = base_query.filter(RowModel.id.in_(issue_row_ids))

    # Fast SQL-level keyset pagination path when no dynamic sort or text filter is active
    if not sort and not filter_text:
        total_count = base_query.count()
        page_query = base_query
        if cursor is not None:
            try:
                cursor_row_index = int(cursor)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid cursor value",
                ) from exc
            page_query = page_query.filter(RowModel.row_index > cursor_row_index)

        fetched = page_query.order_by(RowModel.row_index.asc()).limit(limit + 1).all()
        has_more = len(fetched) > limit
        page_rows = fetched[:limit]

        resolved_vid, overlays = _resolve_cell_overlays(
            db, dataset.id, version_id, [r.id for r in page_rows]
        )

        items = [
            RowItemResponse(
                id=r.id,
                row_index=r.row_index,
                values={**(r.raw_json or {}), **overlays.get(r.id, {})},
            )
            for r in page_rows
        ]
        next_cursor = str(page_rows[-1].row_index) if has_more and page_rows else None
        return RowPageResponse(
            dataset_id=dataset.id,
            version_id=resolved_vid,
            total_count=total_count,
            limit=limit,
            next_cursor=next_cursor,
            has_more=has_more,
            items=items,
        )

    # Filtered or sorted path across effective cell values
    sort_col_type: str | None = None
    if sort:
        col = (
            db.query(ColumnModel)
            .filter(ColumnModel.dataset_id == dataset.id, ColumnModel.name == sort)
            .first()
        )
        if not col:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown sort column '{sort}'",
            )
        sort_col_type = col.inferred_type

    all_rows = base_query.order_by(RowModel.row_index.asc()).all()
    resolved_vid, overlays = _resolve_cell_overlays(db, dataset.id, version_id, None)

    resolved_items: list[RowItemResponse] = []
    needle = filter_text.strip().lower() if filter_text else None
    for r in all_rows:
        merged = {**(r.raw_json or {}), **overlays.get(r.id, {})}
        if needle:
            if not any(needle in str(v).lower() for v in merged.values() if v is not None):
                continue
        resolved_items.append(RowItemResponse(id=r.id, row_index=r.row_index, values=merged))

    if sort:
        reverse = sort_dir == "desc"
        non_empty = [it for it in resolved_items if _sort_key_for_value(it.values.get(sort), sort_col_type)[0] == 0]
        empty = [it for it in resolved_items if _sort_key_for_value(it.values.get(sort), sort_col_type)[0] == 1]
        non_empty.sort(key=lambda it: _sort_key_for_value(it.values.get(sort), sort_col_type)[1], reverse=reverse)
        resolved_items = non_empty + empty

    offset = 0
    if cursor is not None:
        try:
            offset = int(cursor)
            if offset < 0:
                raise ValueError
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cursor value",
            ) from exc

    total_count = len(resolved_items)
    page_items = resolved_items[offset : offset + limit]
    has_more = (offset + limit) < total_count
    next_cursor = str(offset + limit) if has_more else None

    return RowPageResponse(
        dataset_id=dataset.id,
        version_id=resolved_vid,
        total_count=total_count,
        limit=limit,
        next_cursor=next_cursor,
        has_more=has_more,
        items=page_items,
    )


@router.post(
    "/datasets/{dataset_id}/profile",
    response_model=JobStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_dataset_profile(
    dataset_id: str,
    dataset_ctx: Annotated[
        tuple[Dataset, Project, Membership],
        Depends(require_dataset_role(["admin", "steward"])),
    ],
):
    """Manually trigger re-profiling and issue detection of a dataset."""
    dataset, _, _ = dataset_ctx
    job = enqueue(profile_dataset, dataset_id=dataset.id)
    return JobStatusResponse(
        job_id=job.id,
        status=job.get_status(),
        result=job.result,
        error=job.error,
    )


@router.get("/datasets/{dataset_id}/issues", response_model=list[IssueResponse])
def get_dataset_issues(
    dataset_id: str,
    dataset_ctx: Annotated[
        tuple[Dataset, Project, Membership],
        Depends(require_dataset_role(["admin", "steward", "stakeholder", "contributor"])),
    ],
    db: Annotated[Session, Depends(get_db)],
    severity: Annotated[str | None, Query()] = None,
    type: Annotated[str | None, Query()] = None,
    column_id: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
):
    """Retrieve detected and human-created issues for a dataset with optional filters."""
    dataset, _, _ = dataset_ctx
    query = db.query(Issue).filter(Issue.dataset_id == dataset.id)

    if severity:
        query = query.filter(Issue.severity == severity)
    if type:
        query = query.filter(Issue.type == type)
    if column_id:
        query = query.filter(Issue.column_id == column_id)
    if status_filter:
        query = query.filter(Issue.status == status_filter)

    severity_order = case(
        (Issue.severity == "critical", 0),
        (Issue.severity == "high", 1),
        (Issue.severity == "medium", 2),
        (Issue.severity == "low", 3),
        else_=4,
    )
    return query.order_by(severity_order, Issue.created_at.asc()).all()

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.database import get_db
from app.models.entities import Dataset, Membership, Project
from app.routers.deps import require_project_role
from app.schemas.dataset import (
    DatasetItemSummary,
    DatasetResponse,
    DatasetUploadResponse,
)
from app.services.ingest import inspect_xlsx_sheets, parse_and_persist_dataset
from app.services.storage import get_storage
from app.workers import enqueue

router = APIRouter(tags=["Datasets"])

ALLOWED_EXTENSIONS = {".csv", ".tsv", ".xlsx"}


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

    # Read content and validate max file size
    content = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    # Save original file untouched (byte-identical)
    storage = get_storage()
    stored_path = storage.save(file.filename, content)

    base_name = Path(file.filename).stem

    # Multi-sheet Excel handling
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

    # Single-sheet CSV, TSV, or single-sheet Excel
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
    """List all datasets in a project."""
    project, _ = project_and_membership
    datasets = (
        db.query(Dataset)
        .filter(Dataset.project_id == project.id)
        .order_by(Dataset.created_at.desc())
        .all()
    )
    return datasets


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
def get_dataset(
    dataset_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    """Retrieve metadata and status for a specific dataset."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found",
        )
    return dataset

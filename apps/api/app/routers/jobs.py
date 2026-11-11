from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.entities import Dataset, Issue, Membership, Project, User
from app.routers.deps import get_current_user
from app.schemas.dataset import JobStatusResponse
from app.workers import get_job

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Poll the status of an asynchronous background job (authenticated workspace access required)."""
    handle = get_job(job_id)
    if not handle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    dataset_id = getattr(handle, "dataset_id", None)
    if not dataset_id and isinstance(handle.result, dict):
        dataset_id = handle.result.get("dataset_id")

    if not isinstance(dataset_id, str) or not dataset_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this background job",
        )

    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    project = db.query(Project).filter(Project.id == dataset.project_id).first() if dataset else None
    membership = (
        db.query(Membership)
        .filter(
            Membership.workspace_id == project.workspace_id,
            Membership.user_id == current_user.id,
        )
        .first()
        if project
        else None
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this background job",
        )
    if membership.role == "contributor":
        assigned = (
            db.query(Issue.id)
            .filter(Issue.dataset_id == dataset.id, Issue.assignee_id == current_user.id)
            .first()
        )
        if not assigned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Contributors may only inspect jobs for assigned datasets",
            )

    return JobStatusResponse(
        job_id=handle.id,
        status=handle.get_status(),
        result=handle.result,
        error=handle.error,
    )

from fastapi import APIRouter, HTTPException, status

from app.schemas.dataset import JobStatusResponse
from app.workers import get_job

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str):
    """Poll the status of an asynchronous background job."""
    handle = get_job(job_id)
    if not handle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return JobStatusResponse(
        job_id=handle.id,
        status=handle.get_status(),
        result=handle.result,
        error=handle.error,
    )

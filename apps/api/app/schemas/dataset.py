from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DatasetItemSummary(BaseModel):
    dataset_id: str
    name: str
    job_id: str


class DatasetUploadResponse(BaseModel):
    dataset_id: str
    job_id: str
    name: str
    status: str
    datasets: list[DatasetItemSummary] | None = None


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    source_type: str
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Any | None = None
    error: str | None = None

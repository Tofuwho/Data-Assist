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


class IssueCounts(BaseModel):
    total: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    source_type: str
    status: str
    error_message: str | None = None
    stats_json: dict[str, Any] | None = None
    issue_counts: IssueCounts | None = None
    created_at: datetime
    updated_at: datetime


class ColumnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    name: str
    position: int
    inferred_type: str | None = None
    semantic_hint: str | None = None
    stats_json: dict[str, Any] | None = None
    created_at: datetime


class IssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    type: str
    severity: str
    column_id: str | None = None
    row_ids: list[str] | None = None
    affected_count: int = 0
    status: str
    source: str = "auto"
    assignee_id: str | None = None
    description: str
    details_json: dict[str, Any] | None = None
    created_at: datetime


class RowItemResponse(BaseModel):
    id: str
    row_index: int
    values: dict[str, Any]


class RowPageResponse(BaseModel):
    dataset_id: str
    version_id: str | None = None
    total_count: int
    limit: int
    next_cursor: str | None = None
    has_more: bool
    items: list[RowItemResponse]


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Any | None = None
    error: str | None = None

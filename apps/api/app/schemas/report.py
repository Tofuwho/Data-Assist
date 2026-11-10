from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ReportTemplate = Literal[
    "auto",
    "executive_sales",
    "survey_insights",
    "inventory_summary",
    "general_summary",
]
ReportStatus = Literal["draft", "in_review", "approved", "published"]


class AnalyzeDatasetRequest(BaseModel):
    version_id: str | None = None
    template: ReportTemplate = "auto"
    title: str | None = Field(default=None, max_length=255)
    include_narrative: bool = True
    llm_provider: str | None = None


class CreateReportRequest(BaseModel):
    dataset_id: str
    dataset_version_id: str | None = None
    title: str | None = Field(default=None, max_length=255)
    template: ReportTemplate = "auto"
    layout_json: dict[str, Any] | None = None
    include_narrative: bool = True
    llm_provider: str | None = None


class UpdateReportRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: ReportStatus | None = None
    layout_json: dict[str, Any] | None = None


class GenerateNarrativeRequest(BaseModel):
    block_id: str | None = None
    llm_provider: str | None = None


class AnalysisColumnOption(BaseModel):
    name: str
    inferred_type: str | None = None
    semantic_hint: str | None = None


class DatasetAnalysisResponse(BaseModel):
    dataset_id: str
    dataset_name: str
    version_id: str
    version_number: int
    generated_at: str
    overview: dict[str, Any]
    measures: list[dict[str, Any]]
    primary_measure: dict[str, Any] | None = None
    dimensions: list[dict[str, Any]]
    segment_breakdowns: list[dict[str, Any]]
    time_series: dict[str, Any] | None = None
    correlations: list[dict[str, Any]]
    data_quality_caveats: list[dict[str, Any]]
    columns: list[AnalysisColumnOption] = Field(default_factory=list)


class ReportListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    dataset_id: str
    dataset_name: str
    dataset_version_id: str
    version_number: int
    title: str
    status: str
    template: str = "general_summary"
    block_count: int = 0
    created_at: datetime
    updated_at: datetime


class ComputedBlockResponse(BaseModel):
    id: str
    type: str
    title: str
    subtitle: str | None = None
    width: str = "full"
    config: dict[str, Any] = Field(default_factory=dict)
    data: Any = None


class ReportDetailResponse(BaseModel):
    id: str
    project_id: str
    dataset_id: str
    dataset_name: str
    dataset_version_id: str
    version_number: int
    title: str
    status: str
    template: str
    layout_json: dict[str, Any]
    computed_blocks: list[ComputedBlockResponse]
    analysis: DatasetAnalysisResponse
    created_at: datetime
    updated_at: datetime


class RowChangeAuditItem(BaseModel):
    id: str
    column_name: str
    before: str | None = None
    after: str | None = None
    source: str
    reason: str | None = None
    status: str
    created_at: str | None = None


class LineageRowItem(BaseModel):
    row_id: str
    row_index: int
    raw_values: dict[str, Any]
    effective_values: dict[str, Any]
    changed_columns: list[str]
    changes: list[RowChangeAuditItem] = Field(default_factory=list)


class BlockLineageResponse(BaseModel):
    block_id: str
    block_type: str
    block_title: str
    bucket_key: str | None = None
    bucket_label: str | None = None
    dataset_id: str
    dataset_name: str
    version_id: str
    version_number: int
    highlight_columns: list[str]
    columns: list[str]
    total_matching_rows: int
    excluded_row_count: int
    excluded_reasons: dict[str, int]
    limit: int
    offset: int
    has_more: bool
    rows: list[LineageRowItem]

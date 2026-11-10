from dataclasses import dataclass, field
from typing import Any

MAX_STORED_ROW_IDS = 1000


@dataclass
class DetectedIssue:
    """Common shape returned by every deterministic issue detector."""

    issue_type: str
    severity: str  # low | medium | high | critical
    column_id: str | None
    row_ids: list[str]
    affected_count: int
    description: str
    details_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class ColumnInfo:
    """Lightweight column context passed to detectors."""

    id: str
    name: str
    position: int
    inferred_type: str
    semantic_hint: str | None
    stats_json: dict[str, Any]


@dataclass
class RowInfo:
    """Lightweight row context passed to detectors."""

    id: str
    row_index: int
    values: dict[str, Any]

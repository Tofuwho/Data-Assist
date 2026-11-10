from typing import Any

from app.services.profiling.detectors.base import ColumnInfo, DetectedIssue, RowInfo
from app.services.profiling.profiler import is_null_or_null_like


def detect_missing_values(columns: list[ColumnInfo], rows: list[RowInfo]) -> list[DetectedIssue]:
    """Detect missing and null-like values per column with severity based on null %."""
    issues: list[DetectedIssue] = []
    if not rows:
        return issues

    for col in columns:
        stats = col.stats_json or {}
        null_count = stats.get("null_count", 0)
        null_pct = stats.get("null_pct", 0.0)
        if null_count <= 0:
            continue

        affected_row_ids: list[str] = []
        examples: list[dict[str, Any]] = []
        for r in rows:
            raw_val = r.values.get(col.name, "")
            is_missing, is_null_like = is_null_or_null_like(raw_val)
            if is_missing:
                affected_row_ids.append(r.id)
                if len(examples) < 5:
                    examples.append(
                        {
                            "row_index": r.row_index,
                            "value": str(raw_val) if raw_val is not None else "",
                            "kind": "null_like" if is_null_like else "empty",
                        }
                    )

        if null_pct > 20.0:
            severity = "high"
        elif null_pct >= 5.0:
            severity = "medium"
        else:
            severity = "low"

        empty_cnt = stats.get("empty_count", 0)
        null_like_cnt = stats.get("null_like_count", 0)
        issues.append(
            DetectedIssue(
                issue_type="missing_values",
                severity=severity,
                column_id=col.id,
                row_ids=affected_row_ids,
                affected_count=len(affected_row_ids),
                description=f"Column `{col.name}` has {len(affected_row_ids)} missing or null-like value(s) ({null_pct}%)",
                details_json={
                    "column_name": col.name,
                    "null_count": len(affected_row_ids),
                    "empty_count": empty_cnt,
                    "null_like_count": null_like_cnt,
                    "null_pct": null_pct,
                    "examples": examples,
                },
            )
        )

    return issues

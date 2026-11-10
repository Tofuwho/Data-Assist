from collections import defaultdict
from typing import Any

from app.services.profiling.detectors.base import ColumnInfo, DetectedIssue, RowInfo


def detect_duplicate_rows(columns: list[ColumnInfo], rows: list[RowInfo]) -> list[DetectedIssue]:
    """Detect exact duplicate rows across all dataset columns."""
    if len(rows) < 2 or not columns:
        return []

    col_names = [c.name for c in columns]
    groups: dict[tuple[str, ...], list[RowInfo]] = defaultdict(list)

    for r in rows:
        key = tuple(str(r.values.get(name, "")) for name in col_names)
        groups[key].append(r)

    dup_groups = [grp for grp in groups.values() if len(grp) > 1]
    if not dup_groups:
        return []

    affected_row_ids: list[str] = []
    sample_groups: list[dict[str, Any]] = []
    extra_count = 0

    for grp in dup_groups:
        extra_count += len(grp) - 1
        for r in grp:
            affected_row_ids.append(r.id)
        if len(sample_groups) < 5:
            sample_groups.append(
                {
                    "row_indices": [r.row_index for r in grp[:10]],
                    "count": len(grp),
                    "sample": {k: grp[0].values.get(k, "") for k in col_names[:5]},
                }
            )

    return [
        DetectedIssue(
            issue_type="duplicate_rows",
            severity="medium",
            column_id=None,
            row_ids=affected_row_ids,
            affected_count=len(affected_row_ids),
            description=f"Found {len(dup_groups)} exact duplicate row group(s) affecting {len(affected_row_ids)} row(s) ({extra_count} extra copy/copies)",
            details_json={
                "duplicate_groups_count": len(dup_groups),
                "extra_duplicates_count": extra_count,
                "examples": sample_groups,
            },
        )
    ]

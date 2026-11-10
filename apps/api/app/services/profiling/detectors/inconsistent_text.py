from collections import defaultdict
from typing import Any

from app.services.profiling.detectors.base import ColumnInfo, DetectedIssue, RowInfo
from app.services.profiling.profiler import is_null_or_null_like


def detect_inconsistent_text(columns: list[ColumnInfo], rows: list[RowInfo]) -> list[DetectedIssue]:
    """Detect leading/trailing whitespace and inconsistent casing across text/category values."""
    issues: list[DetectedIssue] = []
    if not rows:
        return issues

    for col in columns:
        # Skip free_text sentences for case noise; still check whitespace everywhere
        whitespace_rows: list[RowInfo] = []
        case_groups: dict[str, dict[str, list[RowInfo]]] = defaultdict(lambda: defaultdict(list))

        for r in rows:
            raw = r.values.get(col.name, "")
            is_missing, _ = is_null_or_null_like(raw)
            if is_missing:
                continue
            s = str(raw)
            stripped = s.strip()
            if s != stripped:
                whitespace_rows.append(r)

            if col.inferred_type not in ("free_text", "date", "datetime"):
                case_groups[stripped.lower()][stripped].append(r)

        casing_conflicts = {
            norm: variants
            for norm, variants in case_groups.items()
            if len(variants) > 1
        }

        if not whitespace_rows and not casing_conflicts:
            continue

        affected_set: set[str] = {r.id for r in whitespace_rows}
        conflict_examples: list[dict[str, Any]] = []
        for _norm, variants in list(casing_conflicts.items())[:5]:
            conflict_examples.append({"variants": list(variants.keys())})
            for r_list in variants.values():
                for r in r_list:
                    affected_set.add(r.id)

        # Include remaining conflict rows beyond preview
        for variants in casing_conflicts.values():
            for r_list in variants.values():
                for r in r_list:
                    affected_set.add(r.id)

        ordered_ids = [r.id for r in rows if r.id in affected_set]
        reasons: list[str] = []
        if whitespace_rows:
            reasons.append(f"{len(whitespace_rows)} value(s) with leading/trailing whitespace")
        if casing_conflicts:
            reasons.append(f"{len(casing_conflicts)} casing conflict group(s)")

        issues.append(
            DetectedIssue(
                issue_type="inconsistent_text",
                severity="low",
                column_id=col.id,
                row_ids=ordered_ids,
                affected_count=len(ordered_ids),
                description=f"Column `{col.name}` has {' and '.join(reasons)}",
                details_json={
                    "column_name": col.name,
                    "whitespace_count": len(whitespace_rows),
                    "casing_conflicts_count": len(casing_conflicts),
                    "examples": {
                        "whitespace": [str(r.values.get(col.name, "")) for r in whitespace_rows[:5]],
                        "casing": conflict_examples,
                    },
                },
            )
        )

    return issues

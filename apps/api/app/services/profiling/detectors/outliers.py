from typing import Any

from app.services.profiling.detectors.base import ColumnInfo, DetectedIssue, RowInfo
from app.services.profiling.profiler import (
    is_null_or_null_like,
    parse_currency_value,
    parse_numeric_value,
    parse_percentage_value,
)


def _extract_numeric(val: str, inferred_type: str) -> float | None:
    s = val.strip()
    if inferred_type == "currency":
        c = parse_currency_value(s)
        if c is not None:
            return c
        _, num = parse_numeric_value(s)
        return num
    if inferred_type == "percentage":
        return parse_percentage_value(s)
    if inferred_type in ("integer", "decimal"):
        _, num = parse_numeric_value(s)
        return num
    return None


def detect_outliers(columns: list[ColumnInfo], rows: list[RowInfo]) -> list[DetectedIssue]:
    """Detect statistical outliers using the IQR method (1.5 * IQR). Flags only; never alters values."""
    issues: list[DetectedIssue] = []
    if len(rows) < 5:
        return issues

    for col in columns:
        if col.inferred_type not in ("integer", "decimal", "currency", "percentage"):
            continue

        stats = col.stats_json or {}
        numeric = stats.get("numeric")
        if not numeric or numeric.get("valid_count", 0) < 5:
            continue

        q1 = numeric["q1"]
        q3 = numeric["q3"]
        iqr = numeric["iqr"]
        if iqr <= 0:
            continue

        lower_fence = q1 - 1.5 * iqr
        upper_fence = q3 + 1.5 * iqr

        outlier_rows: list[RowInfo] = []
        examples: list[dict[str, Any]] = []

        for r in rows:
            raw = r.values.get(col.name, "")
            is_missing, _ = is_null_or_null_like(raw)
            if is_missing:
                continue
            num = _extract_numeric(str(raw), col.inferred_type)
            if num is None:
                continue
            if num < lower_fence or num > upper_fence:
                outlier_rows.append(r)
                if len(examples) < 5:
                    examples.append(
                        {
                            "row_index": r.row_index,
                            "raw_value": str(raw),
                            "numeric_value": num,
                        }
                    )

        if outlier_rows:
            issues.append(
                DetectedIssue(
                    issue_type="outliers",
                    severity="low",
                    column_id=col.id,
                    row_ids=[r.id for r in outlier_rows],
                    affected_count=len(outlier_rows),
                    description=f"Column `{col.name}` has {len(outlier_rows)} numeric outlier(s) outside IQR bounds [{round(lower_fence, 2)}, {round(upper_fence, 2)}]",
                    details_json={
                        "column_name": col.name,
                        "method": "iqr",
                        "q1": q1,
                        "q3": q3,
                        "iqr": iqr,
                        "lower_fence": round(lower_fence, 4),
                        "upper_fence": round(upper_fence, 4),
                        "examples": examples,
                    },
                )
            )

    return issues

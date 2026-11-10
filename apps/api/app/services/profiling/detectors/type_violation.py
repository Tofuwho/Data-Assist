from typing import Any

from app.services.profiling.detectors.base import ColumnInfo, DetectedIssue, RowInfo
from app.services.profiling.profiler import (
    BOOL_TEXT_VALUES,
    EMAIL_RE,
    PHONE_RE,
    is_null_or_null_like,
    parse_currency_value,
    parse_date_or_datetime,
    parse_numeric_value,
    parse_percentage_value,
)

STRICT_TYPED_COLUMNS = {
    "integer",
    "decimal",
    "currency",
    "percentage",
    "date",
    "datetime",
    "boolean",
    "email",
    "phone",
}


def _matches_inferred_type(val: str, inferred_type: str) -> bool:
    s = val.strip()
    if inferred_type == "integer":
        kind, _ = parse_numeric_value(s)
        return kind == "integer"
    if inferred_type == "decimal":
        kind, _ = parse_numeric_value(s)
        return kind in ("integer", "decimal")
    if inferred_type == "currency":
        if parse_currency_value(s) is not None:
            return True
        kind, _ = parse_numeric_value(s)
        return kind is not None
    if inferred_type == "percentage":
        return parse_percentage_value(s) is not None
    if inferred_type == "date":
        dt_kind, _, _, _ = parse_date_or_datetime(s)
        return dt_kind == "date"
    if inferred_type == "datetime":
        dt_kind, _, _, _ = parse_date_or_datetime(s)
        return dt_kind in ("date", "datetime")
    if inferred_type == "boolean":
        return s.lower() in BOOL_TEXT_VALUES
    if inferred_type == "email":
        return bool(EMAIL_RE.match(s))
    if inferred_type == "phone":
        digits = sum(c.isdigit() for c in s)
        return bool(PHONE_RE.match(s)) and 7 <= digits <= 15
    return True


def detect_type_violations(columns: list[ColumnInfo], rows: list[RowInfo]) -> list[DetectedIssue]:
    """Detect values that violate a column's dominant inferred type."""
    issues: list[DetectedIssue] = []
    if not rows:
        return issues

    for col in columns:
        if col.inferred_type not in STRICT_TYPED_COLUMNS:
            continue

        violating_rows: list[RowInfo] = []
        examples: list[dict[str, Any]] = []

        for r in rows:
            raw = r.values.get(col.name, "")
            is_missing, _ = is_null_or_null_like(raw)
            if is_missing:
                continue
            s = str(raw)
            if not _matches_inferred_type(s, col.inferred_type):
                violating_rows.append(r)
                if len(examples) < 5:
                    examples.append({"row_index": r.row_index, "value": s})

        if violating_rows:
            issues.append(
                DetectedIssue(
                    issue_type="type_violation",
                    severity="medium",
                    column_id=col.id,
                    row_ids=[r.id for r in violating_rows],
                    affected_count=len(violating_rows),
                    description=f"Column `{col.name}` (expected `{col.inferred_type}`) has {len(violating_rows)} value(s) violating its inferred type",
                    details_json={
                        "column_name": col.name,
                        "expected_type": col.inferred_type,
                        "examples": examples,
                    },
                )
            )

    return issues

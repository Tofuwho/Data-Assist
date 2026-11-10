import re
from collections import Counter

from app.services.profiling.detectors.base import ColumnInfo, DetectedIssue, RowInfo
from app.services.profiling.profiler import (
    is_null_or_null_like,
    parse_currency_value,
    parse_date_or_datetime,
    parse_numeric_value,
)


def _currency_style(val: str) -> str | None:
    s = val.strip()
    if "$" in s:
        return "USD_symbol ($)"
    if "€" in s:
        return "EUR_symbol (€)"
    if "£" in s:
        return "GBP_symbol (£)"
    if "¥" in s:
        return "JPY_symbol (¥)"
    m = re.search(r"\b(USD|EUR|GBP|CAD|AUD|JPY|SGD|CHF)\b", s, re.IGNORECASE)
    if m:
        return f"code_{m.group(1).upper()}"
    kind, _ = parse_numeric_value(s)
    if kind is not None:
        return "plain_number"
    return None


def detect_mixed_formats(columns: list[ColumnInfo], rows: list[RowInfo]) -> list[DetectedIssue]:
    """Detect columns mixing incompatible date, currency, numeric, or scale formats."""
    issues: list[DetectedIssue] = []
    if not rows:
        return issues

    for col in columns:
        stats = col.stats_json or {}
        inferred = col.inferred_type

        # 1. Mixed date/datetime formats or ambiguous dates
        if inferred in ("date", "datetime"):
            date_info = stats.get("date") or {}
            formats: dict[str, int] = date_info.get("formats") or {}
            ambig = date_info.get("ambiguous_count", 0)
            if len(formats) > 1 or ambig > 0:
                dominant_fmt = max(formats, key=formats.get) if formats else None
                affected_ids: list[str] = []
                examples: list[dict[str, str]] = []
                for r in rows:
                    raw = r.values.get(col.name, "")
                    is_missing, _ = is_null_or_null_like(raw)
                    if is_missing:
                        continue
                    _, fmt_label, _, is_ambig = parse_date_or_datetime(str(raw))
                    if fmt_label and (fmt_label != dominant_fmt or is_ambig):
                        affected_ids.append(r.id)
                        if len(examples) < 5:
                            examples.append({"value": str(raw), "format": fmt_label})

                if not affected_ids:
                    affected_ids = [r.id for r in rows if not is_null_or_null_like(r.values.get(col.name, ""))[0]]

                fmt_preview = ", ".join(list(formats.keys())[:4])
                desc = f"Column `{col.name}` mixes {len(formats)} date format(s) ({fmt_preview})"
                if ambig > 0:
                    desc += f" including {ambig} ambiguous date(s)"

                issues.append(
                    DetectedIssue(
                        issue_type="mixed_formats",
                        severity="high",
                        column_id=col.id,
                        row_ids=affected_ids,
                        affected_count=len(affected_ids),
                        description=desc,
                        details_json={
                            "column_name": col.name,
                            "formats": formats,
                            "ambiguous_count": ambig,
                            "examples": examples,
                        },
                    )
                )
            continue

        # 2. Mixed currency formats (e.g., $, USD, €, plain decimals)
        if inferred == "currency":
            styles: Counter[str] = Counter()
            row_styles: list[tuple[RowInfo, str]] = []
            for r in rows:
                raw = r.values.get(col.name, "")
                is_missing, _ = is_null_or_null_like(raw)
                if is_missing:
                    continue
                s = str(raw).strip()
                if parse_currency_value(s) is not None or parse_numeric_value(s)[0] is not None:
                    style = _currency_style(s)
                    if style:
                        styles[style] += 1
                        row_styles.append((r, style))

            if len(styles) > 1:
                dominant_style = styles.most_common(1)[0][0]
                affected_ids = [r.id for r, st in row_styles if st != dominant_style]
                examples = [
                    {"value": str(r.values.get(col.name, "")), "style": st}
                    for r, st in row_styles
                    if st != dominant_style
                ][:5]
                issues.append(
                    DetectedIssue(
                        issue_type="mixed_formats",
                        severity="high",
                        column_id=col.id,
                        row_ids=affected_ids,
                        affected_count=len(affected_ids),
                        description=f"Column `{col.name}` mixes {len(styles)} currency/number formats ({', '.join(styles.keys())})",
                        details_json={
                            "column_name": col.name,
                            "styles": dict(styles),
                            "examples": examples,
                        },
                    )
                )
            continue

        # 3. Mixed scale / value shapes in 'mixed' columns (e.g. Satisfaction_Score: 5/5, 9/10, 4, Satisfied)
        if inferred == "mixed":
            affected_ids = [
                r.id
                for r in rows
                if not is_null_or_null_like(r.values.get(col.name, ""))[0]
            ]
            patterns = stats.get("format_patterns") or {}
            issues.append(
                DetectedIssue(
                    issue_type="mixed_formats",
                    severity="medium",
                    column_id=col.id,
                    row_ids=affected_ids,
                    affected_count=len(affected_ids),
                    description=f"Column `{col.name}` mixes incompatible value formats/scales ({len(patterns)} distinct patterns)",
                    details_json={
                        "column_name": col.name,
                        "format_patterns": patterns,
                        "examples": stats.get("top_values", [])[:5],
                    },
                )
            )

    return issues

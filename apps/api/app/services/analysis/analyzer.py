import math
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from app.models.entities import ColumnModel
from app.services.analysis.resolver import (
    EffectiveDataset,
    EffectiveRow,
    extract_date_bucket,
    extract_numeric_for_analysis,
)
from app.services.profiling.profiler import is_null_or_null_like

MISSING_BUCKET_KEY = "__missing__"
MISSING_BUCKET_LABEL = "(Missing)"

CURRENCY_SYMBOL_RE = re.compile(r"(\$|€|£|¥|₹|USD|EUR|GBP|CAD|AUD|JPY|SGD|CHF)", re.IGNORECASE)


def _is_identifier_like(col: ColumnModel) -> bool:
    name = col.name.strip().lower().replace("-", "_").replace(" ", "_")
    if col.inferred_type == "identifier" or col.semantic_hint == "identifier":
        return True
    if name == "id" or name.endswith("_id") or name.startswith("id_"):
        return True
    return False


def _measure_format_style(col: ColumnModel) -> str:
    name = col.name.strip().lower()
    if col.inferred_type == "currency" or col.semantic_hint == "amount":
        return "currency"
    if col.inferred_type == "percentage" or col.semantic_hint == "percentage":
        return "percent"
    if any(tok in name for tok in ("amount", "revenue", "sales", "price", "cost", "salary", "budget", "profit")):
        return "currency"
    if any(tok in name for tok in ("pct", "percent", "rate", "margin", "ratio")):
        return "percent"
    return "number"


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * pct
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return sorted_vals[int(pos)]
    weight = pos - low
    return sorted_vals[low] * (1 - weight) + sorted_vals[high] * weight


def _compute_numeric_stats(values: list[float]) -> dict[str, float]:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    total = sum(sorted_vals)
    mid = n // 2
    if n % 2 == 1:
        median_val = sorted_vals[mid]
    else:
        median_val = (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
    q1 = _percentile(sorted_vals, 0.25)
    q3 = _percentile(sorted_vals, 0.75)
    return {
        "sum": round(total, 4),
        "mean": round(total / n, 4),
        "median": round(median_val, 4),
        "min": round(sorted_vals[0], 4),
        "max": round(sorted_vals[-1], 4),
        "q1": round(q1, 4),
        "q3": round(q3, 4),
        "iqr": round(q3 - q1, 4),
    }


def _rank_measure_score(col: ColumnModel, valid_count: int, unparseable_count: int, row_count: int) -> float:
    score = 0.0
    name = col.name.strip().lower()
    if col.inferred_type == "currency":
        score += 55.0
    elif col.inferred_type in ("decimal", "integer"):
        score += 35.0
    elif col.inferred_type == "percentage":
        score += 20.0
    elif col.inferred_type == "mixed":
        score += 5.0

    if col.semantic_hint in ("amount", "revenue", "sales"):
        score += 30.0
    elif col.semantic_hint in ("quantity", "weight"):
        score += 22.0
    elif col.semantic_hint in ("score",):
        score += 12.0

    if any(k in name for k in ("revenue", "sales", "amount", "profit", "total")):
        score += 20.0
    elif any(k in name for k in ("quantity", "qty", "units", "price", "cost", "budget", "weight")):
        score += 12.0

    if row_count > 0:
        score += (valid_count / row_count) * 15.0
        score -= (unparseable_count / row_count) * 25.0
    return score


def _rank_dimension_score(col: ColumnModel, distinct_count: int, non_null_count: int) -> float:
    if distinct_count < 2:
        return -100.0
    score = 0.0
    hint = (col.semantic_hint or "").lower()
    name = col.name.strip().lower()

    if hint in ("region", "department", "category", "status", "recommendation"):
        score += 45.0
    elif hint == "customer_name":
        score += 30.0

    if any(k in name for k in ("region", "department", "category", "status", "product", "warehouse", "recommend")):
        score += 20.0

    if col.inferred_type == "category":
        score += 25.0
    elif col.inferred_type == "boolean":
        score += 18.0
    elif col.inferred_type == "mixed":
        score += 10.0

    # Ideal stakeholder segmentation cardinality is 2..15 distinct groups
    if 2 <= distinct_count <= 12:
        score += 25.0
    elif distinct_count <= 25:
        score += 12.0
    else:
        score -= 30.0

    if non_null_count > 0:
        score += min(non_null_count / 100.0, 5.0)
    return score


def _extract_dimension_bucket(raw_val: Any) -> tuple[str, str]:
    is_missing, _ = is_null_or_null_like(raw_val)
    if is_missing:
        return MISSING_BUCKET_KEY, MISSING_BUCKET_LABEL
    cleaned = str(raw_val).strip()
    return cleaned, cleaned


def _pearson_correlation(pairs: list[tuple[float, float]]) -> float | None:
    n = len(pairs)
    if n < 5:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    den_x = sum((x - mean_x) ** 2 for x in xs)
    den_y = sum((y - mean_y) ** 2 for y in ys)
    denom = math.sqrt(den_x * den_y)
    if denom <= 1e-12:
        return None
    return round(num / denom, 4)


def _compute_dataset_completeness(effective: EffectiveDataset) -> tuple[int, float]:
    row_count = len(effective.rows)
    col_count = len(effective.columns)
    total_cells = row_count * col_count
    if total_cells == 0:
        return 0, 100.0

    null_cells = 0
    for row in effective.rows:
        for col in effective.columns:
            is_missing, _ = is_null_or_null_like(row.values.get(col.name, ""))
            if is_missing:
                null_cells += 1

    completeness_pct = round(((total_cells - null_cells) / total_cells) * 100.0, 2)
    return null_cells, completeness_pct


def analyze_dataset(effective: EffectiveDataset) -> dict[str, Any]:
    """Compute a deterministic stakeholder-grade analysis summary on an EffectiveDataset."""
    row_count = len(effective.rows)
    col_count = len(effective.columns)
    null_cells, completeness_pct = _compute_dataset_completeness(effective)

    open_issues = [i for i in effective.issues if i.status in ("open", "in_review")]
    resolved_issues = [i for i in effective.issues if i.status in ("resolved", "dismissed")]
    high_critical_issues = [i for i in open_issues if i.severity in ("high", "critical")]

    # Compute honest data readiness score
    penalty = 0.0
    for issue in open_issues:
        if issue.severity == "critical":
            penalty += 15.0
        elif issue.severity == "high":
            penalty += 8.0
        elif issue.severity == "medium":
            penalty += 3.0
        else:
            penalty += 1.0
    if completeness_pct < 100.0:
        penalty += (100.0 - completeness_pct) * 1.2
    readiness_score = max(0.0, min(100.0, round(100.0 - penalty, 1)))

    if len(high_critical_issues) >= 3 or completeness_pct < 80.0 or readiness_score < 60.0:
        readiness = "caution"
    elif open_issues or completeness_pct < 98.0:
        readiness = "needs_review"
    else:
        readiness = "verified"

    overview = {
        "row_count": row_count,
        "column_count": col_count,
        "null_cells": null_cells,
        "completeness_pct": completeness_pct,
        "open_issues_count": len(open_issues),
        "high_critical_issues_count": len(high_critical_issues),
        "resolved_issues_count": len(resolved_issues),
        "readiness": readiness,
        "readiness_score": readiness_score,
    }

    caveats: list[dict[str, Any]] = []
    caveat_idx = 1

    def add_caveat(
        severity: str,
        category: str,
        title: str,
        message: str,
        affected_count: int,
        column: str | None = None,
    ) -> None:
        nonlocal caveat_idx
        caveats.append(
            {
                "id": f"cav_{caveat_idx}",
                "severity": severity,
                "category": category,
                "column": column,
                "title": title,
                "message": message,
                "affected_count": affected_count,
            }
        )
        caveat_idx += 1

    if high_critical_issues:
        add_caveat(
            severity="high",
            category="open_issues",
            title=f"{len(high_critical_issues)} high/critical data quality issue(s) open",
            message=(
                f"{len(high_critical_issues)} high or critical quality issue(s) remain open across "
                f"{len(open_issues)} total open issue(s). Interpret downstream totals with the column caveats below."
            ),
            affected_count=len(high_critical_issues),
        )

    if completeness_pct < 99.0 and null_cells > 0:
        add_caveat(
            severity="medium" if completeness_pct >= 90.0 else "high",
            category="completeness",
            title=f"Dataset completeness is {completeness_pct}%",
            message=(
                f"{null_cells} missing or null-like cell(s) detected across {row_count * col_count} cells "
                f"({completeness_pct}% populated)."
            ),
            affected_count=null_cells,
        )

    # Identify candidate numeric measures
    measures: list[dict[str, Any]] = []
    measure_series_by_col: dict[str, list[tuple[EffectiveRow, float | None, str]]] = {}

    for col in effective.columns:
        if _is_identifier_like(col):
            continue
        if col.inferred_type not in ("currency", "integer", "decimal", "percentage", "mixed"):
            continue

        extracted: list[tuple[EffectiveRow, float | None, str]] = []
        valid_vals: list[float] = []
        missing_count = 0
        unparseable_count = 0
        currency_tokens: Counter[str] = Counter()

        for row in effective.rows:
            raw_val = row.values.get(col.name, "")
            num_val, status_flag = extract_numeric_for_analysis(raw_val, col.inferred_type)
            extracted.append((row, num_val, status_flag))
            if status_flag == "valid" and num_val is not None:
                valid_vals.append(num_val)
                if col.inferred_type == "currency":
                    for sym in CURRENCY_SYMBOL_RE.findall(str(raw_val)):
                        currency_tokens[sym.upper()] += 1
            elif status_flag == "missing":
                missing_count += 1
            else:
                unparseable_count += 1

        # Guard mixed columns (e.g. survey ratings '5/5', 'Satisfied', '4')
        non_missing_count = len(valid_vals) + unparseable_count
        if col.inferred_type == "mixed":
            if len(valid_vals) < 3 or (
                non_missing_count > 0 and len(valid_vals) / non_missing_count < 0.5
            ):
                add_caveat(
                    severity="medium",
                    category="mixed_scale",
                    column=col.name,
                    title=f"'{col.name}' mixes scales/labels ({unparseable_count} non-numeric entries)",
                    message=(
                        f"Column '{col.name}' mixes numeric scores with text or ratio formats (such as slash-separated ratings or text labels). "
                        f"It is summarized categorically rather than summed or averaged until standardized."
                    ),
                    affected_count=non_missing_count,
                )
                continue

        if not valid_vals:
            continue

        measure_series_by_col[col.name] = extracted
        stats = _compute_numeric_stats(valid_vals)
        fmt_style = _measure_format_style(col)
        score = _rank_measure_score(col, len(valid_vals), unparseable_count, row_count)

        # Normalize distinct currency symbols ($ / USD vs EUR / €)
        normalized_currency_groups: set[str] = set()
        for tok in currency_tokens:
            if tok in ("$", "USD"):
                normalized_currency_groups.add("USD ($)")
            elif tok in ("€", "EUR"):
                normalized_currency_groups.add("EUR (€)")
            elif tok in ("£", "GBP"):
                normalized_currency_groups.add("GBP (£)")
            else:
                normalized_currency_groups.add(tok)

        if len(normalized_currency_groups) > 1:
            joined = ", ".join(sorted(normalized_currency_groups))
            add_caveat(
                severity="high",
                category="mixed_currency",
                column=col.name,
                title=f"Mixed currencies in '{col.name}' ({joined})",
                message=(
                    f"Column '{col.name}' mixes currency notations ({joined}). Aggregated totals sum face values "
                    f"without FX conversion until currencies are normalized."
                ),
                affected_count=len(valid_vals),
            )

        if unparseable_count > 0:
            add_caveat(
                severity="high" if unparseable_count > max(1, int(row_count * 0.1)) else "medium",
                category="unparseable_numeric",
                column=col.name,
                title=f"{unparseable_count} unparseable value(s) excluded in '{col.name}'",
                message=(
                    f"{unparseable_count} row(s) in '{col.name}' could not be parsed as numeric and were excluded "
                    f"from sums and averages (traced in block lineage)."
                ),
                affected_count=unparseable_count,
            )

        measures.append(
            {
                "column": col.name,
                "inferred_type": col.inferred_type,
                "semantic_hint": col.semantic_hint,
                "format_style": fmt_style,
                "valid_count": len(valid_vals),
                "missing_count": missing_count,
                "unparseable_count": unparseable_count,
                "currency_notations": sorted(normalized_currency_groups),
                "is_primary": False,
                "_rank": score,
                **stats,
            }
        )

    measures.sort(key=lambda m: m["_rank"], reverse=True)
    primary_measure: dict[str, Any] | None = None
    if measures:
        measures[0]["is_primary"] = True
        primary_measure = measures[0]
    for m in measures:
        m.pop("_rank", None)

    # Identify candidate dimensions
    dimensions: list[dict[str, Any]] = []
    for col in effective.columns:
        if _is_identifier_like(col):
            continue
        if col.inferred_type in ("email", "phone", "date", "datetime", "currency", "integer", "decimal", "percentage"):
            continue

        bucket_counts: Counter[str] = Counter()
        missing_dim = 0
        for row in effective.rows:
            b_key, _ = _extract_dimension_bucket(row.values.get(col.name, ""))
            if b_key == MISSING_BUCKET_KEY:
                missing_dim += 1
            else:
                bucket_counts[b_key] += 1

        distinct_count = len(bucket_counts)
        non_null_count = sum(bucket_counts.values())
        if distinct_count < 2:
            continue
        if col.inferred_type == "free_text" and distinct_count > 12:
            continue
        if distinct_count > 25 and (col.semantic_hint or "") not in ("customer_name", "region", "department", "category"):
            continue

        dim_score = _rank_dimension_score(col, distinct_count, non_null_count)
        top_values = [
            {
                "value": val,
                "count": cnt,
                "share_pct": round((cnt / row_count) * 100.0, 2) if row_count else 0.0,
            }
            for val, cnt in bucket_counts.most_common(8)
        ]
        dimensions.append(
            {
                "column": col.name,
                "inferred_type": col.inferred_type,
                "semantic_hint": col.semantic_hint,
                "distinct_count": distinct_count,
                "non_null_count": non_null_count,
                "missing_count": missing_dim,
                "top_values": top_values,
                "_rank": dim_score,
            }
        )

    dimensions.sort(key=lambda d: d["_rank"], reverse=True)
    for d in dimensions:
        d.pop("_rank", None)

    # Segment breakdowns for top 3 dimensions
    primary_col_name = primary_measure["column"] if primary_measure else None
    primary_series = measure_series_by_col.get(primary_col_name) if primary_col_name else None
    primary_total_sum = primary_measure["sum"] if primary_measure else 0.0

    segment_breakdowns: list[dict[str, Any]] = []
    for dim in dimensions[:3]:
        dim_col = dim["column"]
        buckets: dict[str, dict[str, Any]] = {}

        for idx, row in enumerate(effective.rows):
            b_key, b_label = _extract_dimension_bucket(row.values.get(dim_col, ""))
            if b_key not in buckets:
                buckets[b_key] = {
                    "key": b_key,
                    "label": b_label,
                    "row_count": 0,
                    "metric_valid_count": 0,
                    "metric_excluded_count": 0,
                    "metric_values": [],
                }
            entry = buckets[b_key]
            entry["row_count"] += 1
            if primary_series is not None:
                _, num_val, status_flag = primary_series[idx]
                if status_flag == "valid" and num_val is not None:
                    entry["metric_valid_count"] += 1
                    entry["metric_values"].append(num_val)
                else:
                    entry["metric_excluded_count"] += 1

        segments_out: list[dict[str, Any]] = []
        for entry in buckets.values():
            m_vals = entry.pop("metric_values")
            m_sum = round(sum(m_vals), 4) if m_vals else 0.0
            m_mean = round(sum(m_vals) / len(m_vals), 4) if m_vals else None
            segments_out.append(
                {
                    **entry,
                    "row_share_pct": round((entry["row_count"] / row_count) * 100.0, 2) if row_count else 0.0,
                    "metric_sum": m_sum if primary_col_name else None,
                    "metric_mean": m_mean if primary_col_name else None,
                    "metric_share_pct": (
                        round((m_sum / primary_total_sum) * 100.0, 2)
                        if primary_col_name and primary_total_sum > 0
                        else 0.0
                    ),
                }
            )

        if primary_col_name:
            segments_out.sort(
                key=lambda s: (s["key"] == MISSING_BUCKET_KEY, -(s["metric_sum"] or 0.0), -s["row_count"], s["label"])
            )
        else:
            segments_out.sort(key=lambda s: (s["key"] == MISSING_BUCKET_KEY, -s["row_count"], s["label"]))

        non_missing_segments = [s for s in segments_out if s["key"] != MISSING_BUCKET_KEY]
        top_seg = non_missing_segments[0] if non_missing_segments else (segments_out[0] if segments_out else None)

        segment_breakdowns.append(
            {
                "dimension": dim_col,
                "semantic_hint": dim["semantic_hint"],
                "metric_column": primary_col_name,
                "metric_format_style": primary_measure["format_style"] if primary_measure else "number",
                "unique_bucket_count": len(segments_out),
                "top_segment": top_seg["label"] if top_seg else None,
                "top_segment_share_pct": (
                    top_seg["metric_share_pct"] if (top_seg and primary_col_name) else (top_seg["row_share_pct"] if top_seg else 0.0)
                ),
                "segments": segments_out[:15],
            }
        )

    # Time series across primary date/datetime column
    time_series: dict[str, Any] | None = None
    date_cols = [c for c in effective.columns if c.inferred_type in ("date", "datetime")]
    if date_cols:
        date_col = date_cols[0]
        # Decide granularity from non-ambiguous dates first
        parsed_day_keys: list[str] = []
        valid_date_count = 0
        ambiguous_skipped = 0
        unparseable_skipped = 0
        missing_dates = 0

        for row in effective.rows:
            k, _, st = extract_date_bucket(row.values.get(date_col.name, ""), granularity="day")
            if st == "valid" and k is not None:
                valid_date_count += 1
                parsed_day_keys.append(k)
            elif st == "ambiguous":
                ambiguous_skipped += 1
            elif st == "missing":
                missing_dates += 1
            else:
                unparseable_skipped += 1

        if ambiguous_skipped > 0:
            add_caveat(
                severity="high",
                category="ambiguous_dates",
                column=date_col.name,
                title=f"{ambiguous_skipped} ambiguous date(s) skipped in '{date_col.name}'",
                message=(
                    f"{ambiguous_skipped} date value(s) in '{date_col.name}' have ambiguous MM/DD vs DD/MM order. "
                    f"Never silently guessed; excluded from time-series charts until standardized."
                ),
                affected_count=ambiguous_skipped,
            )
        if unparseable_skipped > 0:
            add_caveat(
                severity="medium",
                category="unparseable_dates",
                column=date_col.name,
                title=f"{unparseable_skipped} unparseable date(s) skipped in '{date_col.name}'",
                message=(
                    f"{unparseable_skipped} value(s) in '{date_col.name}' could not be parsed as dates and were "
                    f"excluded from trend calculations."
                ),
                affected_count=unparseable_skipped,
            )

        granularity = "day"
        if len(parsed_day_keys) >= 2:
            span_days = (
                datetime.fromisoformat(max(parsed_day_keys)).date()
                - datetime.fromisoformat(min(parsed_day_keys)).date()
            ).days
            if span_days > 90:
                granularity = "month"

        ts_buckets: dict[str, dict[str, Any]] = {}
        for idx, row in enumerate(effective.rows):
            b_key, b_label, st = extract_date_bucket(row.values.get(date_col.name, ""), granularity=granularity)
            if st != "valid" or b_key is None:
                continue
            if b_key not in ts_buckets:
                ts_buckets[b_key] = {
                    "bucket_key": b_key,
                    "label": b_label or b_key,
                    "row_count": 0,
                    "metric_valid_count": 0,
                    "metric_values": [],
                }
            pt = ts_buckets[b_key]
            pt["row_count"] += 1
            if primary_series is not None:
                _, num_val, m_status = primary_series[idx]
                if m_status == "valid" and num_val is not None:
                    pt["metric_valid_count"] += 1
                    pt["metric_values"].append(num_val)

        points: list[dict[str, Any]] = []
        for b_key in sorted(ts_buckets.keys()):
            pt = ts_buckets[b_key]
            vals = pt.pop("metric_values")
            pt["metric_sum"] = round(sum(vals), 4) if (vals and primary_col_name) else (0.0 if primary_col_name else None)
            pt["metric_mean"] = round(sum(vals) / len(vals), 4) if vals else None
            points.append(pt)

        period_change_abs: float | None = None
        period_change_pct: float | None = None
        peak_period: dict[str, Any] | None = None
        if len(points) >= 2:
            val_key = "metric_sum" if primary_col_name else "row_count"
            first_v = float(points[0][val_key] or 0.0)
            last_v = float(points[-1][val_key] or 0.0)
            period_change_abs = round(last_v - first_v, 4)
            if abs(first_v) > 1e-9:
                period_change_pct = round(((last_v - first_v) / abs(first_v)) * 100.0, 2)
            peak = max(points, key=lambda p: float(p[val_key] or 0.0))
            peak_period = {
                "bucket_key": peak["bucket_key"],
                "label": peak["label"],
                "value": peak[val_key],
            }

        time_series = {
            "date_column": date_col.name,
            "granularity": granularity,
            "metric_column": primary_col_name,
            "metric_format_style": primary_measure["format_style"] if primary_measure else "number",
            "valid_date_count": valid_date_count,
            "ambiguous_skipped_count": ambiguous_skipped,
            "unparseable_skipped_count": unparseable_skipped,
            "missing_count": missing_dates,
            "start_period": points[0]["bucket_key"] if points else None,
            "end_period": points[-1]["bucket_key"] if points else None,
            "period_change_abs": period_change_abs,
            "period_change_pct": period_change_pct,
            "peak_period": peak_period,
            "points": points,
        }

    # Pairwise Pearson correlations across numeric measures
    correlations: list[dict[str, Any]] = []
    if len(measures) >= 2:
        for i in range(len(measures)):
            for j in range(i + 1, len(measures)):
                col_a = measures[i]["column"]
                col_b = measures[j]["column"]
                ser_a = measure_series_by_col[col_a]
                ser_b = measure_series_by_col[col_b]
                pairs = [
                    (ser_a[idx][1], ser_b[idx][1])
                    for idx in range(row_count)
                    if ser_a[idx][2] == "valid"
                    and ser_b[idx][2] == "valid"
                    and ser_a[idx][1] is not None
                    and ser_b[idx][1] is not None
                ]
                r_val = _pearson_correlation(pairs)
                if r_val is None:
                    continue
                abs_r = abs(r_val)
                strength = "strong" if abs_r >= 0.7 else ("moderate" if abs_r >= 0.4 else "weak")
                direction = "positive" if r_val >= 0 else "negative"
                correlations.append(
                    {
                        "column_a": col_a,
                        "column_b": col_b,
                        "pearson_r": r_val,
                        "paired_rows": len(pairs),
                        "strength": strength,
                        "direction": direction,
                    }
                )
        correlations.sort(key=lambda c: abs(c["pearson_r"]), reverse=True)

    # Surface actionable label_variants / duplicate / near_duplicates open issues as stakeholder caveats
    for issue in open_issues:
        if issue.type in ("label_variants", "duplicate_rows", "near_duplicates"):
            col_name = effective.columns_by_id[issue.column_id].name if issue.column_id in effective.columns_by_id else None
            add_caveat(
                severity=issue.severity,
                category=issue.type,
                column=col_name,
                title=issue.description,
                message=(
                    f"{issue.description} Segment totals reflect raw distinct values until standardized or merged."
                ),
                affected_count=issue.affected_count,
            )

    return {
        "dataset_id": effective.dataset.id,
        "dataset_name": effective.dataset.name,
        "version_id": effective.version.id,
        "version_number": effective.version.version_number,
        "generated_at": datetime.now(UTC).isoformat(),
        "overview": overview,
        "measures": measures,
        "primary_measure": primary_measure,
        "dimensions": dimensions,
        "segment_breakdowns": segment_breakdowns,
        "time_series": time_series,
        "correlations": correlations,
        "data_quality_caveats": caveats,
    }


def _detect_template(effective: EffectiveDataset, analysis: dict[str, Any], requested: str) -> str:
    if requested != "auto":
        return requested

    col_names = {c.name.strip().lower() for c in effective.columns}
    hints = {c.semantic_hint for c in effective.columns if c.semantic_hint}

    survey_score = sum(
        1
        for kw in ("respondent", "satisfaction", "recommend", "feedback", "department", "score")
        if any(kw in n for n in col_names) or kw in hints
    )
    inventory_score = sum(
        1
        for kw in ("sku", "warehouse", "quantity", "weight", "reorder", "stock")
        if any(kw in n for n in col_names) or kw in hints
    )
    sales_score = sum(
        1
        for kw in ("amount", "revenue", "sales", "transaction", "customer", "product", "price")
        if any(kw in n for n in col_names) or kw in hints
    )

    if survey_score >= 2:
        return "survey_insights"
    if inventory_score >= 2:
        return "inventory_summary"
    if sales_score >= 2 or (analysis.get("primary_measure") and analysis["primary_measure"]["format_style"] == "currency"):
        return "executive_sales"
    return "general_summary"


def recommend_report_layout(
    effective: EffectiveDataset,
    analysis: dict[str, Any],
    template: str = "auto",
) -> tuple[str, dict[str, Any]]:
    """Build a starter interactive stakeholder report layout_json based on dataset schema & analysis."""
    resolved_template = _detect_template(effective, analysis, template)
    measures: list[dict[str, Any]] = analysis.get("measures", [])
    primary_measure: dict[str, Any] | None = analysis.get("primary_measure")
    dimensions: list[dict[str, Any]] = analysis.get("dimensions", [])
    time_series: dict[str, Any] | None = analysis.get("time_series")

    blocks: list[dict[str, Any]] = []

    # 1. Executive Narrative Block (always first)
    blocks.append(
        {
            "id": "blk_narrative_1",
            "type": "narrative",
            "title": "Executive Briefing & Key Takeaways",
            "subtitle": "Grounded strictly in backend-computed metrics & quality checks",
            "width": "full",
            "config": {},
            "content": None,
        }
    )

    # Helper to find dimension/measure matching preferred hints
    def pick_dim(preferred_hints: tuple[str, ...], exclude: set[str] | None = None) -> dict[str, Any] | None:
        excluded = exclude or set()
        for hint in preferred_hints:
            for d in dimensions:
                if d["column"] not in excluded and (d.get("semantic_hint") == hint or hint in d["column"].lower()):
                    return d
        for d in dimensions:
            if d["column"] not in excluded:
                return d
        return None

    def pick_measure(preferred_hints: tuple[str, ...], exclude: set[str] | None = None) -> dict[str, Any] | None:
        excluded = exclude or set()
        for hint in preferred_hints:
            for m in measures:
                if m["column"] not in excluded and (m.get("semantic_hint") == hint or hint in m["column"].lower()):
                    return m
        for m in measures:
            if m["column"] not in excluded:
                return m
        return None

    # 2. KPI Row (3 KPIs)
    if primary_measure:
        p_col = primary_measure["column"]
        p_fmt = primary_measure["format_style"]
        sum_label = "Total" if resolved_template != "survey_insights" else "Total"
        blocks.append(
            {
                "id": "blk_kpi_1",
                "type": "kpi",
                "title": f"{sum_label} {p_col}",
                "subtitle": f"Across {primary_measure['valid_count']} valid rows",
                "width": "third",
                "config": {
                    "metric_column": p_col,
                    "aggregation": "sum",
                    "format_style": p_fmt,
                },
            }
        )
        blocks.append(
            {
                "id": "blk_kpi_2",
                "type": "kpi",
                "title": f"Average {p_col}",
                "subtitle": "Mean per valid record",
                "width": "third",
                "config": {
                    "metric_column": p_col,
                    "aggregation": "mean",
                    "format_style": p_fmt,
                },
            }
        )
    else:
        blocks.append(
            {
                "id": "blk_kpi_1",
                "type": "kpi",
                "title": "Total Records Analyzed",
                "subtitle": "All effective dataset rows",
                "width": "third",
                "config": {
                    "metric_column": None,
                    "aggregation": "count",
                    "format_style": "number",
                },
            }
        )
        # Try second KPI from primary dimension top category if available
        top_dim = dimensions[0] if dimensions else None
        if top_dim and top_dim["top_values"]:
            top_val = top_dim["top_values"][0]["value"]
            blocks.append(
                {
                    "id": "blk_kpi_2",
                    "type": "kpi",
                    "title": f"{top_dim['column']}: {top_val}",
                    "subtitle": f"Count in leading {top_dim['column']}",
                    "width": "third",
                    "config": {
                        "metric_column": None,
                        "aggregation": "count",
                        "format_style": "number",
                        "filter_column": top_dim["column"],
                        "filter_value": top_val,
                    },
                }
            )
        else:
            blocks.append(
                {
                    "id": "blk_kpi_2",
                    "type": "kpi",
                    "title": "Tracked Columns",
                    "subtitle": f"{analysis['overview']['completeness_pct']}% overall completeness",
                    "width": "third",
                    "config": {
                        "metric_column": None,
                        "aggregation": "count",
                        "format_style": "number",
                    },
                }
            )

    second_measure = pick_measure(
        ("quantity", "weight", "unit", "price"),
        exclude={primary_measure["column"]} if primary_measure else set(),
    )
    if second_measure:
        blocks.append(
            {
                "id": "blk_kpi_3",
                "type": "kpi",
                "title": f"Total {second_measure['column']}",
                "subtitle": f"Across {second_measure['valid_count']} valid rows",
                "width": "third",
                "config": {
                    "metric_column": second_measure["column"],
                    "aggregation": "sum",
                    "format_style": second_measure["format_style"],
                },
            }
        )
    elif primary_measure:
        blocks.append(
            {
                "id": "blk_kpi_3",
                "type": "kpi",
                "title": f"Total Records ({primary_measure['valid_count']} valid)",
                "subtitle": f"{primary_measure['unparseable_count']} excluded values",
                "width": "third",
                "config": {
                    "metric_column": None,
                    "aggregation": "count",
                    "format_style": "number",
                },
            }
        )
    else:
        second_dim = dimensions[1] if len(dimensions) > 1 else (dimensions[0] if dimensions else None)
        if second_dim and second_dim["top_values"]:
            tv = second_dim["top_values"][0]["value"]
            blocks.append(
                {
                    "id": "blk_kpi_3",
                    "type": "kpi",
                    "title": f"{second_dim['column']}: {tv}",
                    "subtitle": f"Leading response in {second_dim['column']}",
                    "width": "third",
                    "config": {
                        "metric_column": None,
                        "aggregation": "count",
                        "format_style": "number",
                        "filter_column": second_dim["column"],
                        "filter_value": tv,
                    },
                }
            )

    # 3. Time-series chart if we have >= 2 unambiguous valid points
    if time_series and len(time_series.get("points", [])) >= 2:
        y_col = primary_measure["column"] if primary_measure else None
        y_fmt = primary_measure["format_style"] if primary_measure else "number"
        agg = "sum" if y_col else "count"
        metric_noun = y_col if y_col else "Activity"
        blocks.append(
            {
                "id": "blk_line_1",
                "type": "line_chart",
                "title": f"{metric_noun} Over Time ({time_series['granularity'].title()})",
                "subtitle": (
                    f"Based on {time_series['valid_date_count']} valid dates in '{time_series['date_column']}'"
                    + (
                        f" ({time_series['ambiguous_skipped_count']} ambiguous excluded)"
                        if time_series["ambiguous_skipped_count"]
                        else ""
                    )
                ),
                "width": "full",
                "config": {
                    "x_column": time_series["date_column"],
                    "y_column": y_col,
                    "aggregation": agg,
                    "granularity": time_series["granularity"],
                    "format_style": y_fmt,
                },
            }
        )

    # 4. Primary breakdown bar chart + composition pie chart
    if resolved_template == "survey_insights":
        dim1 = pick_dim(("department", "category", "region"))
        dim2 = pick_dim(("recommendation", "score", "status"), exclude={dim1["column"]} if dim1 else set())
    elif resolved_template == "inventory_summary":
        dim1 = pick_dim(("category", "region", "status"))
        dim2 = pick_dim(("status", "region", "category"), exclude={dim1["column"]} if dim1 else set())
    else:
        dim1 = pick_dim(("region", "category", "customer_name", "status"))
        dim2 = pick_dim(("status", "category", "region"), exclude={dim1["column"]} if dim1 else set())

    if dim1:
        m_col = primary_measure["column"] if primary_measure else None
        m_fmt = primary_measure["format_style"] if primary_measure else "number"
        agg = "sum" if m_col else "count"
        blocks.append(
            {
                "id": "blk_bar_1",
                "type": "bar_chart",
                "title": f"{m_col or 'Record Count'} by {dim1['column']}",
                "subtitle": "Click any bar to inspect underlying source rows & lineage",
                "width": "half" if dim2 else "full",
                "config": {
                    "dimension_column": dim1["column"],
                    "metric_column": m_col,
                    "aggregation": agg,
                    "format_style": m_fmt,
                    "limit": 10,
                    "sort_by": "value_desc",
                },
            }
        )

    if dim2:
        m_col = primary_measure["column"] if primary_measure else None
        m_fmt = primary_measure["format_style"] if primary_measure else "number"
        agg = "sum" if (m_col and resolved_template != "survey_insights") else "count"
        blocks.append(
            {
                "id": "blk_pie_1",
                "type": "pie_chart",
                "title": f"{'Share of ' + m_col if agg == 'sum' and m_col else 'Breakdown'} by {dim2['column']}",
                "subtitle": "Click a slice to drill down into exact contributing records",
                "width": "half" if dim1 else "full",
                "config": {
                    "dimension_column": dim2["column"],
                    "metric_column": m_col if agg == "sum" else None,
                    "aggregation": agg,
                    "format_style": m_fmt if agg == "sum" else "number",
                    "limit": 8,
                },
            }
        )

    # 5. Summary Table for top dimension
    table_dim = pick_dim(("customer_name", "product", "category", "region", "department")) or dim1 or dim2
    if table_dim:
        m_col = primary_measure["column"] if primary_measure else None
        m_fmt = primary_measure["format_style"] if primary_measure else "number"
        blocks.append(
            {
                "id": "blk_table_1",
                "type": "summary_table",
                "title": f"{table_dim['column']} Performance Summary",
                "subtitle": "Click any row to verify contributing records & audit history",
                "width": "full",
                "config": {
                    "dimension_column": table_dim["column"],
                    "metric_column": m_col,
                    "secondary_metric_column": second_measure["column"] if second_measure else None,
                    "aggregation": "sum" if m_col else "count",
                    "format_style": m_fmt,
                    "limit": 15,
                },
            }
        )

    # 6. Data Quality & Methodology Caveats block
    blocks.append(
        {
            "id": "blk_quality_1",
            "type": "data_quality",
            "title": "Data Quality, Coverage & Methodology Caveats",
            "subtitle": f"Completeness {analysis['overview']['completeness_pct']}% · Readiness: {analysis['overview']['readiness'].replace('_', ' ').title()}",
            "width": "full",
            "config": {"show_resolved": False},
        }
    )

    template_titles = {
        "executive_sales": f"{effective.dataset.name} — Executive Performance Report",
        "survey_insights": f"{effective.dataset.name} — Stakeholder Survey Insights",
        "inventory_summary": f"{effective.dataset.name} — Inventory & Operations Summary",
        "general_summary": f"{effective.dataset.name} — Stakeholder Analysis Report",
    }

    title = template_titles.get(resolved_template, f"{effective.dataset.name} — Stakeholder Analysis Report")
    layout = {
        "version": 1,
        "template": resolved_template,
        "blocks": blocks,
    }
    return title, layout


def build_metrics_packet_from_blocks(
    report_title: str,
    dataset_name: str,
    analysis: dict[str, Any],
    computed_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble verified numeric metrics packet (never raw rows) for LLM narrative synthesis."""
    overview = analysis.get("overview", {})
    primary = analysis.get("primary_measure")
    time_series = analysis.get("time_series")

    block_summaries: list[dict[str, Any]] = []
    for blk in computed_blocks:
        btype = blk.get("type")
        data = blk.get("data") or {}
        if btype == "kpi":
            block_summaries.append(
                {
                    "id": blk.get("id"),
                    "type": "kpi",
                    "title": blk.get("title"),
                    "value": data.get("value"),
                    "formatted_value": data.get("formatted_value"),
                    "aggregation": data.get("aggregation"),
                    "matching_rows": data.get("matching_rows"),
                    "excluded_rows": data.get("excluded_rows"),
                }
            )
        elif btype in ("bar_chart", "pie_chart", "summary_table"):
            rows_or_items = data.get("items") or data.get("rows") or []
            block_summaries.append(
                {
                    "id": blk.get("id"),
                    "type": btype,
                    "title": blk.get("title"),
                    "dimension": data.get("dimension_column"),
                    "metric": data.get("metric_column"),
                    "total_value": data.get("total_value"),
                    "total_rows": data.get("total_rows"),
                    "excluded_rows": data.get("excluded_rows"),
                    "top_items": [
                        {
                            "label": item.get("label"),
                            "value": item.get("value"),
                            "row_count": item.get("row_count"),
                            "share_pct": item.get("share_pct"),
                        }
                        for item in rows_or_items[:5]
                    ],
                }
            )
        elif btype in ("line_chart", "area_chart"):
            pts = data.get("points") or []
            block_summaries.append(
                {
                    "id": blk.get("id"),
                    "type": btype,
                    "title": blk.get("title"),
                    "date_column": data.get("date_column"),
                    "granularity": data.get("granularity"),
                    "point_count": len(pts),
                    "total_value": data.get("total_value"),
                    "ambiguous_skipped_count": data.get("ambiguous_skipped_count"),
                    "unparseable_skipped_count": data.get("unparseable_skipped_count"),
                    "start_date": pts[0].get("bucket_key") if pts else None,
                    "end_date": pts[-1].get("bucket_key") if pts else None,
                    "start_value": pts[0].get("value") if pts else None,
                    "end_value": pts[-1].get("value") if pts else None,
                }
            )

    ts_summary = None
    if time_series:
        ts_summary = {
            "date_column": time_series.get("date_column"),
            "granularity": time_series.get("granularity"),
            "valid_date_count": time_series.get("valid_date_count"),
            "ambiguous_skipped_count": time_series.get("ambiguous_skipped_count"),
            "unparseable_skipped_count": time_series.get("unparseable_skipped_count"),
            "start_period": time_series.get("start_period"),
            "end_period": time_series.get("end_period"),
            "period_change_abs": time_series.get("period_change_abs"),
            "period_change_pct": time_series.get("period_change_pct"),
            "peak_period": time_series.get("peak_period"),
        }

    return {
        "report_title": report_title,
        "dataset_name": dataset_name,
        "version_number": analysis.get("version_number"),
        "overview": overview,
        "primary_measure": (
            {
                "column": primary["column"],
                "format_style": primary["format_style"],
                "sum": primary["sum"],
                "mean": primary["mean"],
                "median": primary["median"],
                "min": primary["min"],
                "max": primary["max"],
                "valid_count": primary["valid_count"],
                "missing_count": primary["missing_count"],
                "unparseable_count": primary["unparseable_count"],
                "currency_notations": primary.get("currency_notations", []),
            }
            if primary
            else None
        ),
        "measures": [
            {
                "column": m["column"],
                "format_style": m["format_style"],
                "sum": m["sum"],
                "mean": m["mean"],
                "min": m["min"],
                "max": m["max"],
                "valid_count": m["valid_count"],
                "unparseable_count": m["unparseable_count"],
            }
            for m in analysis.get("measures", [])[:5]
        ],
        "segment_breakdowns": [
            {
                "dimension": b["dimension"],
                "metric_column": b["metric_column"],
                "unique_bucket_count": b["unique_bucket_count"],
                "top_segment": b["top_segment"],
                "top_segment_share_pct": b["top_segment_share_pct"],
                "top_segments": [
                    {
                        "label": s["label"],
                        "row_count": s["row_count"],
                        "row_share_pct": s["row_share_pct"],
                        "metric_sum": s["metric_sum"],
                        "metric_share_pct": s["metric_share_pct"],
                    }
                    for s in b["segments"][:5]
                ],
            }
            for b in analysis.get("segment_breakdowns", [])
        ],
        "time_series": ts_summary,
        "correlations": analysis.get("correlations", [])[:3],
        "computed_blocks": block_summaries,
        "data_quality_caveats": analysis.get("data_quality_caveats", [])[:6],
    }

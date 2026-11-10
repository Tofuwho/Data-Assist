import math
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import Change, DatasetVersion
from app.services.analysis.analyzer import MISSING_BUCKET_KEY, MISSING_BUCKET_LABEL
from app.services.analysis.resolver import (
    EffectiveDataset,
    EffectiveRow,
    extract_date_bucket,
    extract_numeric_for_analysis,
)
from app.services.profiling.profiler import is_null_or_null_like


def format_display_value(value: float | int | None, format_style: str | None = "number") -> str:
    """Format a computed scalar deterministically for executive display."""
    if value is None:
        return "—"
    num = float(value)
    if format_style == "currency":
        return f"-${abs(num):,.2f}" if num < 0 else f"${num:,.2f}"
    if format_style == "percent":
        if abs(num - round(num)) <= 1e-6:
            return f"{int(round(num)):,}%"
        return f"{num:,.2f}%"
    if abs(num - round(num)) <= 1e-6:
        return f"{int(round(num)):,}"
    return f"{num:,.2f}"


def _dimension_bucket(raw_val: Any) -> tuple[str, str]:
    is_missing, _ = is_null_or_null_like(raw_val)
    if is_missing:
        return MISSING_BUCKET_KEY, MISSING_BUCKET_LABEL
    cleaned = str(raw_val).strip()
    return cleaned, cleaned


def _median(values: list[float]) -> float:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2 == 1:
        return sorted_vals[mid]
    return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0


def _aggregate(values: list[float], agg: str, fallback_row_count: int) -> float:
    if agg == "count":
        return float(fallback_row_count)
    if not values:
        return 0.0
    if agg == "sum":
        return round(sum(values), 4)
    if agg == "mean":
        return round(sum(values) / len(values), 4)
    if agg == "median":
        return round(_median(values), 4)
    if agg == "min":
        return round(min(values), 4)
    if agg == "max":
        return round(max(values), 4)
    return round(sum(values), 4)


def _filter_rows(rows: list[EffectiveRow], config: dict[str, Any]) -> list[EffectiveRow]:
    filter_col = config.get("filter_column")
    filter_val = config.get("filter_value")
    if not filter_col or filter_val is None or str(filter_val).strip() == "":
        return rows
    target = str(filter_val).strip()
    out: list[EffectiveRow] = []
    for row in rows:
        b_key, b_label = _dimension_bucket(row.values.get(filter_col, ""))
        if b_key == target or b_label == target:
            out.append(row)
    return out


def _evaluate_kpi(effective: EffectiveDataset, block: dict[str, Any]) -> dict[str, Any]:
    cfg = block.get("config") or {}
    metric_col = cfg.get("metric_column")
    agg = cfg.get("aggregation") or ("sum" if metric_col else "count")
    fmt = cfg.get("format_style") or "number"

    filtered_rows = _filter_rows(effective.rows, cfg)
    col_model = effective.columns_by_name.get(metric_col) if metric_col else None
    inferred_type = col_model.inferred_type if col_model else None

    if not metric_col or agg == "count":
        val = len(filtered_rows)
        return {
            "metric_column": metric_col,
            "aggregation": "count",
            "format_style": fmt if fmt != "currency" else "number",
            "value": val,
            "formatted_value": format_display_value(val, "number"),
            "matching_rows": val,
            "excluded_rows": 0,
            "missing_rows": 0,
            "unparseable_rows": 0,
        }

    valid_vals: list[float] = []
    missing_rows = 0
    unparseable_rows = 0
    for row in filtered_rows:
        num_val, status = extract_numeric_for_analysis(row.values.get(metric_col, ""), inferred_type)
        if status == "valid" and num_val is not None:
            valid_vals.append(num_val)
        elif status == "missing":
            missing_rows += 1
        else:
            unparseable_rows += 1

    agg_val = _aggregate(valid_vals, agg, len(valid_vals)) if valid_vals else None
    return {
        "metric_column": metric_col,
        "aggregation": agg,
        "format_style": fmt,
        "value": agg_val,
        "formatted_value": format_display_value(agg_val, fmt),
        "matching_rows": len(valid_vals),
        "excluded_rows": missing_rows + unparseable_rows,
        "missing_rows": missing_rows,
        "unparseable_rows": unparseable_rows,
    }


def _evaluate_categorical_block(effective: EffectiveDataset, block: dict[str, Any]) -> dict[str, Any]:
    cfg = block.get("config") or {}
    dim_col = cfg.get("dimension_column") or ""
    metric_col = cfg.get("metric_column")
    agg = cfg.get("aggregation") or ("sum" if metric_col else "count")
    fmt = cfg.get("format_style") or ("number" if agg == "count" or not metric_col else "number")
    limit = int(cfg.get("limit") or (8 if block.get("type") == "pie_chart" else 10))
    sort_by = cfg.get("sort_by") or "value_desc"

    if not dim_col or dim_col not in effective.columns_by_name:
        return {
            "dimension_column": dim_col,
            "metric_column": metric_col,
            "aggregation": agg,
            "format_style": fmt,
            "total_value": 0.0,
            "total_rows": 0,
            "excluded_rows": 0,
            "items": [],
        }

    filtered_rows = _filter_rows(effective.rows, cfg)
    col_model = effective.columns_by_name.get(metric_col) if metric_col else None
    inferred_type = col_model.inferred_type if col_model else None

    sec_col = cfg.get("secondary_metric_column")
    sec_col_model = effective.columns_by_name.get(sec_col) if sec_col else None
    sec_type = sec_col_model.inferred_type if sec_col_model else None

    buckets: dict[str, dict[str, Any]] = {}
    total_excluded = 0

    for row in filtered_rows:
        b_key, b_label = _dimension_bucket(row.values.get(dim_col, ""))
        if b_key not in buckets:
            buckets[b_key] = {
                "bucket_key": b_key,
                "label": b_label,
                "row_count": 0,
                "valid_vals": [],
                "sec_vals": [],
                "excluded_rows": 0,
            }
        entry = buckets[b_key]
        entry["row_count"] += 1

        if metric_col and agg != "count":
            num_val, status = extract_numeric_for_analysis(row.values.get(metric_col, ""), inferred_type)
            if status == "valid" and num_val is not None:
                entry["valid_vals"].append(num_val)
            else:
                entry["excluded_rows"] += 1
                total_excluded += 1

        if sec_col:
            sec_val, sec_status = extract_numeric_for_analysis(row.values.get(sec_col, ""), sec_type)
            if sec_status == "valid" and sec_val is not None:
                entry["sec_vals"].append(sec_val)

    all_bucket_values = [
        _aggregate(b["valid_vals"], agg, b["row_count"])
        for b in buckets.values()
    ]
    total_value = round(sum(v for v in all_bucket_values if v is not None), 4)
    effective_fmt = "number" if (agg == "count" or not metric_col) else fmt

    items: list[dict[str, Any]] = []
    for entry in buckets.values():
        vals = entry["valid_vals"]
        sec_vals = entry["sec_vals"]
        val = _aggregate(vals, agg, entry["row_count"])
        mean_val = round(sum(vals) / len(vals), 4) if vals else (float(entry["row_count"]) if agg == "count" else None)
        sec_sum = round(sum(sec_vals), 4) if sec_vals else None
        share_pct = round((val / total_value) * 100.0, 2) if total_value > 0 else 0.0
        items.append(
            {
                "bucket_key": entry["bucket_key"],
                "label": entry["label"],
                "value": val,
                "formatted_value": format_display_value(val, effective_fmt),
                "mean_value": mean_val,
                "formatted_mean": format_display_value(mean_val, effective_fmt) if mean_val is not None else "—",
                "secondary_value": sec_sum,
                "row_count": entry["row_count"],
                "valid_metric_count": len(vals) if (metric_col and agg != "count") else entry["row_count"],
                "excluded_rows": entry["excluded_rows"],
                "share_pct": share_pct,
            }
        )

    if sort_by == "value_asc":
        items.sort(key=lambda it: (it["bucket_key"] == MISSING_BUCKET_KEY, it["value"], -it["row_count"], it["label"]))
    elif sort_by == "label_asc":
        items.sort(key=lambda it: (it["bucket_key"] == MISSING_BUCKET_KEY, it["label"].lower()))
    else:
        items.sort(key=lambda it: (it["bucket_key"] == MISSING_BUCKET_KEY, -it["value"], -it["row_count"], it["label"]))

    limited_items = items[:limit]
    return {
        "dimension_column": dim_col,
        "metric_column": metric_col,
        "secondary_metric_column": sec_col,
        "aggregation": agg,
        "format_style": effective_fmt,
        "total_value": total_value,
        "formatted_total": format_display_value(total_value, effective_fmt),
        "total_rows": len(filtered_rows),
        "excluded_rows": total_excluded,
        "bucket_count": len(items),
        "items": limited_items,
    }


def _evaluate_time_series_block(effective: EffectiveDataset, block: dict[str, Any]) -> dict[str, Any]:
    cfg = block.get("config") or {}
    x_col = cfg.get("x_column") or ""
    y_col = cfg.get("y_column") or cfg.get("metric_column")
    agg = cfg.get("aggregation") or ("sum" if y_col else "count")
    granularity = cfg.get("granularity") or "day"
    fmt = cfg.get("format_style") or "number"

    if not x_col or x_col not in effective.columns_by_name:
        return {
            "date_column": x_col,
            "metric_column": y_col,
            "aggregation": agg,
            "granularity": granularity,
            "format_style": fmt,
            "total_value": 0.0,
            "valid_date_count": 0,
            "ambiguous_skipped_count": 0,
            "unparseable_skipped_count": 0,
            "missing_date_count": 0,
            "points": [],
        }

    filtered_rows = _filter_rows(effective.rows, cfg)
    col_model = effective.columns_by_name.get(y_col) if y_col else None
    inferred_type = col_model.inferred_type if col_model else None

    buckets: dict[str, dict[str, Any]] = {}
    valid_date_count = 0
    ambiguous_skipped = 0
    unparseable_skipped = 0
    missing_date_count = 0

    for row in filtered_rows:
        b_key, b_label, dt_status = extract_date_bucket(row.values.get(x_col, ""), granularity=granularity)
        if dt_status == "ambiguous":
            ambiguous_skipped += 1
            continue
        if dt_status == "missing":
            missing_date_count += 1
            continue
        if dt_status != "valid" or b_key is None:
            unparseable_skipped += 1
            continue

        valid_date_count += 1
        if b_key not in buckets:
            buckets[b_key] = {
                "bucket_key": b_key,
                "label": b_label or b_key,
                "row_count": 0,
                "valid_vals": [],
                "excluded_rows": 0,
            }
        entry = buckets[b_key]
        entry["row_count"] += 1

        if y_col and agg != "count":
            num_val, m_status = extract_numeric_for_analysis(row.values.get(y_col, ""), inferred_type)
            if m_status == "valid" and num_val is not None:
                entry["valid_vals"].append(num_val)
            else:
                entry["excluded_rows"] += 1

    effective_fmt = "number" if (agg == "count" or not y_col) else fmt
    points: list[dict[str, Any]] = []
    all_vals_for_total: list[float] = []
    for b_key in sorted(buckets.keys()):
        entry = buckets[b_key]
        vals = entry["valid_vals"]
        val = _aggregate(vals, agg, entry["row_count"])
        all_vals_for_total.append(val)
        points.append(
            {
                "bucket_key": entry["bucket_key"],
                "label": entry["label"],
                "value": val,
                "formatted_value": format_display_value(val, effective_fmt),
                "row_count": entry["row_count"],
                "valid_metric_count": len(vals) if (y_col and agg != "count") else entry["row_count"],
                "excluded_rows": entry["excluded_rows"],
            }
        )

    total_val = round(sum(all_vals_for_total), 4)
    return {
        "date_column": x_col,
        "metric_column": y_col,
        "aggregation": agg,
        "granularity": granularity,
        "format_style": effective_fmt,
        "total_value": total_val,
        "formatted_total": format_display_value(total_val, effective_fmt),
        "valid_date_count": valid_date_count,
        "ambiguous_skipped_count": ambiguous_skipped,
        "unparseable_skipped_count": unparseable_skipped,
        "missing_date_count": missing_date_count,
        "points": points,
    }


def evaluate_report_blocks(
    effective: EffectiveDataset,
    layout_json: dict[str, Any],
    analysis: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Deterministically evaluate every block in layout_json from resolved EffectiveDataset rows."""
    blocks = layout_json.get("blocks") or []
    computed: list[dict[str, Any]] = []

    for blk in blocks:
        btype = blk.get("type", "")
        base = {
            "id": blk.get("id", ""),
            "type": btype,
            "title": blk.get("title", ""),
            "subtitle": blk.get("subtitle"),
            "width": blk.get("width", "full"),
            "config": blk.get("config") or {},
        }

        if btype == "kpi":
            computed.append({**base, "data": _evaluate_kpi(effective, blk)})
        elif btype in ("bar_chart", "pie_chart", "summary_table"):
            cat_data = _evaluate_categorical_block(effective, blk)
            if btype == "summary_table":
                cat_data = {**cat_data, "rows": cat_data.pop("items")}
            computed.append({**base, "data": cat_data})
        elif btype in ("line_chart", "area_chart"):
            computed.append({**base, "data": _evaluate_time_series_block(effective, blk)})
        elif btype == "data_quality":
            overview = (analysis or {}).get("overview") or {}
            caveats = (analysis or {}).get("data_quality_caveats") or []
            computed.append(
                {
                    **base,
                    "data": {
                        "overview": overview,
                        "caveats": caveats,
                    },
                }
            )
        elif btype == "narrative":
            computed.append({**base, "data": blk.get("content")})
        else:
            computed.append({**base, "data": blk.get("content") or {}})

    return computed


def extract_block_lineage(
    db: Session,
    effective: EffectiveDataset,
    block: dict[str, Any],
    bucket_key: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Trace exact contributing source RowModel records and audit Change history for a block or bucket."""
    btype = block.get("type", "")
    cfg = block.get("config") or {}
    filtered_rows = _filter_rows(effective.rows, cfg)

    matching_rows: list[EffectiveRow] = []
    excluded_rows: list[EffectiveRow] = []
    excluded_reasons: dict[str, int] = {"missing": 0, "unparseable": 0, "ambiguous_date": 0}
    bucket_label = bucket_key

    if btype == "kpi":
        metric_col = cfg.get("metric_column")
        agg = cfg.get("aggregation") or ("sum" if metric_col else "count")
        col_model = effective.columns_by_name.get(metric_col) if metric_col else None
        inferred_type = col_model.inferred_type if col_model else None

        if not metric_col or agg == "count":
            matching_rows = list(filtered_rows)
        else:
            for row in filtered_rows:
                _, status = extract_numeric_for_analysis(row.values.get(metric_col, ""), inferred_type)
                if status == "valid":
                    matching_rows.append(row)
                else:
                    excluded_rows.append(row)
                    if status in excluded_reasons:
                        excluded_reasons[status] += 1

        if bucket_key == "__excluded__":
            target_rows = excluded_rows
            bucket_label = "Excluded / Unparseable Records"
        else:
            target_rows = matching_rows

    elif btype in ("bar_chart", "pie_chart", "summary_table"):
        dim_col = cfg.get("dimension_column") or ""
        metric_col = cfg.get("metric_column")
        agg = cfg.get("aggregation") or ("sum" if metric_col else "count")
        col_model = effective.columns_by_name.get(metric_col) if metric_col else None
        inferred_type = col_model.inferred_type if col_model else None

        for row in filtered_rows:
            b_key, b_label = _dimension_bucket(row.values.get(dim_col, ""))
            if bucket_key is not None and bucket_key != "__excluded__" and b_key != bucket_key:
                continue
            if bucket_key is not None and bucket_key != "__excluded__":
                bucket_label = b_label

            if metric_col and agg != "count":
                _, status = extract_numeric_for_analysis(row.values.get(metric_col, ""), inferred_type)
                if status == "valid":
                    matching_rows.append(row)
                else:
                    excluded_rows.append(row)
                    if status in excluded_reasons:
                        excluded_reasons[status] += 1
            else:
                matching_rows.append(row)

        if bucket_key == "__excluded__":
            target_rows = excluded_rows
            bucket_label = "Excluded Numeric Records"
        else:
            # Show matching rows (and if a segment only has rows with excluded metric, keep honest count)
            target_rows = matching_rows

    elif btype in ("line_chart", "area_chart"):
        x_col = cfg.get("x_column") or ""
        y_col = cfg.get("y_column") or cfg.get("metric_column")
        agg = cfg.get("aggregation") or ("sum" if y_col else "count")
        granularity = cfg.get("granularity") or "day"
        col_model = effective.columns_by_name.get(y_col) if y_col else None
        inferred_type = col_model.inferred_type if col_model else None

        for row in filtered_rows:
            b_key, b_label, dt_status = extract_date_bucket(row.values.get(x_col, ""), granularity=granularity)
            if dt_status != "valid" or b_key is None:
                excluded_rows.append(row)
                if dt_status == "ambiguous":
                    excluded_reasons["ambiguous_date"] += 1
                elif dt_status == "missing":
                    excluded_reasons["missing"] += 1
                else:
                    excluded_reasons["unparseable"] += 1
                continue

            if bucket_key is not None and bucket_key != "__excluded__" and b_key != bucket_key:
                continue
            if bucket_key is not None and bucket_key != "__excluded__":
                bucket_label = b_label or b_key

            if y_col and agg != "count":
                _, m_status = extract_numeric_for_analysis(row.values.get(y_col, ""), inferred_type)
                if m_status == "valid":
                    matching_rows.append(row)
                else:
                    excluded_rows.append(row)
                    if m_status in excluded_reasons:
                        excluded_reasons[m_status] += 1
            else:
                matching_rows.append(row)

        if bucket_key == "__excluded__":
            target_rows = excluded_rows
            bucket_label = "Skipped Ambiguous / Unparseable Dates"
        else:
            target_rows = matching_rows
    else:
        target_rows = filtered_rows

    total_matching = len(target_rows)
    sliced = target_rows[offset : offset + limit]

    # Fetch recorded Change history for sliced row IDs up to effective version
    applicable_version_ids = [
        v.id
        for v in db.query(DatasetVersion.id, DatasetVersion.version_number)
        .filter(
            DatasetVersion.dataset_id == effective.dataset.id,
            DatasetVersion.version_number <= effective.version.version_number,
        )
        .all()
    ]
    changes_by_row: dict[str, list[dict[str, Any]]] = {}
    if sliced and applicable_version_ids:
        row_ids = [r.id for r in sliced]
        change_rows = (
            db.query(Change)
            .filter(
                Change.row_id.in_(row_ids),
                Change.dataset_version_id.in_(applicable_version_ids),
            )
            .order_by(Change.created_at.asc())
            .all()
        )
        for ch in change_rows:
            col = effective.columns_by_id.get(ch.column_id)
            changes_by_row.setdefault(ch.row_id, []).append(
                {
                    "id": ch.id,
                    "column_name": col.name if col else ch.column_id,
                    "before": ch.before,
                    "after": ch.after,
                    "source": ch.source,
                    "reason": ch.reason,
                    "status": ch.status,
                    "created_at": ch.created_at.isoformat() if ch.created_at else None,
                }
            )

    highlight_cols: list[str] = []
    for key in ("dimension_column", "metric_column", "secondary_metric_column", "x_column", "y_column", "filter_column"):
        val = cfg.get(key)
        if val and val not in highlight_cols:
            highlight_cols.append(val)

    return {
        "block_id": block.get("id", ""),
        "block_type": btype,
        "block_title": block.get("title", ""),
        "bucket_key": bucket_key,
        "bucket_label": bucket_label,
        "dataset_id": effective.dataset.id,
        "dataset_name": effective.dataset.name,
        "version_id": effective.version.id,
        "version_number": effective.version.version_number,
        "highlight_columns": highlight_cols,
        "columns": [c.name for c in effective.columns],
        "total_matching_rows": total_matching,
        "excluded_row_count": len(excluded_rows),
        "excluded_reasons": {k: v for k, v in excluded_reasons.items() if v > 0},
        "limit": limit,
        "offset": offset,
        "has_more": (offset + len(sliced)) < total_matching,
        "rows": [
            {
                "row_id": r.id,
                "row_index": r.row_index,
                "raw_values": r.raw_values,
                "effective_values": r.values,
                "changed_columns": sorted(r.changed_columns),
                "changes": changes_by_row.get(r.id, []),
            }
            for r in sliced
        ],
    }


def _finite_or_none(val: Any) -> Any:
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val

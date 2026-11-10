from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import (
    CellValue,
    ColumnModel,
    Dataset,
    DatasetVersion,
    Issue,
    RowModel,
)
from app.services.profiling.profiler import (
    is_null_or_null_like,
    parse_currency_value,
    parse_date_or_datetime,
    parse_numeric_value,
    parse_percentage_value,
)


@dataclass
class EffectiveRow:
    """Resolved row representation combining immutable raw_json with versioned cell_values."""

    id: str
    row_index: int
    raw_values: dict[str, Any]
    values: dict[str, Any]
    changed_columns: set[str] = field(default_factory=set)


@dataclass
class EffectiveDataset:
    """Complete dataset view at a specific DatasetVersion."""

    dataset: Dataset
    version: DatasetVersion
    columns: list[ColumnModel]
    columns_by_name: dict[str, ColumnModel]
    columns_by_id: dict[str, ColumnModel]
    issues: list[Issue]
    rows: list[EffectiveRow]


def resolve_effective_dataset(
    db: Session,
    dataset_id: str,
    version_id: str | None = None,
) -> EffectiveDataset:
    """Resolve effective dataset rows up to version_id (or latest version) without mutating raw rows."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise ValueError(f"Dataset {dataset_id} not found")

    versions = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset.id)
        .order_by(DatasetVersion.version_number.asc())
        .all()
    )
    if not versions:
        raise ValueError(f"Dataset {dataset_id} has no versions")

    target_version = versions[-1]
    if version_id:
        matched = next((v for v in versions if v.id == version_id), None)
        if not matched:
            raise ValueError(f"Dataset version {version_id} not found for dataset {dataset_id}")
        target_version = matched

    columns = (
        db.query(ColumnModel)
        .filter(ColumnModel.dataset_id == dataset.id)
        .order_by(ColumnModel.position.asc())
        .all()
    )
    columns_by_name = {c.name: c for c in columns}
    columns_by_id = {c.id: c for c in columns}

    issues = (
        db.query(Issue)
        .filter(Issue.dataset_id == dataset.id)
        .order_by(Issue.created_at.asc())
        .all()
    )

    raw_rows = (
        db.query(RowModel)
        .filter(RowModel.dataset_id == dataset.id)
        .order_by(RowModel.row_index.asc())
        .all()
    )

    applicable_version_ids = [
        v.id for v in versions if v.version_number <= target_version.version_number
    ]
    version_rank = {v.id: v.version_number for v in versions}

    overlays: dict[str, dict[str, Any]] = defaultdict(dict)
    changed_cols_map: dict[str, set[str]] = defaultdict(set)

    if applicable_version_ids:
        cells = (
            db.query(CellValue)
            .filter(CellValue.dataset_version_id.in_(applicable_version_ids))
            .all()
        )
        cells.sort(key=lambda c: version_rank.get(c.dataset_version_id, 0))
        for cell in cells:
            col = columns_by_id.get(cell.column_id)
            if col:
                overlays[cell.row_id][col.name] = cell.value
                changed_cols_map[cell.row_id].add(col.name)

    effective_rows: list[EffectiveRow] = []
    for r in raw_rows:
        raw_vals = dict(r.raw_json or {})
        row_overlay = overlays.get(r.id)
        if row_overlay:
            merged = {**raw_vals, **row_overlay}
        else:
            merged = raw_vals
        effective_rows.append(
            EffectiveRow(
                id=r.id,
                row_index=r.row_index,
                raw_values=raw_vals,
                values=merged,
                changed_columns=set(changed_cols_map.get(r.id, ())),
            )
        )

    return EffectiveDataset(
        dataset=dataset,
        version=target_version,
        columns=columns,
        columns_by_name=columns_by_name,
        columns_by_id=columns_by_id,
        issues=issues,
        rows=effective_rows,
    )


def resolve_effective_dataset_from_version(
    db: Session,
    dataset_version_id: str,
) -> EffectiveDataset:
    """Resolve effective dataset locked to an explicit DatasetVersion ID."""
    version = db.query(DatasetVersion).filter(DatasetVersion.id == dataset_version_id).first()
    if not version:
        raise ValueError(f"DatasetVersion {dataset_version_id} not found")
    return resolve_effective_dataset(db, dataset_id=version.dataset_id, version_id=version.id)


def extract_numeric_for_analysis(
    raw_val: Any,
    inferred_type: str | None = None,
) -> tuple[float | None, str]:
    """Deterministically extract a numeric value for analysis without guessing ambiguous strings.

    Returns (float_val_or_None, status) where status is 'valid' | 'missing' | 'unparseable'.
    """
    is_missing, _ = is_null_or_null_like(raw_val)
    if is_missing:
        return None, "missing"

    s = str(raw_val).strip()

    if inferred_type == "currency":
        c = parse_currency_value(s)
        if c is not None:
            return c, "valid"
        _, n = parse_numeric_value(s)
        return (n, "valid") if n is not None else (None, "unparseable")

    if inferred_type == "percentage":
        p = parse_percentage_value(s)
        if p is not None:
            return p, "valid"
        _, n = parse_numeric_value(s)
        return (n, "valid") if n is not None else (None, "unparseable")

    # General numeric extraction fallback
    _, n = parse_numeric_value(s)
    if n is not None:
        return n, "valid"

    c = parse_currency_value(s)
    if c is not None:
        return c, "valid"

    p = parse_percentage_value(s)
    if p is not None:
        return p, "valid"

    return None, "unparseable"


def extract_date_bucket(
    raw_val: Any,
    granularity: str = "day",
) -> tuple[str | None, str | None, str]:
    """Deterministically bucket a date string, never guessing ambiguous MM/DD vs DD/MM dates.

    Returns (sort_key, display_label, status) where status is
    'valid' | 'missing' | 'ambiguous' | 'unparseable'.
    """
    is_missing, _ = is_null_or_null_like(raw_val)
    if is_missing:
        return None, None, "missing"

    kind, _, parsed_date, is_ambiguous = parse_date_or_datetime(str(raw_val))
    if is_ambiguous:
        return None, None, "ambiguous"
    if kind is None or parsed_date is None:
        return None, None, "unparseable"

    if granularity == "month":
        key = f"{parsed_date.year:04d}-{parsed_date.month:02d}"
        label = parsed_date.strftime("%b %Y")
        return key, label, "valid"

    if granularity == "week":
        iso = parsed_date.isocalendar()
        key = f"{iso.year:04d}-W{iso.week:02d}"
        label = f"W{iso.week:02d} {iso.year}"
        return key, label, "valid"

    key = parsed_date.isoformat()
    return key, key, "valid"

import re
from collections import defaultdict
from typing import Any

from rapidfuzz import fuzz

from app.services.profiling.detectors.base import ColumnInfo, DetectedIssue, RowInfo
from app.services.profiling.profiler import is_null_or_null_like

CORP_SUFFIX_RE = re.compile(
    r"\b(inc|incorporated|llc|corp|corporation|ltd|limited|co|company|plc|gmbh)\b\.?",
    re.IGNORECASE,
)
PUNCT_SPACE_RE = re.compile(r"[^a-z0-9]+")


def _normalize_entity(val: str) -> str:
    cleaned = CORP_SUFFIX_RE.sub("", val.lower())
    return PUNCT_SPACE_RE.sub(" ", cleaned).strip()


def _normalize_row_signature(row: RowInfo, col_names: list[str]) -> str:
    parts: list[str] = []
    for name in col_names:
        raw = str(row.values.get(name, "")).strip().lower()
        parts.append(PUNCT_SPACE_RE.sub(" ", raw).strip())
    return " | ".join(parts)


def detect_near_duplicates(
    columns: list[ColumnInfo],
    rows: list[RowInfo],
    threshold: float = 85.0,
) -> list[DetectedIssue]:
    """Detect near-duplicate rows (ignoring identifier columns) and near-duplicate entity names."""
    issues: list[DetectedIssue] = []
    if len(rows) < 2 or not columns:
        return issues

    # 1. Entity / customer name near-duplicates (e.g., "Globex Inc." vs "Globex")
    for col in columns:
        if col.semantic_hint not in ("customer_name",) and "customer" not in col.name.lower():
            continue

        by_raw: dict[str, list[RowInfo]] = defaultdict(list)
        for r in rows:
            val = r.values.get(col.name, "")
            is_missing, _ = is_null_or_null_like(val)
            if not is_missing:
                by_raw[str(val).strip()].append(r)

        distinct_vals = list(by_raw.keys())
        if len(distinct_vals) < 2 or len(distinct_vals) > 500:
            continue

        # Build clusters of near-duplicate entity strings (excluding exact case-only matches,
        # which are handled by inconsistent_text, unless combined with suffix differences)
        parent = {v: v for v in distinct_vals}

        def find(x: str, p: dict[str, str] = parent) -> str:
            while p[x] != x:
                p[x] = p[p[x]]
                x = p[x]
            return x

        def union(a: str, b: str, p: dict[str, str] = parent) -> None:
            ra, rb = find(a, p), find(b, p)
            if ra != rb:
                p[rb] = ra

        norm_map = {v: _normalize_entity(v) for v in distinct_vals}
        for i in range(len(distinct_vals)):
            for j in range(i + 1, len(distinct_vals)):
                a, b = distinct_vals[i], distinct_vals[j]
                if a.lower() == b.lower():
                    continue
                na, nb = norm_map[a], norm_map[b]
                if not na or not nb:
                    continue
                if na == nb or fuzz.token_sort_ratio(na, nb) >= threshold:
                    union(a, b)

        clusters: dict[str, list[str]] = defaultdict(list)
        for v in distinct_vals:
            clusters[find(v)].append(v)

        near_clusters = [vals for vals in clusters.values() if len(vals) > 1]
        if near_clusters:
            affected_row_ids: list[str] = []
            examples: list[dict[str, Any]] = []
            for grp in near_clusters:
                for val in grp:
                    for r in by_raw[val]:
                        affected_row_ids.append(r.id)
                if len(examples) < 5:
                    examples.append({"variants": grp})

            issues.append(
                DetectedIssue(
                    issue_type="near_duplicates",
                    severity="medium",
                    column_id=col.id,
                    row_ids=affected_row_ids,
                    affected_count=len(affected_row_ids),
                    description=f"Column `{col.name}` contains {len(near_clusters)} near-duplicate entity cluster(s) (e.g., {', '.join(near_clusters[0][:3])})",
                    details_json={
                        "scope": "column_entities",
                        "column_name": col.name,
                        "threshold": threshold,
                        "clusters": [c for c in near_clusters[:10]],
                        "examples": examples,
                    },
                )
            )

    # 2. Row-level near-duplicates (excluding identifier columns and exact duplicates)
    non_id_cols = [c.name for c in columns if c.inferred_type != "identifier"]
    if not non_id_cols:
        return issues

    all_col_names = [c.name for c in columns]
    max_pairwise_rows = min(len(rows), 500)
    signatures = [_normalize_row_signature(r, non_id_cols) for r in rows[:max_pairwise_rows]]
    exact_full = [tuple(str(r.values.get(c, "")) for c in all_col_names) for r in rows[:max_pairwise_rows]]

    near_pair_row_ids: set[str] = set()
    pair_examples: list[dict[str, Any]] = []

    for i in range(max_pairwise_rows):
        for j in range(i + 1, max_pairwise_rows):
            if exact_full[i] == exact_full[j]:
                continue
            ratio = fuzz.token_sort_ratio(signatures[i], signatures[j])
            if ratio >= threshold:
                r1, r2 = rows[i], rows[j]
                near_pair_row_ids.add(r1.id)
                near_pair_row_ids.add(r2.id)
                if len(pair_examples) < 5:
                    pair_examples.append(
                        {
                            "row_indices": [r1.row_index, r2.row_index],
                            "similarity": round(ratio, 1),
                        }
                    )

    if near_pair_row_ids:
        ordered_ids = [r.id for r in rows if r.id in near_pair_row_ids]
        issues.append(
            DetectedIssue(
                issue_type="near_duplicates",
                severity="medium",
                column_id=None,
                row_ids=ordered_ids,
                affected_count=len(ordered_ids),
                description=f"Detected {len(ordered_ids)} row(s) that are near-duplicates across non-ID columns (similarity >= {int(threshold)}%)",
                details_json={
                    "scope": "rows",
                    "threshold": threshold,
                    "examples": pair_examples,
                },
            )
        )

    return issues

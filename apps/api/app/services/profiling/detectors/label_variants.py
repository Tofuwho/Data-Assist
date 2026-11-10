import re
from collections import defaultdict
from typing import Any

from rapidfuzz import fuzz

from app.services.profiling.detectors.base import ColumnInfo, DetectedIssue, RowInfo
from app.services.profiling.profiler import is_null_or_null_like

NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

# Deterministic standard US state / abbreviation mapping used only for region-hinted columns
US_STATE_ABBREV = {
    "al": "alabama",
    "ak": "alaska",
    "az": "arizona",
    "ar": "arkansas",
    "ca": "california",
    "calif": "california",
    "co": "colorado",
    "ct": "connecticut",
    "de": "delaware",
    "fl": "florida",
    "fla": "florida",
    "ga": "georgia",
    "hi": "hawaii",
    "id": "idaho",
    "il": "illinois",
    "in": "indiana",
    "ia": "iowa",
    "ks": "kansas",
    "ky": "kentucky",
    "la": "louisiana",
    "me": "maine",
    "md": "maryland",
    "ma": "massachusetts",
    "mi": "michigan",
    "mn": "minnesota",
    "ms": "mississippi",
    "mo": "missouri",
    "mt": "montana",
    "ne": "nebraska",
    "nv": "nevada",
    "nh": "new hampshire",
    "nj": "new jersey",
    "nm": "new mexico",
    "ny": "new york",
    "nc": "north carolina",
    "nd": "north dakota",
    "oh": "ohio",
    "ok": "oklahoma",
    "or": "oregon",
    "pa": "pennsylvania",
    "ri": "rhode island",
    "sc": "south carolina",
    "sd": "south dakota",
    "tn": "tennessee",
    "tx": "texas",
    "tex": "texas",
    "ut": "utah",
    "vt": "vermont",
    "va": "virginia",
    "wa": "washington",
    "wv": "west virginia",
    "wi": "wisconsin",
    "wy": "wyoming",
    "dc": "district of columbia",
}


def _clean_tokens(text: str) -> str:
    return NON_ALNUM_RE.sub(" ", text.lower()).strip()


def _compact(text: str) -> str:
    return NON_ALNUM_RE.sub("", text.lower())


def _canonical_region_form(text: str) -> str:
    cleaned = _clean_tokens(text)
    compact = _compact(text)
    if compact in US_STATE_ABBREV:
        return US_STATE_ABBREV[compact]
    if cleaned in US_STATE_ABBREV:
        return US_STATE_ABBREV[cleaned]
    return cleaned


def _are_label_variants(a: str, b: str, is_region: bool, fuzzy_threshold: float) -> bool:
    if a == b:
        return False

    comp_a, comp_b = _compact(a), _compact(b)
    if not comp_a or not comp_b:
        return False

    # 1. Exact compact equivalence (e.g. "N.Y." vs "NY", "New York" vs "new york")
    if comp_a == comp_b:
        return True

    # 2. Region canonicalization (e.g. "CA", "Calif.", "CALIFORNIA" -> "california")
    if is_region:
        if _canonical_region_form(a) == _canonical_region_form(b):
            return True

    toks_a = _clean_tokens(a).split()
    toks_b = _clean_tokens(b).split()

    # 3. Multi-word acronym match (e.g. "NY" vs "New York")
    if len(toks_a) == 1 and len(toks_b) >= 2 and comp_a == "".join(t[0] for t in toks_b if t):
        return True
    if len(toks_b) == 1 and len(toks_a) >= 2 and comp_b == "".join(t[0] for t in toks_a if t):
        return True

    # 4. Prefix abbreviation (e.g. "eng" vs "Engineering", "calif" vs "California")
    if len(toks_a) == 1 and len(toks_b) == 1:
        short, long = (comp_a, comp_b) if len(comp_a) <= len(comp_b) else (comp_b, comp_a)
        if len(short) >= 3 and len(long) >= len(short) + 2 and long.startswith(short):
            return True

    # 5. Token overlap for multi-word label vs standalone keyword (e.g. "support" vs "Customer Support")
    if len(toks_a) != len(toks_b):
        if len(toks_a) == 1 and len(toks_a[0]) >= 5 and toks_a[0] in toks_b:
            return True
        if len(toks_b) == 1 and len(toks_b[0]) >= 5 and toks_b[0] in toks_a:
            return True

    # 6. Fuzzy edit similarity for typos on words >= 4 chars
    if min(len(comp_a), len(comp_b)) >= 4 and fuzz.ratio(comp_a, comp_b) >= fuzzy_threshold:
        return True

    return False


def detect_label_variants(
    columns: list[ColumnInfo],
    rows: list[RowInfo],
    fuzzy_threshold: float = 85.0,
) -> list[DetectedIssue]:
    """Detect inconsistent category labels (same concept, different spelling/abbreviation)."""
    issues: list[DetectedIssue] = []
    if len(rows) < 2:
        return issues

    for col in columns:
        # Target categorical/dimension columns; skip customer_name (handled by near_duplicates) and free_text/identifiers
        if col.inferred_type != "category":
            continue
        if col.semantic_hint == "customer_name":
            continue

        by_value: dict[str, list[RowInfo]] = defaultdict(list)
        for r in rows:
            raw = r.values.get(col.name, "")
            is_missing, _ = is_null_or_null_like(raw)
            if not is_missing:
                by_value[str(raw).strip()].append(r)

        distinct_vals = list(by_value.keys())
        if len(distinct_vals) < 2 or len(distinct_vals) > 150:
            continue

        is_region = col.semantic_hint == "region" or any(
            k in col.name.lower() for k in ("region", "state", "country", "location")
        )

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

        for i in range(len(distinct_vals)):
            for j in range(i + 1, len(distinct_vals)):
                a, b = distinct_vals[i], distinct_vals[j]
                if _are_label_variants(a, b, is_region=is_region, fuzzy_threshold=fuzzy_threshold):
                    union(a, b)

        groups: dict[str, list[str]] = defaultdict(list)
        for v in distinct_vals:
            groups[find(v)].append(v)

        variant_clusters = [sorted(vals, key=lambda x: (-len(by_value[x]), x)) for vals in groups.values() if len(vals) > 1]
        if not variant_clusters:
            continue

        affected_set: set[str] = set()
        cluster_details: list[dict[str, Any]] = []
        for cluster in variant_clusters:
            total_cluster_rows = 0
            for val in cluster:
                for r in by_value[val]:
                    affected_set.add(r.id)
                    total_cluster_rows += 1
            cluster_details.append(
                {
                    "variants": cluster,
                    "row_count": total_cluster_rows,
                }
            )

        ordered_ids = [r.id for r in rows if r.id in affected_set]
        preview = ", ".join(f"[{', '.join(c['variants'][:3])}]" for c in cluster_details[:3])

        issues.append(
            DetectedIssue(
                issue_type="label_variants",
                severity="medium",
                column_id=col.id,
                row_ids=ordered_ids,
                affected_count=len(ordered_ids),
                description=f"Column `{col.name}` has {len(variant_clusters)} inconsistent label variant group(s): {preview}",
                details_json={
                    "column_name": col.name,
                    "clusters": cluster_details[:10],
                },
            )
        )

    return issues

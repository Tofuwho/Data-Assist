import logging
import math
import re
import time
from collections import Counter
from datetime import UTC, date, datetime
from typing import Any

from app.models.database import SessionLocal
from app.models.entities import ColumnModel, Dataset, RowModel

logger = logging.getLogger(__name__)

NULL_LIKE_VALUES = {"n/a", "na", "null", "none", "-", "#n/a"}

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[\d\s().-]{7,20}$")
PERCENTAGE_RE = re.compile(r"^[+-]?\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*%$|^[+-]?\s*\d+(?:\.\d+)?\s*%$")
LEADING_ZERO_INT_RE = re.compile(r"^0\d+$")
IDENTIFIER_CODE_RE = re.compile(r"^[A-Za-z]{1,6}[-_]?\d{2,}$|^\d{2,}[-_][A-Za-z0-9]+$")
PLAIN_INT_RE = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})*$|^[+-]?\d+$")
PLAIN_FLOAT_RE = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})*\.\d+$|^[+-]?\d+\.\d+$")

CURRENCY_PREFIX_RE = re.compile(
    r"^(?:\(\s*)?[+-]?\s*(?:\$|€|£|¥|₹|USD|EUR|GBP|CAD|AUD|JPY|SGD|CHF)\s*[+-]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)(?:\s*\))?$",
    re.IGNORECASE,
)
CURRENCY_SUFFIX_RE = re.compile(
    r"^[+-]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?:\$|€|£|¥|₹|USD|EUR|GBP|CAD|AUD|JPY|SGD|CHF)$",
    re.IGNORECASE,
)
BOOL_TEXT_VALUES = {"true", "false", "yes", "no", "y", "n", "t", "f"}

# Order matters: unambiguous ISO / named-month formats first, then slash/dash numeric formats.
EXPLICIT_DATE_FORMATS: list[tuple[str, str]] = [
    ("%Y-%m-%d", "%Y-%m-%d"),
    ("%Y/%m/%d", "%Y/%m/%d"),
    ("%Y.%m.%d", "%Y.%m.%d"),
    ("%d-%b-%Y", "%d-%b-%Y"),
    ("%d-%b-%y", "%d-%b-%y"),
    ("%d %b %Y", "%d %b %Y"),
    ("%b %d, %Y", "%b %d, %Y"),
    ("%B %d, %Y", "%B %d, %Y"),
    ("%m/%d/%Y", "%m/%d/%Y"),
    ("%d/%m/%Y", "%d/%m/%Y"),
    ("%m-%d-%Y", "%m-%d-%Y"),
    ("%d-%m-%Y", "%d-%m-%Y"),
    ("%m/%d/%y", "%m/%d/%y"),
    ("%d/%m/%y", "%d/%m/%y"),
]

EXPLICIT_DATETIME_FORMATS: list[tuple[str, str]] = [
    ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"),
    ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S"),
    ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%SZ"),
    ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M"),
    ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S"),
    ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S"),
    ("%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M"),
    ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M"),
]

NUMERIC_DATE_RE = re.compile(r"^(\d{1,2})([/-])(\d{1,2})\2(\d{2,4})$")

IDENTIFIER_NAME_HINTS = (
    "id",
    "sku",
    "code",
    "zip",
    "postal",
    "pin",
    "account",
    "invoice",
    "order_no",
    "transaction",
    "respondent",
)


def is_null_or_null_like(raw_val: Any) -> tuple[bool, bool]:
    """Return (is_missing, is_null_like).

    Empty/whitespace-only strings count as missing (is_missing=True, is_null_like=False).
    Tokens like 'N/A', 'NA', 'null', 'none', '-', '#N/A' count as missing and null_like.
    """
    if raw_val is None:
        return True, False
    s = str(raw_val).strip()
    if s == "":
        return True, False
    if s.lower() in NULL_LIKE_VALUES:
        return True, True
    return False, False


def parse_currency_value(text: str) -> float | None:
    """Parse a currency string like '$1,250.00', '3400 USD', '€850.00' into float."""
    s = text.strip()
    if not s:
        return None
    negative = (s.startswith("(") and s.endswith(")")) or s.startswith("-")
    m = CURRENCY_PREFIX_RE.match(s) or CURRENCY_SUFFIX_RE.match(s)
    if not m:
        return None
    num_str = m.group(1).replace(",", "")
    try:
        val = float(num_str)
        return -val if negative and val > 0 else val
    except ValueError:
        return None


def parse_percentage_value(text: str) -> float | None:
    """Parse percentage string like '12.5%' into float 12.5."""
    s = text.strip()
    if not PERCENTAGE_RE.match(s):
        return None
    try:
        return float(s[:-1].replace(",", "").strip())
    except ValueError:
        return None


def parse_numeric_value(text: str) -> tuple[str | None, float | None]:
    """Parse plain integer or decimal string (no currency/percent).

    Rejects leading-zero strings like '00123' so ZIP codes and IDs stay identifiers.
    Returns ('integer' | 'decimal' | None, float_val | None).
    """
    s = text.strip()
    if not s:
        return None, None
    unsigned = s.lstrip("+-")
    if LEADING_ZERO_INT_RE.match(unsigned):
        return None, None
    if PLAIN_INT_RE.match(s):
        try:
            return "integer", float(s.replace(",", ""))
        except ValueError:
            return None, None
    if PLAIN_FLOAT_RE.match(s):
        try:
            return "decimal", float(s.replace(",", ""))
        except ValueError:
            return None, None
    return None, None


def parse_date_or_datetime(text: str) -> tuple[str | None, str | None, date | None, bool]:
    """Classify text as datetime or date without silently guessing ambiguous DD/MM vs MM/DD.

    Returns: (kind: 'date'|'datetime'|None, format_label, parsed_date, is_ambiguous)
    """
    s = text.strip()
    if not s:
        return None, None, None, False

    for fmt, label in EXPLICIT_DATETIME_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            return "datetime", label, dt.date(), False
        except ValueError:
            continue

    m = NUMERIC_DATE_RE.match(s)
    if m:
        part1 = int(m.group(1))
        sep = m.group(2)
        part2 = int(m.group(3))
        year_str = m.group(4)
        yr_fmt = "%Y" if len(year_str) == 4 else "%y"

        # If both first and second numbers are <= 12 and unequal (e.g. 03/04/2025),
        # never silently pick MM/DD vs DD/MM!
        if 1 <= part1 <= 12 and 1 <= part2 <= 12 and part1 != part2:
            # Verify at least valid year/month/day
            try:
                datetime.strptime(s, f"%m{sep}%d{sep}{yr_fmt}")
                label = f"ambiguous (%m{sep}%d{sep}{yr_fmt} or %d{sep}%m{sep}{yr_fmt})"
                return "date", label, None, True
            except ValueError:
                pass

    for fmt, label in EXPLICIT_DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            return "date", label, dt.date(), False
        except ValueError:
            continue

    return None, None, None, False


def compute_format_pattern(text: str) -> str:
    """Compute generalized shape of a value (e.g. '99/99/9999', 'AAA-999')."""
    s = text.strip()
    if len(s) > 32:
        return f"<text:{len(s)} chars>"
    out: list[str] = []
    for ch in s:
        if ch.isdigit():
            out.append("9")
        elif ch.isalpha():
            out.append("A" if ch.isupper() else "a")
        else:
            out.append(ch)
    return "".join(out)


def classify_case_style(text: str) -> str:
    """Classify alphabetic casing style: upper, lower, title, mixed, or non_alpha."""
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return "non_alpha"
    s = text.strip()
    if s.isupper():
        return "upper"
    if s.islower():
        return "lower"
    if s.istitle():
        return "title"
    return "mixed"


def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Compute linear-interpolated percentile on sorted values."""
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


def infer_semantic_hint(col_name: str, inferred_type: str, values: list[str]) -> str | None:
    """Best-effort rule-based semantic hint from column name and values."""
    name = col_name.strip().lower().replace("-", "_").replace(" ", "_")

    if inferred_type == "email" or "email" in name or "e_mail" in name:
        return "email"
    if inferred_type == "phone" or "phone" in name or "mobile" in name or "tel" in name:
        return "phone"
    if inferred_type in ("date", "datetime") or any(k in name for k in ("date", "time", "created", "submitted", "timestamp")):
        return "datetime" if inferred_type == "datetime" else "date"
    if inferred_type == "currency" or any(k in name for k in ("amount", "price", "revenue", "cost", "salary", "total", "sales", "spend", "budget")):
        return "amount"
    if inferred_type == "percentage" or any(k in name for k in ("pct", "percent", "rate", "margin", "ratio")):
        return "percentage"
    if any(k in name for k in ("region", "state", "country", "city", "territory", "location", "warehouse")):
        return "region"
    if any(k in name for k in ("customer", "client", "company", "vendor", "account_name")):
        return "customer_name"
    if any(k in name for k in ("department", "dept", "team", "division")):
        return "department"
    if "status" in name or "state" == name:
        return "status"
    if "category" in name or "segment" in name or "type" in name:
        return "category"
    if "score" in name or "rating" in name or "satisfaction" in name or "nps" in name:
        return "score"
    if "recommend" in name:
        return "recommendation"
    if any(k in name for k in ("feedback", "comment", "note", "description", "review", "summary")):
        return "feedback"
    if any(k in name for k in ("qty", "quantity", "units", "count")):
        return "quantity"
    if "weight" in name:
        return "weight"
    if inferred_type == "identifier" or name == "id" or name.endswith("_id") or any(k in name for k in ("sku", "zip", "postal", "code")):
        return "identifier"

    if inferred_type == "category":
        return "category"
    return None


def _looks_like_identifier(col_name: str, values: list[str]) -> bool:
    """Detect IDs, SKUs, ZIP codes, and code-like values that shouldn't be coerced as numbers."""
    if not values:
        return False
    name = col_name.strip().lower().replace("-", "_").replace(" ", "_")
    header_is_id = (
        name == "id"
        or name.endswith("_id")
        or name.startswith("id_")
        or any(hint in name for hint in IDENTIFIER_NAME_HINTS)
    )

    leading_zero_count = 0
    code_count = 0
    lengths: set[int] = set()
    digit_only_count = 0

    for raw in values:
        s = raw.strip()
        lengths.add(len(s))
        if LEADING_ZERO_INT_RE.match(s):
            leading_zero_count += 1
        if IDENTIFIER_CODE_RE.match(s):
            code_count += 1
        if s.isdigit():
            digit_only_count += 1

    n = len(values)
    # Explicit prefix/code pattern like TX1001, R001, SKU-101
    if code_count / n >= 0.8:
        return True
    # Leading zeros (e.g. 02138, 00042)
    if leading_zero_count / n >= 0.3:
        return True
    # Header explicitly says id/zip/postal/code and values are mostly uniform/digit codes
    if header_is_id and (digit_only_count / n >= 0.8 or len(set(values)) / n >= 0.8):
        if len(lengths) == 1 or digit_only_count / n >= 0.8:
            return True
    return False


def profile_column_values(col_name: str, raw_values: list[Any]) -> dict[str, Any]:
    """Compute complete statistical profile and inferred type for a single column."""
    total_count = len(raw_values)
    empty_count = 0
    null_like_count = 0
    non_null_raw: list[str] = []

    for val in raw_values:
        is_missing, is_null_like = is_null_or_null_like(val)
        if is_missing:
            if is_null_like:
                null_like_count += 1
            else:
                empty_count += 1
        else:
            non_null_raw.append(str(val))

    null_count = empty_count + null_like_count
    non_null_count = len(non_null_raw)
    null_pct = round((null_count / total_count) * 100, 2) if total_count > 0 else 0.0

    # Value frequencies & format patterns (preserve raw string for exact top_values)
    value_counts = Counter(non_null_raw)
    distinct_count = len(value_counts)
    top_values = [{"value": val, "count": cnt} for val, cnt in value_counts.most_common(10)]

    format_counter: Counter[str] = Counter()
    date_format_counter: Counter[str] = Counter()
    parsed_dates: list[date] = []
    ambiguous_date_count = 0

    # Per-value type votes
    type_counts: Counter[str] = Counter()
    numeric_values: list[float] = []

    # Text metrics
    lengths: list[int] = []
    word_counts: list[int] = []
    whitespace_count = 0
    case_counter: Counter[str] = Counter()

    for raw in non_null_raw:
        stripped = raw.strip()
        if raw != stripped:
            whitespace_count += 1

        lengths.append(len(stripped))
        word_counts.append(len(stripped.split()))
        case_counter[classify_case_style(stripped)] += 1
        format_counter[compute_format_pattern(stripped)] += 1

        # Classify value
        if EMAIL_RE.match(stripped):
            type_counts["email"] += 1
            continue

        cur_val = parse_currency_value(stripped)
        if cur_val is not None:
            type_counts["currency"] += 1
            numeric_values.append(cur_val)
            continue

        pct_val = parse_percentage_value(stripped)
        if pct_val is not None:
            type_counts["percentage"] += 1
            numeric_values.append(pct_val)
            continue

        dt_kind, dt_fmt, dt_obj, is_ambig = parse_date_or_datetime(stripped)
        if dt_kind is not None:
            type_counts[dt_kind] += 1
            if dt_fmt:
                date_format_counter[dt_fmt] += 1
            if is_ambig:
                ambiguous_date_count += 1
            elif dt_obj is not None:
                parsed_dates.append(dt_obj)
            continue

        num_kind, num_val = parse_numeric_value(stripped)
        if num_kind is not None and num_val is not None:
            type_counts[num_kind] += 1
            numeric_values.append(num_val)
            continue

        if stripped.lower() in BOOL_TEXT_VALUES:
            type_counts["boolean"] += 1
            continue

        digit_count = sum(ch.isdigit() for ch in stripped)
        if PHONE_RE.match(stripped) and 7 <= digit_count <= 15:
            type_counts["phone"] += 1
            continue

        type_counts["text"] += 1

    # Determine dominant inferred_type
    inferred_type = _resolve_inferred_type(
        col_name=col_name,
        non_null_raw=non_null_raw,
        type_counts=type_counts,
        distinct_count=distinct_count,
        lengths=lengths,
        word_counts=word_counts,
    )

    # Numeric stats
    numeric_stats: dict[str, Any] | None = None
    if numeric_values and inferred_type in ("integer", "decimal", "currency", "percentage", "mixed"):
        sorted_nums = sorted(numeric_values)
        n_valid = len(sorted_nums)
        total_sum = sum(sorted_nums)
        mid = n_valid // 2
        if n_valid % 2 == 1:
            median_val = sorted_nums[mid]
        else:
            median_val = (sorted_nums[mid - 1] + sorted_nums[mid]) / 2.0
        q1 = _percentile(sorted_nums, 0.25)
        q3 = _percentile(sorted_nums, 0.75)

        numeric_stats = {
            "min": round(sorted_nums[0], 4),
            "max": round(sorted_nums[-1], 4),
            "mean": round(total_sum / n_valid, 4),
            "median": round(median_val, 4),
            "sum": round(total_sum, 4),
            "q1": round(q1, 4),
            "q3": round(q3, 4),
            "iqr": round(q3 - q1, 4),
            "valid_count": n_valid,
            "invalid_count": non_null_count - n_valid,
        }

    # Text stats
    text_stats: dict[str, Any] | None = None
    if non_null_count > 0:
        text_stats = {
            "min_length": min(lengths),
            "max_length": max(lengths),
            "avg_length": round(sum(lengths) / non_null_count, 2),
            "whitespace_count": whitespace_count,
            "whitespace_pct": round((whitespace_count / non_null_count) * 100, 2),
            "case_distribution": {
                "upper": case_counter.get("upper", 0),
                "lower": case_counter.get("lower", 0),
                "title": case_counter.get("title", 0),
                "mixed": case_counter.get("mixed", 0),
                "non_alpha": case_counter.get("non_alpha", 0),
            },
        }

    # Date stats
    date_stats: dict[str, Any] | None = None
    if date_format_counter:
        date_stats = {
            "formats": dict(date_format_counter),
            "ambiguous_count": ambiguous_date_count,
            "min": min(parsed_dates).isoformat() if parsed_dates else None,
            "max": max(parsed_dates).isoformat() if parsed_dates else None,
        }

    semantic_hint = infer_semantic_hint(col_name, inferred_type, non_null_raw)

    stats_json = {
        "total_count": total_count,
        "non_null_count": non_null_count,
        "null_count": null_count,
        "empty_count": empty_count,
        "null_like_count": null_like_count,
        "null_pct": null_pct,
        "distinct_count": distinct_count,
        "top_values": top_values,
        "format_patterns": dict(format_counter.most_common(15)),
        "numeric": numeric_stats,
        "text": text_stats,
        "date": date_stats,
    }

    return {
        "inferred_type": inferred_type,
        "semantic_hint": semantic_hint,
        "stats_json": stats_json,
    }


def _resolve_inferred_type(
    col_name: str,
    non_null_raw: list[str],
    type_counts: Counter[str],
    distinct_count: int,
    lengths: list[int],
    word_counts: list[int],
) -> str:
    """Determine dominant column type cleanly, preventing ID false positives."""
    n = len(non_null_raw)
    if n == 0:
        return "free_text"

    # Check identifier guard first (IDs, ZIPs, SKUs, codes)
    if _looks_like_identifier(col_name, non_null_raw):
        return "identifier"

    # Combine compatible numeric / date buckets for dominant type check
    cur_cnt = type_counts.get("currency", 0)
    int_cnt = type_counts.get("integer", 0)
    dec_cnt = type_counts.get("decimal", 0)
    pct_cnt = type_counts.get("percentage", 0)
    date_cnt = type_counts.get("date", 0)
    dt_cnt = type_counts.get("datetime", 0)
    bool_cnt = type_counts.get("boolean", 0)
    email_cnt = type_counts.get("email", 0)
    phone_cnt = type_counts.get("phone", 0)
    text_cnt = type_counts.get("text", 0)

    if email_cnt / n >= 0.8:
        return "email"
    if phone_cnt / n >= 0.8:
        return "phone"
    if bool_cnt / n >= 0.8:
        return "boolean"
    if pct_cnt / n >= 0.8:
        return "percentage"

    # Currency + plain numbers when currency dominates
    if cur_cnt > 0 and (cur_cnt + int_cnt + dec_cnt) / n >= 0.7 and cur_cnt / (cur_cnt + int_cnt + dec_cnt) >= 0.4:
        return "currency"

    if (int_cnt + dec_cnt) / n >= 0.8:
        return "decimal" if dec_cnt > 0 else "integer"

    if (date_cnt + dt_cnt) / n >= 0.75:
        return "datetime" if dt_cnt > date_cnt else "date"

    # Mixed type check: e.g. survey scores mixing integers/ratios/text ("5/5", "Satisfied", "4")
    # where non-text typed values coexist substantially with text values (neither >= 75%)
    structured_cnt = cur_cnt + int_cnt + dec_cnt + pct_cnt + date_cnt + dt_cnt + bool_cnt + email_cnt + phone_cnt
    if structured_cnt > 0 and text_cnt > 0:
        structured_ratio = structured_cnt / n
        if 0.15 <= structured_ratio < 0.75:
            return "mixed"

    # Also detect ratio/scale mixes in text (e.g. '5/5', '9/10' mixed with words like 'Satisfied')
    ratio_cnt = sum(1 for v in non_null_raw if re.match(r"^\d+\s*/\s*\d+$", v.strip()))
    if ratio_cnt > 0 and (ratio_cnt + int_cnt + dec_cnt) < n and (ratio_cnt + int_cnt + dec_cnt) / n >= 0.2:
        return "mixed"

    # Text: category vs free_text
    avg_len = sum(lengths) / n if lengths else 0.0
    max_len = max(lengths) if lengths else 0
    avg_words = sum(word_counts) / n if word_counts else 0.0
    name_lower = col_name.strip().lower()

    if any(k in name_lower for k in ("feedback", "comment", "description", "notes", "review", "message")):
        if avg_words >= 2.0 or max_len >= 25:
            return "free_text"

    if avg_words >= 3.0 or avg_len > 35 or max_len > 80:
        return "free_text"

    if distinct_count <= 50 and (distinct_count / n <= 0.75 or max_len <= 30):
        return "category"

    return "free_text" if avg_len > 25 else "category"


def profile_dataset(dataset_id: str) -> dict[str, Any]:
    """Compute column profiles and dataset-level completeness stats and persist to DB."""
    start_time = time.perf_counter()
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter_by(id=dataset_id).first()
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")

        columns = (
            db.query(ColumnModel)
            .filter_by(dataset_id=dataset_id)
            .order_by(ColumnModel.position)
            .all()
        )
        rows = (
            db.query(RowModel)
            .filter_by(dataset_id=dataset_id)
            .order_by(RowModel.row_index)
            .all()
        )

        row_count = len(rows)
        column_count = len(columns)
        total_cells = row_count * column_count
        total_null_cells = 0
        total_null_like_cells = 0

        for col in columns:
            col_values = [row.raw_json.get(col.name, "") for row in rows]
            profile = profile_column_values(col.name, col_values)
            col.inferred_type = profile["inferred_type"]
            col.semantic_hint = profile["semantic_hint"]
            col.stats_json = profile["stats_json"]

            total_null_cells += profile["stats_json"]["null_count"]
            total_null_like_cells += profile["stats_json"]["null_like_count"]

        completeness_pct = (
            round(((total_cells - total_null_cells) / total_cells) * 100, 2)
            if total_cells > 0
            else 100.0
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        dataset.stats_json = {
            "row_count": row_count,
            "column_count": column_count,
            "total_cells": total_cells,
            "null_cells": total_null_cells,
            "null_like_cells": total_null_like_cells,
            "completeness_pct": completeness_pct,
            "profiled_at": datetime.now(UTC).isoformat(),
            "profile_duration_ms": duration_ms,
        }

        db.commit()

        logger.info(
            "Profiled dataset %s (%d rows, %d cols, %.2f%% completeness) in %.2fms",
            dataset_id,
            row_count,
            column_count,
            completeness_pct,
            duration_ms,
        )
        return {
            "dataset_id": dataset_id,
            "row_count": row_count,
            "column_count": column_count,
            "completeness_pct": completeness_pct,
            "profile_duration_ms": duration_ms,
        }
    except Exception as exc:
        db.rollback()
        logger.error("Profiling failed for dataset %s: %s", dataset_id, exc, exc_info=True)
        raise
    finally:
        db.close()

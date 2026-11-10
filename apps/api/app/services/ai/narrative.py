import json
import re
from datetime import UTC, datetime
from typing import Any

from app.services.ai.client import LLMClient, get_llm_client
from app.services.analysis.analyzer import build_metrics_packet_from_blocks

NARRATIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["headline", "executive_summary", "key_findings", "recommendations", "caveats"],
    "properties": {
        "headline": {"type": "string"},
        "executive_summary": {"type": "string"},
        "key_findings": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "string"}},
        "caveats": {"type": "array", "items": {"type": "string"}},
    },
}

SYSTEM_PROMPT = (
    "You are an executive data analyst briefing business stakeholders. "
    "Describe ONLY numbers, counts, percentages, and dates explicitly present in METRICS_PACKET_JSON. "
    "Never invent, extrapolate, or estimate figures not present in METRICS_PACKET_JSON. "
    "Highlight honest data quality caveats when present. "
    "Return strictly valid JSON with keys: headline, executive_summary, key_findings, recommendations, caveats."
)

ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?\b")
YEAR_MONTH_RE = re.compile(r"\b\d{4}-\d{2}\b")
ISO_WEEK_RE = re.compile(r"\b\d{4}-W\d{2}\b|\bW\d{2}\s+\d{4}\b")
NUMBER_MENTION_RE = re.compile(
    r"(?:(?<=^)|(?<=[\s(\[{\$€£¥₹]))[+-]?(?:\$|€|£|¥|₹|USD|EUR|GBP|CAD|AUD|JPY|SGD|CHF)?\s*"
    r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?(?!\w)",
    re.IGNORECASE,
)


def _collect_allowed_values(obj: Any, nums: set[float], date_tokens: set[str]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        nums.add(float(obj))
        return
    if isinstance(obj, str):
        for m in ISO_DATE_RE.findall(obj):
            date_tokens.add(m[:10])
            nums.add(float(m[:4]))
        for ym in YEAR_MONTH_RE.findall(obj):
            date_tokens.add(ym)
            nums.add(float(ym[:4]))
        for wk in ISO_WEEK_RE.findall(obj):
            date_tokens.add(wk)
        # Also allow numbers inside preformatted scalar strings (like formatted_value "$39,770.50")
        for m in NUMBER_MENTION_RE.finditer(obj):
            parsed = _parse_mention_float(m.group(0))
            if parsed is not None:
                nums.add(parsed)
        return
    if isinstance(obj, list):
        for item in obj:
            _collect_allowed_values(item, nums, date_tokens)
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            # Allow keys? No, values hold verified metrics; caveat strings stay controlled
            if k in ("title", "message", "formatted_value", "label", "start_period", "end_period", "start_date", "end_date"):
                _collect_allowed_values(v, nums, date_tokens)
            elif k != "id":
                _collect_allowed_values(v, nums, date_tokens)


def _parse_mention_float(token: str) -> float | None:
    cleaned = token.strip()
    negative = False
    if cleaned.startswith("-"):
        negative = True
        cleaned = cleaned[1:].strip()
    elif cleaned.startswith("+"):
        cleaned = cleaned[1:].strip()

    for sym in ("$", "€", "£", "¥", "₹", "USD", "EUR", "GBP", "CAD", "AUD", "JPY", "SGD", "CHF"):
        if cleaned.upper().startswith(sym):
            cleaned = cleaned[len(sym) :].strip()
        if cleaned.upper().endswith(sym):
            cleaned = cleaned[: -len(sym)].strip()

    if cleaned.endswith("%"):
        cleaned = cleaned[:-1].strip()

    if not cleaned:
        return None
    if "-" in cleaned and not cleaned.startswith("-"):
        return None
    cleaned = cleaned.replace(",", "")
    try:
        val = float(cleaned)
        return -val if negative and val > 0 else val
    except ValueError:
        return None


def _number_matches_allowed(candidate: float, allowed: set[float]) -> bool:
    for ref in allowed:
        if abs(candidate - ref) <= 1e-6:
            return True
        if any(abs(candidate - round(ref, decimals)) <= 1e-6 for decimals in (0, 1, 2, 3, 4)):
            return True
    return False


def verify_narrative_numbers(
    narrative_data: dict[str, Any],
    metrics_packet: dict[str, Any],
) -> dict[str, Any]:
    """Verify every numeric and ISO date mention in generated narrative exists in metrics_packet."""
    allowed_numbers: set[float] = set()
    allowed_dates: set[str] = set()
    _collect_allowed_values(metrics_packet, allowed_numbers, allowed_dates)

    texts: list[str] = [
        str(narrative_data.get("headline") or ""),
        str(narrative_data.get("executive_summary") or ""),
        *[str(x) for x in (narrative_data.get("key_findings") or [])],
        *[str(x) for x in (narrative_data.get("recommendations") or [])],
        *[str(x) for x in (narrative_data.get("caveats") or [])],
    ]

    unverified: list[str] = []
    checked_count = 0

    for text in texts:
        # 1. Check ISO dates & YYYY-MM & ISO week tokens first, then strip them from text
        stripped = text
        for iso_match in ISO_DATE_RE.findall(stripped):
            checked_count += 1
            if iso_match[:10] not in allowed_dates:
                unverified.append(iso_match)
        stripped = ISO_DATE_RE.sub(" ", stripped)

        for ym_match in YEAR_MONTH_RE.findall(stripped):
            checked_count += 1
            if ym_match not in allowed_dates and not any(d.startswith(ym_match) for d in allowed_dates):
                unverified.append(ym_match)
        stripped = YEAR_MONTH_RE.sub(" ", stripped)

        for wk_match in ISO_WEEK_RE.findall(stripped):
            checked_count += 1
            if wk_match not in allowed_dates:
                unverified.append(wk_match)
        stripped = ISO_WEEK_RE.sub(" ", stripped)

        # 2. Check remaining numeric mentions
        for match in NUMBER_MENTION_RE.finditer(stripped):
            raw_tok = match.group(0).strip()
            val = _parse_mention_float(raw_tok)
            if val is None:
                continue
            checked_count += 1
            if not _number_matches_allowed(val, allowed_numbers):
                unverified.append(raw_tok)

    return {
        "verified": len(unverified) == 0,
        "total_numbers_checked": checked_count,
        "unverified_numbers": unverified,
        "checked_at": datetime.now(UTC).isoformat(),
    }


def _validate_narrative_structure(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("LLM output must be a JSON object")

    for req_str in ("headline", "executive_summary"):
        val = payload.get(req_str)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"Missing or empty string field '{req_str}'")

    for req_list in ("key_findings", "recommendations", "caveats"):
        val = payload.get(req_list)
        if not isinstance(val, list):
            raise ValueError(f"Field '{req_list}' must be a list of strings")

    return {
        "headline": payload["headline"].strip(),
        "executive_summary": payload["executive_summary"].strip(),
        "key_findings": [str(x).strip() for x in payload["key_findings"] if str(x).strip()],
        "recommendations": [str(x).strip() for x in payload["recommendations"] if str(x).strip()],
        "caveats": [str(x).strip() for x in payload["caveats"] if str(x).strip()],
    }


def generate_report_narrative(
    report_title: str,
    dataset_name: str,
    analysis: dict[str, Any],
    computed_blocks: list[dict[str, Any]],
    client: LLMClient | None = None,
) -> dict[str, Any]:
    """Generate schema-validated and numerically verified executive narrative from backend metrics."""
    llm = client or get_llm_client()
    metrics_packet = build_metrics_packet_from_blocks(
        report_title=report_title,
        dataset_name=dataset_name,
        analysis=analysis,
        computed_blocks=computed_blocks,
    )

    base_user_prompt = (
        "Generate an executive briefing for stakeholders grounded ONLY in the metrics packet below.\n"
        f"METRICS_PACKET_JSON:\n{json.dumps(metrics_packet, indent=2)}"
    )

    last_error: Exception | None = None
    narrative: dict[str, Any] | None = None
    verification: dict[str, Any] = {
        "verified": False,
        "total_numbers_checked": 0,
        "unverified_numbers": [],
        "checked_at": datetime.now(UTC).isoformat(),
    }

    retry_hint = ""
    for attempt in range(2):
        prompt = base_user_prompt if attempt == 0 else f"{base_user_prompt}\n\nCORRECTION NOTE: {retry_hint}"
        try:
            raw = llm.complete_json(SYSTEM_PROMPT, prompt, NARRATIVE_SCHEMA)
            narrative = _validate_narrative_structure(raw)
        except Exception as exc:
            last_error = exc
            retry_hint = f"Previous response failed schema validation ({exc}). Return ONLY valid JSON matching schema."
            continue

        verification = verify_narrative_numbers(narrative, metrics_packet)
        if verification["verified"]:
            break
        retry_hint = (
            "Remove or fix unverified numbers that do not appear in METRICS_PACKET_JSON: "
            + ", ".join(verification["unverified_numbers"])
        )

    if narrative is None:
        raise ValueError(f"Failed to generate valid narrative JSON: {last_error}")

    return {
        **narrative,
        "provider": getattr(llm, "provider_name", type(llm).__name__),
        "model": getattr(llm, "model_name", "custom"),
        "generated_at": datetime.now(UTC).isoformat(),
        "verification": verification,
    }

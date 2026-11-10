import hashlib
import json
import logging
import time
from typing import Any, Protocol

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """Swappable LLM interface matching BUILD_PLAN.md Section 6."""

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]: ...


def _hash_prompt(system: str, user: str) -> str:
    return hashlib.sha256(f"{system}\n---\n{user}".encode()).hexdigest()[:16]


def _strip_json_fences(raw_text: str) -> str:
    s = raw_text.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def _extract_metrics_packet(user_prompt: str) -> dict[str, Any]:
    marker = "METRICS_PACKET_JSON:"
    idx = user_prompt.find(marker)
    candidate = user_prompt[idx + len(marker) :].strip() if idx != -1 else user_prompt.strip()

    # Locate the outermost JSON object cleanly
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {}


def _format_metric_number(value: Any, format_style: str | None) -> str:
    if value is None:
        return "0"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)

    if abs(num - round(num)) <= 1e-6 and format_style != "currency":
        num_str = f"{int(round(num)):,}"
    else:
        num_str = f"{num:,.2f}"

    if format_style == "currency":
        if num < 0:
            return f"-${abs(num):,.2f}"
        return f"${num:,.2f}"
    if format_style == "percent":
        return f"{num_str}%"
    return num_str


class MockLLMClient:
    """Offline deterministic synthesizer using only metrics provided inside the prompt JSON."""

    provider_name = "mock"
    model_name = "deterministic-narrative-v1"

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        prompt_hash = _hash_prompt(system, user)
        packet = _extract_metrics_packet(user)

        required = set(schema.get("required", []))
        if "headline" in required and "executive_summary" in required:
            result = self._build_executive_narrative(packet)
        else:
            # Safe generic JSON fallback matching required keys if called for other structured tasks
            result = {k: "" for k in required}

        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        logger.info(
            "LLM call completed provider=%s model=%s prompt_hash=%s tokens_est=%d latency_ms=%.2f",
            self.provider_name,
            self.model_name,
            prompt_hash,
            max(1, len(user) // 4),
            latency_ms,
        )
        return result

    def _build_executive_narrative(self, packet: dict[str, Any]) -> dict[str, Any]:
        dataset_name = packet.get("dataset_name", "Dataset")
        overview = packet.get("overview") or {}
        primary = packet.get("primary_measure")
        breakdowns = packet.get("segment_breakdowns") or []
        time_series = packet.get("time_series")
        correlations = packet.get("correlations") or []
        caveats_raw = packet.get("data_quality_caveats") or []

        row_count = overview.get("row_count", 0)
        col_count = overview.get("column_count", 0)
        completeness = overview.get("completeness_pct", 100.0)
        open_issues = overview.get("open_issues_count", 0)
        high_crit = overview.get("high_critical_issues_count", 0)
        readiness = str(overview.get("readiness", "needs_review")).replace("_", " ")

        # Headline
        if primary:
            p_col = primary["column"]
            p_fmt = primary.get("format_style")
            p_sum = _format_metric_number(primary.get("sum"), p_fmt)
            if breakdowns and breakdowns[0].get("top_segment"):
                top_seg = breakdowns[0]["top_segment"]
                top_share = breakdowns[0].get("top_segment_share_pct", 0.0)
                headline = (
                    f"{dataset_name}: {p_col} totals {p_sum} across {primary.get('valid_count', row_count)} valid records, "
                    f"led by {top_seg} ({top_share}%)"
                )
            else:
                headline = f"{dataset_name}: {p_col} totals {p_sum} across {row_count} records"
        elif breakdowns and breakdowns[0].get("top_segment"):
            b0 = breakdowns[0]
            headline = (
                f"{dataset_name}: {row_count} records analyzed; {b0['dimension']} led by "
                f"{b0['top_segment']} ({b0.get('top_segment_share_pct', 0.0)}%)"
            )
        else:
            headline = f"{dataset_name}: {row_count} records analyzed at {completeness}% completeness"

        # Executive Summary
        summary_parts: list[str] = [
            f"Analysis covers {row_count} rows and {col_count} columns with {completeness}% cell completeness "
            f"(readiness status: {readiness}; {open_issues} open quality issue(s))."
        ]
        if primary:
            p_col = primary["column"]
            p_fmt = primary.get("format_style")
            p_sum = _format_metric_number(primary.get("sum"), p_fmt)
            p_mean = _format_metric_number(primary.get("mean"), p_fmt)
            summary_parts.append(
                f"Primary metric {p_col} sums to {p_sum} with a mean of {p_mean} across "
                f"{primary.get('valid_count', 0)} valid rows."
            )
            if primary.get("unparseable_count", 0):
                summary_parts.append(
                    f"{primary['unparseable_count']} unparseable row(s) were excluded from numeric aggregation and isolated in block lineage."
                )
        if time_series and time_series.get("start_period") and time_series.get("end_period"):
            ts_str = (
                f"Chronological coverage spans {time_series['start_period']} through {time_series['end_period']} "
                f"across {time_series.get('valid_date_count', 0)} valid dates"
            )
            if time_series.get("period_change_pct") is not None:
                ts_str += f" ({time_series['period_change_pct']}% change between start and end periods)"
            summary_parts.append(ts_str + ".")
        executive_summary = " ".join(summary_parts)

        # Key Findings
        findings: list[str] = []
        if primary:
            p_col = primary["column"]
            p_fmt = primary.get("format_style")
            findings.append(
                f"{p_col} ranges from {_format_metric_number(primary.get('min'), p_fmt)} to "
                f"{_format_metric_number(primary.get('max'), p_fmt)}, with median "
                f"{_format_metric_number(primary.get('median'), p_fmt)}."
            )

        for bd in breakdowns:
            if not bd.get("top_segment"):
                continue
            top_items = bd.get("top_segments") or []
            if bd.get("metric_column") and top_items:
                top_val_fmt = _format_metric_number(
                    top_items[0].get("metric_sum"),
                    primary.get("format_style") if primary else "number",
                )
                findings.append(
                    f"By {bd['dimension']}, '{bd['top_segment']}' accounts for {top_val_fmt} "
                    f"({bd.get('top_segment_share_pct', 0.0)}% share across {top_items[0].get('row_count', 0)} row(s)); "
                    f"{bd.get('unique_bucket_count', 0)} distinct group(s) detected."
                )
            elif top_items:
                findings.append(
                    f"By {bd['dimension']}, '{bd['top_segment']}' leads with {top_items[0].get('row_count', 0)} row(s) "
                    f"({bd.get('top_segment_share_pct', 0.0)}% of records) across {bd.get('unique_bucket_count', 0)} distinct group(s)."
                )

        if time_series and time_series.get("peak_period"):
            pk = time_series["peak_period"]
            pk_fmt = _format_metric_number(
                pk.get("value"),
                primary.get("format_style") if primary else "number",
            )
            findings.append(
                f"Peak {time_series['granularity']} activity occurred in {pk.get('label')} at {pk_fmt}."
            )

        if correlations:
            c0 = correlations[0]
            findings.append(
                f"{c0['column_a']} and {c0['column_b']} show a {c0['strength']} {c0['direction']} linear "
                f"correlation (r = {c0['pearson_r']}) across {c0['paired_rows']} paired rows."
            )

        if not findings:
            findings.append(
                f"Dataset contains {row_count} records across {col_count} columns with {completeness}% completeness."
            )

        # Recommendations grounded in detected findings/caveats
        recommendations: list[str] = []
        has_label_variants = any(c.get("category") == "label_variants" for c in caveats_raw)
        has_mixed_currency = any(c.get("category") == "mixed_currency" for c in caveats_raw)
        has_ambiguous_dates = any(c.get("category") == "ambiguous_dates" for c in caveats_raw)
        has_unparseable = any(c.get("category") == "unparseable_numeric" for c in caveats_raw)
        has_mixed_scale = any(c.get("category") == "mixed_scale" for c in caveats_raw)

        if has_label_variants:
            recommendations.append(
                "Standardize casing and abbreviation variants in categorical columns so fragmented segment totals consolidate accurately."
            )
        if has_mixed_currency:
            recommendations.append(
                "Separate or FX-convert mixed currency notations before presenting combined monetary totals for financial sign-off."
            )
        if has_ambiguous_dates:
            recommendations.append(
                "Confirm the source date convention (MM/DD vs DD/MM) for skipped ambiguous dates to restore full timeline coverage."
            )
        if has_unparseable:
            recommendations.append(
                "Review and remediate unparseable numeric records via click-through block lineage before executive distribution."
            )
        if has_mixed_scale:
            recommendations.append(
                "Normalize mixed rating formats onto a uniform numeric scale to unlock weighted satisfaction KPIs."
            )
        if not recommendations:
            recommendations.append(
                f"Data quality is strong ({completeness}% completeness); submit this report with {high_crit} high/critical issues remaining for stakeholder review."
            )

        # Caveats citing only exact packet strings/numbers
        caveats: list[str] = []
        for cav in caveats_raw:
            col = cav.get("column")
            prefix = f"[{col}] " if col else ""
            caveats.append(f"{prefix}{cav.get('title', 'Quality notice')}.")
        if not caveats:
            caveats.append(f"No critical quality caveats detected ({open_issues} open issue(s) across {row_count} rows).")

        return {
            "headline": headline,
            "executive_summary": executive_summary,
            "key_findings": findings[:5],
            "recommendations": recommendations[:4],
            "caveats": caveats[:5],
        }


class OpenAILLMClient:
    """OpenAI Chat Completions JSON client."""

    provider_name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.model_name = model

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        prompt_hash = _hash_prompt(system, user)
        payload = {
            "model": self.model_name,
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": f"{system}\nReturn strictly valid JSON matching schema: {json.dumps(schema)}"},
                {"role": "user", "content": user},
            ],
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()

        usage = body.get("usage", {})
        raw_text = body["choices"][0]["message"]["content"]
        parsed = json.loads(_strip_json_fences(raw_text))
        logger.info(
            "LLM call completed provider=%s model=%s prompt_hash=%s usage=%s latency_ms=%.2f",
            self.provider_name,
            self.model_name,
            prompt_hash,
            usage,
            round((time.perf_counter() - started) * 1000.0, 2),
        )
        return parsed


class AnthropicLLMClient:
    """Anthropic Messages JSON client."""

    provider_name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-3-5-haiku-latest") -> None:
        self.api_key = api_key
        self.model_name = model

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        prompt_hash = _hash_prompt(system, user)
        payload = {
            "model": self.model_name,
            "max_tokens": 1600,
            "temperature": 0.1,
            "system": f"{system}\nOutput ONLY valid JSON matching schema: {json.dumps(schema)}",
            "messages": [{"role": "user", "content": user}],
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()

        usage = body.get("usage", {})
        raw_text = "".join(part.get("text", "") for part in body.get("content", []) if part.get("type") == "text")
        parsed = json.loads(_strip_json_fences(raw_text))
        logger.info(
            "LLM call completed provider=%s model=%s prompt_hash=%s usage=%s latency_ms=%.2f",
            self.provider_name,
            self.model_name,
            prompt_hash,
            usage,
            round((time.perf_counter() - started) * 1000.0, 2),
        )
        return parsed


class GeminiLLMClient:
    """Google Gemini GenerateContent JSON client."""

    provider_name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self.api_key = api_key
        self.model_name = model

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        prompt_hash = _hash_prompt(system, user)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        payload = {
            "systemInstruction": {
                "parts": [{"text": f"{system}\nReturn strictly valid JSON matching schema: {json.dumps(schema)}"}]
            },
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, params={"key": self.api_key}, json=payload)
            resp.raise_for_status()
            body = resp.json()

        usage = body.get("usageMetadata", {})
        candidates = body.get("candidates") or []
        raw_text = candidates[0]["content"]["parts"][0]["text"]
        parsed = json.loads(_strip_json_fences(raw_text))
        logger.info(
            "LLM call completed provider=%s model=%s prompt_hash=%s usage=%s latency_ms=%.2f",
            self.provider_name,
            self.model_name,
            prompt_hash,
            usage,
            round((time.perf_counter() - started) * 1000.0, 2),
        )
        return parsed


def get_llm_client(provider: str | None = None) -> LLMClient:
    """Instantiate configured LLM client (`mock` default offline, or `openai` / `anthropic` / `gemini`)."""
    chosen = (provider or settings.LLM_PROVIDER or "mock").strip().lower()
    if chosen == "mock":
        return MockLLMClient()

    if chosen == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY must be set when LLM_PROVIDER=openai")
        model = settings.LLM_MODEL or "gpt-4o-mini"
        return OpenAILLMClient(api_key=settings.OPENAI_API_KEY, model=model)

    if chosen == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY must be set when LLM_PROVIDER=anthropic")
        model = (
            "claude-3-5-haiku-latest"
            if not settings.LLM_MODEL or settings.LLM_MODEL == "gpt-4o-mini"
            else settings.LLM_MODEL
        )
        return AnthropicLLMClient(api_key=settings.ANTHROPIC_API_KEY, model=model)

    if chosen == "gemini":
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY must be set when LLM_PROVIDER=gemini")
        model = (
            "gemini-2.0-flash"
            if not settings.LLM_MODEL or settings.LLM_MODEL == "gpt-4o-mini"
            else settings.LLM_MODEL
        )
        return GeminiLLMClient(api_key=settings.GEMINI_API_KEY, model=model)

    raise ValueError(f"Unsupported LLM_PROVIDER: {chosen}")

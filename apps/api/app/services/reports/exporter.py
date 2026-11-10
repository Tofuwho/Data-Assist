import io
from datetime import UTC, datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.services.analysis.resolver import EffectiveDataset

MAX_AUDIT_EXPORT_ROWS = 10000


def _auto_fit_columns(ws: Any, max_width: int = 48) -> None:
    for col_idx in range(1, ws.max_column + 1):
        max_len = 10
        col_letter = get_column_letter(col_idx)
        for row_idx in range(1, min(ws.max_row + 1, 200)):
            val = ws.cell(row=row_idx, column=col_idx).value
            if val is not None:
                text = str(val).splitlines()[0] if str(val) else ""
                max_len = max(max_len, len(text) + 3)
        ws.column_dimensions[col_letter].width = min(max_len, max_width)


def build_report_xlsx(
    report_title: str,
    report_status: str,
    effective: EffectiveDataset,
    analysis: dict[str, Any],
    computed_blocks: list[dict[str, Any]],
) -> bytes:
    """Export an executive multi-sheet XLSX stakeholder workbook from computed report blocks & effective rows."""
    wb = Workbook()

    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    sub_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    section_font = Font(bold=True, color="0F172A", size=12)
    title_font = Font(bold=True, color="0F172A", size=16)

    # Sheet 1: Executive Summary
    ws_exec = wb.active
    ws_exec.title = "Executive Summary"

    ws_exec["A1"] = report_title
    ws_exec["A1"].font = title_font
    ws_exec["A2"] = f"Dataset: {effective.dataset.name} (v{effective.version.version_number}) | Status: {report_status.upper()}"
    ws_exec["A3"] = f"Exported: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"

    overview = analysis.get("overview") or {}
    row_cursor = 5
    ws_exec.cell(row=row_cursor, column=1, value="Overview Metric").font = header_font
    ws_exec.cell(row=row_cursor, column=1).fill = header_fill
    ws_exec.cell(row=row_cursor, column=2, value="Value").font = header_font
    ws_exec.cell(row=row_cursor, column=2).fill = header_fill
    row_cursor += 1

    overview_rows = [
        ("Rows Analyzed", overview.get("row_count", 0)),
        ("Columns", overview.get("column_count", 0)),
        ("Cell Completeness (%)", overview.get("completeness_pct", 100.0)),
        ("Data Readiness", str(overview.get("readiness", "needs_review")).replace("_", " ").title()),
        ("Open Quality Issues", overview.get("open_issues_count", 0)),
        ("High / Critical Issues", overview.get("high_critical_issues_count", 0)),
    ]
    for label, val in overview_rows:
        ws_exec.cell(row=row_cursor, column=1, value=label)
        ws_exec.cell(row=row_cursor, column=2, value=val)
        row_cursor += 1

    # KPI Summary
    kpi_blocks = [b for b in computed_blocks if b.get("type") == "kpi"]
    if kpi_blocks:
        row_cursor += 1
        ws_exec.cell(row=row_cursor, column=1, value="Key Performance Indicators").font = section_font
        row_cursor += 1
        for col_idx, h in enumerate(["KPI", "Aggregation", "Value", "Contributing Rows", "Excluded Rows"], start=1):
            cell = ws_exec.cell(row=row_cursor, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
        row_cursor += 1
        for kb in kpi_blocks:
            d = kb.get("data") or {}
            ws_exec.cell(row=row_cursor, column=1, value=kb.get("title", ""))
            ws_exec.cell(row=row_cursor, column=2, value=d.get("aggregation", ""))
            ws_exec.cell(row=row_cursor, column=3, value=d.get("formatted_value", ""))
            ws_exec.cell(row=row_cursor, column=4, value=d.get("matching_rows", 0))
            ws_exec.cell(row=row_cursor, column=5, value=d.get("excluded_rows", 0))
            row_cursor += 1

    # Narrative block
    narrative_blocks = [b for b in computed_blocks if b.get("type") == "narrative" and b.get("data")]
    if narrative_blocks:
        nd = narrative_blocks[0]["data"]
        row_cursor += 1
        ws_exec.cell(row=row_cursor, column=1, value="Executive Briefing").font = section_font
        row_cursor += 1
        ws_exec.cell(row=row_cursor, column=1, value="Headline").font = Font(bold=True)
        ws_exec.cell(row=row_cursor, column=2, value=nd.get("headline", "")).alignment = Alignment(wrap_text=True)
        row_cursor += 1
        ws_exec.cell(row=row_cursor, column=1, value="Summary").font = Font(bold=True)
        ws_exec.cell(row=row_cursor, column=2, value=nd.get("executive_summary", "")).alignment = Alignment(wrap_text=True)
        row_cursor += 1

        verif = nd.get("verification") or {}
        ws_exec.cell(row=row_cursor, column=1, value="Numeric Grounding").font = Font(bold=True)
        ws_exec.cell(
            row=row_cursor,
            column=2,
            value=(
                f"Verified ({verif.get('total_numbers_checked', 0)} numbers checked)"
                if verif.get("verified")
                else f"Needs Review (Unverified: {', '.join(verif.get('unverified_numbers', []))})"
            ),
        )
        row_cursor += 1

        for idx, item in enumerate(nd.get("key_findings") or [], start=1):
            ws_exec.cell(row=row_cursor, column=1, value=f"Finding {idx}").font = Font(bold=True)
            ws_exec.cell(row=row_cursor, column=2, value=item).alignment = Alignment(wrap_text=True)
            row_cursor += 1

        for idx, item in enumerate(nd.get("recommendations") or [], start=1):
            ws_exec.cell(row=row_cursor, column=1, value=f"Recommendation {idx}").font = Font(bold=True)
            ws_exec.cell(row=row_cursor, column=2, value=item).alignment = Alignment(wrap_text=True)
            row_cursor += 1

    # Data Quality Caveats
    caveats = analysis.get("data_quality_caveats") or []
    if caveats:
        row_cursor += 1
        ws_exec.cell(row=row_cursor, column=1, value="Data Quality & Methodology Caveats").font = section_font
        row_cursor += 1
        for col_idx, h in enumerate(["Severity", "Column", "Caveat", "Details", "Affected"], start=1):
            cell = ws_exec.cell(row=row_cursor, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
        row_cursor += 1
        for cav in caveats:
            ws_exec.cell(row=row_cursor, column=1, value=str(cav.get("severity", "")).upper())
            ws_exec.cell(row=row_cursor, column=2, value=cav.get("column") or "Dataset")
            ws_exec.cell(row=row_cursor, column=3, value=cav.get("title", ""))
            ws_exec.cell(row=row_cursor, column=4, value=cav.get("message", "")).alignment = Alignment(wrap_text=True)
            ws_exec.cell(row=row_cursor, column=5, value=cav.get("affected_count", 0))
            row_cursor += 1

    _auto_fit_columns(ws_exec, max_width=72)

    # Sheet 2: Metrics & Charts Data
    ws_data = wb.create_sheet("Metrics & Charts Data")
    data_row = 1
    for blk in computed_blocks:
        btype = blk.get("type")
        if btype not in ("bar_chart", "pie_chart", "line_chart", "area_chart", "summary_table"):
            continue
        d = blk.get("data") or {}
        ws_data.cell(row=data_row, column=1, value=blk.get("title", "")).font = section_font
        data_row += 1

        if btype in ("line_chart", "area_chart"):
            headers = ["Period", "Value", "Rows", "Valid Metric Rows", "Excluded Rows"]
            for ci, h in enumerate(headers, start=1):
                c = ws_data.cell(row=data_row, column=ci, value=h)
                c.font = header_font
                c.fill = header_fill
            data_row += 1
            for pt in d.get("points") or []:
                ws_data.cell(row=data_row, column=1, value=pt.get("label"))
                ws_data.cell(row=data_row, column=2, value=pt.get("value"))
                ws_data.cell(row=data_row, column=3, value=pt.get("row_count"))
                ws_data.cell(row=data_row, column=4, value=pt.get("valid_metric_count"))
                ws_data.cell(row=data_row, column=5, value=pt.get("excluded_rows"))
                data_row += 1
        else:
            items = d.get("items") or d.get("rows") or []
            headers = ["Segment", "Value", "Share (%)", "Rows", "Valid Metric Rows", "Excluded Rows"]
            for ci, h in enumerate(headers, start=1):
                c = ws_data.cell(row=data_row, column=ci, value=h)
                c.font = header_font
                c.fill = header_fill
            data_row += 1
            for it in items:
                ws_data.cell(row=data_row, column=1, value=it.get("label"))
                ws_data.cell(row=data_row, column=2, value=it.get("value"))
                ws_data.cell(row=data_row, column=3, value=it.get("share_pct"))
                ws_data.cell(row=data_row, column=4, value=it.get("row_count"))
                ws_data.cell(row=data_row, column=5, value=it.get("valid_metric_count"))
                ws_data.cell(row=data_row, column=6, value=it.get("excluded_rows"))
                data_row += 1
        data_row += 1

    if data_row == 1:
        ws_data["A1"] = "No chart or breakdown blocks configured in this report."
    _auto_fit_columns(ws_data)

    # Sheet 3: Source Data Audit
    ws_audit = wb.create_sheet("Source Data Audit")
    audit_headers = ["row_index", *[c.name for c in effective.columns], "modified_columns"]
    for ci, h in enumerate(audit_headers, start=1):
        cell = ws_audit.cell(row=1, column=ci, value=h)
        cell.font = header_font
        cell.fill = header_fill

    for r_idx, row in enumerate(effective.rows[:MAX_AUDIT_EXPORT_ROWS], start=2):
        ws_audit.cell(row=r_idx, column=1, value=row.row_index)
        for ci, col in enumerate(effective.columns, start=2):
            raw_val = row.values.get(col.name, "")
            safe_val = (
                f"'{raw_val}"
                if isinstance(raw_val, str) and raw_val.startswith(("=", "@", "\t", "\r"))
                else raw_val
            )
            c = ws_audit.cell(row=r_idx, column=ci, value=safe_val)
            if col.name in row.changed_columns:
                c.fill = sub_fill
        ws_audit.cell(
            row=r_idx,
            column=len(audit_headers),
            value=", ".join(sorted(row.changed_columns)) if row.changed_columns else "",
        )

    _auto_fit_columns(ws_audit)

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()

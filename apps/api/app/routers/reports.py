import copy
import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.database import get_db
from app.models.entities import (
    AuditLog,
    Dataset,
    DatasetVersion,
    Membership,
    Project,
    Report,
)
from app.routers.deps import (
    require_dataset_role,
    require_project_role,
    require_report_role,
)
from app.schemas.report import (
    AnalysisColumnOption,
    AnalyzeDatasetRequest,
    BlockLineageResponse,
    CreateReportRequest,
    DatasetAnalysisResponse,
    GenerateNarrativeRequest,
    ReportDetailResponse,
    ReportListItemResponse,
    UpdateReportRequest,
)
from app.services.ai import generate_report_narrative
from app.services.ai.client import get_llm_client
from app.services.analysis import (
    EffectiveDataset,
    analyze_dataset,
    recommend_report_layout,
    resolve_effective_dataset,
    resolve_effective_dataset_from_version,
)
from app.services.reports import (
    build_report_xlsx,
    evaluate_report_blocks,
    extract_block_lineage,
)

router = APIRouter(tags=["Reports & Analysis"])

READ_ROLES = ["admin", "steward", "stakeholder"]
WRITE_ROLES = ["admin", "steward"]


def _build_analysis_response(effective: EffectiveDataset, analysis: dict[str, Any]) -> DatasetAnalysisResponse:
    return DatasetAnalysisResponse(
        **analysis,
        columns=[
            AnalysisColumnOption(
                name=col.name,
                inferred_type=col.inferred_type,
                semantic_hint=col.semantic_hint,
            )
            for col in effective.columns
        ],
    )


def _evaluate_and_serialize_report(
    report: Report,
    effective: EffectiveDataset,
    analysis: dict[str, Any] | None = None,
) -> ReportDetailResponse:
    computed_analysis = analysis or analyze_dataset(effective)
    layout = copy.deepcopy(report.layout_json or {"version": 1, "template": "general_summary", "blocks": []})
    computed_blocks = evaluate_report_blocks(effective, layout, analysis=computed_analysis)
    return ReportDetailResponse(
        id=report.id,
        project_id=report.project_id,
        dataset_id=effective.dataset.id,
        dataset_name=effective.dataset.name,
        dataset_version_id=effective.version.id,
        version_number=effective.version.version_number,
        title=report.title,
        status=report.status,
        template=str(layout.get("template") or "general_summary"),
        layout_json=layout,
        computed_blocks=computed_blocks,
        analysis=_build_analysis_response(effective, computed_analysis),
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    return cleaned or "stakeholder_report"


@router.get("/datasets/{dataset_id}/analysis", response_model=DatasetAnalysisResponse)
def get_dataset_analysis(
    dataset_ctx: Annotated[tuple[Dataset, Project, Membership], Depends(require_dataset_role(READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    version_id: Annotated[str | None, Query()] = None,
):
    """Compute deterministic KPIs, segment breakdowns, time trends, correlations, and quality caveats."""
    dataset, _, _ = dataset_ctx
    try:
        effective = resolve_effective_dataset(db, dataset_id=dataset.id, version_id=version_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    analysis = analyze_dataset(effective)
    return _build_analysis_response(effective, analysis)


@router.post(
    "/datasets/{dataset_id}/analyze",
    response_model=ReportDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def analyze_dataset_into_report(
    payload: AnalyzeDatasetRequest,
    dataset_ctx: Annotated[tuple[Dataset, Project, Membership], Depends(require_dataset_role(WRITE_ROLES))],
    db: Annotated[Session, Depends(get_db)],
):
    """Analyze a dataset version, generate recommended stakeholder report layout, compute blocks & verified narrative."""
    dataset, project, membership = dataset_ctx
    try:
        effective = resolve_effective_dataset(db, dataset_id=dataset.id, version_id=payload.version_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    analysis = analyze_dataset(effective)
    recommended_title, layout = recommend_report_layout(effective, analysis, template=payload.template)
    report_title = (payload.title or "").strip() or recommended_title

    computed_blocks = evaluate_report_blocks(effective, layout, analysis=analysis)

    if payload.include_narrative:
        try:
            llm_client = get_llm_client(payload.llm_provider)
            narrative = generate_report_narrative(
                report_title=report_title,
                dataset_name=effective.dataset.name,
                analysis=analysis,
                computed_blocks=computed_blocks,
                client=llm_client,
            )
            for blk in layout.get("blocks", []):
                if blk.get("type") == "narrative":
                    blk["content"] = narrative
                    break
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    report = Report(
        project_id=project.id,
        dataset_version_id=effective.version.id,
        title=report_title,
        status="draft",
        layout_json=layout,
    )
    db.add(report)
    db.flush()

    db.add(
        AuditLog(
            workspace_id=project.workspace_id,
            actor_id=membership.user_id,
            action="report.generated",
            payload_json={
                "report_id": report.id,
                "dataset_id": effective.dataset.id,
                "dataset_version_id": effective.version.id,
                "template": layout.get("template"),
            },
        )
    )
    db.commit()
    db.refresh(report)

    return _evaluate_and_serialize_report(report, effective, analysis=analysis)


@router.get("/projects/{project_id}/reports", response_model=list[ReportListItemResponse])
def list_project_reports(
    project_ctx: Annotated[tuple[Project, Membership], Depends(require_project_role(READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
):
    """List stakeholder reports in a project ordered by latest update."""
    project, _ = project_ctx
    rows = (
        db.query(Report, DatasetVersion, Dataset)
        .join(DatasetVersion, Report.dataset_version_id == DatasetVersion.id)
        .join(Dataset, DatasetVersion.dataset_id == Dataset.id)
        .filter(Report.project_id == project.id)
        .order_by(Report.updated_at.desc())
        .all()
    )

    items: list[ReportListItemResponse] = []
    for report, version, dataset in rows:
        layout = report.layout_json or {}
        items.append(
            ReportListItemResponse(
                id=report.id,
                project_id=report.project_id,
                dataset_id=dataset.id,
                dataset_name=dataset.name,
                dataset_version_id=version.id,
                version_number=version.version_number,
                title=report.title,
                status=report.status,
                template=str(layout.get("template") or "general_summary"),
                block_count=len(layout.get("blocks") or []),
                created_at=report.created_at,
                updated_at=report.updated_at,
            )
        )
    return items


@router.post(
    "/projects/{project_id}/reports",
    response_model=ReportDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_report(
    payload: CreateReportRequest,
    project_ctx: Annotated[tuple[Project, Membership], Depends(require_project_role(WRITE_ROLES))],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a custom or templated stakeholder report for a dataset inside the project."""
    project, membership = project_ctx
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == payload.dataset_id, Dataset.project_id == project.id)
        .first()
    )
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {payload.dataset_id} not found in project {project.id}",
        )

    try:
        effective = resolve_effective_dataset(
            db,
            dataset_id=dataset.id,
            version_id=payload.dataset_version_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    analysis = analyze_dataset(effective)
    if payload.layout_json is not None:
        layout = copy.deepcopy(payload.layout_json)
        if "version" not in layout:
            layout["version"] = 1
        if "template" not in layout:
            layout["template"] = payload.template
        if "blocks" not in layout:
            layout["blocks"] = []
        report_title = (payload.title or "").strip() or f"{dataset.name} — Custom Stakeholder Report"
    else:
        recommended_title, layout = recommend_report_layout(effective, analysis, template=payload.template)
        report_title = (payload.title or "").strip() or recommended_title

    computed_blocks = evaluate_report_blocks(effective, layout, analysis=analysis)
    if payload.include_narrative:
        has_narrative_without_content = any(
            b.get("type") == "narrative" and not b.get("content") for b in layout.get("blocks", [])
        )
        if has_narrative_without_content:
            llm_client = get_llm_client(payload.llm_provider)
            narrative = generate_report_narrative(
                report_title=report_title,
                dataset_name=effective.dataset.name,
                analysis=analysis,
                computed_blocks=computed_blocks,
                client=llm_client,
            )
            for blk in layout.get("blocks", []):
                if blk.get("type") == "narrative":
                    blk["content"] = narrative
                    break

    report = Report(
        project_id=project.id,
        dataset_version_id=effective.version.id,
        title=report_title,
        status="draft",
        layout_json=layout,
    )
    db.add(report)
    db.flush()

    db.add(
        AuditLog(
            workspace_id=project.workspace_id,
            actor_id=membership.user_id,
            action="report.created",
            payload_json={
                "report_id": report.id,
                "dataset_id": dataset.id,
                "dataset_version_id": effective.version.id,
            },
        )
    )
    db.commit()
    db.refresh(report)
    return _evaluate_and_serialize_report(report, effective, analysis=analysis)


@router.get("/reports/{report_id}", response_model=ReportDetailResponse)
def get_report(
    report_ctx: Annotated[tuple[Report, Project, Membership], Depends(require_report_role(READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
):
    """Fetch report definition along with live server-computed block metrics and analysis summary."""
    report, _, _ = report_ctx
    try:
        effective = resolve_effective_dataset_from_version(db, report.dataset_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _evaluate_and_serialize_report(report, effective)


@router.patch("/reports/{report_id}", response_model=ReportDetailResponse)
def update_report(
    payload: UpdateReportRequest,
    report_ctx: Annotated[tuple[Report, Project, Membership], Depends(require_report_role(WRITE_ROLES))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update report title, workflow status, or interactive layout blocks and recompute metrics."""
    report, project, membership = report_ctx

    if payload.title is not None:
        report.title = payload.title.strip()
    if payload.status is not None:
        report.status = payload.status
    if payload.layout_json is not None:
        new_layout = copy.deepcopy(payload.layout_json)
        if "version" not in new_layout:
            new_layout["version"] = 1
        if "blocks" not in new_layout:
            new_layout["blocks"] = []
        report.layout_json = new_layout
        flag_modified(report, "layout_json")

    db.add(
        AuditLog(
            workspace_id=project.workspace_id,
            actor_id=membership.user_id,
            action="report.updated",
            payload_json={
                "report_id": report.id,
                "status": report.status,
                "block_count": len((report.layout_json or {}).get("blocks") or []),
            },
        )
    )
    db.commit()
    db.refresh(report)

    effective = resolve_effective_dataset_from_version(db, report.dataset_version_id)
    return _evaluate_and_serialize_report(report, effective)


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(
    report_ctx: Annotated[tuple[Report, Project, Membership], Depends(require_report_role(WRITE_ROLES))],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete a stakeholder report."""
    report, project, membership = report_ctx
    report_id = report.id
    db.delete(report)
    db.add(
        AuditLog(
            workspace_id=project.workspace_id,
            actor_id=membership.user_id,
            action="report.deleted",
            payload_json={"report_id": report_id},
        )
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reports/{report_id}/compute", response_model=ReportDetailResponse)
def compute_report(
    report_ctx: Annotated[tuple[Report, Project, Membership], Depends(require_report_role(READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
):
    """Force server-side evaluation of all report blocks from current effective dataset version."""
    report, _, _ = report_ctx
    effective = resolve_effective_dataset_from_version(db, report.dataset_version_id)
    return _evaluate_and_serialize_report(report, effective)


@router.post("/reports/{report_id}/narrative", response_model=ReportDetailResponse)
def generate_narrative_for_report(
    payload: GenerateNarrativeRequest,
    report_ctx: Annotated[tuple[Report, Project, Membership], Depends(require_report_role(WRITE_ROLES))],
    db: Annotated[Session, Depends(get_db)],
):
    """Synthesize a grounded executive narrative from verified backend metrics and verify all numbers."""
    report, project, membership = report_ctx
    effective = resolve_effective_dataset_from_version(db, report.dataset_version_id)
    analysis = analyze_dataset(effective)

    layout = copy.deepcopy(report.layout_json or {"version": 1, "template": "general_summary", "blocks": []})
    blocks = list(layout.get("blocks") or [])
    computed_blocks = evaluate_report_blocks(effective, layout, analysis=analysis)

    try:
        llm_client = get_llm_client(payload.llm_provider)
        narrative = generate_report_narrative(
            report_title=report.title,
            dataset_name=effective.dataset.name,
            analysis=analysis,
            computed_blocks=computed_blocks,
            client=llm_client,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    target_block = None
    if payload.block_id:
        target_block = next(
            (b for b in blocks if b.get("id") == payload.block_id and b.get("type") == "narrative"),
            None,
        )
    if target_block is None:
        target_block = next((b for b in blocks if b.get("type") == "narrative"), None)

    if target_block is not None:
        target_block["content"] = narrative
    else:
        blocks.insert(
            0,
            {
                "id": "blk_narrative_1",
                "type": "narrative",
                "title": "Executive Briefing & Key Takeaways",
                "subtitle": "Grounded strictly in backend-computed metrics & quality checks",
                "width": "full",
                "config": {},
                "content": narrative,
            },
        )
        layout["blocks"] = blocks

    report.layout_json = layout
    flag_modified(report, "layout_json")
    db.add(
        AuditLog(
            workspace_id=project.workspace_id,
            actor_id=membership.user_id,
            action="report.narrative_generated",
            payload_json={
                "report_id": report.id,
                "provider": narrative.get("provider"),
                "verified": narrative.get("verification", {}).get("verified"),
            },
        )
    )
    db.commit()
    db.refresh(report)

    return _evaluate_and_serialize_report(report, effective, analysis=analysis)


@router.get("/reports/{report_id}/blocks/{block_id}/lineage", response_model=BlockLineageResponse)
def get_report_block_lineage(
    block_id: str,
    report_ctx: Annotated[tuple[Report, Project, Membership], Depends(require_report_role(READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    bucket_key: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Return exact contributing source RowModel records and audit history for any report block or chart segment."""
    report, _, _ = report_ctx
    layout = report.layout_json or {}
    blocks = layout.get("blocks") or []
    block = next((b for b in blocks if b.get("id") == block_id), None)
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Block {block_id} not found in report {report.id}",
        )

    effective = resolve_effective_dataset_from_version(db, report.dataset_version_id)
    lineage = extract_block_lineage(
        db=db,
        effective=effective,
        block=block,
        bucket_key=bucket_key,
        limit=limit,
        offset=offset,
    )
    return BlockLineageResponse(**lineage)


@router.get("/reports/{report_id}/export")
def export_report(
    report_ctx: Annotated[tuple[Report, Project, Membership], Depends(require_report_role(READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    format: Annotated[Literal["xlsx", "json"], Query()] = "xlsx",
):
    """Export stakeholder report as a multi-sheet XLSX workbook or structured JSON bundle."""
    report, _, _ = report_ctx
    effective = resolve_effective_dataset_from_version(db, report.dataset_version_id)
    analysis = analyze_dataset(effective)
    layout = report.layout_json or {"version": 1, "blocks": []}
    computed_blocks = evaluate_report_blocks(effective, layout, analysis=analysis)

    if format == "json":
        return _evaluate_and_serialize_report(report, effective, analysis=analysis)

    xlsx_bytes = build_report_xlsx(
        report_title=report.title,
        report_status=report.status,
        effective=effective,
        analysis=analysis,
        computed_blocks=computed_blocks,
    )
    filename = f"{_safe_filename(report.title)}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

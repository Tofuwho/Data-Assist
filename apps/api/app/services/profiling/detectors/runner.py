import logging
from typing import Any

from app.models.database import SessionLocal
from app.models.entities import ColumnModel, Dataset, Issue, RowModel
from app.services.profiling.detectors.base import (
    MAX_STORED_ROW_IDS,
    ColumnInfo,
    DetectedIssue,
    RowInfo,
)
from app.services.profiling.detectors.duplicate_rows import detect_duplicate_rows
from app.services.profiling.detectors.inconsistent_text import detect_inconsistent_text
from app.services.profiling.detectors.label_variants import detect_label_variants
from app.services.profiling.detectors.missing_values import detect_missing_values
from app.services.profiling.detectors.mixed_formats import detect_mixed_formats
from app.services.profiling.detectors.near_duplicates import detect_near_duplicates
from app.services.profiling.detectors.outliers import detect_outliers
from app.services.profiling.detectors.type_violation import detect_type_violations

logger = logging.getLogger(__name__)


def run_all_detectors(columns: list[ColumnInfo], rows: list[RowInfo]) -> list[DetectedIssue]:
    """Run all deterministic issue detectors and return combined issue list."""
    detected: list[DetectedIssue] = []
    detected.extend(detect_missing_values(columns, rows))
    detected.extend(detect_duplicate_rows(columns, rows))
    detected.extend(detect_near_duplicates(columns, rows))
    detected.extend(detect_mixed_formats(columns, rows))
    detected.extend(detect_inconsistent_text(columns, rows))
    detected.extend(detect_type_violations(columns, rows))
    detected.extend(detect_outliers(columns, rows))
    detected.extend(detect_label_variants(columns, rows))
    return detected


def detect_dataset_issues(dataset_id: str) -> dict[str, Any]:
    """Run deterministic issue detection on a profiled dataset and persist results.

    Re-running replaces previous auto-detected open issues while preserving
    human-created issues and any issues already resolved/dismissed/in_review.
    """
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter_by(id=dataset_id).first()
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")

        db_cols = (
            db.query(ColumnModel)
            .filter_by(dataset_id=dataset_id)
            .order_by(ColumnModel.position)
            .all()
        )
        db_rows = (
            db.query(RowModel)
            .filter_by(dataset_id=dataset_id)
            .order_by(RowModel.row_index)
            .all()
        )

        col_infos = [
            ColumnInfo(
                id=c.id,
                name=c.name,
                position=c.position,
                inferred_type=c.inferred_type or "free_text",
                semantic_hint=c.semantic_hint,
                stats_json=c.stats_json or {},
            )
            for c in db_cols
        ]
        row_infos = [
            RowInfo(
                id=r.id,
                row_index=r.row_index,
                values=r.raw_json or {},
            )
            for r in db_rows
        ]

        detected = run_all_detectors(col_infos, row_infos)

        # Preserve human-created issues and already-resolved/dismissed/in_review auto issues
        preserved_keys = {
            (issue.type, issue.column_id)
            for issue in db.query(Issue)
            .filter(
                Issue.dataset_id == dataset_id,
                Issue.source == "auto",
                Issue.status.in_(["resolved", "dismissed", "in_review"]),
            )
            .all()
        }

        # Delete previous auto-detected open issues
        db.query(Issue).filter(
            Issue.dataset_id == dataset_id,
            Issue.source == "auto",
            Issue.status == "open",
        ).delete(synchronize_session=False)

        created_count = 0
        for d in detected:
            if (d.issue_type, d.column_id) in preserved_keys:
                continue
            issue = Issue(
                dataset_id=dataset_id,
                type=d.issue_type,
                severity=d.severity,
                column_id=d.column_id,
                row_ids=d.row_ids[:MAX_STORED_ROW_IDS],
                affected_count=d.affected_count,
                status="open",
                source="auto",
                description=d.description,
                details_json=d.details_json,
            )
            db.add(issue)
            created_count += 1

        db.commit()
        logger.info("Detected %d issues for dataset %s", created_count, dataset_id)
        return {"dataset_id": dataset_id, "issues_detected": created_count}
    except Exception as exc:
        db.rollback()
        logger.error("Issue detection failed for dataset %s: %s", dataset_id, exc, exc_info=True)
        raise
    finally:
        db.close()

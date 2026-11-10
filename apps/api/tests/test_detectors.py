import io
from pathlib import Path

from fastapi.testclient import TestClient

from app.models.entities import Issue
from app.services.profiling.detectors import (
    ColumnInfo,
    RowInfo,
    detect_dataset_issues,
    run_all_detectors,
)
from app.services.profiling.profiler import profile_column_values


def _setup_project(client: TestClient) -> tuple[str, dict]:
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "detectors@cleardata.io",
            "password": "Password123!",
            "name": "Dana Detector",
            "workspace_name": "Detection Workspace",
        },
    )
    assert res.status_code == 201, res.text
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    ws_id = client.get("/api/v1/workspaces", headers=headers).json()[0]["id"]
    proj = client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        headers=headers,
        json={"name": "Detection Project"},
    )
    assert proj.status_code == 201
    return proj.json()["id"], headers


def _load_fixture(name: str) -> bytes:
    p = Path("fixtures") / name
    if not p.exists():
        p = Path("../../fixtures") / name
    return p.read_bytes()


def _build_context(headers: list[str], raw_rows: list[dict[str, str]]) -> tuple[list[ColumnInfo], list[RowInfo]]:
    cols: list[ColumnInfo] = []
    for pos, name in enumerate(headers):
        vals = [r.get(name, "") for r in raw_rows]
        prof = profile_column_values(name, vals)
        cols.append(
            ColumnInfo(
                id=f"col-{pos}",
                name=name,
                position=pos,
                inferred_type=prof["inferred_type"],
                semantic_hint=prof["semantic_hint"],
                stats_json=prof["stats_json"],
            )
        )
    rows = [RowInfo(id=f"row-{i}", row_index=i, values=r) for i, r in enumerate(raw_rows)]
    return cols, rows


def test_clean_dataset_produces_zero_issues(client: TestClient):
    """A clean dataset with consistent types, formatting, and distinct labels must produce 0 issues."""
    project_id, headers = _setup_project(client)
    clean_csv = (
        b"Order_ID,Customer_Name,Order_Date,Amount,Region,Status\n"
        b"ORD-101,Acme Corp,2024-01-01,$100.00,North,Completed\n"
        b"ORD-102,Beta LLC,2024-01-02,$200.00,South,Completed\n"
        b"ORD-103,Gamma Inc,2024-01-03,$150.00,East,Pending\n"
        b"ORD-104,Delta Co,2024-01-04,$180.00,West,Completed\n"
        b"ORD-105,Omega Ltd,2024-01-05,$220.00,North,Pending\n"
    )
    up = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("clean_sales.csv", io.BytesIO(clean_csv), "text/csv")},
    )
    assert up.status_code == 202
    dataset_id = up.json()["dataset_id"]

    issues = client.get(f"/api/v1/datasets/{dataset_id}/issues", headers=headers).json()
    assert issues == []


def test_messy_sales_issues_detected(client: TestClient):
    """Verify detectors catch mixed formats, type violations, label variants, near duplicates, outliers, missing values."""
    project_id, headers = _setup_project(client)
    up = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("messy_sales.csv", io.BytesIO(_load_fixture("messy_sales.csv")), "text/csv")},
    )
    assert up.status_code == 202
    dataset_id = up.json()["dataset_id"]

    cols = {
        c["id"]: c["name"]
        for c in client.get(f"/api/v1/datasets/{dataset_id}/columns", headers=headers).json()
    }
    issues = client.get(f"/api/v1/datasets/{dataset_id}/issues", headers=headers).json()

    by_type_col = {(i["type"], cols.get(i["column_id"])): i for i in issues}

    assert ("mixed_formats", "Date") in by_type_col
    assert by_type_col[("mixed_formats", "Date")]["severity"] == "high"

    assert ("mixed_formats", "Amount") in by_type_col
    assert by_type_col[("mixed_formats", "Amount")]["severity"] == "high"

    assert ("type_violation", "Amount") in by_type_col
    assert by_type_col[("type_violation", "Amount")]["affected_count"] == 1

    assert ("label_variants", "Region") in by_type_col
    assert by_type_col[("label_variants", "Region")]["severity"] == "medium"

    assert ("near_duplicates", "Customer_Name") in by_type_col
    assert ("inconsistent_text", "Customer_Name") in by_type_col
    assert ("inconsistent_text", "Amount") in by_type_col  # leading/trailing whitespace on "  1,750.00 "

    assert ("missing_values", "Date") in by_type_col
    assert ("missing_values", "Customer_Name") in by_type_col
    assert ("missing_values", "Status") in by_type_col

    assert ("outliers", "Amount") in by_type_col
    assert by_type_col[("outliers", "Amount")]["severity"] == "low"

    # Test query filters on GET /issues
    high_issues = client.get(f"/api/v1/datasets/{dataset_id}/issues?severity=high", headers=headers).json()
    assert len(high_issues) >= 2
    assert all(i["severity"] == "high" for i in high_issues)

    date_col_id = next(cid for cid, cname in cols.items() if cname == "Date")
    date_issues = client.get(
        f"/api/v1/datasets/{dataset_id}/issues?column_id={date_col_id}&type=mixed_formats",
        headers=headers,
    ).json()
    assert len(date_issues) == 1


def test_survey_results_issues_detected(client: TestClient):
    """Verify survey_results.csv detects department label variants and mixed satisfaction scales."""
    project_id, headers = _setup_project(client)
    up = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("survey_results.csv", io.BytesIO(_load_fixture("survey_results.csv")), "text/csv")},
    )
    assert up.status_code == 202
    dataset_id = up.json()["dataset_id"]

    cols = {
        c["id"]: c["name"]
        for c in client.get(f"/api/v1/datasets/{dataset_id}/columns", headers=headers).json()
    }
    issues = client.get(f"/api/v1/datasets/{dataset_id}/issues", headers=headers).json()
    pairs = {(i["type"], cols.get(i["column_id"])) for i in issues}

    assert ("label_variants", "Department") in pairs
    assert ("mixed_formats", "Satisfaction_Score") in pairs
    assert ("missing_values", "Department") in pairs


def test_exact_duplicate_rows_and_missing_severity_thresholds():
    """Verify exact duplicate detector and missing_values severity thresholds (>20% high, 5-20% med, <5% low)."""
    rows_data = [{"ID": f"R{i}", "HighMiss": "", "MedMiss": "ok", "LowMiss": "ok"} for i in range(25)]
    for i in range(5):
        rows_data[i]["HighMiss"] = "val"  # 80% missing -> high
    for i in range(3):
        rows_data[i]["MedMiss"] = ""  # 12% missing -> medium
    rows_data[0]["LowMiss"] = ""  # 4% missing -> low
    # Duplicate row identical to row 5
    rows_data.append(dict(rows_data[5]))

    cols, rows = _build_context(["ID", "HighMiss", "MedMiss", "LowMiss"], rows_data)
    detected = run_all_detectors(cols, rows)

    by_type = {(d.issue_type, d.column_id): d for d in detected}
    assert by_type[("missing_values", "col-1")].severity == "high"
    assert by_type[("missing_values", "col-2")].severity == "medium"
    assert by_type[("missing_values", "col-3")].severity == "low"
    assert ("duplicate_rows", None) in by_type
    assert by_type[("duplicate_rows", None)].affected_count == 2


def test_rerun_preserves_human_and_resolved_issues_and_caps_row_ids(client: TestClient, db_session):
    """Re-running detection preserves human/resolved issues and caps stored row_ids at 1,000."""
    project_id, headers = _setup_project(client)

    # Create dataset with 1,050 rows having missing values in Notes
    lines = ["ID,Notes"] + [f"ID{i}," for i in range(1050)]
    csv_bytes = "\n".join(lines).encode("utf-8")

    up = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("many_rows.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert up.status_code == 202
    dataset_id = up.json()["dataset_id"]

    issues = db_session.query(Issue).filter_by(dataset_id=dataset_id).all()
    missing_issue = next(i for i in issues if i.type == "missing_values")
    assert missing_issue.affected_count == 1050
    assert len(missing_issue.row_ids) == 1000

    # Mark auto issue as resolved and add a human issue
    missing_issue.status = "resolved"
    human_issue = Issue(
        dataset_id=dataset_id,
        type="custom_review",
        severity="high",
        column_id=None,
        row_ids=[],
        affected_count=0,
        status="open",
        source="human",
        description="Analyst flagged fiscal calendar question",
    )
    db_session.add(human_issue)
    db_session.commit()

    # Re-run issue detection
    detect_dataset_issues(dataset_id)

    db_session.expire_all()
    after_issues = db_session.query(Issue).filter_by(dataset_id=dataset_id).all()
    assert any(i.id == human_issue.id and i.source == "human" for i in after_issues)
    assert any(i.id == missing_issue.id and i.status == "resolved" for i in after_issues)
    # Resolved auto issue should not be duplicated as a new open missing_values issue
    assert sum(1 for i in after_issues if i.type == "missing_values") == 1

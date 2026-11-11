import io
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.models.entities import CellValue, Change, ColumnModel, DatasetVersion, Issue, RowModel


def _setup_workspace(client: TestClient) -> tuple[str, str, dict]:
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "analyst_admin@cleardata.io",
            "password": "Password123!",
            "name": "Alice Analyst",
            "workspace_name": "Analytics Workspace",
        },
    )
    assert res.status_code == 201, res.text
    admin_headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    ws_id = client.get("/api/v1/workspaces", headers=admin_headers).json()[0]["id"]
    proj_res = client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        headers=admin_headers,
        json={"name": "Q1 Executive Insights"},
    )
    assert proj_res.status_code == 201, proj_res.text
    return ws_id, proj_res.json()["id"], admin_headers


def _load_fixture(name: str) -> bytes:
    path = Path("fixtures") / name
    if not path.exists():
        path = Path("../../fixtures") / name
    return path.read_bytes()


def test_analyze_messy_sales_survey_and_inventory_fixtures(client: TestClient):
    """Verify end-to-end deterministic analysis, templates, and verified narrative across all 3 fixtures."""
    _, project_id, headers = _setup_workspace(client)

    # 1. messy_sales.csv -> executive_sales
    up_sales = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("messy_sales.csv", io.BytesIO(_load_fixture("messy_sales.csv")), "text/csv")},
    )
    assert up_sales.status_code == 202
    sales_id = up_sales.json()["dataset_id"]

    an_sales = client.post(
        f"/api/v1/datasets/{sales_id}/analyze",
        headers=headers,
        json={"template": "auto", "include_narrative": True},
    )
    assert an_sales.status_code == 201, an_sales.text
    sales_rep = an_sales.json()
    assert sales_rep["template"] == "executive_sales"
    assert sales_rep["version_number"] == 1
    assert sales_rep["analysis"]["primary_measure"]["column"] == "Amount"
    assert sales_rep["analysis"]["primary_measure"]["sum"] == 40620.5
    assert sales_rep["analysis"]["primary_measure"]["unparseable_count"] == 1

    caveat_cats = {c["category"] for c in sales_rep["analysis"]["data_quality_caveats"]}
    assert "mixed_currency" in caveat_cats
    assert "unparseable_numeric" in caveat_cats
    assert "label_variants" in caveat_cats

    kpi_1 = next(b for b in sales_rep["computed_blocks"] if b["id"] == "blk_kpi_1")
    assert kpi_1["data"]["value"] == 40620.5
    assert kpi_1["data"]["formatted_value"] == "$40,620.50"
    assert kpi_1["data"]["matching_rows"] == 14
    assert kpi_1["data"]["excluded_rows"] == 1

    nar = next(b for b in sales_rep["computed_blocks"] if b["type"] == "narrative")
    assert nar["data"]["verification"]["verified"] is True
    assert nar["data"]["verification"]["unverified_numbers"] == []

    # 2. survey_results.csv -> survey_insights (mixed score safely excluded from numeric sum)
    up_survey = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("survey_results.csv", io.BytesIO(_load_fixture("survey_results.csv")), "text/csv")},
    )
    assert up_survey.status_code == 202
    survey_id = up_survey.json()["dataset_id"]

    an_survey = client.post(
        f"/api/v1/datasets/{survey_id}/analyze",
        headers=headers,
        json={"template": "auto", "include_narrative": True},
    )
    assert an_survey.status_code == 201, an_survey.text
    survey_rep = an_survey.json()
    assert survey_rep["template"] == "survey_insights"
    assert survey_rep["analysis"]["primary_measure"] is None
    assert any(c["category"] == "mixed_scale" for c in survey_rep["analysis"]["data_quality_caveats"])
    assert next(b for b in survey_rep["computed_blocks"] if b["type"] == "narrative")["data"]["verification"]["verified"] is True

    # 3. inventory.xlsx -> inventory_summary
    up_inv = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={
            "file": (
                "inventory.xlsx",
                io.BytesIO(_load_fixture("inventory.xlsx")),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert up_inv.status_code == 202
    north_id = next(d["dataset_id"] for d in up_inv.json()["datasets"] if "Warehouse_North" in d["name"])
    an_inv = client.post(
        f"/api/v1/datasets/{north_id}/analyze",
        headers=headers,
        json={"template": "auto", "include_narrative": True},
    )
    assert an_inv.status_code == 201
    inv_rep = an_inv.json()
    assert inv_rep["template"] == "inventory_summary"
    assert inv_rep["analysis"]["primary_measure"]["column"] == "Quantity"
    assert inv_rep["analysis"]["primary_measure"]["sum"] == 4130.0


def test_ambiguous_dates_and_click_through_lineage(client: TestClient):
    """Ambiguous dates never guessed; chart/KPI/excluded lineage matches exact source RowModel records."""
    _, project_id, headers = _setup_workspace(client)
    csv_bytes = (
        b"Order_ID,Order_Date,Region,Sales\n"
        b"O1,2024-05-01,East,$100.00\n"
        b"O2,2024-05-01,East,$200.00\n"
        b"O3,2024-05-02,West,$300.00\n"
        b"O4,03/04/2024,West,$400.00\n"  # Ambiguous MM/DD vs DD/MM
        b"O5,2024-05-03,East,bad_num\n"  # Unparseable Sales
    )
    up = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("orders.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert up.status_code == 202
    dataset_id = up.json()["dataset_id"]

    an = client.post(
        f"/api/v1/datasets/{dataset_id}/analyze",
        headers=headers,
        json={"template": "executive_sales"},
    )
    assert an.status_code == 201
    rep = an.json()
    rep_id = rep["id"]

    line_blk = next(b for b in rep["computed_blocks"] if b["type"] == "line_chart")
    assert line_blk["data"]["ambiguous_skipped_count"] == 1
    assert line_blk["data"]["valid_date_count"] == 4
    # 2024-05-01 -> 300, 2024-05-02 -> 300, 2024-05-03 -> 0 (excluded valid numeric)
    points_by_day = {p["bucket_key"]: p for p in line_blk["data"]["points"]}
    assert points_by_day["2024-05-01"]["value"] == 300.0
    assert points_by_day["2024-05-02"]["value"] == 300.0

    # Lineage for bar_chart bucket_key=East -> O1 & O2 (valid Sales), O5 excluded
    bar_blk = next(b for b in rep["computed_blocks"] if b["type"] == "bar_chart")
    lin_east = client.get(
        f"/api/v1/reports/{rep_id}/blocks/{bar_blk['id']}/lineage?bucket_key=East",
        headers=headers,
    )
    assert lin_east.status_code == 200
    east_data = lin_east.json()
    assert east_data["total_matching_rows"] == 2
    assert east_data["excluded_row_count"] == 1
    order_ids = [r["effective_values"]["Order_ID"] for r in east_data["rows"]]
    assert set(order_ids) == {"O1", "O2"}

    # Excluded rows lineage for line_chart catches O4 (ambiguous date) & O5 (unparseable metric)
    lin_excl = client.get(
        f"/api/v1/reports/{rep_id}/blocks/{line_blk['id']}/lineage?bucket_key=__excluded__",
        headers=headers,
    )
    assert lin_excl.status_code == 200
    excl_data = lin_excl.json()
    assert excl_data["total_matching_rows"] == 2
    excl_ids = {r["effective_values"]["Order_ID"] for r in excl_data["rows"]}
    assert excl_ids == {"O4", "O5"}


def test_version_locked_cell_overlay_and_change_lineage(client: TestClient, db_session):
    """Reports lock to DatasetVersion and surface overlaid CellValues + Change audit history."""
    _, project_id, headers = _setup_workspace(client)
    up = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("messy_sales.csv", io.BytesIO(_load_fixture("messy_sales.csv")), "text/csv")},
    )
    dataset_id = up.json()["dataset_id"]

    # Generate v1 report first
    r_v1 = client.post(
        f"/api/v1/datasets/{dataset_id}/analyze",
        headers=headers,
        json={"template": "executive_sales"},
    ).json()

    # Create DatasetVersion 2 with CellValue overlay fixing TX1008 invalid_amount -> $1,000.00
    v1 = db_session.query(DatasetVersion).filter_by(dataset_id=dataset_id, version_number=1).first()
    v2 = DatasetVersion(dataset_id=dataset_id, version_number=2, note="Fix invalid amount on TX1008")
    db_session.add(v2)
    db_session.flush()

    amt_col = db_session.query(ColumnModel).filter_by(dataset_id=dataset_id, name="Amount").first()
    tx1008_row = next(
        r for r in db_session.query(RowModel).filter_by(dataset_id=dataset_id).all()
        if r.raw_json.get("Transaction_ID") == "TX1008"
    )
    db_session.add(
        CellValue(
            dataset_version_id=v2.id,
            row_id=tx1008_row.id,
            column_id=amt_col.id,
            value="$1,000.00",
        )
    )
    db_session.add(
        Change(
            dataset_version_id=v2.id,
            row_id=tx1008_row.id,
            column_id=amt_col.id,
            before="invalid_amount",
            after="$1,000.00",
            source="human",
            reason="Verified invoice #1008",
            status="accepted",
        )
    )
    db_session.commit()

    # Create v2 report explicitly
    r_v2 = client.post(
        f"/api/v1/datasets/{dataset_id}/analyze",
        headers=headers,
        json={"version_id": v2.id, "template": "executive_sales"},
    ).json()

    # v1 stays locked to original 40,620.50; v2 reflects 41,620.50 with 15 valid rows
    v1_fetched = client.get(f"/api/v1/reports/{r_v1['id']}", headers=headers).json()
    assert v1_fetched["dataset_version_id"] == v1.id
    assert next(b for b in v1_fetched["computed_blocks"] if b["id"] == "blk_kpi_1")["data"]["value"] == 40620.5

    assert r_v2["version_number"] == 2
    kpi_v2 = next(b for b in r_v2["computed_blocks"] if b["id"] == "blk_kpi_1")["data"]
    assert kpi_v2["value"] == 41620.5
    assert kpi_v2["matching_rows"] == 15
    assert kpi_v2["excluded_rows"] == 0

    # Lineage on v2 KPI surfaces TX1008 raw vs effective values + Change record
    lineage_v2 = client.get(
        f"/api/v1/reports/{r_v2['id']}/blocks/blk_kpi_1/lineage?limit=50",
        headers=headers,
    ).json()
    tx1008_lin = next(r for r in lineage_v2["rows"] if r["raw_values"]["Transaction_ID"] == "TX1008")
    assert tx1008_lin["raw_values"]["Amount"] == "invalid_amount"
    assert tx1008_lin["effective_values"]["Amount"] == "$1,000.00"
    assert tx1008_lin["changed_columns"] == ["Amount"]
    assert len(tx1008_lin["changes"]) == 1
    assert tx1008_lin["changes"][0]["reason"] == "Verified invoice #1008"


def test_report_crud_recompute_xlsx_export_and_rbac(client: TestClient, db_session):
    """Verify CRUD, XLSX multi-sheet workbook export, formula guard, narrative endpoint, and RBAC."""
    ws_id, project_id, admin_headers = _setup_workspace(client)
    csv_payload = (
        b"Item,Category,Revenue\n"
        b"=SUM(A1),+Hardware,$500.00\n"
        b"-2+3,@Software,$1200.00\n"
    )
    up = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=admin_headers,
        files={"file": ("formula_test.csv", io.BytesIO(csv_payload), "text/csv")},
    )
    dataset_id = up.json()["dataset_id"]

    # Create custom report via project endpoint
    create_res = client.post(
        f"/api/v1/projects/{project_id}/reports",
        headers=admin_headers,
        json={"dataset_id": dataset_id, "title": "Board Brief", "template": "general_summary"},
    )
    assert create_res.status_code == 201
    rep_id = create_res.json()["id"]

    # Project report listing
    list_res = client.get(f"/api/v1/projects/{project_id}/reports", headers=admin_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1
    assert list_res.json()[0]["title"] == "Board Brief"

    # Patch title, status, and add custom KPI block
    layout = create_res.json()["layout_json"]
    layout["blocks"].append(
        {
            "id": "blk_custom_avg",
            "type": "kpi",
            "title": "Median Revenue",
            "width": "third",
            "config": {"metric_column": "Revenue", "aggregation": "median", "format_style": "currency"},
        }
    )
    patch_res = client.patch(
        f"/api/v1/reports/{rep_id}",
        headers=admin_headers,
        json={"title": "Updated Board Brief", "status": "in_review", "layout_json": layout},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "in_review"
    assert next(b for b in patch_res.json()["computed_blocks"] if b["id"] == "blk_custom_avg")["data"]["value"] == 850.0

    # Regenerate narrative
    nar_res = client.post(
        f"/api/v1/reports/{rep_id}/narrative",
        headers=admin_headers,
        json={},
    )
    assert nar_res.status_code == 200
    assert next(b for b in nar_res.json()["computed_blocks"] if b["type"] == "narrative")["data"]["verification"]["verified"] is True

    # Export XLSX workbook & inspect with openpyxl
    exp_res = client.get(f"/api/v1/reports/{rep_id}/export?format=xlsx", headers=admin_headers)
    assert exp_res.status_code == 200
    assert "spreadsheetml" in exp_res.headers["content-type"]
    wb = load_workbook(io.BytesIO(exp_res.content))
    assert wb.sheetnames == ["Executive Summary", "Metrics & Charts Data", "Source Data Audit"]
    ws_data = wb["Metrics & Charts Data"]
    ws_audit = wb["Source Data Audit"]
    # Formula injection guard prefixes '=', '+', '-', '@' across both Metrics and Audit sheets
    assert ws_audit.cell(row=2, column=2).value == "'=SUM(A1)"
    assert ws_audit.cell(row=2, column=3).value == "'+Hardware"
    assert ws_audit.cell(row=3, column=2).value == "'-2+3"
    assert ws_audit.cell(row=3, column=3).value == "'@Software"
    sheet2_labels = {
        ws_data.cell(row=r, column=1).value for r in range(1, ws_data.max_row + 1)
    }
    assert "'+Hardware" in sheet2_labels
    assert "'@Software" in sheet2_labels

    # Register stakeholder & contributor with assigned issue
    reg_stake = client.post(
        "/api/v1/auth/register",
        json={"email": "stake_rep@cleardata.io", "password": "Password123!", "name": "Stake"},
    )
    stake_headers = {"Authorization": f"Bearer {reg_stake.json()['access_token']}"}
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=admin_headers,
        json={"email": "stake_rep@cleardata.io", "role": "stakeholder"},
    )

    reg_contrib = client.post(
        "/api/v1/auth/register",
        json={"email": "contrib_rep@cleardata.io", "password": "Password123!", "name": "Contrib"},
    )
    contrib_id = reg_contrib.json()["user"]["id"]
    contrib_headers = {"Authorization": f"Bearer {reg_contrib.json()['access_token']}"}
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=admin_headers,
        json={"email": "contrib_rep@cleardata.io", "role": "contributor"},
    )
    db_session.add(
        Issue(
            dataset_id=dataset_id,
            type="clarification",
            severity="low",
            description="Check formula row",
            assignee_id=contrib_id,
            source="human",
        )
    )
    db_session.commit()

    # Stakeholder can read report, preview analysis, inspect lineage, compute, and export
    assert client.get(f"/api/v1/datasets/{dataset_id}/analysis", headers=stake_headers).status_code == 200
    assert client.get(f"/api/v1/reports/{rep_id}", headers=stake_headers).status_code == 200
    assert client.post(f"/api/v1/reports/{rep_id}/compute", headers=stake_headers).status_code == 200
    assert client.get(f"/api/v1/reports/{rep_id}/blocks/blk_kpi_1/lineage", headers=stake_headers).status_code == 200
    assert client.get(f"/api/v1/reports/{rep_id}/export?format=xlsx", headers=stake_headers).status_code == 200

    # Stakeholder cannot mutate, analyze, regenerate narrative, or delete
    assert client.post(f"/api/v1/datasets/{dataset_id}/analyze", headers=stake_headers, json={}).status_code == 403
    assert client.patch(f"/api/v1/reports/{rep_id}", headers=stake_headers, json={"title": "Nope"}).status_code == 403
    assert client.post(f"/api/v1/reports/{rep_id}/narrative", headers=stake_headers, json={}).status_code == 403
    assert client.delete(f"/api/v1/reports/{rep_id}", headers=stake_headers).status_code == 403

    # Contributor blocked from stakeholder reporting endpoints even with assigned issue
    assert client.get(f"/api/v1/datasets/{dataset_id}/analysis", headers=contrib_headers).status_code == 403
    assert client.get(f"/api/v1/projects/{project_id}/reports", headers=contrib_headers).status_code == 403
    assert client.get(f"/api/v1/reports/{rep_id}", headers=contrib_headers).status_code == 403

    # 404s
    assert client.get("/api/v1/reports/missing-rep", headers=admin_headers).status_code == 404
    assert client.get(f"/api/v1/reports/{rep_id}/blocks/missing-blk/lineage", headers=admin_headers).status_code == 404

    # Delete report
    del_res = client.delete(f"/api/v1/reports/{rep_id}", headers=admin_headers)
    assert del_res.status_code == 204
    assert client.get(f"/api/v1/reports/{rep_id}", headers=admin_headers).status_code == 404

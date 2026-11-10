import io
from pathlib import Path

from fastapi.testclient import TestClient

from app.services.profiling import profile_column_values


def _setup_workspace_and_project(client: TestClient) -> tuple[str, dict]:
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "profiler@cleardata.io",
            "password": "Password123!",
            "name": "Pat Profiler",
            "workspace_name": "Profiling Workspace",
        },
    )
    assert res.status_code == 201, res.text
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    ws_id = client.get("/api/v1/workspaces", headers=headers).json()[0]["id"]
    proj_res = client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        headers=headers,
        json={"name": "Profiling Project"},
    )
    assert proj_res.status_code == 201, proj_res.text
    return proj_res.json()["id"], headers


def _load_fixture(name: str) -> bytes:
    path = Path("fixtures") / name
    if not path.exists():
        path = Path("../../fixtures") / name
    return path.read_bytes()


def test_profile_messy_sales_fixture(client: TestClient):
    """Upload messy_sales.csv and verify chained profiling via GET /datasets/{id}/columns."""
    project_id, headers = _setup_workspace_and_project(client)

    upload_res = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("messy_sales.csv", io.BytesIO(_load_fixture("messy_sales.csv")), "text/csv")},
    )
    assert upload_res.status_code == 202, upload_res.text
    dataset_id = upload_res.json()["dataset_id"]

    # Check dataset-level stats
    ds_res = client.get(f"/api/v1/datasets/{dataset_id}", headers=headers)
    assert ds_res.status_code == 200
    ds_data = ds_res.json()
    assert ds_data["stats_json"] is not None
    assert ds_data["stats_json"]["row_count"] == 15
    assert ds_data["stats_json"]["column_count"] == 7
    assert ds_data["stats_json"]["null_cells"] == 3  # 1 Date N/A + 1 Customer_Name empty + 1 Status empty
    assert ds_data["stats_json"]["null_like_cells"] == 1
    assert ds_data["stats_json"]["completeness_pct"] == 97.14

    # Check column profiles
    cols_res = client.get(f"/api/v1/datasets/{dataset_id}/columns", headers=headers)
    assert cols_res.status_code == 200
    cols = {c["name"]: c for c in cols_res.json()}

    assert cols["Transaction_ID"]["inferred_type"] == "identifier"
    assert cols["Transaction_ID"]["semantic_hint"] == "identifier"

    # Mixed date formats + N/A null-like value
    date_col = cols["Date"]
    assert date_col["inferred_type"] == "date"
    assert date_col["semantic_hint"] == "date"
    assert date_col["stats_json"]["null_count"] == 1
    assert date_col["stats_json"]["null_like_count"] == 1
    assert date_col["stats_json"]["empty_count"] == 0
    date_formats = date_col["stats_json"]["date"]["formats"]
    assert len(date_formats) >= 5
    assert "%Y-%m-%d" in date_formats
    assert "%m/%d/%Y" in date_formats
    assert "%d-%b-%Y" in date_formats
    assert date_col["stats_json"]["date"]["min"] == "2024-01-15"
    assert date_col["stats_json"]["date"]["max"] == "2024-01-28"

    # Currency column with mixed formats, invalid_amount, and whitespace
    amt_col = cols["Amount"]
    assert amt_col["inferred_type"] == "currency"
    assert amt_col["semantic_hint"] == "amount"
    assert amt_col["stats_json"]["numeric"]["valid_count"] == 14
    assert amt_col["stats_json"]["numeric"]["invalid_count"] == 1
    assert amt_col["stats_json"]["numeric"]["min"] == 0.0
    assert amt_col["stats_json"]["numeric"]["max"] == 12450.0
    assert amt_col["stats_json"]["text"]["whitespace_count"] >= 1

    # Region & Customer_Name & Status
    assert cols["Region"]["inferred_type"] == "category"
    assert cols["Region"]["semantic_hint"] == "region"
    assert cols["Customer_Name"]["stats_json"]["null_count"] == 1
    assert cols["Customer_Name"]["stats_json"]["empty_count"] == 1
    assert cols["Customer_Name"]["semantic_hint"] == "customer_name"
    assert cols["Status"]["stats_json"]["null_count"] == 1


def test_profile_survey_results_fixture(client: TestClient):
    """Verify survey_results.csv profiling: datetime, mixed scales, and free_text."""
    project_id, headers = _setup_workspace_and_project(client)

    upload_res = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("survey_results.csv", io.BytesIO(_load_fixture("survey_results.csv")), "text/csv")},
    )
    assert upload_res.status_code == 202
    dataset_id = upload_res.json()["dataset_id"]

    cols = {
        c["name"]: c
        for c in client.get(f"/api/v1/datasets/{dataset_id}/columns", headers=headers).json()
    }

    assert cols["Respondent_ID"]["inferred_type"] == "identifier"
    assert cols["Submission_Time"]["inferred_type"] == "datetime"
    assert cols["Department"]["inferred_type"] == "category"
    assert cols["Department"]["stats_json"]["null_count"] == 1
    assert cols["Satisfaction_Score"]["inferred_type"] == "mixed"
    assert cols["Feedback_Text"]["inferred_type"] == "free_text"


def test_profile_inventory_xlsx_fixture(client: TestClient):
    """Verify inventory.xlsx multi-sheet profiling."""
    project_id, headers = _setup_workspace_and_project(client)

    upload_res = client.post(
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
    assert upload_res.status_code == 202
    datasets = upload_res.json()["datasets"]
    assert len(datasets) == 2

    north = next(d for d in datasets if "Warehouse_North" in d["name"])
    cols = {
        c["name"]: c
        for c in client.get(f"/api/v1/datasets/{north['dataset_id']}/columns", headers=headers).json()
    }

    assert cols["SKU"]["inferred_type"] == "identifier"
    assert cols["Quantity"]["inferred_type"] == "integer"
    assert cols["Quantity"]["stats_json"]["numeric"]["min"] == 50.0
    assert cols["Quantity"]["stats_json"]["numeric"]["max"] == 2500.0
    assert cols["Quantity"]["stats_json"]["numeric"]["sum"] == 4130.0


def test_profile_ambiguous_dates_not_silently_resolved():
    """Dates like 03/04/2025 must record ambiguity instead of picking MM/DD or DD/MM."""
    profile = profile_column_values("order_date", ["03/04/2025", "05/06/2025", "01/02/2025"])
    assert profile["inferred_type"] == "date"
    date_stats = profile["stats_json"]["date"]
    assert date_stats["ambiguous_count"] == 3
    assert date_stats["min"] is None
    assert date_stats["max"] is None
    assert any("ambiguous" in fmt for fmt in date_stats["formats"])


def test_profile_identifier_zip_and_phone_no_numeric_false_positive():
    """ZIP codes with leading zeros and phone numbers must not be classified as integers."""
    zip_profile = profile_column_values("postal_code", ["02138", "07030", "10001", "01803"])
    assert zip_profile["inferred_type"] == "identifier"
    assert zip_profile["stats_json"]["numeric"] is None

    phone_profile = profile_column_values("contact_phone", ["+1 (555) 123-4567", "555-987-6543", "415.555.0199"])
    assert phone_profile["inferred_type"] == "phone"
    assert phone_profile["semantic_hint"] == "phone"


def test_profile_null_like_tokens_and_case_distribution():
    """All null-like variants are counted separately and casing stats are accurate."""
    profile = profile_column_values(
        "status",
        ["ACTIVE", "active", "Active", "Pending Review", "", "   ", "N/A", "NA", "null", "none", "-", "#N/A"],
    )
    stats = profile["stats_json"]
    assert stats["total_count"] == 12
    assert stats["empty_count"] == 2
    assert stats["null_like_count"] == 6
    assert stats["null_count"] == 8
    assert stats["non_null_count"] == 4
    case_dist = stats["text"]["case_distribution"]
    assert case_dist["upper"] == 1
    assert case_dist["lower"] == 1
    assert case_dist["title"] == 2


def test_profile_endpoint_rbac_and_manual_reprofile(client: TestClient):
    """Non-members get 403; missing datasets get 404; steward can manually re-profile."""
    project_id, admin_headers = _setup_workspace_and_project(client)
    upload_res = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=admin_headers,
        files={"file": ("small.csv", io.BytesIO(b"A,B\n1,2\n3,4"), "text/csv")},
    )
    dataset_id = upload_res.json()["dataset_id"]

    # Register outsider
    out_res = client.post(
        "/api/v1/auth/register",
        json={"email": "outsider@cleardata.io", "password": "Password123!", "name": "Outsider"},
    )
    outsider_headers = {"Authorization": f"Bearer {out_res.json()['access_token']}"}

    assert client.get(f"/api/v1/datasets/{dataset_id}/columns", headers=outsider_headers).status_code == 403
    assert client.get("/api/v1/datasets/missing-id/columns", headers=admin_headers).status_code == 404

    reprofile_res = client.post(f"/api/v1/datasets/{dataset_id}/profile", headers=admin_headers)
    assert reprofile_res.status_code == 202
    assert reprofile_res.json()["status"] == "finished"

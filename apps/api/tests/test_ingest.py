import io
from pathlib import Path

from fastapi.testclient import TestClient

from app.models.entities import ColumnModel, Dataset, DatasetVersion, RowModel


def create_admin_and_project(client: TestClient) -> tuple[str, str, dict]:
    """Helper creating an admin user, workspace, and project."""
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "steward@cleardata.io",
            "password": "Password123!",
            "name": "Data Steward",
            "workspace_name": "Analytics Workspace",
        },
    )
    assert res.status_code == 201, res.text
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ws_res = client.get("/api/v1/workspaces", headers=headers)
    assert ws_res.status_code == 200
    workspace_id = ws_res.json()[0]["id"]

    proj_res = client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        headers=headers,
        json={"name": "Data Ingest Test Project"},
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    return workspace_id, project_id, headers


def test_upload_messy_sales_fixture(client: TestClient, db_session):
    """Test uploading messy_sales.csv: verifies rows, columns, versioning, and byte fidelity."""
    _, project_id, headers = create_admin_and_project(client)

    fixture_path = Path("fixtures/messy_sales.csv")
    if not fixture_path.exists():
        fixture_path = Path("../../fixtures/messy_sales.csv")
    raw_content = fixture_path.read_bytes()

    response = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("messy_sales.csv", io.BytesIO(raw_content), "text/csv")},
    )
    assert response.status_code == 202, response.text
    data = response.json()
    assert "dataset_id" in data
    assert "job_id" in data
    dataset_id = data["dataset_id"]

    # Verify dataset in database
    dataset = db_session.query(Dataset).filter_by(id=dataset_id).first()
    assert dataset is not None
    assert dataset.status == "ready"
    assert dataset.error_message is None

    # Verify byte-identical preservation of raw file on disk
    stored_bytes = Path(dataset.raw_file_path).read_bytes()
    assert stored_bytes == raw_content

    # Verify columns (7 columns)
    columns = (
        db_session.query(ColumnModel)
        .filter_by(dataset_id=dataset_id)
        .order_by(ColumnModel.position)
        .all()
    )
    col_names = [c.name for c in columns]
    assert col_names == [
        "Transaction_ID",
        "Customer_Name",
        "Date",
        "Amount",
        "Region",
        "Product_Category",
        "Status",
    ]

    # Verify rows (15 rows)
    rows = (
        db_session.query(RowModel)
        .filter_by(dataset_id=dataset_id)
        .order_by(RowModel.row_index)
        .all()
    )
    assert len(rows) == 15
    assert rows[0].raw_json["Transaction_ID"] == "TX1001"
    assert rows[2].raw_json["Amount"] == "3400 USD"
    assert rows[7].raw_json["Amount"] == "invalid_amount"

    # Verify version 1 note
    versions = db_session.query(DatasetVersion).filter_by(dataset_id=dataset_id).all()
    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert versions[0].note == "Original import"

    # Verify job polling endpoint
    job_res = client.get(f"/api/v1/jobs/{data['job_id']}")
    assert job_res.status_code == 200
    assert job_res.json()["status"] == "finished"


def test_upload_survey_results_fixture(client: TestClient, db_session):
    """Test uploading survey_results.csv: 10 rows and 6 columns."""
    _, project_id, headers = create_admin_and_project(client)

    fixture_path = Path("fixtures/survey_results.csv")
    if not fixture_path.exists():
        fixture_path = Path("../../fixtures/survey_results.csv")
    raw_content = fixture_path.read_bytes()

    response = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("survey_results.csv", io.BytesIO(raw_content), "text/csv")},
    )
    assert response.status_code == 202
    dataset_id = response.json()["dataset_id"]

    dataset = db_session.query(Dataset).filter_by(id=dataset_id).first()
    assert dataset.status == "ready"

    columns = db_session.query(ColumnModel).filter_by(dataset_id=dataset_id).all()
    assert len(columns) == 6
    rows = db_session.query(RowModel).filter_by(dataset_id=dataset_id).all()
    assert len(rows) == 10


def test_upload_inventory_xlsx_multisheet_fixture(client: TestClient, db_session):
    """Test uploading inventory.xlsx: creates one dataset per sheet and handles title banners."""
    _, project_id, headers = create_admin_and_project(client)

    fixture_path = Path("fixtures/inventory.xlsx")
    if not fixture_path.exists():
        fixture_path = Path("../../fixtures/inventory.xlsx")
    raw_content = fixture_path.read_bytes()

    response = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={
            "file": (
                "inventory.xlsx",
                io.BytesIO(raw_content),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert data["datasets"] is not None
    assert len(data["datasets"]) == 2

    # Check sheet 1: Warehouse_North
    north_summary = next(d for d in data["datasets"] if "Warehouse_North" in d["name"])
    ds_north = db_session.query(Dataset).filter_by(id=north_summary["dataset_id"]).first()
    assert ds_north.status == "ready"
    cols_north = db_session.query(ColumnModel).filter_by(dataset_id=ds_north.id).all()
    assert [c.name for c in sorted(cols_north, key=lambda x: x.position)] == [
        "SKU",
        "Item Description",
        "Category",
        "Quantity",
        "Weight",
    ]
    rows_north = db_session.query(RowModel).filter_by(dataset_id=ds_north.id).all()
    assert len(rows_north) == 5

    # Check sheet 2: Warehouse_South
    south_summary = next(d for d in data["datasets"] if "Warehouse_South" in d["name"])
    ds_south = db_session.query(Dataset).filter_by(id=south_summary["dataset_id"]).first()
    assert ds_south.status == "ready"
    rows_south = db_session.query(RowModel).filter_by(dataset_id=ds_south.id).all()
    assert len(rows_south) == 4


def test_upload_utf8_bom_and_semicolon(client: TestClient, db_session):
    """Test encoding with UTF-8 BOM and delimiter detection with semicolon."""
    _, project_id, headers = create_admin_and_project(client)

    # Content with BOM and semicolon delimiter
    bom_content = "Product;Category;Cost\nLaptop;Electronics;1200\nMouse;Electronics;25".encode(
        "utf-8-sig"
    )

    response = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("bom_test.csv", io.BytesIO(bom_content), "text/csv")},
    )
    assert response.status_code == 202
    dataset_id = response.json()["dataset_id"]

    columns = (
        db_session.query(ColumnModel)
        .filter_by(dataset_id=dataset_id)
        .order_by(ColumnModel.position)
        .all()
    )
    assert [c.name for c in columns] == ["Product", "Category", "Cost"]
    assert "\ufeff" not in columns[0].name


def test_upload_duplicate_headers(client: TestClient, db_session):
    """Test duplicate header names are suffix-numbered (Name, Name_2, Name_3)."""
    _, project_id, headers = create_admin_and_project(client)

    content = b"Name,Score,Name,Name\nAlice,90,Eng,Extra\nBob,85,Sales,Extra2"

    response = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("dupe_headers.csv", io.BytesIO(content), "text/csv")},
    )
    assert response.status_code == 202
    dataset_id = response.json()["dataset_id"]

    columns = (
        db_session.query(ColumnModel)
        .filter_by(dataset_id=dataset_id)
        .order_by(ColumnModel.position)
        .all()
    )
    assert [c.name for c in columns] == ["Name", "Score", "Name_2", "Name_3"]


def test_upload_unsupported_file_extension(client: TestClient):
    """Test uploading an unsupported extension returns standard 400 error format."""
    _, project_id, headers = create_admin_and_project(client)

    response = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("payload.exe", io.BytesIO(b"bad content"), "application/octet-stream")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_400"
    assert "Unsupported file extension" in data["error"]["message"]


def test_upload_rbac_contributor_forbidden(client: TestClient):
    """Test that contributors cannot upload datasets (steward/admin only)."""
    workspace_id, project_id, admin_headers = create_admin_and_project(client)

    # Register contributor
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "contributor@cleardata.io",
            "password": "Password123!",
            "name": "Carl Contributor",
        },
    )
    contrib_token = reg_res.json()["access_token"]
    contrib_headers = {"Authorization": f"Bearer {contrib_token}"}

    # Add as contributor
    client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers=admin_headers,
        json={"email": "contributor@cleardata.io", "role": "contributor"},
    )

    # Contributor attempts upload -> 403 Forbidden
    response = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=contrib_headers,
        files={"file": ("sample.csv", io.BytesIO(b"A,B\n1,2"), "text/csv")},
    )
    assert response.status_code == 403
    assert "Operation requires one of roles" in response.json()["error"]["message"]

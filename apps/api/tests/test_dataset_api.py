import io
from pathlib import Path

from fastapi.testclient import TestClient

from app.models.entities import Issue


def _setup_workspace(client: TestClient):
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "api_admin@cleardata.io",
            "password": "Password123!",
            "name": "Api Admin",
            "workspace_name": "Dataset API Workspace",
        },
    )
    assert res.status_code == 201
    admin_headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    ws_id = client.get("/api/v1/workspaces", headers=admin_headers).json()[0]["id"]
    proj_res = client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        headers=admin_headers,
        json={"name": "Dataset API Project"},
    )
    assert proj_res.status_code == 201
    return ws_id, proj_res.json()["id"], admin_headers


def _load_fixture(name: str) -> bytes:
    p = Path("fixtures") / name
    if not p.exists():
        p = Path("../../fixtures") / name
    return p.read_bytes()


def test_dataset_rows_cursor_pagination_sort_filter_and_issue_focus(client: TestClient):
    """Verify cursor pagination boundaries, numeric sorting, contains filter, and issue row filtering."""
    _, project_id, headers = _setup_workspace(client)
    up = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        files={"file": ("messy_sales.csv", io.BytesIO(_load_fixture("messy_sales.csv")), "text/csv")},
    )
    assert up.status_code == 202
    dataset_id = up.json()["dataset_id"]

    # Check project & dataset metadata endpoints
    proj_res = client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert proj_res.status_code == 200
    assert proj_res.json()["name"] == "Dataset API Project"

    list_res = client.get(f"/api/v1/projects/{project_id}/datasets", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1
    assert list_res.json()[0]["issue_counts"]["total"] >= 1

    # Paginate with limit=6 across 15 rows -> 6, 6, 3
    page1 = client.get(f"/api/v1/datasets/{dataset_id}/rows?limit=6", headers=headers).json()
    assert len(page1["items"]) == 6
    assert page1["total_count"] == 15
    assert page1["has_more"] is True
    assert page1["next_cursor"] == "5"

    page2 = client.get(
        f"/api/v1/datasets/{dataset_id}/rows?limit=6&cursor={page1['next_cursor']}",
        headers=headers,
    ).json()
    assert len(page2["items"]) == 6
    assert page2["has_more"] is True
    assert page2["items"][0]["row_index"] == 6

    page3 = client.get(
        f"/api/v1/datasets/{dataset_id}/rows?limit=6&cursor={page2['next_cursor']}",
        headers=headers,
    ).json()
    assert len(page3["items"]) == 3
    assert page3["has_more"] is False
    assert page3["next_cursor"] is None

    # Boundary validation: limit > 500 -> 422, limit < 1 -> 422, invalid cursor -> 400
    assert client.get(f"/api/v1/datasets/{dataset_id}/rows?limit=501", headers=headers).status_code == 422
    assert client.get(f"/api/v1/datasets/{dataset_id}/rows?limit=0", headers=headers).status_code == 422
    assert client.get(f"/api/v1/datasets/{dataset_id}/rows?cursor=abc", headers=headers).status_code == 400

    # Numeric-aware sorting on Amount descending (should put $12,450.00 first, invalid_amount at the end)
    sorted_desc = client.get(
        f"/api/v1/datasets/{dataset_id}/rows?sort=Amount&sort_dir=desc&limit=5",
        headers=headers,
    ).json()
    assert sorted_desc["items"][0]["values"]["Transaction_ID"] == "TX1015"
    assert sorted_desc["items"][1]["values"]["Transaction_ID"] == "TX1012"

    # Contains filter
    filtered = client.get(
        f"/api/v1/datasets/{dataset_id}/rows?filter=acme",
        headers=headers,
    ).json()
    assert filtered["total_count"] == 3
    assert all("acme" in r["values"]["Customer_Name"].lower() for r in filtered["items"])

    # Issue focus filter
    issues = client.get(f"/api/v1/datasets/{dataset_id}/issues?type=type_violation", headers=headers).json()
    assert len(issues) == 1
    tv_rows = client.get(
        f"/api/v1/datasets/{dataset_id}/rows?issue_id={issues[0]['id']}",
        headers=headers,
    ).json()
    assert tv_rows["total_count"] == 1
    assert tv_rows["items"][0]["values"]["Amount"] == "invalid_amount"


def test_dataset_api_permissions_contributor_stub_and_404s(client: TestClient, db_session):
    """Enforce workspace membership, contributor assignment stub, and 404 errors."""
    ws_id, project_id, admin_headers = _setup_workspace(client)
    up = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=admin_headers,
        files={"file": ("data.csv", io.BytesIO(b"A,B\n1,x\n2,y"), "text/csv")},
    )
    dataset_id = up.json()["dataset_id"]

    # Register contributor and add to workspace
    reg_contrib = client.post(
        "/api/v1/auth/register",
        json={"email": "contrib@cleardata.io", "password": "Password123!", "name": "Carl"},
    )
    contrib_id = reg_contrib.json()["user"]["id"]
    contrib_headers = {"Authorization": f"Bearer {reg_contrib.json()['access_token']}"}
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=admin_headers,
        json={"email": "contrib@cleardata.io", "role": "contributor"},
    )

    # Register stakeholder and add to workspace
    reg_stake = client.post(
        "/api/v1/auth/register",
        json={"email": "stake@cleardata.io", "password": "Password123!", "name": "Sally"},
    )
    stake_headers = {"Authorization": f"Bearer {reg_stake.json()['access_token']}"}
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=admin_headers,
        json={"email": "stake@cleardata.io", "role": "stakeholder"},
    )

    # Stakeholder sees dataset & rows
    assert client.get(f"/api/v1/datasets/{dataset_id}", headers=stake_headers).status_code == 200
    assert client.get(f"/api/v1/datasets/{dataset_id}/rows", headers=stake_headers).status_code == 200

    # Contributor sees 0 datasets in project list and 403 on unassigned dataset
    assert client.get(f"/api/v1/projects/{project_id}/datasets", headers=contrib_headers).json() == []
    assert client.get(f"/api/v1/datasets/{dataset_id}", headers=contrib_headers).status_code == 403
    assert client.get(f"/api/v1/datasets/{dataset_id}/rows", headers=contrib_headers).status_code == 403

    # Assign an issue on the dataset to the contributor -> contributor can now inspect it
    issue = Issue(
        dataset_id=dataset_id,
        type="clarification",
        severity="medium",
        description="Verify row",
        assignee_id=contrib_id,
        source="human",
    )
    db_session.add(issue)
    db_session.commit()

    assert len(client.get(f"/api/v1/projects/{project_id}/datasets", headers=contrib_headers).json()) == 1
    assert client.get(f"/api/v1/datasets/{dataset_id}/rows", headers=contrib_headers).status_code == 200

    # 404s
    assert client.get("/api/v1/datasets/does-not-exist/rows", headers=admin_headers).status_code == 404
    assert client.get("/api/v1/projects/does-not-exist", headers=admin_headers).status_code == 404
    assert client.get("/api/v1/projects/does-not-exist/datasets", headers=admin_headers).status_code == 404

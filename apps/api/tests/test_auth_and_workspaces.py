import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.database import Base, get_db


@pytest.fixture
def client_and_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_auth_and_rbac_flow(client_and_db):
    client = client_and_db

    # 1. Register first user (Admin)
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@cleardata.io",
            "password": "Password123!",
            "name": "Alice Admin",
            "workspace_name": "Acme Corp Data",
        },
    )
    assert reg_resp.status_code == 201, reg_resp.text
    admin_data = reg_resp.json()
    assert "access_token" in admin_data
    assert admin_data["user"]["email"] == "admin@cleardata.io"
    admin_token = admin_data["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Login with valid credentials
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@cleardata.io", "password": "Password123!"},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()

    # 3. Login with wrong password -> 401
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@cleardata.io", "password": "WrongPassword"},
    )
    assert bad_login.status_code == 401
    assert "error" in bad_login.json()

    # 4. Check /me endpoint
    me_resp = client.get("/api/v1/auth/me", headers=admin_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["name"] == "Alice Admin"

    # 5. List workspaces for Alice Admin
    ws_list_resp = client.get("/api/v1/workspaces", headers=admin_headers)
    assert ws_list_resp.status_code == 200
    workspaces = ws_list_resp.json()
    assert len(workspaces) == 1
    workspace_id = workspaces[0]["id"]
    assert workspaces[0]["name"] == "Acme Corp Data"
    assert workspaces[0]["role"] == "admin"

    # 6. Register a second user (Bob)
    reg_bob = client.post(
        "/api/v1/auth/register",
        json={
            "email": "bob@cleardata.io",
            "password": "Password123!",
            "name": "Bob Contributor",
        },
    )
    assert reg_bob.status_code == 201
    bob_token = reg_bob.json()["access_token"]
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    # 7. Bob attempts to view Alice's workspace before being added -> 403 Forbidden
    forbidden_resp = client.get(f"/api/v1/workspaces/{workspace_id}", headers=bob_headers)
    assert forbidden_resp.status_code == 403

    # 8. Alice (admin) adds Bob as contributor to Acme Corp Data
    add_member_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers=admin_headers,
        json={"email": "bob@cleardata.io", "role": "contributor"},
    )
    assert add_member_resp.status_code == 201
    assert add_member_resp.json()["role"] == "contributor"

    # 9. Bob now has access to the workspace
    bob_ws_resp = client.get(f"/api/v1/workspaces/{workspace_id}", headers=bob_headers)
    assert bob_ws_resp.status_code == 200
    assert bob_ws_resp.json()["name"] == "Acme Corp Data"

    # 10. Bob (contributor) tries to create a project in Acme Corp Data -> 403 Forbidden
    bob_create_proj = client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        headers=bob_headers,
        json={"name": "Unauthorized Project"},
    )
    assert bob_create_proj.status_code == 403

    # 11. Alice (admin) creates a project -> 201 Created
    proj_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        headers=admin_headers,
        json={"name": "Q3 Sales Analytics"},
    )
    assert proj_resp.status_code == 201
    assert proj_resp.json()["name"] == "Q3 Sales Analytics"

    # 12. Both Alice and Bob can view project list
    proj_list_resp = client.get(f"/api/v1/workspaces/{workspace_id}/projects", headers=bob_headers)
    assert proj_list_resp.status_code == 200
    assert len(proj_list_resp.json()) == 1

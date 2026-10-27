from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.entities import Membership, Project, User, Workspace
from app.routers.deps import get_current_user, require_workspace_role
from app.schemas.auth import UserResponse
from app.schemas.workspace import (
    AddMemberRequest,
    MembershipResponse,
    ProjectCreateRequest,
    ProjectResponse,
    WorkspaceCreateRequest,
    WorkspaceResponse,
)

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.get("", response_model=list[WorkspaceResponse])
def list_user_workspaces(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """List all workspaces that current user is a member of."""
    memberships = db.query(Membership).filter(Membership.user_id == current_user.id).all()
    results = []
    for m in memberships:
        ws = m.workspace
        results.append(
            WorkspaceResponse(
                id=ws.id,
                name=ws.name,
                role=m.role,
                created_at=ws.created_at,
                updated_at=ws.updated_at,
            )
        )
    return results


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a new workspace and make current user the admin."""
    workspace = Workspace(name=payload.name.strip())
    db.add(workspace)
    db.flush()

    membership = Membership(
        user_id=current_user.id,
        workspace_id=workspace.id,
        role="admin",
    )
    db.add(membership)
    db.commit()
    db.refresh(workspace)

    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        role="admin",
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    dependencies=[Depends(require_workspace_role(["admin", "steward", "stakeholder", "contributor"]))],
)
def get_workspace(
    workspace_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get single workspace details for an authorized member."""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    membership = (
        db.query(Membership)
        .filter(Membership.workspace_id == workspace_id, Membership.user_id == current_user.id)
        .first()
    )

    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        role=membership.role if membership else None,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


@router.get(
    "/{workspace_id}/members",
    response_model=list[MembershipResponse],
    dependencies=[Depends(require_workspace_role(["admin", "steward", "stakeholder", "contributor"]))],
)
def list_workspace_members(
    workspace_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    """List members of a workspace."""
    memberships = db.query(Membership).filter(Membership.workspace_id == workspace_id).all()
    results = []
    for m in memberships:
        results.append(
            MembershipResponse(
                id=m.id,
                user_id=m.user_id,
                workspace_id=m.workspace_id,
                role=m.role,
                user=UserResponse.model_validate(m.user),
                created_at=m.created_at,
            )
        )
    return results


@router.post(
    "/{workspace_id}/members",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_role(["admin"]))],
)
def add_workspace_member(
    workspace_id: str,
    payload: AddMemberRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """Add a member to workspace by email (requires admin role)."""
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email '{payload.email}' not found. They must register first.",
        )

    existing = (
        db.query(Membership)
        .filter(Membership.workspace_id == workspace_id, Membership.user_id == user.id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this workspace",
        )

    membership = Membership(
        workspace_id=workspace_id,
        user_id=user.id,
        role=payload.role,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)

    return MembershipResponse(
        id=membership.id,
        user_id=membership.user_id,
        workspace_id=membership.workspace_id,
        role=membership.role,
        user=UserResponse.model_validate(user),
        created_at=membership.created_at,
    )


@router.get(
    "/{workspace_id}/projects",
    response_model=list[ProjectResponse],
    dependencies=[Depends(require_workspace_role(["admin", "steward", "stakeholder", "contributor"]))],
)
def list_workspace_projects(
    workspace_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    """List projects inside a workspace."""
    projects = (
        db.query(Project)
        .filter(Project.workspace_id == workspace_id)
        .order_by(Project.created_at.desc())
        .all()
    )
    return [ProjectResponse.model_validate(p) for p in projects]


@router.post(
    "/{workspace_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_role(["admin", "steward"]))],
)
def create_workspace_project(
    workspace_id: str,
    payload: ProjectCreateRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """Create a new project in a workspace (requires admin or steward role)."""
    project = Project(
        workspace_id=workspace_id,
        name=payload.name.strip(),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectResponse.model_validate(project)

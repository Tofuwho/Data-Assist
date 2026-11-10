from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.entities import Dataset, Issue, Membership, Project, User
from app.services.auth import decode_access_token


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> User:
    """Extract and authenticate current user from Bearer JWT token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_workspace_role(allowed_roles: list[str]) -> Callable:
    """Dependency factory checking that current user has one of allowed roles in workspace."""

    async def role_checker(
        workspace_id: Annotated[str, Path(description="Workspace ID")],
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> Membership:
        membership = (
            db.query(Membership)
            .filter(
                Membership.workspace_id == workspace_id,
                Membership.user_id == current_user.id,
            )
            .first()
        )

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this workspace",
            )

        if membership.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of roles: {', '.join(allowed_roles)}. Your role is '{membership.role}'",
            )

        return membership

    return role_checker


def require_project_role(allowed_roles: list[str]) -> Callable:
    """Dependency checking that current user has one of allowed roles in the workspace of the project."""

    async def project_role_checker(
        project_id: Annotated[str, Path(description="Project ID")],
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> tuple[Project, Membership]:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found",
            )

        membership = (
            db.query(Membership)
            .filter(
                Membership.workspace_id == project.workspace_id,
                Membership.user_id == current_user.id,
            )
            .first()
        )

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this project's workspace",
            )

        if membership.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of roles: {', '.join(allowed_roles)}. Your role is '{membership.role}'",
            )

        return project, membership

    return project_role_checker


def require_dataset_role(allowed_roles: list[str]) -> Callable:
    """Dependency checking that current user has one of allowed roles in the workspace of the dataset."""

    async def dataset_role_checker(
        dataset_id: Annotated[str, Path(description="Dataset ID")],
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> tuple[Dataset, Project, Membership]:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset {dataset_id} not found",
            )

        project = db.query(Project).filter(Project.id == dataset.project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project for dataset {dataset_id} not found",
            )

        membership = (
            db.query(Membership)
            .filter(
                Membership.workspace_id == project.workspace_id,
                Membership.user_id == current_user.id,
            )
            .first()
        )

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this dataset's workspace",
            )

        if membership.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of roles: {', '.join(allowed_roles)}. Your role is '{membership.role}'",
            )

        # Contributor stub check (full dataset/task assignment arrives in Phase 4):
        # contributors may only inspect datasets where at least one issue is assigned to them.
        if membership.role == "contributor":
            assigned = (
                db.query(Issue.id)
                .filter(Issue.dataset_id == dataset.id, Issue.assignee_id == current_user.id)
                .first()
            )
            if not assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Contributors may only access datasets assigned to them",
                )

        return dataset, project, membership

    return dataset_role_checker

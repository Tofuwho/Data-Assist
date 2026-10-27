from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.entities import Membership, User, Workspace
from app.routers.deps import get_current_user
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: UserRegisterRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """Register a new user, create their default workspace as admin, and return auth token."""
    existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists",
        )

    # 1. Create user
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
    )
    db.add(user)
    db.flush()

    # 2. Create default workspace and assign admin membership
    ws_name = (payload.workspace_name or f"{user.name}'s Workspace").strip()
    workspace = Workspace(name=ws_name)
    db.add(workspace)
    db.flush()

    membership = Membership(
        user_id=user.id,
        workspace_id=workspace.id,
        role="admin",
    )
    db.add(membership)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login_user(
    payload: UserLoginRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """Authenticate with email and password and return access token."""
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(data={"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    """Return the profile of the authenticated user."""
    return UserResponse.model_validate(current_user)

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import UserResponse


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    role: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MembershipResponse(BaseModel):
    id: str
    user_id: str
    workspace_id: str
    role: str
    user: UserResponse | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AddMemberRequest(BaseModel):
    email: str
    role: str = Field(default="contributor", pattern="^(admin|steward|stakeholder|contributor)$")


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ProjectResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

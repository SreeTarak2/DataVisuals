"""
Workspace Schemas (Core)
------------------------
These schemas define:
- Workspace (the tenant boundary)
- Workspace membership (owner/member roles)
- Workspace settings

Every other entity (datasets, metrics, knowledge, investigations)
scopes to workspace_id.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime


# ---------------------------------------------------
# Base Config
# ---------------------------------------------------
class _Config:
    from_attributes = True
    extra = "forbid"
    use_enum_values = True


# ---------------------------------------------------
# WORKSPACE SETTINGS
# ---------------------------------------------------
class WorkspaceSettings(BaseModel):
    """Configurable workspace preferences."""

    default_date_range: str = "last_30_days"
    preferred_domain: Optional[str] = None
    timezone: str = "UTC"
    currency: str = "USD"

    class Config(_Config):
        pass


# ---------------------------------------------------
# WORKSPACE (Primary Entity)
# ---------------------------------------------------
class WorkspaceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

    class Config(_Config):
        pass


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    settings: Optional[WorkspaceSettings] = None

    class Config(_Config):
        pass


class Workspace(WorkspaceBase):
    id: str
    owner_id: str
    settings: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    is_personal: bool = False

    member_count: int = 0
    dataset_count: int = 0

    created_at: datetime
    updated_at: datetime

    class Config(_Config):
        pass


# ---------------------------------------------------
# WORKSPACE MEMBERSHIP
# ---------------------------------------------------
class WorkspaceMemberBase(BaseModel):
    role: Literal["owner", "admin", "member", "viewer"] = "member"

    class Config(_Config):
        pass


class WorkspaceMemberCreate(WorkspaceMemberBase):
    user_id: str


class WorkspaceMemberUpdate(BaseModel):
    """Used when updating an existing member's role."""
    role: Literal["admin", "member", "viewer"]

    class Config(_Config):
        pass


class WorkspaceMember(WorkspaceMemberBase):
    id: str
    workspace_id: str
    user_id: str
    added_by: str
    joined_at: datetime

    # Denormalized user info for list responses
    username: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None

    class Config(_Config):
        pass


# ---------------------------------------------------
# WORKSPACE SUMMARY (for list views)
# ---------------------------------------------------
class WorkspaceSummary(BaseModel):
    """Lightweight workspace representation for sidebar listings."""

    id: str
    name: str
    role: str
    is_personal: bool
    member_count: int
    dataset_count: int
    updated_at: datetime

    class Config(_Config):
        pass


# ---------------------------------------------------
# Export
# ---------------------------------------------------
__all__ = [
    "WorkspaceSettings",
    "WorkspaceBase",
    "WorkspaceCreate",
    "WorkspaceUpdate",
    "Workspace",
    "WorkspaceMemberBase",
    "WorkspaceMemberCreate",
    "WorkspaceMemberUpdate",
    "WorkspaceMember",
    "WorkspaceSummary",
]

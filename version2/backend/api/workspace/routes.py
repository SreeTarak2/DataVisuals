"""
Workspace API Routes
=====================
REST endpoints for workspace and membership management.

Routes:
    POST   /api/workspaces                     Create workspace
    GET    /api/workspaces                      List user's workspaces
    GET    /api/workspaces/{id}                 Get workspace details
    PUT    /api/workspaces/{id}                 Update workspace
    DELETE /api/workspaces/{id}                 Delete workspace

    POST   /api/workspaces/{id}/members         Add member
    GET    /api/workspaces/{id}/members          List members
    DELETE /api/workspaces/{id}/members/{uid}    Remove member
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from db.schemas_workspace import (
    Workspace,
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceMember,
    WorkspaceMemberCreate,
    WorkspaceMemberUpdate,
)
from services.auth_service import get_current_user
from services.workspace import workspace_service
from middleware.workspace import get_current_workspace, get_workspace_admin, require_permission

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Workspace CRUD ────────────────────────────────────────────────────────────


@router.post("", response_model=Workspace, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new workspace."""
    result = await workspace_service.create_workspace(
        name=payload.name,
        owner_id=current_user["id"],
        description=payload.description,
    )
    return result


@router.get("")
async def list_workspaces(
    current_user: dict = Depends(get_current_user),
):
    """List all workspaces the current user is a member of."""
    workspaces = await workspace_service.get_user_workspaces(current_user["id"])
    return {"workspaces": workspaces}


@router.get("/{workspace_id}", response_model=Workspace)
async def get_workspace(
    workspace_id: str,
    workspace: dict = Depends(get_current_workspace),
):
    """Get workspace details. Only accessible to workspace members."""
    result = await workspace_service.get_workspace(workspace["workspace_id"])
    if not result:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return result


@router.put("/{workspace_id}", response_model=Workspace)
async def update_workspace(
    workspace_id: str,
    payload: WorkspaceUpdate,
    workspace: dict = Depends(get_workspace_admin),
    current_user: dict = Depends(get_current_user),
):
    """Update workspace settings. Owner only."""
    return await workspace_service.update_workspace(
        workspace_id=workspace["workspace_id"],
        update=payload,
        user_id=current_user["id"],
    )


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: str,
    workspace: dict = Depends(get_workspace_admin),
    current_user: dict = Depends(get_current_user),
):
    """Delete a workspace. Owner only. Personal workspaces cannot be deleted."""
    await workspace_service.delete_workspace(
        workspace_id=workspace["workspace_id"],
        user_id=current_user["id"],
    )


# ─── Membership ────────────────────────────────────────────────────────────────


@router.post("/{workspace_id}/members", response_model=WorkspaceMember)
async def add_member(
    workspace_id: str,
    payload: WorkspaceMemberCreate,
    workspace: dict = Depends(get_workspace_admin),
    current_user: dict = Depends(get_current_user),
):
    """Add a member to the workspace. Owner/Admin only."""
    return await workspace_service.add_member(
        workspace_id=workspace["workspace_id"],
        member_data=payload,
        added_by=current_user["id"],
    )


@router.get("/{workspace_id}/members")
async def list_members(
    workspace_id: str,
    workspace: dict = Depends(require_permission("workspace:list_members")),
):
    """List all workspace members. Any member can list."""
    members = await workspace_service.list_members(workspace["workspace_id"])
    return {"members": members}


@router.put("/{workspace_id}/members/{target_user_id}/role", response_model=WorkspaceMember)
async def update_member_role(
    workspace_id: str,
    target_user_id: str,
    payload: WorkspaceMemberUpdate,
    workspace: dict = Depends(require_permission("workspace:change_role")),
    current_user: dict = Depends(get_current_user),
):
    """Change a member's role. Owner/Admin only. Cannot change owner's role."""
    result = await workspace_service.update_member_role(
        workspace_id=workspace["workspace_id"],
        target_user_id=target_user_id,
        new_role=payload.role,
        requested_by=current_user["id"],
    )
    return result


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    workspace_id: str,
    user_id: str,
    workspace: dict = Depends(get_workspace_admin),
    current_user: dict = Depends(get_current_user),
):
    """Remove a member from the workspace. Owner only."""
    await workspace_service.remove_member(
        workspace_id=workspace["workspace_id"],
        user_id=user_id,
        requested_by=current_user["id"],
    )

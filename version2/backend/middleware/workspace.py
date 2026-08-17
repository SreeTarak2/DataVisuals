"""
Workspace Middleware
====================
Resolves the active workspace context for every authenticated request.

Resolution order:
1. X-Workspace-Id HTTP header (frontend sends this on workspace switch)
2. workspace_id claim from JWT token (set on login)
3. Personal workspace lookup (fallback for backward compatibility)

Usage:
    from middleware.workspace import get_current_workspace, require_permission

    @router.get("/endpoint")
    async def my_endpoint(
        workspace: dict = Depends(get_current_workspace),
    ):
        wid = workspace["workspace_id"]
        role = workspace["role"]
"""

import logging
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status

from services.auth_service import get_current_user
from services.workspace import workspace_service
from core.permissions import has_permission

logger = logging.getLogger(__name__)


async def get_current_workspace(
    request: Request,
    current_user: dict = Depends(get_current_user),
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
) -> dict:
    """
    Resolve the active workspace for the current request.

    Returns: {"workspace_id": str, "role": str}

    The resolved workspace is guaranteed to be one the user is a member of.
    """
    user_id = current_user["id"]

    # 1. Try X-Workspace-Id header
    workspace_id = x_workspace_id

    # 2. Fall back to JWT claim
    if not workspace_id:
        workspace_id = current_user.get("workspace_id")

    # 3. Resolve via service (validates membership, falls back to personal workspace)
    try:
        result = await workspace_service.resolve_workspace(workspace_id, user_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve workspace for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve workspace context",
        )


def require_permission(action: str):
    """
    Factory that returns a FastAPI dependency to check a specific permission.

    Usage:
        @router.delete("/{id}")
        async def delete_endpoint(
            workspace: dict = Depends(require_permission("workspace:delete")),
        ):
            ...

    This replaces the old get_workspace_admin() with a flexible system.
    """
    async def _check_permission(
        workspace: dict = Depends(get_current_workspace),
    ) -> dict:
        role = workspace["role"]
        if not has_permission(role, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {action}",
            )
        return workspace

    return _check_permission


# ── Convenience aliases for common permission levels ─────────────────────
# These match the most common use cases so route handlers stay readable.

get_workspace_owner = require_permission("workspace:delete")
get_workspace_admin = require_permission("workspace:update")
get_workspace_member = require_permission("dataset:upload")

# Backward compatibility: old name for any workspace member + up
get_workspace_member_or_up = require_permission("data:view")

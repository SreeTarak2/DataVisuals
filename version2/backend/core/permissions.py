"""
Workspace Permissions
=====================
Centralized role-based permission definitions for workspaces.

Each action maps to a minimal role required to perform it.
Roles are hierarchical: owner > admin > member > viewer.
"""

from typing import List, Literal

# ── Role Hierarchy (ordered most → least privileged) ────────────────────
# Each role inherits permissions from roles below it.
ROLE_HIERARCHY = ["owner", "admin", "member", "viewer"]
ALL_ROLES = Literal["owner", "admin", "member", "viewer"]

# ── Workspace-level actions ─────────────────────────────────────────────
PERMISSIONS = {
    # Workspace CRUD
    "workspace:delete":          ["owner"],
    "workspace:update":          ["owner", "admin"],
    "workspace:transfer_owner":  ["owner"],

    # Membership management
    "workspace:invite":          ["owner", "admin"],
    "workspace:remove_member":   ["owner", "admin"],
    "workspace:change_role":     ["owner", "admin"],
    "workspace:list_members":    ["owner", "admin", "member", "viewer"],

    # Dataset management
    "dataset:upload":            ["owner", "admin", "member"],
    "dataset:delete":            ["owner", "admin"],
    "dataset:edit":              ["owner", "admin", "member"],

    # Charts and analysis
    "chart:create":              ["owner", "admin", "member"],
    "chart:delete_own":          ["owner", "admin", "member"],
    "chart:delete_any":          ["owner", "admin"],
    "chart:edit":                ["owner", "admin", "member"],

    # Dashboard
    "dashboard:create":          ["owner", "admin", "member"],
    "dashboard:delete":          ["owner", "admin"],
    "dashboard:share":           ["owner", "admin", "member"],

    # AI / Analysis
    "analysis:run":              ["owner", "admin", "member"],
    "analysis:delete":           ["owner", "admin"],

    # Settings
    "settings:view":             ["owner", "admin", "member", "viewer"],
    "settings:edit":             ["owner", "admin"],

    # Billing (future)
    "billing:view":              ["owner", "admin"],
    "billing:edit":              ["owner"],

    # View-only
    "data:view":                 ["owner", "admin", "member", "viewer"],
    "data:export":               ["owner", "admin", "member"],
}


def role_index(role: str) -> int:
    """Get the hierarchical index of a role. Lower = more privileged."""
    try:
        return ROLE_HIERARCHY.index(role)
    except ValueError:
        return len(ROLE_HIERARCHY)  # Unknown roles get lowest privilege


def has_permission(user_role: str, action: str) -> bool:
    """
    Check if a user with the given role has permission for an action.

    Uses hierarchical comparison: owner can do everything admin can, etc.
    """
    allowed_roles = PERMISSIONS.get(action)
    if not allowed_roles:
        return False

    user_idx = role_index(user_role)
    # User's role must be >= the minimum required role (lower index = higher privilege)
    for allowed in allowed_roles:
        allowed_idx = role_index(allowed)
        if user_idx <= allowed_idx:
            return True
    return False


def min_role_for(action: str) -> str:
    """
    Return the minimum role required for an action.
    Useful for UI hints like 'Owner only' or 'Admin+'.
    """
    allowed = PERMISSIONS.get(action, [])
    if not allowed:
        return "owner"  # safest default
    # Return the least privileged role that can perform this action
    max_idx = max(role_index(r) for r in allowed)
    return ROLE_HIERARCHY[max_idx]


def get_allowed_actions(user_role: str) -> List[str]:
    """Return all actions a user with the given role can perform."""
    return [
        action for action in PERMISSIONS
        if has_permission(user_role, action)
    ]


def can_manage_role(current_role: str, target_role: str) -> bool:
    """
    Check if a user can assign/manage another user with the given target role.
    You can only manage roles below your own.
    """
    return role_index(current_role) < role_index(target_role)

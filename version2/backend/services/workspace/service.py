"""
Workspace Service
=================
Manages workspaces (the tenant boundary) and workspace membership.

Responsibilities:
- Create, read, update, delete workspaces
- Add/remove workspace members
- Auto-create personal workspace on user registration
- Resolve current workspace for authenticated requests
"""

import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List

from bson import ObjectId
from fastapi import HTTPException, status

from db.database import get_database
from db.schemas_workspace import (
    Workspace,
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceMember,
    WorkspaceMemberCreate,
    WorkspaceMemberUpdate,
    WorkspaceSummary,
    WorkspaceSettings,
)
from core.permissions import has_permission, can_manage_role

logger = logging.getLogger(__name__)


class WorkspaceService:
    """CRUD + membership for workspaces."""

    # Personal-workspace resolution cache for resolve_effective_workspace_id.
    _PERSONAL_WORKSPACE_CACHE_TTL = 300  # seconds

    def __init__(self):
        # user_id -> (workspace_id, cached_at_monotonic)
        self._personal_workspace_cache: dict[str, tuple[str, float]] = {}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_db(self):
        return get_database()

    @staticmethod
    def _to_id(id_or_str) -> ObjectId:
        try:
            return ObjectId(id_or_str)
        except Exception:
            return id_or_str

    @staticmethod
    def _clean_doc(doc: dict, id_field: str = "_id") -> dict:
        doc["id"] = str(doc.pop(id_field))
        return doc

    # ── Create ────────────────────────────────────────────────────────────────

    async def create_workspace(
        self,
        name: str,
        owner_id: str,
        description: Optional[str] = None,
        is_personal: bool = False,
    ) -> dict:
        """Create a new workspace and add the owner as the first member."""
        db = self._get_db()

        workspace_doc = {
            "name": name,
            "description": description or "",
            "owner_id": owner_id,
            "settings": WorkspaceSettings().model_dump(),
            "is_personal": is_personal,
            "member_count": 1,
            "dataset_count": 0,
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }

        result = await db.workspaces.insert_one(workspace_doc)
        workspace_id = str(result.inserted_id)
        workspace_doc["_id"] = workspace_id

        # Add owner as the first member
        member_doc = {
            "workspace_id": workspace_id,
            "user_id": owner_id,
            "role": "owner",
            "added_by": owner_id,
            "joined_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }
        await db.workspace_members.insert_one(member_doc)

        logger.info(f"Workspace created: {workspace_id} ('{name}') by user {owner_id}")
        return self._clean_doc(workspace_doc)

    async def create_personal_workspace(self, user_id: str, username: str) -> dict:
        """Auto-create a personal workspace for a new user."""
        return await self.create_workspace(
            name=f"{username}'s Workspace",
            owner_id=user_id,
            description="Your personal workspace",
            is_personal=True,
        )

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_workspace(self, workspace_id: str) -> Optional[dict]:
        """Get a workspace by ID."""
        db = self._get_db()
        doc = await db.workspaces.find_one({"_id": self._to_id(workspace_id)})
        if doc:
            return self._clean_doc(doc)
        return None

    async def get_user_workspaces(self, user_id: str) -> List[dict]:
        """List all workspaces the user is a member of."""
        db = self._get_db()

        # Find membership records
        memberships = (
            await db.workspace_members.find({"user_id": user_id})
            .sort("joined_at", -1)
            .to_list(length=100)
        )

        if not memberships:
            return []

        workspace_ids = [m["workspace_id"] for m in memberships]
        id_to_role = {m["workspace_id"]: m["role"] for m in memberships}

        workspaces = (
            await db.workspaces.find({"_id": {"$in": [self._to_id(wid) for wid in workspace_ids]}})
            .to_list(length=100)
        )

        results = []
        for ws in workspaces:
            ws_id = str(ws["_id"])
            results.append({
                "id": ws_id,
                "name": ws.get("name", ""),
                "role": id_to_role.get(ws_id, "member"),
                "is_personal": ws.get("is_personal", False),
                "member_count": ws.get("member_count", 0),
                "dataset_count": ws.get("dataset_count", 0),
                "updated_at": ws.get("updated_at"),
            })

        return results

    async def get_personal_workspace(self, user_id: str) -> Optional[dict]:
        """Get the user's personal workspace, creating one if it doesn't exist."""
        db = self._get_db()

        doc = await db.workspaces.find_one({
            "owner_id": user_id,
            "is_personal": True,
        })

        if doc:
            return self._clean_doc(doc)

        # No personal workspace — create one (backfill for existing users)
        logger.info(f"No personal workspace found for user {user_id}, creating one")
        username = await self._get_username(user_id)
        return await self.create_personal_workspace(user_id, username or user_id[:8])

    async def _get_username(self, user_id: str) -> Optional[str]:
        """Get username from users collection."""
        try:
            db = self._get_db()
            user = await db.users.find_one({"_id": self._to_id(user_id)})
            if user:
                return user.get("username")
        except Exception:
            pass
        return None

    # ── Update ────────────────────────────────────────────────────────────────

    async def update_workspace(self, workspace_id: str, update: WorkspaceUpdate, user_id: str) -> dict:
        """Update workspace settings. Validates ownership."""
        db = self._get_db()

        workspace = await db.workspaces.find_one({"_id": self._to_id(workspace_id)})
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        if str(workspace.get("owner_id")) != user_id:
            raise HTTPException(status_code=403, detail="Only workspace owner can update settings")

        update_data = {}
        if update.name is not None:
            update_data["name"] = update.name
        if update.description is not None:
            update_data["description"] = update.description
        if update.settings is not None:
            update_data["settings"] = update.settings.model_dump()

        if not update_data:
            return self._clean_doc(workspace)

        update_data["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None)

        await db.workspaces.update_one(
            {"_id": self._to_id(workspace_id)},
            {"$set": update_data},
        )

        updated = await db.workspaces.find_one({"_id": self._to_id(workspace_id)})
        return self._clean_doc(updated)

    # ── Delete ────────────────────────────────────────────────────────────────

    async def delete_workspace(self, workspace_id: str, user_id: str):
        """Delete a workspace. Only the owner can delete. Personal workspaces cannot be deleted."""
        db = self._get_db()

        workspace = await db.workspaces.find_one({"_id": self._to_id(workspace_id)})
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        if str(workspace.get("owner_id")) != user_id:
            raise HTTPException(status_code=403, detail="Only workspace owner can delete")

        if workspace.get("is_personal"):
            raise HTTPException(status_code=400, detail="Cannot delete personal workspace")

        await db.workspaces.delete_one({"_id": self._to_id(workspace_id)})
        await db.workspace_members.delete_many({"workspace_id": workspace_id})

        logger.info(f"Workspace deleted: {workspace_id} by user {user_id}")

    # ── Membership ────────────────────────────────────────────────────────────

    async def add_member(self, workspace_id: str, member_data: WorkspaceMemberCreate, added_by: str) -> dict:
        """Add a member to a workspace.

        Accepts either a MongoDB ObjectId or an email address in user_id.
        If an email is provided, the user is looked up by email.
        """
        db = self._get_db()

        workspace = await db.workspaces.find_one({"_id": self._to_id(workspace_id)})
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        # ── Resolve user_id: support both ObjectId and email ──
        user_id = member_data.user_id
        try:
            # Test if it's a valid ObjectId
            ObjectId(user_id)
        except Exception:
            # Not a valid ObjectId — treat as email and look up user
            user = await db.users.find_one({"email": user_id})
            if not user:
                raise HTTPException(
                    status_code=404,
                    detail=f"No user found with email '{user_id}'. The user must register first before being invited.",
                )
            user_id = str(user["_id"])

        # Check if already a member
        existing = await db.workspace_members.find_one({
            "workspace_id": workspace_id,
            "user_id": user_id,
        })
        if existing:
            raise HTTPException(status_code=409, detail="User is already a member of this workspace")

        member_doc = {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "role": member_data.role,
            "added_by": added_by,
            "joined_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }

        result = await db.workspace_members.insert_one(member_doc)
        member_doc["_id"] = str(result.inserted_id)
        member_doc["id"] = member_doc.pop("_id")

        # Increment member count
        await db.workspaces.update_one(
            {"_id": self._to_id(workspace_id)},
            {"$inc": {"member_count": 1}, "$set": {"updated_at": datetime.now(timezone.utc).replace(tzinfo=None)}},
        )

        logger.info(f"User {user_id} added to workspace {workspace_id} as {member_data.role}")
        return member_doc

    async def get_member(self, workspace_id: str, user_id: str) -> Optional[dict]:
        """Get a specific member record."""
        db = self._get_db()
        doc = await db.workspace_members.find_one({
            "workspace_id": workspace_id,
            "user_id": user_id,
        })
        if doc:
            doc["id"] = str(doc.pop("_id"))
            # Enrich with user info
            try:
                user = await db.users.find_one({"_id": self._to_id(user_id)})
                if user:
                    doc["username"] = user.get("username")
                    doc["email"] = user.get("email")
                    doc["avatar"] = user.get("avatar")
            except Exception:
                pass
            return doc
        return None

    async def list_members(self, workspace_id: str) -> List[dict]:
        """List all members of a workspace with user info."""
        db = self._get_db()

        members = (
            await db.workspace_members.find({"workspace_id": workspace_id})
            .sort("joined_at", 1)
            .to_list(length=100)
        )

        results = []
        for m in members:
            user_id = m["user_id"]
            user = await db.users.find_one({"_id": self._to_id(user_id)})
            results.append({
                "id": str(m.pop("_id")),
                "workspace_id": m["workspace_id"],
                "user_id": user_id,
                "role": m["role"],
                "added_by": m.get("added_by", ""),
                "joined_at": m.get("joined_at"),
                "username": user.get("username") if user else None,
                "email": user.get("email") if user else None,
                "avatar": user.get("avatar") if user else None,
            })

        return results

    async def update_member_role(
        self,
        workspace_id: str,
        target_user_id: str,
        new_role: str,
        requested_by: str,
    ) -> dict:
        """
        Change a member's role. Validates that the requester has permission
        to manage the target (must be a higher role).
        """
        db = self._get_db()

        workspace = await db.workspaces.find_one({"_id": self._to_id(workspace_id)})
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        # Get the requester's role
        requester = await db.workspace_members.find_one({
            "workspace_id": workspace_id,
            "user_id": requested_by,
        })
        if not requester:
            raise HTTPException(status_code=403, detail="Not a workspace member")

        # Cannot change the owner's role
        if str(workspace.get("owner_id")) == target_user_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot change the workspace owner's role. Transfer ownership instead.",
            )

        # Get the target member
        target = await db.workspace_members.find_one({
            "workspace_id": workspace_id,
            "user_id": target_user_id,
        })
        if not target:
            raise HTTPException(status_code=404, detail="Member not found")

        # Validate: requester must have a higher role than the target
        if not can_manage_role(requester["role"], target["role"]):
            raise HTTPException(
                status_code=403,
                detail="Cannot manage users with an equal or higher role than yourself",
            )

        # Validate: new role must be lower than the requester's role
        if not can_manage_role(requester["role"], new_role):
            raise HTTPException(
                status_code=400,
                detail="Cannot assign a role equal to or higher than your own",
            )

        await db.workspace_members.update_one(
            {"workspace_id": workspace_id, "user_id": target_user_id},
            {"$set": {"role": new_role}},
        )

        logger.info(
            f"Member {target_user_id} role changed to {new_role} in workspace "
            f"{workspace_id} by {requested_by}"
        )

        # Return the updated member
        updated = await db.workspace_members.find_one({
            "workspace_id": workspace_id,
            "user_id": target_user_id,
        })
        if updated:
            updated["id"] = str(updated.pop("_id"))
        return updated

    async def remove_member(self, workspace_id: str, user_id: str, requested_by: str):
        """Remove a member from a workspace."""
        db = self._get_db()

        workspace = await db.workspaces.find_one({"_id": self._to_id(workspace_id)})
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        # Cannot remove the owner
        if str(workspace.get("owner_id")) == user_id:
            raise HTTPException(status_code=400, detail="Cannot remove workspace owner")

        result = await db.workspace_members.delete_one({
            "workspace_id": workspace_id,
            "user_id": user_id,
        })

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Member not found")

        # Decrement member count
        await db.workspaces.update_one(
            {"_id": self._to_id(workspace_id)},
            {"$inc": {"member_count": -1}, "$set": {"updated_at": datetime.now(timezone.utc).replace(tzinfo=None)}},
        )

        logger.info(f"User {user_id} removed from workspace {workspace_id} by {requested_by}")

    # ─── Workspace context resolution ─────────────────────────────────────────

    async def resolve_effective_workspace_id(
        self,
        workspace_id: Optional[str],
        user_id: str,
    ) -> str:
        """
        Resolve the workspace id a caller should scope reads/writes with.

        - Returns ``workspace_id`` when provided (an explicit tenant).
        - Otherwise resolves the user's **personal** workspace id — the
          canonical tag that ``migrations/backfill_workspace_id.py`` wrote on
          all legacy documents, so legacy callers that predate workspace
          threading stay correct without any owner-scoped fallback.

        Results are cached per user (TTL ``_PERSONAL_WORKSPACE_CACHE_TTL``)
        because ``get_dataset``/``get_user_datasets`` are hot paths that call
        this on every request when the caller has no workspace context.

        Returns:
            str: the effective workspace id.
        """
        if workspace_id:
            return str(workspace_id)

        cached = self._personal_workspace_cache.get(user_id)
        if cached and (time.monotonic() - cached[1]) < self._PERSONAL_WORKSPACE_CACHE_TTL:
            return cached[0]

        try:
            personal = await self.get_personal_workspace(user_id)
            wid = personal["id"] if personal else user_id
        except Exception as e:
            # Do NOT cache the failure fallback: a transient DB blip must not
            # hide the user's (workspace-OID-tagged) datasets for the whole
            # TTL. Next call will retry resolution.
            logger.warning(
                "Failed to resolve personal workspace for %s: %s", user_id[:8], e
            )
            return user_id

        self._personal_workspace_cache[user_id] = (wid, time.monotonic())
        return wid

    async def resolve_workspace(
        self,
        workspace_id: Optional[str],
        user_id: str,
    ) -> dict:
        """
        Resolve the active workspace for a user.

        1. If workspace_id provided, verify membership and return it.
        2. Otherwise, return the user's personal workspace.

        Returns: {"workspace_id": str, "role": str}
        """
        if workspace_id:
            member = await self.get_member(workspace_id, user_id)
            if not member:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not a member of this workspace",
                )
            return {"workspace_id": workspace_id, "role": member["role"]}

        # Fall back to personal workspace
        personal = await self.get_personal_workspace(user_id)
        if not personal:
            # Create one as last resort
            username = await self._get_username(user_id) or user_id[:8]
            personal = await self.create_personal_workspace(user_id, username)

        return {"workspace_id": personal["id"], "role": "owner"}


# Singleton instance
workspace_service = WorkspaceService()

__all__ = ["WorkspaceService", "workspace_service"]

"""
NotificationService — persistent user notification inbox.

Job events (dataset ready / failed / resumed) are stored in the
``user_notifications`` collection so they survive browser closes and are
visible on any device (desktop or mobile) with the same account.

Every document is tenant-scoped with ``workspace_id`` and indexed for
fast unread queries. Reads are always filtered by both ``user_id`` and
``workspace_id`` so users can only ever see their own notifications.

``create_notification`` persists the event and pushes it in real time to
the user's live WebSocket sockets via :mod:`services.notifications.hub`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

logger = logging.getLogger(__name__)

# Notification types used by job hooks
TYPE_DATASET_READY = "dataset_ready"
TYPE_DATASET_FAILED = "dataset_failed"
TYPE_DATASET_RESUMED = "dataset_resumed"
TYPE_DATASET_REIMPORTED = "dataset_reimported"

# CTA actions — the frontend maps these to navigation / reprocess
CTA_OPEN_DASHBOARD = "open_dashboard"
CTA_RETRY_PROCESSING = "retry_processing"


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a Mongo notification doc to a JSON-safe dict."""
    return {
        "id": str(doc["_id"]),
        "type": doc.get("type", ""),
        "title": doc.get("title", ""),
        "body": doc.get("body", ""),
        "cta": doc.get("cta") or {},
        "dataset_id": doc.get("dataset_id", ""),
        "dataset_name": doc.get("dataset_name", ""),
        "read": bool(doc.get("read", False)),
        "created_at": doc.get("created_at"),
    }


class NotificationService:
    """Persistent notification inbox backed by MongoDB."""

    COLLECTION = "user_notifications"

    async def _get_collection(self):
        from db.database import get_database

        db = get_database()
        return db[self.COLLECTION]

    async def create(
        self,
        user_id: str,
        workspace_id: str,
        notif_type: str,
        title: str,
        body: str = "",
        cta: dict | None = None,
        dataset_id: str = "",
        dataset_name: str = "",
        push: bool = True,
    ) -> dict[str, Any] | None:
        """Persist a notification and optionally push it over WebSocket."""
        if not user_id:
            return None

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        doc = {
            "user_id": user_id,
            "workspace_id": workspace_id or user_id,
            "type": notif_type,
            "title": title,
            "body": body,
            "cta": cta or {},
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "read": False,
            "created_at": now,
        }
        try:
            collection = await self._get_collection()
            result = await collection.insert_one(doc)
        except Exception as e:
            logger.warning(f"[Notifications] Failed to persist notification: {e}")
            return None

        doc["_id"] = result.inserted_id
        payload = _serialize(doc)

        if push:
            from services.notifications.hub import notification_hub

            await notification_hub.push_to_user(
                user_id,
                {"type": "notification", "notification": payload},
            )
        return payload

    async def list(
        self,
        user_id: str,
        workspace_id: str,
        limit: int = 50,
        include_read: bool = True,
    ) -> list[dict[str, Any]]:
        """List a user's notifications, newest first."""
        query: dict[str, Any] = {
            "user_id": user_id,
            "workspace_id": workspace_id or user_id,
        }
        if not include_read:
            query["read"] = False
        try:
            collection = await self._get_collection()
            cursor = (
                collection.find(query)
                .sort("created_at", -1)
                .limit(max(1, min(limit, 200)))
            )
            return [_serialize(doc) async for doc in cursor]
        except Exception as e:
            logger.warning(f"[Notifications] Failed to list notifications: {e}")
            return []

    async def unread_count(self, user_id: str, workspace_id: str) -> int:
        """Number of unread notifications for a user."""
        try:
            collection = await self._get_collection()
            return await collection.count_documents(
                {
                    "user_id": user_id,
                    "workspace_id": workspace_id or user_id,
                    "read": False,
                }
            )
        except Exception as e:
            logger.warning(f"[Notifications] Failed to count unread: {e}")
            return 0

    async def mark_read(self, user_id: str, workspace_id: str, notification_id: str) -> bool:
        """Mark a single notification as read (scoped to the user)."""
        try:
            collection = await self._get_collection()
            result = await collection.update_one(
                {
                    "_id": ObjectId(notification_id),
                    "user_id": user_id,
                    "workspace_id": workspace_id or user_id,
                },
                {"$set": {"read": True}},
            )
            return result.modified_count > 0
        except Exception as e:
            logger.warning(f"[Notifications] Failed to mark read: {e}")
            return False

    async def mark_all_read(self, user_id: str, workspace_id: str) -> int:
        """Mark all of a user's notifications as read. Returns count modified."""
        try:
            collection = await self._get_collection()
            result = await collection.update_many(
                {
                    "user_id": user_id,
                    "workspace_id": workspace_id or user_id,
                    "read": False,
                },
                {"$set": {"read": True}},
            )
            return result.modified_count
        except Exception as e:
            logger.warning(f"[Notifications] Failed to mark all read: {e}")
            return 0


# Singleton
notification_service = NotificationService()


# ── Convenience wrappers (used by pipeline hooks) ───────────────────────────

async def create_notification(
    user_id: str,
    workspace_id: str,
    notif_type: str,
    title: str,
    body: str = "",
    cta: dict | None = None,
    dataset_id: str = "",
    dataset_name: str = "",
    push: bool = True,
):
    return await notification_service.create(
        user_id,
        workspace_id,
        notif_type,
        title,
        body,
        cta,
        dataset_id,
        dataset_name,
        push,
    )


async def list_notifications(user_id: str, workspace_id: str, limit: int = 50, include_read: bool = True):
    return await notification_service.list(user_id, workspace_id, limit, include_read)


async def unread_count(user_id: str, workspace_id: str) -> int:
    return await notification_service.unread_count(user_id, workspace_id)


async def mark_read(user_id: str, workspace_id: str, notification_id: str) -> bool:
    return await notification_service.mark_read(user_id, workspace_id, notification_id)


async def mark_all_read(user_id: str, workspace_id: str) -> int:
    return await notification_service.mark_all_read(user_id, workspace_id)

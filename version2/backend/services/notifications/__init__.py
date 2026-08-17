"""
notifications — persistent user notification inbox + WebSocket push.

Job events (dataset ready / failed / resumed) are persisted to the
``user_notifications`` collection (tenant-scoped by ``workspace_id``) and
pushed in real time to the user's connected WebSocket sockets via the
``NotificationHub`` (registered by the chat WS handler on connect).
"""

from .service import (
    NotificationService,
    create_notification,
    list_notifications,
    mark_all_read,
    mark_read,
    unread_count,
)
from .hub import NotificationHub, notification_hub

__all__ = [
    "NotificationService",
    "create_notification",
    "list_notifications",
    "mark_all_read",
    "mark_read",
    "unread_count",
    "NotificationHub",
    "notification_hub",
]

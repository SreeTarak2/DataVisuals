"""
NotificationHub — per-user WebSocket fan-out for job notifications.

The chat WebSocket handler registers every connected socket here on accept
and unregisters on close. ``push_to_user`` sends a JSON event to all of a
user's live sockets so the frontend bell can update in real time without
polling.

Thread-safety: all mutations happen on the asyncio event loop (register /
unregister are called from the WS handler coroutine; pushes come from
background pipeline tasks on the same loop), so a plain dict is safe.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class NotificationHub:
    """Tracks live WebSocket sockets per user and fans out JSON events."""

    def __init__(self) -> None:
        # user_id -> set of websocket objects
        self._sockets: dict[str, set] = {}

    def register(self, user_id: str, websocket) -> None:
        """Register a connected socket for a user."""
        if not user_id:
            return
        self._sockets.setdefault(user_id, set()).add(websocket)

    def unregister(self, user_id: str, websocket) -> None:
        """Remove a socket (called on WS disconnect / finally)."""
        sockets = self._sockets.get(user_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            self._sockets.pop(user_id, None)

    def is_connected(self, user_id: str) -> bool:
        return bool(self._sockets.get(user_id))

    def socket_count(self, user_id: str) -> int:
        return len(self._sockets.get(user_id, set()))

    def schedule_push(self, user_id: str, payload: dict[str, Any]) -> None:
        """Fire-and-forget push from synchronous code (e.g. the pipeline tracker).

        Schedules ``push_to_user`` on the currently running event loop. Safe
        to call from any pipeline stage; if no loop is running (e.g. a sync
        test harness), the push is silently skipped.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if not self._sockets.get(user_id):
            return
        try:
            loop.create_task(self.push_to_user(user_id, payload))
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"[NotificationHub] Failed to schedule push: {exc}")

    async def push_to_user(self, user_id: str, payload: dict[str, Any]) -> int:
        """Send a JSON event to every live socket for a user.

        Returns the number of sockets the event was delivered to.
        Dead sockets are dropped silently.
        """
        sockets = list(self._sockets.get(user_id, set()))
        if not sockets:
            return 0

        delivered = 0
        dead: list = []
        for ws in sockets:
            try:
                # Skip sockets that are no longer CONNECTED
                try:
                    client_state = ws.client_state.name
                    app_state = ws.application_state.name
                except Exception:
                    client_state = "UNKNOWN"
                    app_state = "UNKNOWN"
                if client_state != "CONNECTED" or app_state != "CONNECTED":
                    dead.append(ws)
                    continue
                await ws.send_json(payload)
                delivered += 1
            except Exception as e:
                logger.debug(f"[NotificationHub] Push failed to socket: {e}")
                dead.append(ws)

        for ws in dead:
            self.unregister(user_id, ws)

        if delivered:
            logger.debug(
                f"[NotificationHub] Pushed {payload.get('type')} to {user_id} "
                f"({delivered}/{len(sockets)} sockets)"
            )
        return delivered


# Singleton used across the app
notification_hub = NotificationHub()

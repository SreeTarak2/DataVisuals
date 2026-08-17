"""
Session management for per-device auth sessions (refresh-token rotation).

Each login creates a ``sessions`` document (one per device) holding a
long-lived opaque refresh token (stored hashed) plus device metadata.
Short-lived access tokens (JWT) carry the session's ``jti`` so a session
can be revoked instantly via the in-memory denylist — no per-request DB
hit for normal requests.

Refresh-token rotation: every ``/auth/refresh`` mints a new refresh token
and stores the previous hash. Presenting a previously-rotated token is
treated as reuse (possible theft) and revokes the whole session.

``RevokedJtiStore`` is the in-memory denylist of revoked access-token
``jti`` values. TTL-bounded so memory stays flat; entries live only as
long as the access token itself would have been valid.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from db.database import get_database

logger = logging.getLogger(__name__)


def hash_refresh_token(token: str) -> str:
    """Deterministic hash used to store refresh tokens at rest."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> str:
    """Opaque, high-entropy refresh token (never stored in plaintext)."""
    return secrets.token_urlsafe(48)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SessionStore:
    """CRUD for the ``sessions`` collection (one doc per device login)."""

    def __init__(self, db=None, refresh_ttl_days: int = 30) -> None:
        self._db = db
        self._refresh_ttl_days = refresh_ttl_days

    @property
    def db(self):
        if self._db is None:
            self._db = get_database()
        return self._db

    async def create_session(
        self,
        user_id: str,
        workspace_id: str,
        refresh_token: str,
        device_name: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        """Insert a new active session; returns the document (includes jti)."""
        now = _utcnow()
        doc = {
            "jti": str(uuid.uuid4()),
            "user_id": user_id,
            "workspace_id": workspace_id,
            "device_name": (device_name or "Unknown device")[:120],
            "ip": ip,
            "user_agent": (user_agent or "")[:300],
            "refresh_token_hash": hash_refresh_token(refresh_token),
            "prev_refresh_token_hash": None,
            "created_at": now,
            "last_used_at": now,
            "expires_at": now + timedelta(days=self._refresh_ttl_days),
            "revoked_at": None,
        }
        await self.db.sessions.insert_one(doc)
        return doc

    async def get_by_jti(self, jti: str) -> Optional[dict]:
        return await self.db.sessions.find_one({"jti": jti})

    async def find_by_refresh_hash(self, refresh_hash: str) -> Optional[dict]:
        """Find a session whose *current* refresh token hash matches."""
        return await self.db.sessions.find_one(
            {"refresh_token_hash": refresh_hash}
        )

    async def find_by_any_hash(self, refresh_hash: str) -> Optional[dict]:
        """Match current OR previous hash (the latter = reuse detection)."""
        return await self.db.sessions.find_one(
            {
                "$or": [
                    {"refresh_token_hash": refresh_hash},
                    {"prev_refresh_token_hash": refresh_hash},
                ]
            }
        )

    async def rotate(
        self,
        session_id: Any,
        current_hash: str,
        new_refresh_token: str,
    ) -> None:
        """Rotate a refresh token: current becomes prev, new becomes current."""
        await self.db.sessions.update_one(
            {"_id": session_id},
            {
                "$set": {
                    "prev_refresh_token_hash": current_hash,
                    "refresh_token_hash": hash_refresh_token(new_refresh_token),
                    "last_used_at": _utcnow(),
                }
            },
        )

    async def revoke(self, jti: str) -> None:
        await self.db.sessions.update_one(
            {"jti": jti}, {"$set": {"revoked_at": _utcnow()}}
        )

    async def revoke_many(self, jtis: list[str]) -> None:
        if not jtis:
            return
        await self.db.sessions.update_many(
            {"jti": {"$in": jtis}}, {"$set": {"revoked_at": _utcnow()}}
        )

    async def list_active(self, user_id: str) -> list[dict]:
        """Active (non-revoked, unexpired) sessions for a user, newest first."""
        cursor = self.db.sessions.find(
            {
                "user_id": user_id,
                "revoked_at": None,
                "expires_at": {"$gt": _utcnow()},
            }
        ).sort("created_at", -1)
        sessions = []
        async for doc in cursor:
            doc["session_id"] = str(doc.pop("_id"))
            # Never expose refresh token material to the client
            doc.pop("refresh_token_hash", None)
            doc.pop("prev_refresh_token_hash", None)
            sessions.append(doc)
        return sessions

    async def revoke_all_except(
        self, user_id: str, keep_jti: Optional[str]
    ) -> list[str]:
        """Revoke every active session except ``keep_jti``; returns revoked jtis."""
        active = await self.list_active(user_id)
        to_revoke = [s["jti"] for s in active if s["jti"] != keep_jti]
        if to_revoke:
            await self.revoke_many(to_revoke)
        return to_revoke


class RevokedJtiStore:
    """In-memory denylist of revoked access-token jtis (bounded TTL).

    Entries live for the access-token lifetime (default 1h) — long enough
    that a revoked token can never be used, short enough that memory stays
    flat. On multi-instance deployments, back this with Redis; the API is
    intentionally tiny (revoke / is_revoked) to allow that swap.
    """

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 20000) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._revoked: dict[str, float] = {}  # jti -> expiry epoch

    def revoke(self, jti: Optional[str], ttl_seconds: Optional[int] = None) -> None:
        if not jti:
            return
        ttl = ttl_seconds or self._ttl_seconds
        self._revoked[jti] = time.time() + ttl
        if len(self._revoked) > self._max_entries:
            self._prune()

    def is_revoked(self, jti: Optional[str]) -> bool:
        if not jti:
            return False
        expires_at = self._revoked.get(jti)
        if expires_at is None:
            return False
        if time.time() > expires_at:
            self._revoked.pop(jti, None)
            return False
        return True

    def _prune(self) -> None:
        now = time.time()
        self._revoked = {
            jti: exp for jti, exp in self._revoked.items() if exp > now
        }


# Module-level singletons (same pattern as the notification hub)
session_store = SessionStore()
revoked_jti_store = RevokedJtiStore()

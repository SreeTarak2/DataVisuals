"""
Unit tests for workspace_service.resolve_effective_workspace_id.

This is the async resolution path that lets legacy callers (which predate
workspace threading) keep working under strict workspace-scoped reads: when
no workspace_id is supplied, the user's *personal* workspace id is resolved
— the canonical tag the backfill migration wrote on all legacy documents.

Verifies:
  - explicit workspace_id wins immediately (no DB access)
  - personal workspace is resolved from the workspaces collection
  - results are TTL-cached (hot read paths call this on every request)
  - falls back to user_id when resolution fails (defensive)
"""

import asyncio

from services.workspace.service import WorkspaceService


class _FakeResult:
    def __init__(self, inserted_id=None):
        self.inserted_id = inserted_id


class _FakeCollection:
    def __init__(self, docs):
        self.docs = list(docs)
        self.find_one_calls = 0
        self.raise_on_query = None  # optional exception to raise on find_one

    async def find_one(self, filt):
        self.find_one_calls += 1
        if self.raise_on_query is not None:
            raise self.raise_on_query
        for d in self.docs:
            if all(d.get(k) == v for k, v in filt.items()):
                return dict(d)
        return None

    async def insert_one(self, doc):
        doc = dict(doc)
        doc["_id"] = "new-ws-1"
        self.docs.append(doc)
        return _FakeResult(inserted_id="new-ws-1")


class _FakeDB:
    def __init__(self, data=None):
        self._collections = {
            name: _FakeCollection(docs) for name, docs in (data or {}).items()
        }

    def __getitem__(self, name):
        return self._collections.setdefault(name, _FakeCollection([]))

    def __getattr__(self, name):
        return self[name]


def _make_service(db) -> WorkspaceService:
    """Fresh service instance wired to a fake DB (avoids shared cache state)."""
    service = WorkspaceService()
    service._get_db = lambda: db
    return service


def _run(coro):
    return asyncio.run(coro)


class TestResolveEffectiveWorkspaceId:
    def test_explicit_workspace_wins_without_db_access(self):
        db = _FakeDB({})
        service = _make_service(db)
        result = _run(service.resolve_effective_workspace_id("ws-9", "user-1"))
        assert result == "ws-9"

    def test_resolves_personal_workspace(self):
        db = _FakeDB(
            {"workspaces": [{"_id": "ws-1", "owner_id": "user-1", "is_personal": True}]}
        )
        service = _make_service(db)
        result = _run(service.resolve_effective_workspace_id(None, "user-1"))
        assert result == "ws-1"

    def test_falls_back_to_user_id_when_resolution_fails(self):
        # A DB error must not crash the hot read path — it falls back to the
        # legacy personal-workspace id (user_id) defensively.
        db = _FakeDB({"workspaces": []})
        db["workspaces"].raise_on_query = RuntimeError("db down")
        service = _make_service(db)
        result = _run(service.resolve_effective_workspace_id(None, "user-1"))
        assert result == "user-1"

    def test_results_are_cached(self):
        db = _FakeDB(
            {"workspaces": [{"_id": "ws-1", "owner_id": "user-1", "is_personal": True}]}
        )
        service = _make_service(db)

        async def _run_twice():
            first = await service.resolve_effective_workspace_id(None, "user-1")
            second = await service.resolve_effective_workspace_id(None, "user-1")
            return first, second

        first, second = _run(_run_twice())
        assert first == "ws-1"
        assert second == "ws-1"
        # TTL cache: the workspaces collection was queried exactly once.
        assert db["workspaces"].find_one_calls == 1

    def test_cache_does_not_leak_between_users(self):
        db = _FakeDB(
            {
                "workspaces": [
                    {"_id": "ws-1", "owner_id": "user-1", "is_personal": True},
                    {"_id": "ws-2", "owner_id": "user-2", "is_personal": True},
                ]
            }
        )
        service = _make_service(db)

        async def _run_both():
            a = await service.resolve_effective_workspace_id(None, "user-1")
            b = await service.resolve_effective_workspace_id(None, "user-2")
            return a, b

        a, b = _run(_run_both())
        assert a == "ws-1"
        assert b == "ws-2"

    def test_explicit_workspace_ignores_cache(self):
        db = _FakeDB(
            {"workspaces": [{"_id": "ws-1", "owner_id": "user-1", "is_personal": True}]}
        )
        service = _make_service(db)

        async def _run_both():
            a = await service.resolve_effective_workspace_id(None, "user-1")
            b = await service.resolve_effective_workspace_id("ws-99", "user-1")
            return a, b

        a, b = _run(_run_both())
        assert a == "ws-1"
        assert b == "ws-99"
        # Explicit workspace path never consults the cache or the DB.
        assert db["workspaces"].find_one_calls == 1

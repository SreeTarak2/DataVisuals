"""
Unit tests for migrations/backfill_workspace_id.py

Uses an in-memory fake DB (no MongoDB required) to verify:
  - legacy docs (missing/null workspace_id) get their owner's personal workspace
  - personal workspaces are created when missing (mirroring app behavior)
  - split collections copy workspace_id from the parent uploads doc
  - already-tagged docs are never touched (idempotent)
  - dry-run counts without writing
"""

import pytest

from migrations.backfill_workspace_id import (
    ALL_COLLECTIONS,
    backfill_by_owner,
    backfill_split_from_uploads,
    backfill_uploads,
    resolve_personal_workspace,
    run_backfill,
)


# ── Fake in-memory MongoDB ──────────────────────────────────────────────────


def _matches(doc: dict, filt: dict) -> bool:
    for key, expected in filt.items():
        if key == "$or":
            if not any(_matches(doc, branch) for branch in expected):
                return False
            continue
        if key == "$and":
            if not all(_matches(doc, branch) for branch in expected):
                return False
            continue
        actual = doc.get(key)
        if isinstance(expected, dict):
            if "$exists" in expected and (expected["$exists"] is False) == (key in doc):
                return False
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            if "$in" in expected and actual not in expected["$in"]:
                return False
            continue
        # `None` matches both missing and explicit null (Mongo semantics)
        if expected is None:
            if key in doc and doc[key] is not None:
                return False
            continue
        if actual != expected:
            return False
    return True


class _FakeResult:
    def __init__(self, modified_count=0, inserted_id=None):
        self.modified_count = modified_count
        self.inserted_id = inserted_id


class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)


class _FakeCollection:
    def __init__(self, docs):
        self.docs = list(docs)

    def find(self, filt):
        return _FakeCursor(d for d in self.docs if _matches(d, filt))

    def find_one(self, filt, projection=None):
        for d in self.docs:
            if _matches(d, filt):
                if projection:
                    return {k: d.get(k) for k in projection}
                return dict(d)
        return None

    def update_many(self, filt, update):
        return self.update_one(filt, update, _many=True)

    def update_one(self, filt, update, _many=False):
        count = 0
        for d in self.docs:
            if _matches(d, filt):
                for k, v in update.get("$set", {}).items():
                    d[k] = v
                count += 1
                if not _many:
                    break
        return _FakeResult(modified_count=count)

    def insert_one(self, doc):
        doc = dict(doc)
        doc["_id"] = doc.get("_id") or f"id-{len(self.docs) + 1}"
        self.docs.append(doc)
        return _FakeResult(inserted_id=doc["_id"])


class _FakeDB:
    def __init__(self, data=None):
        self._collections = {
            name: _FakeCollection(docs) for name, docs in (data or {}).items()
        }

    def __getitem__(self, name):
        return self._collections.setdefault(name, _FakeCollection([]))

    def __getattr__(self, name):
        # The migration script accesses collections via attributes
        # (db.uploads, db.workspaces, ...) like the real app code.
        return self[name]

    def list_collection_names(self):
        return list(self._collections.keys())


def _uploads(*docs):
    return _FakeDB({"uploads": [dict(d) for d in docs]})


# ── resolve_personal_workspace ──────────────────────────────────────────────


class TestResolvePersonalWorkspace:
    def test_existing_personal_workspace_returned(self):
        db = _FakeDB({"workspaces": [{"_id": "ws-1", "owner_id": "u1", "is_personal": True}]})
        wid, created, would_create = resolve_personal_workspace(db, "u1", {})
        assert wid == "ws-1"
        assert created is False
        assert would_create is False

    def test_missing_personal_workspace_created(self):
        db = _FakeDB({"users": [{"_id": "u1", "username": "alice"}]})
        wid, created, would_create = resolve_personal_workspace(db, "u1", {})
        assert created is True
        assert would_create is False
        assert wid is not None
        # owner added as member with role owner
        members = db["workspace_members"].docs
        assert any(
            m["workspace_id"] == wid and m["user_id"] == "u1" and m["role"] == "owner"
            for m in members
        )

    def test_empty_user_id_returns_none(self):
        db = _FakeDB({})
        wid, created, would_create = resolve_personal_workspace(db, "", {})
        assert wid is None
        assert created is False
        assert would_create is False

    def test_cache_avoids_duplicate_creation(self):
        db = _FakeDB({})
        cache: dict = {}
        wid1, _, _ = resolve_personal_workspace(db, "u1", cache)
        wid2, created2, _ = resolve_personal_workspace(db, "u1", cache)
        assert wid1 == wid2
        assert created2 is False
        # only one workspace created
        assert len(db["workspaces"].docs) == 1

    def test_create_if_missing_false_never_writes(self):
        db = _FakeDB({})
        wid, created, would_create = resolve_personal_workspace(
            db, "u1", {}, create_if_missing=False
        )
        assert wid is None
        assert created is False
        assert would_create is True
        # read-only mode must not write anything
        assert db["workspaces"].docs == []
        assert db["workspace_members"].docs == []

    def test_username_lookup_handles_objectid(self):
        from bson import ObjectId

        oid = ObjectId()
        db = _FakeDB({"users": [{u"_id": oid, "username": "alice"}]})
        wid, created, _ = resolve_personal_workspace(db, str(oid), {})
        assert created is True
        workspace = db["workspaces"].docs[0]
        assert workspace["name"] == "alice's Workspace"


# ── backfill_uploads ────────────────────────────────────────────────────────


class TestBackfillUploads:
    def test_legacy_docs_get_owner_personal_workspace(self):
        db = _uploads(
            {"_id": "d1", "user_id": "u1", "name": "a"},  # missing workspace_id
            {"_id": "d2", "user_id": "u1", "workspace_id": None, "name": "b"},  # null
            {"_id": "d3", "user_id": "u2", "name": "c"},
        )
        db["workspaces"].docs = [
            {"_id": "ws-1", "owner_id": "u1", "is_personal": True},
            {"_id": "ws-2", "owner_id": "u2", "is_personal": True},
        ]
        summary = backfill_uploads(db, dry_run=False)
        assert summary["updated"] == 3
        by_id = {d["_id"]: d for d in db["uploads"].docs}
        assert by_id["d1"]["workspace_id"] == "ws-1"
        assert by_id["d2"]["workspace_id"] == "ws-1"
        assert by_id["d3"]["workspace_id"] == "ws-2"

    def test_already_tagged_docs_untouched(self):
        db = _uploads(
            {"_id": "d1", "user_id": "u1", "workspace_id": "ws-1", "name": "a"},
        )
        db["workspaces"].docs = [{"_id": "ws-1", "owner_id": "u1", "is_personal": True}]
        summary = backfill_uploads(db, dry_run=False)
        assert summary["updated"] == 0
        assert db["uploads"].docs[0]["workspace_id"] == "ws-1"

    def test_doc_without_owner_skipped(self):
        db = _uploads({"_id": "d1", "name": "orphan"})
        summary = backfill_uploads(db, dry_run=False)
        assert summary["skipped_no_owner"] == 1
        assert summary["updated"] == 0

    def test_dry_run_counts_without_writing(self):
        db = _uploads({"_id": "d1", "user_id": "u1", "name": "a"})
        db["workspaces"].docs = [{"_id": "ws-1", "owner_id": "u1", "is_personal": True}]
        summary = backfill_uploads(db, dry_run=True)
        assert summary["updated"] == 1
        assert db["uploads"].docs[0].get("workspace_id") is None

    def test_dry_run_with_missing_workspace_creates_nothing(self):
        # Read-only mode must NOT create personal workspaces, even when the
        # owner has none yet.
        db = _uploads({"_id": "d1", "user_id": "u1", "name": "a"})
        summary = backfill_uploads(db, dry_run=True)
        assert summary["updated"] == 1
        assert db["workspaces"].docs == []
        assert db["workspace_members"].docs == []
        assert db["uploads"].docs[0].get("workspace_id") is None

    def test_user_id_as_object_id_normalized(self):
        from bson import ObjectId

        oid = ObjectId()
        db = _uploads({"_id": "d1", "user_id": oid, "name": "a"})
        db["workspaces"].docs = [{"_id": "ws-1", "owner_id": str(oid), "is_personal": True}]
        summary = backfill_uploads(db, dry_run=False)
        assert summary["updated"] == 1
        assert db["uploads"].docs[0]["workspace_id"] == "ws-1"


# ── split collections ───────────────────────────────────────────────────────


class TestBackfillSplitFromUploads:
    def test_copies_workspace_from_parent(self):
        db = _FakeDB(
            {
                "uploads": [{"_id": "d1", "workspace_id": "ws-1"}],
                "dataset_profiles": [{"_id": "p1", "dataset_id": "d1"}],
                "dataset_intelligence": [{"_id": "i1", "dataset_id": "d1"}],
            }
        )
        s1 = backfill_split_from_uploads(db, "dataset_profiles", dry_run=False)
        s2 = backfill_split_from_uploads(db, "dataset_intelligence", dry_run=False)
        assert s1["updated"] == 1
        assert s2["updated"] == 1
        assert db["dataset_profiles"].docs[0]["workspace_id"] == "ws-1"
        assert db["dataset_intelligence"].docs[0]["workspace_id"] == "ws-1"

    def test_no_parent_skipped(self):
        db = _FakeDB({"dataset_profiles": [{"_id": "p1", "dataset_id": "missing"}]})
        summary = backfill_split_from_uploads(db, "dataset_profiles", dry_run=False)
        assert summary["skipped_no_parent"] == 1
        assert summary["updated"] == 0

    def test_untagged_parent_skipped(self):
        # A parent uploads doc without a workspace_id can't provide one — the
        # split doc is skipped (counted under skipped_no_parent).
        db = _FakeDB(
            {
                "uploads": [{"_id": "d1"}],  # no workspace_id yet
                "dataset_profiles": [{"_id": "p1", "dataset_id": "d1"}],
            }
        )
        summary = backfill_split_from_uploads(db, "dataset_profiles", dry_run=False)
        assert summary["skipped_no_parent"] == 1
        assert summary["updated"] == 0

    def test_parent_with_objectid_id_resolved(self):
        from bson import ObjectId

        oid = ObjectId()
        db = _FakeDB(
            {
                "uploads": [{"_id": oid, "workspace_id": "ws-1"}],
                # dataset_id stored as the string form of the ObjectId
                "dataset_profiles": [{"_id": "p1", "dataset_id": str(oid)}],
            }
        )
        summary = backfill_split_from_uploads(db, "dataset_profiles", dry_run=False)
        assert summary["updated"] == 1
        assert db["dataset_profiles"].docs[0]["workspace_id"] == "ws-1"


class TestBackfillByOwner:
    def test_analytics_and_stages_resolved_by_owner(self):
        db = _FakeDB(
            {
                "workspaces": [
                    {"_id": "ws-1", "owner_id": "u1", "is_personal": True},
                    {"_id": "ws-2", "owner_id": "u2", "is_personal": True},
                ],
                "dataset_analytics": [
                    {"_id": "a1", "dataset_id": "d1", "user_id": "u1"},
                    {"_id": "a2", "dataset_id": "d2", "user_id": "u2"},
                ],
                "pipeline_stages": [{"_id": "s1", "dataset_id": "d1", "user_id": "u1"}],
            }
        )
        s1 = backfill_by_owner(db, "dataset_analytics", dry_run=False)
        s2 = backfill_by_owner(db, "pipeline_stages", dry_run=False)
        assert s1["updated"] == 2
        assert s2["updated"] == 1
        by_id = {d["_id"]: d for d in db["dataset_analytics"].docs}
        assert by_id["a1"]["workspace_id"] == "ws-1"
        assert by_id["a2"]["workspace_id"] == "ws-2"
        assert db["pipeline_stages"].docs[0]["workspace_id"] == "ws-1"


# ── run_backfill orchestration ──────────────────────────────────────────────


class TestRunBackfill:
    def test_check_mode_writes_nothing(self):
        db = _FakeDB(
            {
                "workspaces": [{"_id": "ws-1", "owner_id": "u1", "is_personal": True}],
                "uploads": [{"_id": "d1", "user_id": "u1", "name": "a"}],
            }
        )
        results = run_backfill(db, check_only=True, dry_run=True, collections=("uploads",))
        assert results["uploads"]["updated"] == 1
        assert db["uploads"].docs[0].get("workspace_id") is None

    def test_applies_all_default_collections(self):
        db = _FakeDB(
            {
                "workspaces": [{"_id": "ws-1", "owner_id": "u1", "is_personal": True}],
                "uploads": [{"_id": "d1", "user_id": "u1"}],
                "dataset_profiles": [{"_id": "p1", "dataset_id": "d1"}],
                "dataset_intelligence": [{"_id": "i1", "dataset_id": "d1"}],
                "dataset_analytics": [{"_id": "a1", "dataset_id": "d1", "user_id": "u1"}],
                "pipeline_stages": [{"_id": "s1", "dataset_id": "d1", "user_id": "u1"}],
            }
        )
        results = run_backfill(db, dry_run=False)
        assert results["uploads"]["updated"] == 1
        assert results["dataset_profiles"]["updated"] == 1
        assert results["dataset_intelligence"]["updated"] == 1
        assert results["dataset_analytics"]["updated"] == 1
        assert results["pipeline_stages"]["updated"] == 1
        # workspace_id propagated everywhere
        assert db["dataset_profiles"].docs[0]["workspace_id"] == "ws-1"
        assert db["dataset_intelligence"].docs[0]["workspace_id"] == "ws-1"
        assert db["dataset_analytics"].docs[0]["workspace_id"] == "ws-1"
        assert db["pipeline_stages"].docs[0]["workspace_id"] == "ws-1"

    def test_all_collections_registered(self):
        assert "uploads" in ALL_COLLECTIONS
        assert "dataset_profiles" in ALL_COLLECTIONS
        assert "dataset_intelligence" in ALL_COLLECTIONS
        assert "dataset_analytics" in ALL_COLLECTIONS
        assert "pipeline_stages" in ALL_COLLECTIONS

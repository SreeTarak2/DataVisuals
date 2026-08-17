"""
Unit tests for the ontology assumption state machine (Act-then-Validate).

Proves the lifecycle contract:
  1. Inferences are APPLIED (never withheld) — provisional by default.
  2. Human sign-off → validated (confidence pinned, provenance recorded).
  3. Human rejection → remembered; regeneration does not silently resurrect.
  4. Fix → user_defined + validated (the human authors, never).
  5. Drift → a finalized assumption that stops verifying reverts to provisional.
  6. Tenant isolation — workspace B cannot read/alter workspace A's ontology.
"""

import asyncio
from unittest import mock

import pytest

from services.semantic.assumption_store import (
    PROVISIONAL,
    REJECTED,
    SOURCE_DETERMINISTIC,
    SOURCE_LLM,
    SOURCE_USER,
    TYPE_HIERARCHY,
    VALIDATED,
    SemanticAssumption,
    assumption_store,
    new_assumption,
)


# ─── Fake MongoDB (same pattern as test_projects_service.py) ────────────────


class _FakeResult:
    def __init__(self, inserted_id=None, matched=0, modified=0, deleted=0):
        self.inserted_id = inserted_id
        self.matched_count = matched
        self.modified_count = modified
        self.deleted_count = deleted


class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, key, direction=1):
        self._docs.sort(
            key=lambda d: d.get(key[0] if isinstance(key, list) else key, 0),
            reverse=(direction < 0),
        )
        return self

    async def to_list(self, length=None):
        return list(self._docs)


class _FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def _matches(self, doc, filt):
        for k, v in (filt or {}).items():
            if doc.get(k) != v:
                return False
        return True

    async def find_one(self, filt):
        for d in self.docs:
            if self._matches(d, filt):
                return dict(d)
        return None

    async def insert_one(self, doc):
        doc = dict(doc)
        doc["_id"] = doc.get("_id") or f"id-{len(self.docs) + 1}"
        self.docs.append(doc)
        return _FakeResult(inserted_id=doc["_id"])

    async def update_one(self, filt, update):
        for d in self.docs:
            if self._matches(d, filt):
                for op, fields in (update or {}).items():
                    if op == "$set":
                        d.update(fields)
                return _FakeResult(matched=1, modified=1)
        return _FakeResult(matched=0, modified=0)

    async def delete_one(self, filt):
        for i, d in enumerate(self.docs):
            if self._matches(d, filt):
                del self.docs[i]
                return _FakeResult(deleted=1)
        return _FakeResult(deleted=0)

    async def delete_many(self, filt):
        before = len(self.docs)
        self.docs = [d for d in self.docs if not self._matches(d, filt)]
        return _FakeResult(deleted=before - len(self.docs))

    def find(self, filt=None, projection=None):
        # projection is accepted for signature compatibility (counts passes one)
        return _FakeCursor([d for d in self.docs if self._matches(d, filt or {})])


class _FakeDB:
    def __init__(self, data=None):
        self._collections = {
            name: _FakeCollection(docs) for name, docs in (data or {}).items()
        }

    def __getitem__(self, name):
        return self._collections.setdefault(name, _FakeCollection())

    def __getattr__(self, name):
        return self[name]


def _run(coro):
    return asyncio.run(coro)


def _make_assumption(dataset_id="ds-1", workspace_id="ws-A", state=PROVISIONAL, source=SOURCE_LLM, confidence=0.62):
    return new_assumption(
        dataset_id=dataset_id,
        workspace_id=workspace_id,
        type=TYPE_HIERARCHY,
        definition={"columns": ["region", "country"]},
        confidence=confidence,
        evidence={"cardinality": "3 → 12"},
        state=state,
        source=source,
        description="region → country",
    )


@pytest.fixture
def store_with_db():
    """Wire a fresh fake DB into the store singleton (no module-global state)."""
    db = _FakeDB()
    patcher = mock.patch("db.database.get_database", return_value=db)
    patcher.start()
    yield db
    patcher.stop()


# ─────────────────────────────────────────────────────────────────────────────
# 1. ACT FIRST — applied, provisional by default
# ─────────────────────────────────────────────────────────────────────────────


class TestActFirst:
    def test_upsert_creates_provisional_assumption(self, store_with_db):
        db = store_with_db
        a = _make_assumption()
        stored = _run(assumption_store.upsert(a))
        assert stored.state == PROVISIONAL
        assert stored.source == SOURCE_LLM
        assert db["semantic_assumptions"].docs[0]["workspace_id"] == "ws-A"

    def test_upsert_is_idempotent_by_definition(self, store_with_db):
        db = store_with_db
        a1 = _make_assumption()
        _run(assumption_store.upsert(a1))
        _run(assumption_store.upsert(new_assumption(
            dataset_id="ds-1", workspace_id="ws-A", type=TYPE_HIERARCHY,
            definition={"columns": ["region", "country"]}, confidence=0.7,
            evidence={}, state=PROVISIONAL, source=SOURCE_LLM,
        )))
        assert len(db["semantic_assumptions"].docs) == 1


# ─────────────────────────────────────────────────────────────────────────────
# 2. VALIDATE / REJECT (human sign-off on finished work)
# ─────────────────────────────────────────────────────────────────────────────


class TestStateTransitions:
    def test_validate_pins_confidence_and_records_provenance(self, store_with_db):
        db = store_with_db
        a = _make_assumption(confidence=0.62)
        _run(assumption_store.upsert(a))
        updated = _run(assumption_store.set_state("ds-1", "ws-A", a.assumption_id, VALIDATED, user_id="user-A"))
        assert updated is not None
        assert updated.state == VALIDATED
        assert updated.confidence >= 0.99
        assert updated.evidence.get("validated_by") == "user"
        assert updated.user_id == "user-A"

    def test_reject_remembered(self, store_with_db):
        db = store_with_db
        a = _make_assumption()
        _run(assumption_store.upsert(a))
        updated = _run(assumption_store.set_state("ds-1", "ws-A", a.assumption_id, REJECTED))
        assert updated.state == REJECTED

    def test_validation_does_not_resurrect_rejection(self, store_with_db):
        """Regeneration with a mid-confidence proposal must NOT resurrect a rejection."""
        db = store_with_db
        a = _make_assumption(state=REJECTED)
        _run(assumption_store.upsert(a))
        # Same definition re-proposed at 0.62 (below the 0.85 deterministic bar).
        _run(assumption_store.upsert(_make_assumption(state=PROVISIONAL, source=SOURCE_LLM)))
        docs = db["semantic_assumptions"].docs
        assert len(docs) == 1
        assert docs[0]["state"] == REJECTED

    def test_fix_becomes_user_defined_and_validated(self, store_with_db):
        db = store_with_db
        a = _make_assumption()
        _run(assumption_store.upsert(a))
        fixed = _run(assumption_store.update_definition(
            "ds-1", "ws-A", a.assumption_id,
            {"columns": ["country", "state", "city"]},
            description="user fixed geo chain",
            user_id="user-A",
        ))
        assert fixed.state == VALIDATED
        assert fixed.source == SOURCE_USER
        assert fixed.confidence == 1.0
        assert fixed.definition["columns"] == ["country", "state", "city"]


# ─────────────────────────────────────────────────────────────────────────────
# 3. DRIFT — finalize is not permanent
# ─────────────────────────────────────────────────────────────────────────────


class TestDrift:
    def test_apply_drift_reverts_to_provisional_with_flag(self, store_with_db):
        db = store_with_db
        a = _make_assumption(state=VALIDATED)
        _run(assumption_store.upsert(a))
        drifted = _run(assumption_store.apply_drift(a))
        assert drifted.state == PROVISIONAL
        assert drifted.evidence.get("drift_detected") is True
        assert db["semantic_assumptions"].docs[0]["state"] == PROVISIONAL

    def test_high_confidence_deterministic_resurrects_rejection(self, store_with_db):
        """A 1.0-confidence deterministic re-discovery may resurrect a rejection
        (as provisional, never silently validated)."""
        db = store_with_db
        a = _make_assumption(state=REJECTED)
        _run(assumption_store.upsert(a))
        _run(assumption_store.upsert(_make_assumption(
            state=PROVISIONAL, source=SOURCE_DETERMINISTIC, confidence=1.0,
        )))
        assert db["semantic_assumptions"].docs[0]["state"] == PROVISIONAL


# ─────────────────────────────────────────────────────────────────────────────
# 4. TENANT ISOLATION
# ─────────────────────────────────────────────────────────────────────────────


class TestTenantIsolation:
    def test_workspace_b_cannot_list_workspace_a_assumptions(self, store_with_db):
        db = store_with_db
        _run(assumption_store.upsert(_make_assumption(workspace_id="ws-A")))
        list_b = _run(assumption_store.list("ds-1", "ws-B"))
        assert list_b == []

    def test_workspace_b_cannot_get_assumption(self, store_with_db):
        db = store_with_db
        a = _make_assumption(workspace_id="ws-A")
        _run(assumption_store.upsert(a))
        assert _run(assumption_store.get("ds-1", "ws-B", a.assumption_id)) is None

    def test_workspace_b_cannot_validate_assumption(self, store_with_db):
        db = store_with_db
        a = _make_assumption(workspace_id="ws-A")
        _run(assumption_store.upsert(a))
        assert _run(assumption_store.set_state("ds-1", "ws-B", a.assumption_id, VALIDATED)) is None
        # Workspace A's assumption unchanged.
        assert db["semantic_assumptions"].docs[0]["state"] == PROVISIONAL


# ─────────────────────────────────────────────────────────────────────────────
# 5. COUNTS (review-queue badge)
# ─────────────────────────────────────────────────────────────────────────────


class TestCounts:
    def test_counts_by_state(self, store_with_db):
        db = store_with_db
        _run(assumption_store.upsert(_make_assumption()))
        a2 = _make_assumption(workspace_id="ws-A")
        a2.definition = {"columns": ["country", "city"]}
        _run(assumption_store.upsert(a2))
        _run(assumption_store.set_state("ds-1", "ws-A", a2.assumption_id, VALIDATED))
        counts = _run(assumption_store.counts("ds-1", "ws-A"))
        assert counts[PROVISIONAL] == 1
        assert counts[VALIDATED] == 1
        assert counts[REJECTED] == 0

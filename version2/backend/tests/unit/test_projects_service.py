"""
Unit tests for ProjectService — the context-binder backend.

Proves the four architectural constraints hold:

1. TENANT ISOLATION — a project in workspace A is invisible/immutable from
   workspace B (read/update/delete all return "not found").
2. BINDING VALIDATION — sources can only reference EXISTING infrastructure:
   missing db_connections and cross-workspace datasets are rejected.
3. JOURNEY RESILIENCE — when the LLM fails, ``journey_next_question`` does
   not 500; it returns a safe, deterministic fallback question.
4. CONTEXT PROVENANCE — ``add_context_rule`` writes to the belief store with
   source="manual_rule" and binds it to the project.
"""

import asyncio
from unittest import mock

from db.schemas_projects import ProjectCellCreate, ProjectCreate, ProjectSourceCreate, SourceRef
from services.projects.project_service import ProjectService

WS_A = "ws-A"
WS_B = "ws-B"
USER_A = "user-A"
USER_B = "user-B"


# ─────────────────────────────────────────────────────────────────────────────
# Fake MongoDB (same pattern as test_workspace_tenant_resolution.py)
# ─────────────────────────────────────────────────────────────────────────────


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
        if isinstance(key, list):
            key = key[0][0]
        self._docs.sort(key=lambda d: d.get(key, 0), reverse=(direction < 0))
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    async def to_list(self, length=None):
        return list(self._docs)

    def __aiter__(self):
        async def _gen():
            for d in self._docs:
                yield dict(d)

        return _gen()


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
                    elif op == "$inc":
                        for k, v in fields.items():
                            d[k] = d.get(k, 0) + v
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

    def find(self, filt=None):
        return _FakeCursor(d for d in self.docs if self._matches(d, filt or {}))


class _FakeDB:
    def __init__(self, data=None):
        self._collections = {
            name: _FakeCollection(docs) for name, docs in (data or {}).items()
        }

    def __getitem__(self, name):
        return self._collections.setdefault(name, _FakeCollection())

    def __getattr__(self, name):
        return self[name]


def _make_service(db) -> ProjectService:
    """Fresh service wired to a fake DB (avoids module-singleton state)."""
    service = ProjectService()
    patcher = mock.patch("services.projects.project_service.get_database", return_value=db)
    patcher.start()
    service._patcher = patcher
    return service


def _teardown(service):
    service._patcher.stop()


def _run(coro):
    return asyncio.run(coro)


def _project_payload(name="Churn Q3", problem="Why did churn go up in Q3?"):
    return ProjectCreate(name=name, problem_statement=problem)


# ─────────────────────────────────────────────────────────────────────────────
# 1. TENANT ISOLATION
# ─────────────────────────────────────────────────────────────────────────────


class TestTenantIsolation:
    def test_create_project_is_tagged_with_workspace(self):
        db = _FakeDB()
        service = _make_service(db)
        try:
            project = _run(service.create_project(WS_A, USER_A, _project_payload()))
            assert project.workspace_id == WS_A
            assert project.owner_id == USER_A
            stored = db["projects"].docs[0]
            assert stored["workspace_id"] == WS_A
        finally:
            _teardown(service)

    def test_workspace_b_cannot_read_workspace_a_project(self):
        db = _FakeDB()
        service = _make_service(db)
        try:
            project = _run(service.create_project(WS_A, USER_A, _project_payload()))
            # Same project id, queried from workspace B → must be None (404 path).
            result = _run(service.get_project(WS_B, project.id))
            assert result is None
        finally:
            _teardown(service)

    def test_workspace_b_cannot_update_workspace_a_project(self):
        db = _FakeDB()
        service = _make_service(db)
        try:
            project = _run(service.create_project(WS_A, USER_A, _project_payload()))
            from db.schemas_projects import ProjectUpdate

            result = _run(
                service.update_project(
                    WS_B, project.id, ProjectUpdate(name="Hacked name")
                )
            )
            assert result is None
            # Original untouched.
            assert db["projects"].docs[0]["name"] == "Churn Q3"
        finally:
            _teardown(service)

    def test_workspace_b_cannot_delete_workspace_a_project(self):
        db = _FakeDB()
        service = _make_service(db)
        try:
            project = _run(service.create_project(WS_A, USER_A, _project_payload()))
            deleted = _run(service.delete_project(WS_B, project.id))
            assert deleted is False
            assert len(db["projects"].docs) == 1
        finally:
            _teardown(service)

    def test_list_projects_is_workspace_scoped(self):
        db = _FakeDB()
        service = _make_service(db)
        try:
            _run(service.create_project(WS_A, USER_A, _project_payload("A-only")))
            _run(service.create_project(WS_B, USER_B, _project_payload("B-only")))
            list_a = _run(service.list_projects(WS_A, USER_A))
            list_b = _run(service.list_projects(WS_B, USER_B))
            assert [p.name for p in list_a] == ["A-only"]
            assert [p.name for p in list_b] == ["B-only"]
        finally:
            _teardown(service)

    def test_get_project_with_real_objectid_id(self):
        """
        Regression: Mongo auto-generates ObjectIds for ``_id`` — a raw string
        from the URL never matches. Seeding a doc with a real ObjectId and
        querying by its stringified form must find it (production shape).
        """
        from datetime import datetime

        from bson import ObjectId

        oid = ObjectId()
        db = _FakeDB(
            {
                "projects": [
                    {
                        "_id": oid,
                        "workspace_id": WS_A,
                        "owner_id": USER_A,
                        "name": "ObjId project",
                        "problem_statement": "",
                        "status": "draft",
                        "source_count": 0,
                        "cell_count": 0,
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                ]
            }
        )
        service = _make_service(db)
        try:
            # Stringified ObjectId (exactly what the URL path carries).
            project = _run(service.get_project(WS_A, str(oid)))
            assert project is not None
            assert project.id == str(oid)
            assert project.name == "ObjId project"
            # Wrong workspace still cannot see it.
            assert _run(service.get_project(WS_B, str(oid))) is None
        finally:
            _teardown(service)


# ─────────────────────────────────────────────────────────────────────────────
# 2. BINDING VALIDATION (anti-bucket)
# ─────────────────────────────────────────────────────────────────────────────


class TestBindingValidation:
    def _bind(self, service, project_id, ref, kind="data"):
        return _run(
            service.bind_source(
                WS_A,
                project_id,
                USER_A,
                ProjectSourceCreate(kind=kind, ref=SourceRef(**ref)),
            )
        )

    def test_rejects_missing_db_connection(self):
        db = _FakeDB()  # no db_connections seeded
        service = _make_service(db)
        try:
            project = _run(service.create_project(WS_A, USER_A, _project_payload()))
            try:
                self._bind(service, project.id, {"connection_type": "database", "conn_id": "conn-missing"})
                assert False, "expected ValueError for missing connection"
            except ValueError as e:
                assert "not found" in str(e)
        finally:
            _teardown(service)

    def test_rejects_cross_workspace_dataset(self):
        # Dataset lives in workspace A. Binding to workspace B's project must fail.
        db = _FakeDB(
            {
                "uploads": [
                    {"_id": "ds-A", "workspace_id": WS_A, "name": "A data"},
                ]
            }
        )
        service = _make_service(db)
        try:
            # Project created in WS_A (so it exists) — but attempt binding from
            # a WS_B context is simulated by seeding a WS_B project.
            project_b = _run(service.create_project(WS_B, USER_B, _project_payload("B")))
            try:
                _run(
                    service.bind_source(
                        WS_B,
                        project_b.id,
                        USER_B,
                        ProjectSourceCreate(
                            kind="data",
                            ref=SourceRef(connection_type="file", dataset_id="ds-A"),
                        ),
                    )
                )
                assert False, "expected ValueError for cross-workspace dataset"
            except ValueError as e:
                assert "not found in this workspace" in str(e)
        finally:
            _teardown(service)

    def test_binds_existing_connection(self):
        db = _FakeDB(
            {
                "db_connections": [
                    {"_id": "conn-1", "user_id": USER_A, "name": "prod-db", "db_type": "postgresql"},
                ]
            }
        )
        service = _make_service(db)
        try:
            project = _run(service.create_project(WS_A, USER_A, _project_payload()))
            source = self._bind(
                service,
                project.id,
                {"connection_type": "database", "conn_id": "conn-1", "table": "users"},
            )
            assert source.project_id == project.id
            assert source.ref.conn_id == "conn-1"
            assert source.sync["status"] == "idle"
            assert db["projects"].docs[0]["source_count"] == 1
        finally:
            _teardown(service)

    def test_rejects_dlt_without_source_type(self):
        db = _FakeDB(
            {
                "db_connections": [
                    {"_id": "conn-slack", "user_id": USER_A, "name": "slack"},
                ]
            }
        )
        service = _make_service(db)
        try:
            project = _run(service.create_project(WS_A, USER_A, _project_payload()))
            try:
                self._bind(service, project.id, {"connection_type": "dlt", "conn_id": "conn-slack"})
                assert False, "expected ValueError for missing source_type"
            except ValueError as e:
                assert "source_type is required" in str(e)
        finally:
            _teardown(service)


# ─────────────────────────────────────────────────────────────────────────────
# 3. JOURNEY RESILIENCE (LLM down → safe fallback, no 500)
# ─────────────────────────────────────────────────────────────────────────────


class TestJourneyFallback:
    def test_llm_failure_returns_safe_fallback(self):
        db = _FakeDB()
        service = _make_service(db)
        try:
            project = _run(service.create_project(WS_A, USER_A, _project_payload()))

            class _FailingRouter:
                async def call(self, **kwargs):
                    raise RuntimeError("llm down")

            # Patch the ThinkerAgent's llm_router property so BOTH mece_analysis
            # and derive_next_question hit the failing router. Both methods have
            # internal try/except → the journey must degrade, not 500.
            import services.thinker.thinker_agent as thinker_mod

            with mock.patch.object(
                thinker_mod.ThinkerAgent,
                "llm_router",
                new_callable=mock.PropertyMock,
                return_value=_FailingRouter(),
            ):
                with mock.patch(
                    "agents.belief.belief_store.get_belief_store",
                    return_value=mock.Mock(),
                ):
                    result = _run(
                        service.journey_next_question(
                            WS_A, project.id, USER_A
                        )
                    )

            assert result["next_question"]["question"], "fallback question must be non-empty"
            assert result["next_question"]["priority"] in ("high", "medium", "low")
            assert result["answered_count"] == 0
        finally:
            _teardown(service)

    def test_uses_project_name_as_problem_fallback(self):
        """
        The project name doubles as the problem when no explicit problem
        statement is set — the journey still works (LLM mocked to fail so
        no real network call happens).
        """
        db = _FakeDB()
        service = _make_service(db)
        try:
            project = _run(
                service.create_project(WS_A, USER_A, ProjectCreate(name="Why churn up"))
            )

            class _FailingRouter:
                async def call(self, **kwargs):
                    raise RuntimeError("llm down")

            import services.thinker.thinker_agent as thinker_mod

            with mock.patch.object(
                thinker_mod.ThinkerAgent,
                "llm_router",
                new_callable=mock.PropertyMock,
                return_value=_FailingRouter(),
            ):
                with mock.patch(
                    "agents.belief.belief_store.get_belief_store",
                    return_value=mock.Mock(),
                ):
                    result = _run(
                        service.journey_next_question(WS_A, project.id, USER_A)
                    )

            assert result["next_question"]["question"]
        finally:
            _teardown(service)


# ─────────────────────────────────────────────────────────────────────────────
# 4. CONTEXT RULE PROVENANCE (statefulness)
# ─────────────────────────────────────────────────────────────────────────────


class TestContextRuleProvenance:
    def test_rule_written_to_belief_store_with_manual_rule_source(self):
        db = _FakeDB()
        service = _make_service(db)
        try:
            project = _run(service.create_project(WS_A, USER_A, _project_payload()))

            fake_store = mock.Mock()
            fake_store.add_belief = mock.AsyncMock(return_value="belief-1")

            with mock.patch(
                "agents.belief.belief_store.get_belief_store",
                return_value=fake_store,
            ):
                belief_id = _run(
                    service.add_context_rule(
                        WS_A,
                        project.id,
                        USER_A,
                        "Churn = cancelled + failed renewal, not free trials",
                    )
                )

            assert belief_id == "belief-1"
            # Written to the belief store with the right source.
            fake_store.add_belief.assert_called_once()
            kwargs = fake_store.add_belief.call_args.kwargs
            assert kwargs["source"] == "manual_rule"
            assert kwargs["confidence"] == 0.95

            # Bound to the project as a context source with provenance.
            source = db["project_sources"].docs[0]
            assert source["kind"] == "context"
            assert source["ref"]["belief_id"] == "belief-1"
            assert source["ref"]["connection_type"] == "document"
            assert db["projects"].docs[0]["source_count"] == 1
        finally:
            _teardown(service)

    def test_rejects_empty_rule(self):
        db = _FakeDB()
        service = _make_service(db)
        try:
            project = _run(service.create_project(WS_A, USER_A, _project_payload()))
            try:
                _run(service.add_context_rule(WS_A, project.id, USER_A, "   "))
                assert False, "expected ValueError for empty rule"
            except ValueError as e:
                assert "rule_text is required" in str(e)
        finally:
            _teardown(service)


# ─────────────────────────────────────────────────────────────────────────────
# CELLS (journey persistence)
# ─────────────────────────────────────────────────────────────────────────────


class TestCells:
    def test_cells_get_incrementing_order(self):
        db = _FakeDB()
        service = _make_service(db)
        try:
            project = _run(service.create_project(WS_A, USER_A, _project_payload()))
            c1 = _run(
                service.add_cell(
                    WS_A,
                    project.id,
                    ProjectCellCreate(kind="question", question="What drove churn?"),
                )
            )
            c2 = _run(
                service.add_cell(
                    WS_A,
                    project.id,
                    ProjectCellCreate(
                        kind="answer", answer_md="West region dropped 20%."
                    ),
                )
            )
            assert c1.order == 1
            assert c2.order == 2

            cells = _run(service.list_cells(WS_A, project.id))
            assert [c.order for c in cells] == [1, 2]
            # Answer becomes evidence for the journey.
            answered = [c for c in cells if c.answer_md]
            assert len(answered) == 1
            assert answered[0].answer_md == "West region dropped 20%."
        finally:
            _teardown(service)

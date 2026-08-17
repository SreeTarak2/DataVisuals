"""
ProjectService — the analysis container (one problem / one journey).

Design (docs/NOTEBOOK_WORKSPACE.md):
- A project is the container; datasets/connections/context materials are
  bound into it as sources — REFERENCES to existing infrastructure, never
  re-created connections.
- Two source kinds: ``data`` (analyzed) and ``context`` (informs the AI via
  the belief store).
- ``journey_next_question`` implements the "hard questions throughout the
  journey" loop: MECE-decompose the problem, ground the next pivotal
  question in findings already in the project + beliefs.

All reads/writes are tenant-scoped via ``tenant_scope_query``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

from db.database import get_database
from db.schemas_projects import (
    Project,
    ProjectCell,
    ProjectCellUpdate,
    ProjectCreate,
    ProjectSource,
    ProjectSourceCreate,
    ProjectSummary,
    ProjectUpdate,
)
from db.tenant_guard import tenant_scope_query

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_str_id(doc_id: Any) -> str:
    return str(doc_id)


def _as_id(value: Any) -> Any:
    """
    Normalize a string id for ``_id`` queries.

    MongoDB auto-generates ObjectIds for ``_id`` on insert, so a raw string
    from a URL path never matches. Convert to ObjectId when the string is a
    valid 24-hex id; pass through otherwise (string-``_id`` docs, and the
    string-id fake DB used in unit tests, keep working).
    """
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return value


class ProjectService:
    """Tenant-scoped CRUD + binding + journey for the project workspace."""

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    async def create_project(
        self,
        workspace_id: str,
        owner_id: str,
        payload: ProjectCreate,
    ) -> Project:
        db = get_database()
        doc = {
            "workspace_id": str(workspace_id),
            "owner_id": owner_id,
            "name": payload.name,
            "problem_statement": payload.problem_statement or "",
            "status": "draft",
            "source_count": 0,
            "cell_count": 0,
            "created_at": _now(),
            "updated_at": _now(),
        }
        result = await db.projects.insert_one(doc)
        doc["_id"] = result.inserted_id
        logger.info(
            "Created project '%s' (%s) in workspace %s",
            payload.name,
            _to_str_id(result.inserted_id)[:8],
            str(workspace_id)[:8],
        )
        return self._to_project(doc)

    async def get_project(self, workspace_id: str, project_id: str) -> Optional[Project]:
        db = get_database()
        query = tenant_scope_query("projects", {"_id": _as_id(project_id)}, workspace_id)
        doc = await db.projects.find_one(query)
        return self._to_project(doc) if doc else None

    async def list_projects(
        self,
        workspace_id: str,
        owner_id: Optional[str] = None,
    ) -> List[ProjectSummary]:
        db = get_database()
        base: Dict[str, Any] = {}
        if owner_id:
            base["owner_id"] = owner_id
        query = tenant_scope_query("projects", base, workspace_id)
        docs = []
        async for doc in db.projects.find(query).sort("updated_at", -1):
            docs.append(self._to_summary(doc))
        return docs

    async def update_project(
        self,
        workspace_id: str,
        project_id: str,
        payload: ProjectUpdate,
    ) -> Optional[Project]:
        db = get_database()
        query = tenant_scope_query("projects", {"_id": _as_id(project_id)}, workspace_id)
        update: Dict[str, Any] = {
            "updated_at": _now(),
        }
        for field in ("name", "problem_statement", "status"):
            value = getattr(payload, field, None)
            if value is not None:
                update[field] = value
        result = await db.projects.update_one(query, {"$set": update})
        if result.modified_count == 0 and result.matched_count == 0:
            return None
        return await self.get_project(workspace_id, project_id)

    async def delete_project(self, workspace_id: str, project_id: str) -> bool:
        """Delete a project and cascade its sources + cells (all tenant-scoped)."""
        db = get_database()
        query = tenant_scope_query("projects", {"_id": _as_id(project_id)}, workspace_id)
        result = await db.projects.delete_one(query)
        if result.deleted_count == 0:
            return False
        await db.project_sources.delete_many(
            tenant_scope_query("project_sources", {"project_id": project_id}, workspace_id)
        )
        await db.project_cells.delete_many(
            tenant_scope_query("project_cells", {"project_id": project_id}, workspace_id)
        )
        return True

    # ------------------------------------------------------------------
    # Sources (the context binder)
    # ------------------------------------------------------------------

    async def bind_source(
        self,
        workspace_id: str,
        project_id: str,
        user_id: str,
        payload: ProjectSourceCreate,
    ) -> ProjectSource:
        """
        Bind a source to a project.

        The ref must point at EXISTING infrastructure:
        - database/dlt  → a row in ``db_connections`` owned by the user
        - file/sheets   → an upload doc in the workspace
        - document      → free-text context (ingested into beliefs separately)

        Never creates a connection. Raises ValueError if the ref is invalid.
        """
        db = get_database()
        project = await self.get_project(workspace_id, project_id)
        if not project:
            raise ValueError("Project not found")

        await self._validate_ref(user_id, workspace_id, payload.ref)

        doc = {
            "workspace_id": str(workspace_id),
            "project_id": project_id,
            "kind": payload.kind,
            "ref": payload.ref.model_dump(exclude_none=True),
            "sync": {
                "status": "idle",
                "last_sync_at": None,
                "watermark": None,
                "next_sync": "on_demand",
                "error": None,
            },
            "created_at": _now(),
        }
        result = await db.project_sources.insert_one(doc)
        doc["_id"] = result.inserted_id
        await db.projects.update_one(
            tenant_scope_query("projects", {"_id": _as_id(project_id)}, workspace_id),
            {"$inc": {"source_count": 1}, "$set": {"updated_at": _now()}},
        )
        logger.info(
            "Bound %s source (%s) to project %s",
            payload.kind,
            payload.ref.connection_type,
            project_id[:8],
        )
        return self._to_source(doc)

    async def _validate_ref(self, user_id: str, workspace_id: str, ref) -> None:
        """Validate a source ref points at something that actually exists."""
        db = get_database()

        if ref.connection_type in ("database", "dlt"):
            if not ref.conn_id:
                raise ValueError("conn_id is required for database/dlt sources")
            # db_connections is user-scoped (not in TENANT_SCOPED_COLLECTIONS).
            conn = await db.db_connections.find_one(
                {"_id": _as_id(ref.conn_id), "user_id": user_id}
            )
            if not conn:
                raise ValueError(
                    f"Connection {ref.conn_id[:8]} not found for this user"
                )
            if ref.connection_type == "dlt" and not ref.source_type:
                raise ValueError("source_type is required for dlt sources")

        elif ref.connection_type in ("file", "google_sheets"):
            if not ref.dataset_id:
                raise ValueError("dataset_id is required for file/sheets sources")
            query = tenant_scope_query("uploads", {"_id": _as_id(ref.dataset_id)}, workspace_id)
            dataset = await db.uploads.find_one(query)
            if not dataset:
                raise ValueError(
                    f"Dataset {str(ref.dataset_id)[:8]} not found in this workspace"
                )

        elif ref.connection_type == "document":
            if not ref.document_text or not ref.document_text.strip():
                raise ValueError("document_text is required for document sources")
        else:  # pragma: no cover - schema restricts the literal
            raise ValueError(f"Unsupported connection_type: {ref.connection_type}")

    async def list_sources(
        self,
        workspace_id: str,
        project_id: str,
    ) -> List[ProjectSource]:
        db = get_database()
        query = tenant_scope_query(
            "project_sources", {"project_id": project_id}, workspace_id
        )
        docs = []
        async for doc in db.project_sources.find(query).sort("created_at", 1):
            docs.append(self._to_source(doc))
        return docs

    async def sync_source(
        self,
        workspace_id: str,
        project_id: str,
        source_id: str,
        user_id: str,
    ) -> ProjectSource:
        """
        Trigger a sync on a bound source.

        Delegates to the EXISTING incremental machinery (dlt runner / DB
        extractor) — never a bespoke fetch. On failure the source's sync
        state records the error and the project continues (graceful
        degradation).
        """
        db = get_database()
        query = tenant_scope_query(
            "project_sources", {"_id": _as_id(source_id), "project_id": project_id}, workspace_id
        )
        doc = await db.project_sources.find_one(query)
        if not doc:
            raise ValueError("Source not found")

        ref = doc.get("ref", {})
        connection_type = ref.get("connection_type", "")

        # Mark as syncing
        await db.project_sources.update_one(
            query,
            {
                "$set": {
                    "sync.status": "syncing",
                    "sync.last_sync_at": None,
                    "sync.error": None,
                }
            },
        )

        try:
            sync_result = await self._run_sync(user_id, workspace_id, connection_type, ref)
            watermark = (sync_result or {}).get("watermark")
            sync = {
                "status": "ok",
                "last_sync_at": _now().isoformat(),
                "watermark": watermark,
                # The materialized dataset this sync produced — lets the project
                # dashboard compose this source's analytics.
                "dataset_id": (sync_result or {}).get("dataset_id"),
                "next_sync": "on_demand",
                "error": None,
            }
        except Exception as e:  # graceful: one failing source never blocks
            logger.warning(
                "Sync failed for source %s (%s): %s",
                source_id[:8],
                connection_type,
                e,
            )
            sync = {
                "status": "error",
                "last_sync_at": None,
                "watermark": None,
                "next_sync": "on_demand",
                "error": str(e)[:500],
            }

        await db.project_sources.update_one(query, {"$set": {"sync": sync}})
        updated = await db.project_sources.find_one(query)
        return self._to_source(updated)

    async def _run_sync(
        self,
        user_id: str,
        workspace_id: str,
        connection_type: str,
        ref: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Run the actual sync via existing machinery. Returns {watermark, dataset_id}."""
        if connection_type in ("file", "google_sheets", "document"):
            # Already materialized — nothing to fetch. For file/sheets the ref
            # already carries the dataset id.
            return {"watermark": None, "dataset_id": ref.get("dataset_id")}

        if connection_type == "dlt":
            from services.dlt.runner import dlt_runner

            conn_id = ref.get("conn_id")
            source_type = ref.get("source_type", "")
            credentials = await dlt_runner._load_credentials(
                user_id, conn_id, source_type
            )
            result = await dlt_runner.run_sync(
                user_id=user_id,
                conn_id=conn_id,
                source_type=source_type,
                credentials=credentials,
                dataset_name="",
                incremental=True,
                workspace_id=workspace_id,
            )
            return {"watermark": result.schema_hash, "dataset_id": result.dataset_id}

        if connection_type == "database":
            from services.databases.db_connection_service import db_connection_service

            result = await db_connection_service.extract_to_dataset(
                user_id=user_id,
                conn_id=ref.get("conn_id"),
                table_name=ref.get("table"),
                custom_query=None,
                dataset_name="",
                row_limit=100000,
                workspace_id=workspace_id,
            )
            return {
                "watermark": (result or {}).get("schema_hash"),
                "dataset_id": (result or {}).get("dataset_id"),
            }

        raise ValueError(f"No sync path for connection_type={connection_type}")

    # ------------------------------------------------------------------
    # Cells (the journey)
    # ------------------------------------------------------------------

    async def add_cell(
        self,
        workspace_id: str,
        project_id: str,
        payload: ProjectCellUpdate | None = None,
        **kwargs,
    ) -> ProjectCell:
        db = get_database()
        project = await self.get_project(workspace_id, project_id)
        if not project:
            raise ValueError("Project not found")

        # Next order value
        last = (
            await db.project_cells.find(
                tenant_scope_query(
                    "project_cells", {"project_id": project_id}, workspace_id
                )
            )
            .sort("order", -1)
            .limit(1)
            .to_list(length=1)
        )
        order = (last[0].get("order", 0) + 1) if last else 1

        if payload is not None:
            data = payload.model_dump(exclude_none=True)
        else:
            data = {k: v for k, v in kwargs.items() if v is not None}

        doc = {
            "workspace_id": str(workspace_id),
            "project_id": project_id,
            "kind": data.pop("kind", "question"),
            "question": data.pop("question", None),
            "answer_md": data.pop("answer_md", None),
            "provenance": data.pop("provenance", None) or {},
            "status": data.pop("status", "pending"),
            "order": order,
            "created_at": _now(),
            "updated_at": _now(),
        }
        result = await db.project_cells.insert_one(doc)
        doc["_id"] = result.inserted_id
        await db.projects.update_one(
            tenant_scope_query("projects", {"_id": _as_id(project_id)}, workspace_id),
            {"$inc": {"cell_count": 1}, "$set": {"updated_at": _now()}},
        )
        return self._to_cell(doc)

    async def list_cells(
        self,
        workspace_id: str,
        project_id: str,
    ) -> List[ProjectCell]:
        db = get_database()
        query = tenant_scope_query(
            "project_cells", {"project_id": project_id}, workspace_id
        )
        docs = []
        async for doc in db.project_cells.find(query).sort("order", 1):
            docs.append(self._to_cell(doc))
        return docs

    async def update_cell(
        self,
        workspace_id: str,
        project_id: str,
        cell_id: str,
        payload: ProjectCellUpdate,
    ) -> Optional[ProjectCell]:
        db = get_database()
        query = tenant_scope_query(
            "project_cells", {"_id": _as_id(cell_id), "project_id": project_id}, workspace_id
        )
        update: Dict[str, Any] = {"updated_at": _now()}
        for field in ("question", "answer_md", "status"):
            value = getattr(payload, field, None)
            if value is not None:
                update[field] = value
        if payload.provenance is not None:
            update["provenance"] = payload.provenance.model_dump(exclude_none=True)
        result = await db.project_cells.update_one(query, {"$set": update})
        if result.modified_count == 0 and result.matched_count == 0:
            return None
        doc = await db.project_cells.find_one(query)
        return self._to_cell(doc) if doc else None

    # ------------------------------------------------------------------
    # Journey — next pivotal question
    # ------------------------------------------------------------------

    async def journey_next_question(
        self,
        workspace_id: str,
        project_id: str,
        user_id: str,
        problem_statement: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        The "hard questions throughout the journey" loop.

        1. Load the project (problem statement is the problem).
        2. MECE-decompose the problem (ThinkerAgent.mece_analysis).
        3. Gather answered cells (question + answer) as evidence.
        4. Load relevant beliefs (business rules / corrections).
        5. Derive the NEXT pivotal question grounded in evidence.

        Pure backend — fully testable without the frontend.
        """
        project = await self.get_project(workspace_id, project_id)
        if not project:
            raise ValueError("Project not found")

        problem = (problem_statement or project.problem_statement or project.name).strip()
        if not problem:
            raise ValueError(
                "Set a problem statement first — the journey needs a problem to decompose."
            )

        cells = await self.list_cells(workspace_id, project_id)
        answered = [
            {
                "question": c.question,
                "answer": (c.answer_md or "")[:1500],
            }
            for c in cells
            if c.kind in ("question", "answer") and c.answer_md
        ]

        beliefs_context = await self._load_beliefs_context(user_id, problem)

        from services.thinker.thinker_agent import ThinkerAgent

        thinker = ThinkerAgent()
        decomposition = await thinker.mece_analysis(
            problem=problem,
            data_context=None,
        )
        components = decomposition.get("components", []) if isinstance(
            decomposition, dict
        ) else []

        next_q = await thinker.derive_next_question(
            problem=problem,
            components=components,
            answered=answered,
            beliefs_context=beliefs_context,
        )

        return {
            "next_question": next_q,
            "decomposition": components,
            "answered_count": len(answered),
        }

    async def _load_beliefs_context(self, user_id: str, problem: str) -> str:
        """Load business rules / corrections relevant to the problem."""
        try:
            from agents.belief.belief_store import get_belief_store

            belief_store = get_belief_store()
            similar = await belief_store.query_similar_beliefs(
                user_id=user_id,
                query_text=problem,
                n_results=4,
            )
            lines = [
                (b.get("document") or b.get("belief_text") or "").strip()
                for b in similar
                if (b.get("document") or b.get("belief_text") or "").strip()
            ]
            return "\n".join(lines[:4]) if lines else ""
        except Exception as e:  # non-critical — journey still works without beliefs
            logger.debug("Belief context unavailable: %s", e)
            return ""

    # ------------------------------------------------------------------
    # Context ingestion → belief store
    # ------------------------------------------------------------------

    async def add_context_rule(
        self,
        workspace_id: str,
        project_id: str,
        user_id: str,
        rule_text: str,
    ) -> str:
        """
        Add a manual business rule as a context source.

        The rule is ingested into the belief store (source='manual_rule') so
        it informs future answers — and bound to the project as a context
        source so the journey is visible.
        """
        db = get_database()
        project = await self.get_project(workspace_id, project_id)
        if not project:
            raise ValueError("Project not found")
        if not rule_text or not rule_text.strip():
            raise ValueError("rule_text is required")

        from agents.belief.belief_store import get_belief_store

        belief_store = get_belief_store()
        belief_id = await belief_store.add_belief(
            user_id=user_id,
            belief_text=rule_text.strip(),
            source="manual_rule",
            confidence=0.95,
        )

        doc = {
            "workspace_id": str(workspace_id),
            "project_id": project_id,
            "kind": "context",
            "ref": {
                "connection_type": "document",
                "document_text": rule_text.strip(),
                "belief_id": belief_id,
            },
            "sync": {
                "status": "ok",
                "last_sync_at": _now().isoformat(),
                "watermark": None,
                "next_sync": "on_demand",
                "error": None,
            },
            "created_at": _now(),
        }
        result = await db.project_sources.insert_one(doc)
        await db.projects.update_one(
            tenant_scope_query("projects", {"_id": _as_id(project_id)}, workspace_id),
            {"$inc": {"source_count": 1}, "$set": {"updated_at": _now()}},
        )
        logger.info("Added context rule (belief %s) to project %s", belief_id[:8], project_id[:8])
        return belief_id

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @staticmethod
    def _to_project(doc: Dict[str, Any]) -> Project:
        return Project(
            id=_to_str_id(doc["_id"]),
            workspace_id=str(doc["workspace_id"]),
            owner_id=doc["owner_id"],
            name=doc.get("name", ""),
            problem_statement=doc.get("problem_statement"),
            status=doc.get("status", "draft"),
            source_count=doc.get("source_count", 0),
            cell_count=doc.get("cell_count", 0),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )

    @staticmethod
    def _to_summary(doc: Dict[str, Any]) -> ProjectSummary:
        return ProjectSummary(
            id=_to_str_id(doc["_id"]),
            name=doc.get("name", ""),
            problem_statement=doc.get("problem_statement"),
            status=doc.get("status", "draft"),
            source_count=doc.get("source_count", 0),
            cell_count=doc.get("cell_count", 0),
            updated_at=doc["updated_at"],
        )

    @staticmethod
    def _to_source(doc: Dict[str, Any]) -> ProjectSource:
        return ProjectSource(
            id=_to_str_id(doc["_id"]),
            project_id=doc["project_id"],
            workspace_id=str(doc["workspace_id"]),
            kind=doc.get("kind", "data"),
            ref=doc.get("ref", {}),
            sync=doc.get("sync", {}),
            created_at=doc["created_at"],
        )

    @staticmethod
    def _to_cell(doc: Dict[str, Any]) -> ProjectCell:
        return ProjectCell(
            id=_to_str_id(doc["_id"]),
            project_id=doc["project_id"],
            workspace_id=str(doc["workspace_id"]),
            kind=doc.get("kind", "question"),
            question=doc.get("question"),
            answer_md=doc.get("answer_md"),
            provenance=doc.get("provenance", {}) or {},
            status=doc.get("status", "pending"),
            order=doc.get("order", 0),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )


project_service = ProjectService()

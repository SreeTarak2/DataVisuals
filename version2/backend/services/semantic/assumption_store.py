"""
semantic/assumption_store.py — Ontology assumption state machine
================================================================

Implements the "Act-then-Validate" contract (80/20 rule):

  - The system ACTS on every inference — hierarchies, relationships,
    metric definitions are all APPLIED, never withheld pending a question.
  - The human VALIDATES finished results: one-click confirm/reject/fix.
  - Validated assumptions become the governed ontology consumed by
    drill-down, cross-filter, and answer synthesis. Rejected assumptions
    are remembered so the same inference never repeats.

States
------
- ``provisional`` — applied and used, but flagged for review (evidence shown)
- ``validated``   — confirmed (human sign-off or high-confidence deterministic pass)
- ``rejected``    — human rejected; inference is not used and is remembered

Sources
-------
- ``deterministic_pattern`` — pattern/cardinality verified, no LLM (auto-validated)
- ``llm_suggestion``        — LLM proposed, determinism verified
- ``user_defined``          — user fixed/defined the assumption manually

Storage
-------
MongoDB collection ``semantic_assumptions``, tenant-scoped via ``workspace_id``
(registered in ``db/tenant_guard.TENANT_SCOPED_COLLECTIONS`` — every read/write
is workspace-bound; cross-workspace access raises ``TenantIsolationError``).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ─── States ──────────────────────────────────────────────────────────────────

PROVISIONAL = "provisional"
VALIDATED = "validated"
REJECTED = "rejected"
STATES = (PROVISIONAL, VALIDATED, REJECTED)

# ─── Sources ─────────────────────────────────────────────────────────────────

SOURCE_DETERMINISTIC = "deterministic_pattern"
SOURCE_LLM = "llm_suggestion"
SOURCE_USER = "user_defined"

# ─── Types ───────────────────────────────────────────────────────────────────

TYPE_HIERARCHY = "hierarchy"
TYPE_RELATIONSHIP = "relationship"
TYPE_METRIC = "metric_definition"
TYPES = (TYPE_HIERARCHY, TYPE_RELATIONSHIP, TYPE_METRIC)


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


class SemanticAssumption(BaseModel):
    """A single ontology assumption with its lifecycle state."""

    assumption_id: str
    dataset_id: str
    workspace_id: str = ""
    user_id: str = ""
    type: str = TYPE_HIERARCHY                     # hierarchy | relationship | metric_definition
    definition: dict[str, Any] = Field(default_factory=dict)  # e.g. {"columns": [...]}
    confidence: float = 0.0
    evidence: dict[str, Any] = Field(default_factory=dict)    # e.g. {"cardinality": "5 → 49", ...}
    state: str = PROVISIONAL
    source: str = SOURCE_LLM
    description: str = ""
    created_at: str = ""
    updated_at: str = ""

    def signature(self) -> str:
        """Stable identity key: type + definition (order-preserving)."""
        return f"{self.type}:{json.dumps(self.definition, sort_keys=True, default=str)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "assumption_id": self.assumption_id,
            "dataset_id": self.dataset_id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "type": self.type,
            "definition": self.definition,
            "confidence": round(self.confidence, 3),
            "evidence": self.evidence,
            "state": self.state,
            "source": self.source,
            "description": self.description,
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SemanticAssumption":
        return cls(**data)


def new_assumption(
    dataset_id: str,
    workspace_id: str,
    type: str,
    definition: dict[str, Any],
    confidence: float,
    evidence: dict[str, Any],
    state: str = PROVISIONAL,
    source: str = SOURCE_LLM,
    description: str = "",
    user_id: str = "",
    assumption_id: Optional[str] = None,
) -> SemanticAssumption:
    """Build a SemanticAssumption with auto-generated id/timestamps."""
    now = _now()
    return SemanticAssumption(
        assumption_id=assumption_id or f"asmp_{dataset_id[:8]}_{abs(hash(type + json.dumps(definition, sort_keys=True, default=str))) & 0xFFFF:04x}",
        dataset_id=dataset_id,
        workspace_id=workspace_id,
        user_id=user_id,
        type=type,
        definition=definition,
        confidence=confidence,
        evidence=evidence,
        state=state,
        source=source,
        description=description,
        created_at=now,
        updated_at=now,
    )


class SemanticAssumptionStore:
    """Persistent store for ontology assumptions (state machine)."""

    MONGO_COLLECTION = "semantic_assumptions"

    def _get_mongo(self):
        from db.database import get_database

        return get_database()

    # ─── Persistence ────────────────────────────────────────────────────

    async def upsert(self, assumption: SemanticAssumption) -> SemanticAssumption:
        """Insert or update by (dataset_id, signature). State transitions:
        - A validated/rejected assumption is never silently downgraded by a
          regeneration (only drift re-verification or the user changes it).
        - Provisional assumptions are refreshed freely.
        """
        mongo = self._get_mongo()
        coll = mongo[self.MONGO_COLLECTION]

        existing = await coll.find_one(
            {
                "dataset_id": assumption.dataset_id,
                "workspace_id": assumption.workspace_id,
                "type": assumption.type,
                "definition": assumption.definition,
            }
        )

        doc = assumption.to_dict()

        if existing:
            prior_state = existing.get("state", PROVISIONAL)
            prior_source = existing.get("source", "")
            keep_prior = prior_state in (VALIDATED, REJECTED) and prior_source != SOURCE_USER
            if keep_prior and prior_state == VALIDATED:
                # Regeneration proposes a new confidence/evidence — keep the
                # validated state but refresh evidence so the UI stays current.
                doc["state"] = VALIDATED
                doc["evidence"] = assumption.evidence or existing.get("evidence", {})
            elif keep_prior and prior_state == REJECTED:
                # A rejected assumption stays rejected — but a HIGH-confidence
                # deterministic re-discovery may legitimately resurrect it.
                if assumption.confidence >= 0.85 and assumption.source == SOURCE_DETERMINISTIC:
                    doc["state"] = PROVISIONAL
                else:
                    return SemanticAssumption.from_dict(existing)
            doc["assumption_id"] = existing.get("assumption_id", doc["assumption_id"])
            doc["created_at"] = existing.get("created_at", doc["created_at"])
            doc["updated_at"] = _now()
            await coll.update_one(
                {"_id": existing["_id"]},
                {"$set": doc},
            )
            return SemanticAssumption.from_dict(doc)

        await coll.insert_one(doc)
        return assumption

    async def list(
        self,
        dataset_id: str,
        workspace_id: str,
        state: Optional[str] = None,
        type: Optional[str] = None,
    ) -> list[SemanticAssumption]:
        """List assumptions for a dataset (workspace-scoped)."""
        from db.tenant_guard import tenant_scope_query

        base: dict[str, Any] = {"dataset_id": dataset_id}
        if state:
            base["state"] = state
        if type:
            base["type"] = type

        query = tenant_scope_query(self.MONGO_COLLECTION, base, workspace_id)
        mongo = self._get_mongo()
        docs = await mongo[self.MONGO_COLLECTION].find(query).sort("updated_at", -1).to_list(length=None)
        return [SemanticAssumption.from_dict(d) for d in docs]

    async def get(
        self,
        dataset_id: str,
        workspace_id: str,
        assumption_id: str,
    ) -> Optional[SemanticAssumption]:
        from db.tenant_guard import tenant_scope_query

        query = tenant_scope_query(
            self.MONGO_COLLECTION,
            {"dataset_id": dataset_id, "assumption_id": assumption_id},
            workspace_id,
        )
        mongo = self._get_mongo()
        doc = await mongo[self.MONGO_COLLECTION].find_one(query)
        return SemanticAssumption.from_dict(doc) if doc else None

    async def set_state(
        self,
        dataset_id: str,
        workspace_id: str,
        assumption_id: str,
        state: str,
        user_id: str = "",
    ) -> Optional[SemanticAssumption]:
        """Transition an assumption to a new state (validate/reject)."""
        if state not in STATES:
            raise ValueError(f"Invalid state: {state}")

        assumption = await self.get(dataset_id, workspace_id, assumption_id)
        if assumption is None:
            return None

        assumption.state = state
        assumption.updated_at = _now()
        if user_id:
            assumption.user_id = user_id
        # A human sign-off is the strongest evidence there is.
        if state == VALIDATED:
            assumption.confidence = max(assumption.confidence, 0.99)
            assumption.evidence = {**assumption.evidence, "validated_by": "user"}

        mongo = self._get_mongo()
        await mongo[self.MONGO_COLLECTION].update_one(
            {"dataset_id": dataset_id, "workspace_id": workspace_id, "assumption_id": assumption_id},
            {"$set": assumption.to_dict()},
        )
        return assumption

    async def update_definition(
        self,
        dataset_id: str,
        workspace_id: str,
        assumption_id: str,
        definition: dict[str, Any],
        description: str = "",
        user_id: str = "",
    ) -> Optional[SemanticAssumption]:
        """User fixes an assumption — becomes a user_defined, validated assumption."""
        assumption = await self.get(dataset_id, workspace_id, assumption_id)
        if assumption is None:
            return None

        assumption.definition = definition
        assumption.state = VALIDATED
        assumption.source = SOURCE_USER
        assumption.confidence = 1.0
        assumption.description = description or assumption.description
        assumption.updated_at = _now()
        if user_id:
            assumption.user_id = user_id
        assumption.evidence = {**assumption.evidence, "validated_by": "user"}

        mongo = self._get_mongo()
        await mongo[self.MONGO_COLLECTION].update_one(
            {"dataset_id": dataset_id, "workspace_id": workspace_id, "assumption_id": assumption_id},
            {"$set": assumption.to_dict()},
        )
        return assumption

    async def apply_drift(self, assumption: SemanticAssumption) -> SemanticAssumption:
        """Raw downgrade: a finalized assumption that no longer verifies against
        fresh data reverts to provisional and is flagged as drifted.

        Bypasses the keep-validated logic in ``upsert`` — drift is the one
        legitimately allowed to demote a validated assumption.
        """
        assumption.state = PROVISIONAL
        assumption.evidence = {
            **assumption.evidence,
            "drift_detected": True,
            "drifted_at": _now(),
        }
        assumption.updated_at = _now()
        mongo = self._get_mongo()
        await mongo[self.MONGO_COLLECTION].update_one(
            {
                "dataset_id": assumption.dataset_id,
                "workspace_id": assumption.workspace_id,
                "assumption_id": assumption.assumption_id,
            },
            {"$set": assumption.to_dict()},
        )
        return assumption

    async def delete(self, dataset_id: str, workspace_id: str, assumption_id: str) -> bool:
        from db.tenant_guard import tenant_scope_query

        query = tenant_scope_query(
            self.MONGO_COLLECTION,
            {"dataset_id": dataset_id, "assumption_id": assumption_id},
            workspace_id,
        )
        mongo = self._get_mongo()
        result = await mongo[self.MONGO_COLLECTION].delete_one(query)
        return result.deleted_count > 0

    async def delete_all(self, dataset_id: str, workspace_id: str) -> int:
        from db.tenant_guard import tenant_scope_query

        query = tenant_scope_query(self.MONGO_COLLECTION, {"dataset_id": dataset_id}, workspace_id)
        mongo = self._get_mongo()
        result = await mongo[self.MONGO_COLLECTION].delete_many(query)
        return result.deleted_count

    async def counts(
        self,
        dataset_id: str,
        workspace_id: str,
    ) -> dict[str, int]:
        """Summary counts for the review-queue badge."""
        from db.tenant_guard import tenant_scope_query

        query = tenant_scope_query(self.MONGO_COLLECTION, {"dataset_id": dataset_id}, workspace_id)
        mongo = self._get_mongo()
        docs = await mongo[self.MONGO_COLLECTION].find(query, {"state": 1}).to_list(length=None)
        counts = {PROVISIONAL: 0, VALIDATED: 0, REJECTED: 0}
        for d in docs:
            s = d.get("state", PROVISIONAL)
            counts[s] = counts.get(s, 0) + 1
        return counts


# Singleton — lazy DB init
assumption_store = SemanticAssumptionStore()

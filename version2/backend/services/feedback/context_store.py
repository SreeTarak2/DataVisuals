from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import uuid

from bson import ObjectId
from db.database import get_database
from db.schemas_context import (
    CorrectionRule,
    MetricMapping,
    UserQuery,
    UserMemory,
    InteractionEvent,
    SignalType,
    CorrectionScope,
)

logger = logging.getLogger(__name__)


class ContextStore:
    def _get_db(self):
        return get_database()

    async def init_indexes(self):
        db = self._get_db()
        await db.correction_rules.create_index(
            [("workspace_id", 1), ("original_term", 1)], unique=True
        )
        await db.metric_mappings.create_index(
            [("workspace_id", 1), ("term", 1)], unique=True
        )
        await db.user_queries.create_index([("workspace_id", 1), ("created_at", -1)])
        await db.user_memory.create_index(
            [("workspace_id", 1), ("user_id", 1)], unique=True
        )
        await db.interaction_events.create_index(
            [("workspace_id", 1), ("user_id", 1), ("created_at", -1)]
        )
        logger.info("Context store indexes created")

    async def add_correction_rule(
        self,
        original_term: str,
        corrected_term: str,
        interpretation: str,
        scope: CorrectionScope,
        workspace_id: str,
        user_id: str,
    ) -> CorrectionRule:
        rule = CorrectionRule(
            id=str(uuid.uuid4()),
            original_term=original_term,
            corrected_term=corrected_term,
            interpretation=interpretation,
            scope=scope,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        db = self._get_db()
        await db.correction_rules.insert_one(rule.model_dump(exclude={"id"}))
        logger.info(f"Added correction rule: {original_term} -> {corrected_term}")
        return rule

    async def get_correction_rules(
        self,
        workspace_id: str,
        original_term: Optional[str] = None,
    ) -> List[CorrectionRule]:
        query = {"workspace_id": workspace_id}
        if original_term:
            query["original_term"] = original_term
        db = self._get_db()
        cursor = db.correction_rules.find(query)
        docs = await cursor.to_list(length=100)
        rules = []
        for doc in docs:
            doc["id"] = str(doc.pop("_id"))
            rules.append(CorrectionRule(**doc))
        return rules

    async def update_correction_rule_usage(self, rule_id: str):
        db = self._get_db()
        await db.correction_rules.update_one(
            {"_id": ObjectId(rule_id)},
            {"$inc": {"usage_count": 1}, "$set": {"updated_at": datetime.utcnow()}},
        )

    async def add_metric_mapping(
        self,
        term: str,
        definition: str,
        workspace_id: str,
        user_id: str,
        source_column: Optional[str] = None,
        formula: Optional[str] = None,
    ) -> MetricMapping:
        mapping = MetricMapping(
            id=str(uuid.uuid4()),
            term=term,
            definition=definition,
            source_column=source_column,
            formula=formula,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        db = self._get_db()
        await db.metric_mappings.insert_one(mapping.model_dump(exclude={"id"}))
        logger.info(f"Added metric mapping: {term} = {definition}")
        return mapping

    async def get_metric_mappings(
        self,
        workspace_id: str,
        term: Optional[str] = None,
    ) -> List[MetricMapping]:
        query = {"workspace_id": workspace_id}
        if term:
            query["term"] = term
        db = self._get_db()
        cursor = db.metric_mappings.find(query)
        docs = await cursor.to_list(length=100)
        mappings = []
        for doc in docs:
            doc["id"] = str(doc.pop("_id"))
            mappings.append(MetricMapping(**doc))
        return mappings

    async def save_query(
        self,
        text: str,
        workspace_id: str,
        user_id: str,
        dataset_id: Optional[str] = None,
        interpreted_terms: Optional[Dict[str, str]] = None,
        response_text: Optional[str] = None,
    ) -> UserQuery:
        query = UserQuery(
            id=str(uuid.uuid4()),
            text=text,
            workspace_id=workspace_id,
            user_id=user_id,
            dataset_id=dataset_id,
            interpreted_terms=interpreted_terms or {},
            response_text=response_text,
        )
        db = self._get_db()
        await db.user_queries.insert_one(query.model_dump(exclude={"id"}))
        return query

    async def update_query_satisfaction(
        self,
        query_id: str,
        was_satisfactory: bool,
        signal_type: SignalType,
    ):
        db = self._get_db()
        await db.user_queries.update_one(
            {"_id": ObjectId(query_id)},
            {
                "$set": {
                    "was_satisfactory": was_satisfactory,
                    "signal_type": signal_type,
                }
            },
        )

    async def get_user_memory(
        self,
        workspace_id: str,
        user_id: str,
    ) -> Optional[UserMemory]:
        db = self._get_db()
        doc = await db.user_memory.find_one(
            {"workspace_id": workspace_id, "user_id": user_id}
        )
        if doc:
            doc["id"] = str(doc.pop("_id"))
            return UserMemory(**doc)
        return None

    async def upsert_user_memory(
        self,
        workspace_id: str,
        user_id: str,
        frequent_terms: Optional[Dict[str, int]] = None,
        preferred_metrics: Optional[List[str]] = None,
    ) -> UserMemory:
        db = self._get_db()
        query = {"workspace_id": workspace_id, "user_id": user_id}
        update = {
            "$set": {
                "updated_at": datetime.utcnow(),
                "last_query_at": datetime.utcnow(),
            },
            "$inc": {"query_count": 1},
        }
        if frequent_terms:
            update["$set"]["frequent_terms"] = frequent_terms
        if preferred_metrics:
            update["$set"]["preferred_metrics"] = preferred_metrics

        doc = await db.user_memory.find_one_and_update(
            query,
            update,
            upsert=True,
            return_document=True,
        )
        doc["id"] = str(doc.pop("_id"))
        return UserMemory(**doc)

    async def increment_correction_count(
        self,
        workspace_id: str,
        user_id: str,
    ):
        db = self._get_db()
        await db.user_memory.update_one(
            {"workspace_id": workspace_id, "user_id": user_id},
            {
                "$inc": {"correction_count": 1},
                "$set": {"updated_at": datetime.utcnow()},
            },
        )

    async def log_interaction_event(
        self,
        user_id: str,
        workspace_id: str,
        query_text: str,
        event_type: str,
        response_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InteractionEvent:
        event = InteractionEvent(
            id=str(uuid.uuid4()),
            user_id=user_id,
            workspace_id=workspace_id,
            query_text=query_text,
            response_text=response_text,
            event_type=event_type,
            metadata=metadata or {},
        )
        db = self._get_db()
        await db.interaction_events.insert_one(event.model_dump(exclude={"id"}))
        return event

    async def get_recent_events(
        self,
        workspace_id: str,
        user_id: str,
        limit: int = 50,
    ) -> List[InteractionEvent]:
        db = self._get_db()
        cursor = (
            db.interaction_events.find(
                {"workspace_id": workspace_id, "user_id": user_id}
            )
            .sort("created_at", -1)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        events = []
        for doc in docs:
            doc["id"] = str(doc.pop("_id"))
            events.append(InteractionEvent(**doc))
        return events


context_store = ContextStore()

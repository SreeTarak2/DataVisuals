from typing import Optional, List, Dict, Any
import re
import logging

from db.schemas_context import CorrectionScope
from services.feedback.context_store import context_store

logger = logging.getLogger(__name__)


class UserMemoryService:
    def __init__(self):
        pass

    async def get_or_create_memory(
        self,
        workspace_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        memory = await context_store.get_user_memory(workspace_id, user_id)

        if memory:
            return {
                "frequent_terms": memory.frequent_terms,
                "preferred_metrics": memory.preferred_metrics,
                "query_count": memory.query_count,
                "correction_count": memory.correction_count,
            }

        new_memory = await context_store.upsert_user_memory(workspace_id, user_id)

        return {
            "frequent_terms": new_memory.frequent_terms,
            "preferred_metrics": new_memory.preferred_metrics,
            "query_count": new_memory.query_count,
            "correction_count": new_memory.correction_count,
        }

    async def record_query(
        self,
        workspace_id: str,
        user_id: str,
        query: str,
        dataset_id: Optional[str] = None,
    ):
        memory = await context_store.get_user_memory(workspace_id, user_id)

        terms = self._extract_terms_from_query(query)

        frequent_terms = (
            dict(memory.frequent_terms) if memory and memory.frequent_terms else {}
        )

        for term in terms:
            frequent_terms[term] = frequent_terms.get(term, 0) + 1

        await context_store.upsert_user_memory(
            workspace_id,
            user_id,
            frequent_terms=frequent_terms,
        )

        await context_store.save_query(
            text=query,
            workspace_id=workspace_id,
            user_id=user_id,
            dataset_id=dataset_id,
        )

    async def record_correction(
        self,
        workspace_id: str,
        user_id: str,
        original_term: str,
        corrected_term: str,
        interpretation: str,
        scope: CorrectionScope = CorrectionScope.WORKSPACE,
    ):
        rule = await context_store.add_correction_rule(
            original_term=original_term,
            corrected_term=corrected_term,
            interpretation=interpretation,
            scope=scope,
            workspace_id=workspace_id,
            user_id=user_id,
        )

        await context_store.increment_correction_count(workspace_id, user_id)

        return rule

    async def get_correction_rules(
        self,
        workspace_id: str,
        term: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        rules = await context_store.get_correction_rules(workspace_id, term)

        return [
            {
                "original_term": r.original_term,
                "corrected_term": r.corrected_term,
                "interpretation": r.interpretation,
                "scope": r.scope.value,
                "usage_count": r.usage_count,
            }
            for r in rules
        ]

    async def get_metric_mappings(
        self,
        workspace_id: str,
        term: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        mappings = await context_store.get_metric_mappings(workspace_id, term)

        return [
            {
                "term": m.term,
                "definition": m.definition,
                "source_column": m.source_column,
                "formula": m.formula,
            }
            for m in mappings
        ]

    async def assemble_context(
        self,
        workspace_id: str,
        user_id: str,
        query: str,
    ) -> Dict[str, Any]:
        memory = await self.get_or_create_memory(workspace_id, user_id)

        rules = await context_store.get_correction_rules(workspace_id)

        mappings = await context_store.get_metric_mappings(workspace_id)

        relevant_rules = self._find_relevant_rules(query, rules)

        context_parts = []

        if relevant_rules:
            context_parts.append("Your defined interpretations:")
            for rule in relevant_rules:
                context_parts.append(
                    f"- {rule.original_term} = {rule.corrected_term} ({rule.interpretation})"
                )

        if mappings:
            context_parts.append("Metric definitions:")
            for mapping in mappings:
                if mapping.source_column:
                    context_parts.append(
                        f"- {mapping.term}: {mapping.definition} (column: {mapping.source_column})"
                    )
                else:
                    context_parts.append(f"- {mapping.term}: {mapping.definition}")

        return {
            "query": query,
            "context": "\n".join(context_parts) if context_parts else "",
            "rules": relevant_rules,
            "mappings": mappings,
            "user_memory": memory,
        }

    def _extract_terms_from_query(self, query: str) -> List[str]:
        terms = []

        metric_patterns = [
            r"\b(mrr|arr|revenue|sales|bookings|booked|recognized|gross|net)\b",
            r"\b(users?|customers?|subscribers?|accounts?)\b",
            r"\b(churn|retention|growth|expansion)\b",
            r"\b(average|sum|total|count|unique)\b",
        ]

        for pattern in metric_patterns:
            matches = re.findall(pattern, query.lower())
            terms.extend(matches)

        return list(set(terms))

    def _find_relevant_rules(
        self,
        query: str,
        rules: List,
    ) -> List:
        query_lower = query.lower()

        relevant = []
        for rule in rules:
            if rule.original_term.lower() in query_lower:
                relevant.append(rule)

        return relevant


user_memory_service = UserMemoryService()

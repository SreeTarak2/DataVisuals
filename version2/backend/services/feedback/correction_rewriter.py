import re
import logging
from typing import Optional, Dict, List
from services.feedback.context_store import context_store
from db.schemas_context import CorrectionScope

logger = logging.getLogger(__name__)


class CorrectionRewriter:
    def __init__(self):
        pass

    async def apply_corrections(
        self,
        query: str,
        workspace_id: str,
    ) -> tuple[str, List[Dict]]:
        """
        Apply stored correction rules to the query.

        Only **workspace-scoped** rules are applied. Conversation-scoped
        rules captured from one-off phrasing are skipped so they can't leak
        into unrelated sessions.

        Returns:
            - rewritten query with corrections applied
            - list of corrections applied [{"original", "corrected", "rule_id"}]
        """
        rules = await context_store.get_correction_rules(workspace_id)

        if not rules:
            return query, []

        corrections_applied = []
        rewritten = query

        for rule in rules:
            if rule.scope != CorrectionScope.WORKSPACE:
                continue
            # Confidence floor: implicit captures start at 0.8; anything below
            # 0.7 (or legacy defaults of 1.0) is too speculative to rewrite
            # every future query in the workspace.
            if (rule.confidence or 0) < 0.7:
                continue

            original_term = (rule.original_term or "").lower()
            corrected_term = rule.corrected_term
            if not original_term or not corrected_term:
                continue

            pattern = r"\b" + re.escape(original_term) + r"\b"

            if re.search(pattern, rewritten, re.IGNORECASE):
                # Escape backslashes so the replacement can't be parsed as a
                # regex group reference (\g<1>, \1, ...) by re.sub.
                replacement = corrected_term.replace("\\", "\\\\")
                rewritten = re.sub(
                    pattern, replacement, rewritten, flags=re.IGNORECASE
                )
                corrections_applied.append(
                    {
                        "original": rule.original_term,
                        "corrected": corrected_term,
                        "interpretation": rule.interpretation,
                        "rule_id": rule.id,
                    }
                )
                logger.info(f"Applied correction: {original_term} -> {corrected_term}")
                try:
                    await context_store.update_correction_rule_usage(rule.id)
                except Exception as e:
                    logger.debug(f"Failed to bump rule usage (non-critical): {e}")

        return rewritten, corrections_applied

    async def check_metric_mappings(
        self,
        query: str,
        workspace_id: str,
    ) -> tuple[str, List[Dict]]:
        """
        Check for metric term mappings in the query.

        Returns:
            - query with metric mappings documented in context
            - list of mappings found [{"term", "definition"}]
        """
        mappings = await context_store.get_metric_mappings(workspace_id)

        if not mappings:
            return query, []

        mappings_found = []
        context_parts = []

        for mapping in mappings:
            term = mapping.term.lower()
            if term in query.lower():
                mappings_found.append(
                    {
                        "term": mapping.term,
                        "definition": mapping.definition,
                        "source_column": mapping.source_column,
                    }
                )
                if mapping.source_column:
                    context_parts.append(
                        f"{mapping.term}: uses column '{mapping.source_column}'"
                    )

        return query, mappings_found


correction_rewriter = CorrectionRewriter()

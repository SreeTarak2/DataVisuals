import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class TrustVerificationResult:
    def __init__(
        self,
        is_trusted: bool,
        confidence: float,
        checks_passed: List[str],
        checks_failed: List[str],
        warnings: List[str] = None,
        applied_semantics: List[Dict[str, Any]] = None,
    ):
        self.is_trusted = is_trusted
        self.confidence = confidence
        self.checks_passed = checks_passed
        self.checks_failed = checks_failed
        self.warnings = warnings or []
        self.applied_semantics = applied_semantics or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_trusted": self.is_trusted,
            "confidence": self.confidence,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "warnings": self.warnings,
            "applied_semantics": self.applied_semantics,
        }


class TrustVerifier:
    def __init__(self, context_store):
        self.context_store = context_store

    async def verify_query(
        self,
        query: str,
        workspace_id: str,
        dataset_id: Optional[str] = None,
    ) -> TrustVerificationResult:
        semantics = await self.context_store.get_metric_semantics_for_workspace(workspace_id)

        checks_passed = []
        checks_failed = []
        warnings = []
        applied_semantics = []

        if not semantics:
            return TrustVerificationResult(
                is_trusted=True,
                confidence=0.5,
                checks_passed=["no semantic definitions stored"],
                checks_failed=[],
                warnings=["No metric definitions found - query interpretation unchecked"],
            )

        query_lower = query.lower()
        metrics_found = []

        for semantic in semantics:
            if semantic.metric_name.lower() in query_lower:
                metrics_found.append(semantic)
                applied_semantics.append(
                    {
                        "metric_name": semantic.metric_name,
                        "definition": semantic.definition,
                        "formula": semantic.formula,
                    }
                )

                if semantic.formula:
                    checks_passed.append(f"metric_{semantic.metric_name}_formula_checked")

                    if not any(col in query_lower for col in (semantic.source_columns or [])):
                        warnings.append(
                            f"Query for {semantic.metric_name} may not use expected columns "
                            f"{semantic.source_columns}"
                        )

        metrics_with_defs = len([s for s in semantics if s.metric_name])
        metrics_covered = len(metrics_found)

        if metrics_covered == 0:
            confidence = 0.7
            checks_passed.append("no defined metrics in query")
        elif metrics_covered > 0:
            confidence = min(0.95, 0.7 + (0.25 * metrics_covered / max(1, metrics_with_defs)))
            checks_passed.append(f"validated_{metrics_covered}_metrics")
        else:
            confidence = 0.5

        is_trusted = confidence >= 0.6

        logger.info(
            f"Trust verification: {is_trusted} (confidence={confidence:.2f}) "
            f"metrics_found={metrics_covered}"
        )

        return TrustVerificationResult(
            is_trusted=is_trusted,
            confidence=confidence,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            warnings=warnings,
            applied_semantics=applied_semantics,
        )


async def get_verifier():
    from services.feedback.context_store import context_store

    return TrustVerifier(context_store)

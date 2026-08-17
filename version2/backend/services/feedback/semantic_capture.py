import logging
import re
from typing import Optional, List, Tuple

from db.schemas_context import MetricSemantic, ValidationRule

logger = logging.getLogger(__name__)


class SemanticCapture:
    SEMANTIC_CORRECTION_PATTERNS = [
        r"(\w+)\s+means?\s+(.+)",
        r"(\w+)\s+is\s+(.+)",
        r"(\w+)\s+=\s+(.+)",
        r"(\w+)\s+refers?\s+to\s+(.+)",
    ]

    FORMULA_PATTERNS = [
        r"(sum|avg|count)\(([\w_]+)\)",
        r"([\w_]+)\s+where\s+(.+)",
    ]

    def __init__(self):
        self._patterns = [re.compile(p, re.IGNORECASE) for p in self.SEMANTIC_CORRECTION_PATTERNS]

    def extract_metric_semantic(
        self,
        original_term: str,
        corrected_term: str,
        query_context: Optional[str] = None,
    ) -> Optional[Tuple[MetricSemantic, List[ValidationRule]]]:
        full_text = f"{original_term} means {corrected_term}"
        if query_context:
            full_text += f" {query_context}"

        for pattern in self._patterns:
            match = pattern.search(full_text)
            if match:
                metric_name = match.group(1).strip().lower()
                definition = match.group(2).strip()

                formula = None
                source_columns = []
                aggregation = None

                for fp in self.FORMULA_PATTERNS:
                    formula_match = re.search(fp, definition, re.IGNORECASE)
                    if formula_match:
                        formula = definition
                        if "where" in definition.lower():
                            col_match = re.search(
                                r"(sum|avg|count)\(([\w_]+)\)", definition, re.IGNORECASE
                            )
                            if col_match:
                                aggregation = col_match.group(1).lower()
                                source_columns = [col_match.group(2)]
                        else:
                            fn_match = re.search(
                                r"(sum|avg|count)\(([\w_]+)\)", definition, re.IGNORECASE
                            )
                            if fn_match:
                                aggregation = fn_match.group(1).lower()
                                source_columns = [fn_match.group(2)]
                        break

                validation_rules = self._infer_validation_rules(metric_name, definition)

                return MetricSemantic(
                    metric_name=metric_name,
                    definition=definition,
                    formula=formula,
                    source_columns=source_columns,
                    aggregation=aggregation,
                    business_context=definition,
                ), validation_rules

        return None

    def _infer_validation_rules(
        self,
        metric_name: str,
        definition: str,
    ) -> List[ValidationRule]:
        rules = []

        if any(
            m in metric_name.lower() for m in ["revenue", "amount", "sales", "profit", "income"]
        ):
            rules.append(
                ValidationRule(
                    rule_type="RANGE",
                    expression=f"{metric_name} >= 0",
                    threshold=0,
                    fail_message=f"{metric_name} should not be negative",
                )
            )

        if any(m in metric_name.lower() for m in ["rate", "percentage", "margin", "growth"]):
            rules.append(
                ValidationRule(
                    rule_type="RANGE",
                    expression=f"0 <= {metric_name} <= 100",
                    threshold=100,
                    fail_message=f"{metric_name} should be between 0 and 100",
                )
            )

        return rules

    def is_semantic_correction(
        self,
        original_term: str,
        corrected_term: str,
    ) -> bool:
        full_text = f"{original_term} means {corrected_term}"
        return any(p.search(full_text) for p in self._patterns)


semantic_capture = SemanticCapture()

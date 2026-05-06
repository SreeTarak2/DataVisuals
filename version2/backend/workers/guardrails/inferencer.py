"""Guardrail Inferencer - Automatically generates data quality rules from dataset analysis"""

import logging
import uuid
from typing import List, Dict, Any, Optional

import polars as pl

from workers.guardrails.models import GuardrailRule

logger = logging.getLogger(__name__)


class GuardrailInferencer:
    """Analyzes dataset and automatically generates appropriate guardrail rules"""

    def __init__(self, sample_size: int = 1000):
        self.sample_size = sample_size

    def infer_rules(self, df: pl.DataFrame, dataset_id: str) -> List[GuardrailRule]:
        """Analyze dataset and generate appropriate guardrail rules"""
        rules = []
        rule_counter = 0

        if len(df) > self.sample_size:
            df = df.head(self.sample_size)

        for column in df.columns:
            col_type = df[column].dtype
            null_count = df[column].null_count()
            total_rows = len(df)
            null_ratio = null_count / total_rows if total_rows > 0 else 0

            if null_ratio < 0.05 and null_count > 0:
                rule_counter += 1
                rules.append(
                    GuardrailRule(
                        rule_id=str(uuid.uuid4()),
                        column_name=column,
                        rule_type="not_null",
                        parameters={"max_null_ratio": 0.05},
                        severity="warning",
                        description=f"Column '{column}' should have minimal null values (< 5%)",
                    )
                )

            if self._is_id_column(column, df[column]):
                rule_counter += 1
                rules.append(
                    GuardrailRule(
                        rule_id=str(uuid.uuid4()),
                        column_name=column,
                        rule_type="unique",
                        parameters={},
                        severity="critical",
                        description=f"Column '{column}' appears to be an identifier and should be unique",
                    )
                )

            pattern_rule = self._infer_pattern_rule(
                column, df[column], dataset_id, rule_counter
            )
            if pattern_rule:
                rules.append(pattern_rule)
                rule_counter += 1

            if col_type in [
                pl.Int8,
                pl.Int16,
                pl.Int32,
                pl.Int64,
                pl.Float32,
                pl.Float64,
            ]:
                range_rule = self._infer_range_rule(
                    column, df[column], dataset_id, rule_counter
                )
                if range_rule:
                    rules.append(range_rule)
                    rule_counter += 1

            if col_type == pl.Utf8 or col_type == pl.String:
                categorical_rule = self._infer_categorical_rule(
                    column, df[column], dataset_id, rule_counter
                )
                if categorical_rule:
                    rules.append(categorical_rule)
                    rule_counter += 1

        logger.info(f"Generated {len(rules)} guardrail rules from dataset analysis")
        return rules

    def _is_id_column(self, column_name: str, series: pl.Series) -> bool:
        id_patterns = ["id", "uuid", "key", "code", "number"]
        if any(pattern in column_name.lower() for pattern in id_patterns):
            return True
        if series.n_unique() == len(series) and len(series) > 10:
            return True
        return False

    def _infer_pattern_rule(
        self, column_name: str, series: pl.Series, dataset_id: str, counter: int
    ) -> Optional[GuardrailRule]:
        col_lower = column_name.lower()

        if "email" in col_lower:
            return GuardrailRule(
                rule_id=str(uuid.uuid4()),
                column_name=column_name,
                rule_type="pattern",
                parameters={
                    "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                },
                severity="critical",
                description=f"Column '{column_name}' should contain valid email addresses",
            )

        if "phone" in col_lower or "mobile" in col_lower:
            return GuardrailRule(
                rule_id=str(uuid.uuid4()),
                column_name=column_name,
                rule_type="pattern",
                parameters={"pattern": r"^[\d\s\-\+\(\)]{7,20}$"},
                severity="warning",
                description=f"Column '{column_name}' should contain valid phone numbers",
            )

        if "url" in col_lower or "website" in col_lower:
            return GuardrailRule(
                rule_id=str(uuid.uuid4()),
                column_name=column_name,
                rule_type="pattern",
                parameters={"pattern": r"^https?://"},
                severity="warning",
                description=f"Column '{column_name}' should contain valid URLs",
            )

        if "date" in col_lower or "time" in col_lower:
            return GuardrailRule(
                rule_id=str(uuid.uuid4()),
                column_name=column_name,
                rule_type="not_null",
                parameters={},
                severity="critical",
                description=f"Column '{column_name}' should not contain null date values",
            )

        return None

    def _infer_range_rule(
        self, column_name: str, series: pl.Series, dataset_id: str, counter: int
    ) -> Optional[GuardrailRule]:
        if len(series) == 0:
            return None

        non_null = series.drop_nulls()
        if len(non_null) == 0:
            return None

        try:
            min_val = float(non_null.min())
            max_val = float(non_null.max())
        except Exception:
            return None

        if max_val - min_val > 1e9:
            return None

        buffer = (max_val - min_val) * 0.1 if max_val != min_val else 1.0

        return GuardrailRule(
            rule_id=str(uuid.uuid4()),
            column_name=column_name,
            rule_type="range",
            parameters={"min": min_val - buffer, "max": max_val + buffer},
            severity="warning",
            description=f"Column '{column_name}' values should be between {min_val - buffer:.2f} and {max_val + buffer:.2f}",
        )

    def _infer_categorical_rule(
        self, column_name: str, series: pl.Series, dataset_id: str, counter: int
    ) -> Optional[GuardrailRule]:
        if len(series) == 0:
            return None

        non_null = series.drop_nulls()
        if len(non_null) == 0:
            return None

        try:
            unique_count = non_null.n_unique()
            total_count = len(non_null)

            if unique_count < 20 and unique_count / total_count < 0.05:
                categories = non_null.unique().to_list()
                return GuardrailRule(
                    rule_id=str(uuid.uuid4()),
                    column_name=column_name,
                    rule_type="categorical",
                    parameters={"allowed_values": categories},
                    severity="warning",
                    description=f"Column '{column_name}' should only contain values from: {categories[:5]}{'...' if len(categories) > 5 else ''}",
                )
        except Exception as e:
            logger.warning(f"Failed to infer categorical rule for {column_name}: {e}")

        return None


__all__ = ["GuardrailInferencer"]

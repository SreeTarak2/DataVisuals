"""
semantic/validators.py — LLM-Based Validation Gates
====================================================

Two validation gates for the production-grade semantic pipeline:

1. Intent Validator — Checks that the extracted QueryIntent correctly represents
   the user's original question. Prevents cases where the LLM extracts wrong
   metrics, misses filters, or misinterprets dimensions.

2. SQL Validator — Checks that the compiled SQL actually answers the user's
   original question. Prevents technically correct SQL that answers the wrong
   question.

Both validators are:
- Lightweight (fast model, small token budget)
- Non-blocking (return warnings, not hard errors)
- Fast (target < 500ms each)

The orchestrator uses their output for observability and logging, but does NOT
block execution on validation warnings. A failed validation increments a metric
and logs a warning, but the query still executes.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from llm.router import llm_router

logger = logging.getLogger(__name__)


# ── Validation result models ────────────────────────────────────────────────


@dataclass
class ValidationGateResult:
    """Result of a single validation gate check."""

    passed: bool
    confidence: float  # 0.0-1.0
    reason: str = ""
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "confidence": self.confidence,
            "reason": self.reason,
            "warnings": self.warnings,
        }


# ── Intent validator ───────────────────────────────────────────────────────


_INTENT_VALIDATOR_PROMPT = """\
You are a validation gate for a data analytics system.

A user asked: "{query}"

An AI extracted this structured intent from their question:
```json
{intent_json}
```

Available columns (use EXACT names): {columns}

Available metric definitions: {metrics}

══════════════════════════════════════════════════════════════
VALIDATION TASKS — check ALL of the following
══════════════════════════════════════════════════════════════

1. METRIC ACCURACY — Does each extracted metric match what the user asked?
   ✓ The user said "revenue" → intent has metric "revenue" → CORRECT
   ✗ The user said "total profit" → intent has metric "revenue" → WRONG
   ✗ The user said "show me customers" → intent has metric="customers" with
     aggregation="sum" → WRONG (count would be correct)

2. FILTER ACCURACY — Are all filters from the user present?
   ✓ The user said "for 2024" → intent has filter year=2024 → CORRECT
   ✗ The user said "in the US and Canada" → intent has filter country="US"
     but missing "Canada" → WRONG
   ✗ The user said "last month" → no filter present → WRONG

3. DIMENSION ACCURACY — Are all groupings from the user present?
   ✓ The user said "by month and region" → intent has both dimensions → CORRECT
   ✗ The user said "by month" → no dimension → WRONG

4. ORDER/LIMIT ACCURACY — Is ordering and limiting correct?
   ✓ The user said "top 10" → intent has limit=10 → CORRECT
   ✓ The user said "sorted by revenue descending" → intent has order=revenue desc → CORRECT
   ✗ The user said "sorted by revenue" → intent has no order → WRONG

══════════════════════════════════════════════════════════════
OUTPUT FORMAT — return ONLY valid JSON
══════════════════════════════════════════════════════════════

{{
  "passed": true,
  "confidence": 0.95,
  "reason": "Brief explanation of validation result",
  "warnings": [
    "Specific warning about a potential issue",
    "Another warning if applicable"
  ]
}}

Rules:
- "passed": false ONLY if the intent clearly does NOT match the user's question
  (e.g., wrong metric, missing critical filter, completely off-track)
- "passed": true if the intent is a reasonable interpretation, even if not perfect
  (small warnings are fine — use the warnings array)
- "confidence": how sure you are (0.0-1.0)
- "warnings": array of specific issues found (can be empty)
- Return ONLY valid JSON. No markdown. No explanation.
"""


class IntentValidator:
    """Validates that an extracted QueryIntent correctly represents the user's question.

    This is a lightweight, non-blocking validation gate. It catches cases where:
    - The LLM extracted the wrong metric name
    - A filter from the user's question was missed
    - A dimension/grouping was misinterpreted
    - The aggregation type doesn't match the question intent
    """

    async def validate(
        self,
        query: str,
        intent_dict: Dict[str, Any],
        available_columns: List[str],
        available_metrics: List[Dict[str, str]],
    ) -> ValidationGateResult:
        """Validate an extracted intent against the original query.

        Args:
            query: The original user question
            intent_dict: Serialized QueryIntent as a dict
            available_columns: Column names available in the dataset
            available_metrics: Available metric definitions as [{name, display_name}]

        Returns:
            ValidationGateResult with pass/fail + warnings
        """
        if not query or not intent_dict:
            return ValidationGateResult(
                passed=True,
                confidence=1.0,
                reason="Nothing to validate",
            )

        columns_str = ", ".join(available_columns[:30]) if available_columns else "none"
        metrics_str = ", ".join(
            f"{m.get('name', '?')} ({m.get('display_name', '')})"
            for m in available_metrics[:20]
        ) if available_metrics else "none"

        prompt = _INTENT_VALIDATOR_PROMPT.format(
            query=query[:500],
            intent_json=json.dumps(intent_dict, indent=2),
            columns=columns_str,
            metrics=metrics_str,
        )

        try:
            raw = await llm_router.call(
                prompt=prompt,
                model_role="intent_engine",
                expect_json=True,
                temperature=0.0,
                max_tokens=300,
            )

            result = _parse_validation_gate_response(raw)
            if result is None:
                return ValidationGateResult(
                    passed=True,
                    confidence=0.5,
                    reason="Validator returned unparseable response — allowing by default",
                    warnings=["Intent validator returned unparseable response"],
                )

            return result

        except Exception as e:
            logger.warning(f"[IntentValidator] LLM call failed (allowing by default): {e}")
            return ValidationGateResult(
                passed=True,
                confidence=0.5,
                reason=f"Validator LLM call failed — allowing by default: {e}",
                warnings=["Intent validator LLM call failed"],
            )


# Shared helper — used by both validators
def _parse_validation_gate_response(raw: Any) -> Optional[ValidationGateResult]:
    """Parse an LLM response into a ValidationGateResult."""
    if raw is None:
        return None

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    elif not isinstance(raw, dict):
        return None

    return ValidationGateResult(
        passed=bool(raw.get("passed", True)),
        confidence=float(raw.get("confidence", 0.5)),
        reason=str(raw.get("reason", "")),
        warnings=raw.get("warnings", []),
    )


# ── SQL validator ──────────────────────────────────────────────────────────


_SQL_VALIDATOR_PROMPT = """\
You are a validation gate for a data analytics SQL execution engine.

User question: "{query}"

Generated SQL:
```sql
{sql}
```

Available columns (use EXACT names): {columns}

══════════════════════════════════════════════════════════════
VALIDATION TASKS — check ALL of the following
══════════════════════════════════════════════════════════════

1. QUESTION COVERAGE — Does this SQL answer the user's question?
   ✓ User asks "total revenue by month" → SQL has SUM(revenue) + GROUP BY month → CORRECT
   ✗ User asks "total revenue by month" → SQL has COUNT(revenue) → WRONG aggregation
   ✗ User asks "top 10 products" → SQL has no LIMIT 10 → WRONG

2. COLUMN CORRECTNESS — Are all column names exact and valid?
   ✓ SQL uses `revenue` and `month` and both exist in schema → CORRECT
   ✗ SQL uses `revenue_amount` but column is `revenue` → WRONG (hallucination)
   ✗ SQL uses `date_trunc('month', created_at)` but `created_at` doesn't exist → WRONG

3. AGGREGATION CORRECTNESS — Are aggregations appropriate?
   ✓ SUM for additive metrics (revenue, cost) → CORRECT
   ✓ MEDIAN for skewed metrics (price, salary) → CORRECT
   ✗ COUNT for revenue calculation → WRONG
   ✗ No aggregation on a numeric column in a GROUP BY query → WRONG

4. FILTER CORRECTNESS — Are filters from the user present in WHERE?
   ✓ User said "for 2024" → SQL has WHERE year = 2024 → CORRECT
   ✗ User said "only active customers" → no WHERE status filter → WRONG
   ✗ SQL has a filter the user didn't ask for (changes the question) → WRONG

5. SQL SAFETY — Is the SQL safe to execute?
   ✓ SELECT ... FROM data WHERE ... GROUP BY ... → SAFE
   ✗ SELECT * (too many columns returned without LIMIT) → RISKY but valid
   ✗ DROP TABLE, DELETE, INSERT, etc. → DANGEROUS / INVALID

══════════════════════════════════════════════════════════════
OUTPUT FORMAT — return ONLY valid JSON
══════════════════════════════════════════════════════════════

{{
  "passed": true,
  "confidence": 0.95,
  "reason": "Brief explanation",
  "warnings": [
    "Specific warning about a potential issue",
    "Another warning"
  ]
}}

Rules:
- "passed": false ONLY if the SQL clearly does NOT answer the user's question
  (e.g., wrong columns, wrong aggregation, missing critical filter, unsafe SQL)
- "passed": true if the SQL is a reasonable answer, even with minor issues
  (small warnings are fine — use the warnings array)
- "confidence": 0.0-1.0
- "warnings": array of specific issues (can be empty)
- Return ONLY valid JSON. No markdown. No explanation.
"""


class SQLValidator:
    """Validates that compiled SQL correctly answers the user's original question.

    This is a lightweight, non-blocking validation gate. It catches:
    - Wrong column names (hallucination from the compiler)
    - Wrong aggregation type for the question
    - Missing filters from the user's question
    - Extraneous filters the user didn't ask for
    - SQL safety issues (SELECT *, dangerous operations)
    """

    async def validate(
        self,
        query: str,
        sql: str,
        available_columns: List[str],
    ) -> ValidationGateResult:
        """Validate compiled SQL against the original user question.

        Args:
            query: The original user question
            sql: The compiled SQL to validate
            available_columns: Column names available in the dataset

        Returns:
            ValidationGateResult with pass/fail + warnings
        """
        if not query or not sql:
            return ValidationGateResult(
                passed=True,
                confidence=1.0,
                reason="Nothing to validate",
            )

        columns_str = ", ".join(available_columns[:30]) if available_columns else "none"

        prompt = _SQL_VALIDATOR_PROMPT.format(
            query=query[:500],
            sql=sql[:1000],
            columns=columns_str,
        )

        try:
            raw = await llm_router.call(
                prompt=prompt,
                model_role="intent_engine",
                expect_json=True,
                temperature=0.0,
                max_tokens=300,
            )

            result = self._parse_response(raw)
            if result is None:
                return ValidationGateResult(
                    passed=True,
                    confidence=0.5,
                    reason="Validator returned unparseable response — allowing by default",
                    warnings=["SQL validator returned unparseable response"],
                )

            return result

        except Exception as e:
            logger.warning(f"[SQLValidator] LLM call failed (allowing by default): {e}")
            return ValidationGateResult(
                passed=True,
                confidence=0.5,
                reason=f"Validator LLM call failed — allowing by default: {e}",
                warnings=["SQL validator LLM call failed"],
            )

    def _parse_response(self, raw: Any) -> Optional[ValidationGateResult]:
        """Parse the LLM response into a ValidationGateResult."""
        if raw is None:
            return None

        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return None
        elif isinstance(raw, dict):
            pass
        else:
            return None

        if not isinstance(raw, dict):
            return None

        return ValidationGateResult(
            passed=bool(raw.get("passed", True)),
            confidence=float(raw.get("confidence", 0.5)),
            reason=str(raw.get("reason", "")),
            warnings=raw.get("warnings", []),
        )


# ── Validation orchestrator (runs both gates) ─────────────────────────────


@dataclass
class EndToEndValidationResult:
    """Combined result of both validation gates plus the overall decision."""

    intent_validation: Optional[ValidationGateResult] = None
    sql_validation: Optional[ValidationGateResult] = None

    # Overall
    passed: bool = True
    all_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "intent_validation": self.intent_validation.to_dict() if self.intent_validation else None,
            "sql_validation": self.sql_validation.to_dict() if self.sql_validation else None,
            "all_warnings": self.all_warnings,
        }


class ValidationOrchestrator:
    """Runs both validation gates and aggregates results.

    The orchestrator:
    1. Runs intent validation (if intent available)
    2. Runs SQL validation (if SQL available)
    3. Collects all warnings
    4. Makes an overall pass/fail decision

    Both validators are non-blocking — a failed validation does NOT prevent
    execution. It collects warnings for observability.
    """

    def __init__(self):
        self._intent_validator = IntentValidator()
        self._sql_validator = SQLValidator()

    async def validate_all(
        self,
        query: str,
        intent_dict: Optional[Dict[str, Any]] = None,
        sql: Optional[str] = None,
        available_columns: Optional[List[str]] = None,
        available_metrics: Optional[List[Dict[str, str]]] = None,
    ) -> EndToEndValidationResult:
        """Run all validation gates.

        Args:
            query: The original user question
            intent_dict: Serialized QueryIntent dict (optional)
            sql: Compiled SQL (optional)
            available_columns: Column names in the dataset
            available_metrics: Available metric definitions

        Returns:
            EndToEndValidationResult with all validation results
        """
        available_columns = available_columns or []
        available_metrics = available_metrics or []

        # Run intent validation
        intent_result = None
        if intent_dict:
            intent_result = await self._intent_validator.validate(
                query=query,
                intent_dict=intent_dict,
                available_columns=available_columns,
                available_metrics=available_metrics,
            )
            if intent_result.warnings:
                logger.info(
                    f"[Validation] Intent validation: {len(intent_result.warnings)} warnings"
                )

        # Run SQL validation
        sql_result = None
        if sql:
            sql_result = await self._sql_validator.validate(
                query=query,
                sql=sql,
                available_columns=available_columns,
            )
            if sql_result.warnings:
                logger.info(
                    f"[Validation] SQL validation: {len(sql_result.warnings)} warnings"
                )

        # Aggregate warnings
        all_warnings: List[str] = []
        if intent_result and intent_result.warnings:
            all_warnings.extend(intent_result.warnings)
        if sql_result and sql_result.warnings:
            all_warnings.extend(sql_result.warnings)

        # Overall: pass if both validators pass (or are absent)
        passed = True
        if intent_result and not intent_result.passed:
            logger.warning(f"[Validation] Intent validation FAILED: {intent_result.reason}")
            passed = False
        if sql_result and not sql_result.passed:
            logger.warning(f"[Validation] SQL validation FAILED: {sql_result.reason}")
            passed = False

        return EndToEndValidationResult(
            intent_validation=intent_result,
            sql_validation=sql_result,
            passed=passed,
            all_warnings=all_warnings,
        )


# Singletons
validation_orchestrator = ValidationOrchestrator()
intent_validator = IntentValidator()
sql_validator = SQLValidator()

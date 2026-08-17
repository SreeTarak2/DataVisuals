"""
semantic/query_decomposer.py — Query Decomposer (Phase 1 Agent Component)
===========================================================================

The Decomposer is the first missing production-grade agent component.

It takes a complex QueryIntent and breaks it into independent sub-intents
that can be compiled and executed separately. This enables:

1. Comparison queries: "revenue 2024 vs 2023" → two sub-queries, recombined
2. Multi-metric queries with different grains: "daily revenue, monthly churn"
3. Multi-part questions: "top products and their monthly trend"
4. Derived computations: "show revenue, profit, and margin"

Architecture:
  QueryIntent → [Decomposer] → DecompositionPlan {sub_intents: [QueryIntent, ...]}
    → Each sub-intent runs through: [resolve → compile → execute]
    → [Recombinator] merges results
    → Final response

The decomposer is LLM-based for understanding implied comparisons, with
a rule-based fallback for simple IN-filter splitting.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from llm.router import llm_router
from .query_intent import (
    FilterIntent,
    FilterOperator,
    MetricIntent,
    QueryIntent,
)

logger = logging.getLogger(__name__)


# ── Data models ────────────────────────────────────────────────────────────


class MergeStrategy(str, Enum):
    """How sub-query results should be merged."""

    SIDE_BY_SIDE = "side_by_side"
    """Create columns like revenue_2024, revenue_2023 from separate results.
    Used for: "revenue 2024 vs 2023" → side-by-side columns per year."""

    APPEND = "append"
    """Stack results on top of each other (UNION-style).
    Used for: independent questions that should be separate answer blocks."""

    COMPUTE_CHANGE = "compute_change"
    """Add a computed 'change' column from two result sets.
    Used for: "compare 2024 vs 2023" → explicit delta/percent change column."""

    SEPARATE = "separate"
    """Present each result as a completely separate answer.
    Used for: "show me revenue and also list my top customers" — unrelated."""


@dataclass
class SubIntent:
    """A single sub-query within a decomposition plan."""

    id: int
    intent: QueryIntent
    label: str = ""
    depends_on: List[int] = field(default_factory=list)
    """IDs of sub-intents that must execute first. Empty = no dependencies."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "intent": self.intent.to_dict(),
            "depends_on": self.depends_on,
        }


@dataclass
class DecompositionPlan:
    """The plan for decomposing a complex query into sub-queries."""

    sub_intents: List[SubIntent]
    merge_strategy: MergeStrategy = MergeStrategy.SEPARATE
    description: str = ""

    # Column renaming for side_by_side merge
    # {"metric_name": {"suffix": "2024", "suffix": "2023"}, ...}
    column_suffixes: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def is_single(self) -> bool:
        """Check if this plan is effectively a single query (no decomposition)."""
        return len(self.sub_intents) <= 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sub_intents": [s.to_dict() for s in self.sub_intents],
            "merge_strategy": self.merge_strategy.value,
            "description": self.description[:200],
            "column_suffixes": self.column_suffixes,
        }


# ── Decomposition prompt ──────────────────────────────────────────────────


_DECOMPOSITION_PROMPT = """\
You are a Query Decomposer for a data analytics system.

A user asked: "{query}"

The system extracted this structured intent:
```json
{intent_json}
```

Available metrics: {metrics}
Available columns: {columns}

══════════════════════════════════════════════════════════════
DECOMPOSITION TASK
══════════════════════════════════════════════════════════════

Determine if this query should be decomposed into MULTIPLE sub-queries.

DECOMPOSE when:
1. COMPARISON — User explicitly compares two or more values/periods:
   "revenue 2024 vs 2023" → 2 sub-queries (one per year), merge: side_by_side
   "profit Q1 vs Q2 vs Q3" → 3 sub-queries, merge: side_by_side
   "compare before and after the promotion" → 2 sub-queries, merge: compute_change

2. MULTI-GRAIN — Different metrics need different grouping:
   "daily revenue and monthly churn rate" → 2 sub-queries, merge: separate
   
3. UNRELATED QUESTIONS — Query asks two separate things:
   "top 10 products by revenue and what's the monthly trend" → 2 sub-queries, merge: separate

DO NOT DECOMPOSE when:
- Single metric × single dimension × one set of filters (standard query)
- Multiple metrics but same dimension and filters (compiler handles this)
- Simple aggregation (total, average, count)

══════════════════════════════════════════════════════════════
OUTPUT FORMAT — return ONLY valid JSON
══════════════════════════════════════════════════════════════

If NO decomposition needed:
{{"needs_decomposition": false}}

If decomposition needed:
{{"needs_decomposition": true,
  "description": "Brief explanation of why decomposition is needed",
  "merge_strategy": "side_by_side | compute_change | separate",
  "sub_intents": [
    {{
      "id": 1,
      "label": "Revenue 2024",
      "metrics": [{{"name": "revenue", "alias": "revenue", "aggregation": null}}],
      "dimensions": [{{"column": "month", "grain": "month", "alias": null}}],
      "filters": [{{"column": "year", "operator": "=", "value": 2024}}],
      "order": [{{"metric": "revenue", "direction": "desc"}}],
      "limit": null
    }},
    {{
      "id": 2,
      "label": "Revenue 2023",
      "metrics": [{{"name": "revenue", "alias": "revenue", "aggregation": null}}],
      "dimensions": [{{"column": "month", "grain": "month", "alias": null}}],
      "filters": [{{"column": "year", "operator": "=", "value": 2023}}],
      "order": [{{"metric": "revenue", "direction": "desc"}}],
      "limit": null
    }}
  ],
  "column_suffixes": {{"revenue": {{"1": "_2024", "2": "_2023"}}}}
}}

Rules for sub_intents:
- Each sub-intent is a complete, valid QueryIntent (metrics, dimensions, filters, order, limit)
- Use EXACT column names from available columns
- Each sub-intent must be independently compilable
- For "side_by_side": all sub-intents should have the same dimensions
- For "compute_change": exactly 2 sub-intents (before and after)
- For "separate": each sub-intent is independent (different metrics, dimensions, or both)
- Return ONLY valid JSON. No markdown. No explanation.
"""


# ── Decomposer ─────────────────────────────────────────────────────────────


class QueryDecomposer:
    """Decomposes complex QueryIntents into independent sub-query plans.

    Uses LLM-based decomposition for understanding implied comparisons,
    with rule-based fallback for simple IN-filter splitting.
    """

    def __init__(self):
        self._max_retries = 2

    async def decompose(
        self,
        intent: QueryIntent,
        query: str,
        available_columns: Optional[List[str]] = None,
        available_metrics: Optional[List[Dict[str, str]]] = None,
    ) -> DecompositionPlan:
        """Decompose a QueryIntent into a plan with possibly multiple sub-intents.

        Args:
            intent: The extracted QueryIntent
            query: The original user question
            available_columns: Column names in the dataset
            available_metrics: Available metric definitions

        Returns:
            DecompositionPlan with sub-intents and merge strategy.
            If no decomposition needed, returns a plan with a single sub-intent.
        """
        if not intent or not intent.is_metric_query():
            return DecompositionPlan(
                sub_intents=[SubIntent(id=0, intent=intent, label="")],
                merge_strategy=MergeStrategy.SEPARATE,
            )

        available_columns = available_columns or []
        available_metrics = available_metrics or []

        # Try LLM-based decomposition first
        plan = await self._llm_decompose(
            intent=intent,
            query=query,
            available_columns=available_columns,
            available_metrics=available_metrics,
        )

        if plan is not None:
            logger.info(
                f"[Decomposer] LLM plan: {len(plan.sub_intents)} sub-queries, "
                f"merge={plan.merge_strategy.value}"
            )
            return plan

        # LLM failed — try rule-based fallback
        logger.info("[Decomposer] LLM decomposition failed, trying rule-based fallback")
        plan = self._rule_based_decompose(intent)
        if plan is not None:
            return plan

        # No decomposition — pass through as single query
        return DecompositionPlan(
            sub_intents=[SubIntent(id=0, intent=intent, label="")],
            merge_strategy=MergeStrategy.SEPARATE,
        )

    async def _llm_decompose(
        self,
        intent: QueryIntent,
        query: str,
        available_columns: List[str],
        available_metrics: List[Dict[str, str]],
    ) -> Optional[DecompositionPlan]:
        """Try LLM-based decomposition."""
        metrics_str = ", ".join(
            f"{m.get('name', '?')}" for m in available_metrics[:15]
        ) if available_metrics else "none"

        columns_str = ", ".join(available_columns[:25]) if available_columns else "none"

        prompt = _DECOMPOSITION_PROMPT.format(
            query=query[:500],
            intent_json=json.dumps(intent.to_dict(), indent=2),
            metrics=metrics_str,
            columns=columns_str,
        )

        for attempt in range(self._max_retries + 1):
            try:
                raw = await llm_router.call(
                    prompt=prompt,
                    model_role="intent_engine",
                    expect_json=True,
                    temperature=0.1,
                    max_tokens=1000,
                )

                plan = self._parse_llm_response(raw, intent)
                if plan is not None:
                    return plan

                logger.warning(f"[Decomposer] Parse failed on attempt {attempt + 1}")
            except Exception as e:
                logger.warning(f"[Decomposer] LLM call failed on attempt {attempt + 1}: {e}")

        return None

    def _parse_llm_response(
        self, raw: Any, original_intent: QueryIntent
    ) -> Optional[DecompositionPlan]:
        """Parse the LLM response into a DecompositionPlan."""
        if raw is None:
            return None

        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return None
        elif not isinstance(raw, dict):
            return None

        # Check if decomposition is needed
        if not raw.get("needs_decomposition", False):
            return DecompositionPlan(
                sub_intents=[SubIntent(id=0, intent=original_intent, label="")],
                merge_strategy=MergeStrategy.SEPARATE,
            )

        # Parse sub-intents
        sub_raw = raw.get("sub_intents", [])
        if not sub_raw:
            return None

        sub_intents: List[SubIntent] = []
        default_confidence = original_intent.confidence if hasattr(original_intent, 'confidence') else 0.5
        for s in sub_raw:
            sub_intent = self._dict_to_sub_intent(s, default_confidence)
            if sub_intent is None:
                return None
            sub_intents.append(sub_intent)

        # Parse merge strategy
        merge_str = raw.get("merge_strategy", "separate")
        try:
            merge_strategy = MergeStrategy(merge_str)
        except ValueError:
            merge_strategy = MergeStrategy.SEPARATE

        return DecompositionPlan(
            sub_intents=sub_intents,
            merge_strategy=merge_strategy,
            description=raw.get("description", ""),
            column_suffixes=raw.get("column_suffixes", {}),
        )

    def _dict_to_sub_intent(self, data: dict, default_confidence: float = 0.5) -> Optional[SubIntent]:
        """Convert a dict to a SubIntent."""
        try:
            sub_id = int(data.get("id", 0))
            label = data.get("label", "")

            metrics_raw = data.get("metrics", []) or []
            dimensions_raw = data.get("dimensions", []) or []
            filters_raw = data.get("filters", []) or []
            order_raw = data.get("order", []) or []

            from .query_intent import (
                DimensionIntent,
                FilterIntent,
                FilterOperator,
                MetricIntent,
                OrderDirection,
                OrderIntent,
            )

            metrics = [
                MetricIntent(
                    name=m.get("name", ""),
                    alias=m.get("alias"),
                    aggregation=m.get("aggregation"),
                )
                for m in metrics_raw
                if m.get("name")
            ]

            dimensions = [
                DimensionIntent(
                    column=d.get("column", ""),
                    grain=d.get("grain"),
                    alias=d.get("alias"),
                )
                for d in dimensions_raw
                if d.get("column")
            ]

            filters = []
            for f in filters_raw:
                col = f.get("column")
                if not col:
                    continue
                op_str = f.get("operator", "=")
                try:
                    operator = FilterOperator(op_str)
                except ValueError:
                    operator = FilterOperator.EQ
                filters.append(
                    FilterIntent(column=col, operator=operator, value=f.get("value"))
                )

            order = [
                OrderIntent(
                    column=o.get("column"),
                    metric=o.get("metric"),
                    direction=OrderDirection(o.get("direction", "desc")),
                )
                for o in order_raw
            ]

            sub_intent = QueryIntent(
                metrics=metrics,
                dimensions=dimensions,
                filters=filters,
                order=order,
                limit=data.get("limit"),
                has_aggregations=len(metrics) > 0,
                confidence=default_confidence,
            )

            return SubIntent(id=sub_id, intent=sub_intent, label=label)

        except Exception as e:
            logger.warning(f"[Decomposer] Failed to parse sub-intent: {e}")
            return None

    def _rule_based_decompose(self, intent: QueryIntent) -> Optional[DecompositionPlan]:
        """Rule-based fallback: split IN filters into per-value sub-intents.

        Detects filters like year IN (2023, 2024) and creates one
        sub-intent per filter value with EQ instead of IN.
        """
        # Find IN or NOT_IN filters with multiple values
        multi_value_filters = [
            f for f in intent.filters
            if f.operator in (FilterOperator.IN, FilterOperator.NOT_IN)
            and isinstance(f.value, (list, tuple))
            and len(f.value) >= 2
        ]

        if not multi_value_filters:
            return None

        # Take only the first multi-value filter (simplest case)
        target_filter = multi_value_filters[0]
        other_filters = [f for f in intent.filters if f is not target_filter]

        sub_intents: List[SubIntent] = []
        for i, val in enumerate(target_filter.value):
            # Create a sub-intent with EQ instead of IN
            sub_filters = list(other_filters)
            sub_filters.append(
                FilterIntent(
                    column=target_filter.column,
                    operator=FilterOperator.EQ,
                    value=val,
                )
            )

            sub_intent = QueryIntent(
                metrics=list(intent.metrics),
                dimensions=list(intent.dimensions),
                filters=sub_filters,
                order=list(intent.order),
                limit=intent.limit,
                has_aggregations=intent.has_aggregations,
                confidence=intent.confidence,
            )

            sub_intents.append(
                SubIntent(
                    id=i,
                    intent=sub_intent,
                    label=f"{target_filter.column}={val}",
                )
            )

        # Determine the suffix for column naming
        col_suffixes: Dict[str, Dict[str, str]] = {}
        for m in intent.metrics:
            suffixes: Dict[str, str] = {}
            for i, val in enumerate(target_filter.value):
                suffixes[str(i)] = f"_{str(val).replace(' ', '_')}"
            col_suffixes[m.name] = suffixes

        logger.info(
            f"[Decomposer] Rule-based: split {len(sub_intents)} sub-queries "
            f"on filter '{target_filter.column}'"
        )

        return DecompositionPlan(
            sub_intents=sub_intents,
            merge_strategy=MergeStrategy.SIDE_BY_SIDE,
            description=f"Comparison across {target_filter.column} values",
            column_suffixes=col_suffixes,
        )


# Singleton
query_decomposer = QueryDecomposer()

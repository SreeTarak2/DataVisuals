"""
semantic/intent_extractor.py — LLM-Based Structured Intent Extraction
=====================================================================

This is the NEW role of the LLM in the "LLM as translator" architecture.

Instead of writing SQL directly, the LLM:
1. Receives the user's natural language query
2. Receives the dataset schema (column names + types)
3. Receives available metric definitions (names + descriptions)
4. Outputs a structured QueryIntent JSON

The SQL compiler then generates SQL from this intent + governed definitions.
The LLM NEVER writes SQL — it only translates NLQ to structured intent.

This prompt is intentionally SIMPLER than the SQL generation prompt:
- No DuckDB syntax rules
- No "NEVER do X" constraints
- No retry/error feedback
- No governance block to interpret
- Just: "what metrics, what dimensions, what filters"
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from llm.router import llm_router
from .query_intent import (
    DimensionIntent,
    FilterIntent,
    FilterOperator,
    MetricIntent,
    OrderDirection,
    OrderIntent,
    QueryIntent,
    TimeGrain,
)

logger = logging.getLogger(__name__)


# ── Prompt builder ──────────────────────────────────────────────────────────


def _build_intent_extraction_prompt(
    query: str,
    column_schema: str,
    available_metrics: List[Dict[str, str]],
    sample_data: Optional[str] = None,
) -> str:
    """Build the intent extraction prompt.

    Args:
        query: The user's natural language query
        column_schema: Formatted column schema string (name: type)
        available_metrics: List of available metric definitions
            [{"name": "revenue", "display_name": "Revenue", "description": "..."}]
        sample_data: Optional sample data for context
    """
    metric_names = (
        "\n".join(
            f"  - {m['name']}: {m.get('display_name', m['name'])} — {m.get('description', '')}"
            for m in available_metrics
        )
        if available_metrics
        else "  (no metrics defined — infer from column names)"
    )

    schema_block = column_schema if column_schema else "not provided"

    return f"""You are the Intent Engine — a precise NLQ-to-structured-intent translator.

Your ONLY job: translate the user's natural language question into structured JSON.
You do NOT write SQL. You do NOT answer the question. You ONLY extract intent.

══════════════════════════════════════════════════════════════
CONTEXT
══════════════════════════════════════════════════════════════

USER QUESTION: {query}

AVAILABLE COLUMNS (use EXACT names from here):
{schema_block}

AVAILABLE METRICS (governed definitions — use these names when user asks about them):
{metric_names}

{"SAMPLE DATA:" + sample_data if sample_data else ""}

══════════════════════════════════════════════════════════════
EXTRACTION RULES
══════════════════════════════════════════════════════════════

METRICS — Identify what the user wants to COMPUTE (aggregate):
  Examples: "revenue", "how many orders", "average price", "total sales"
  → Output: {{"name": "<metric_name>", "alias": "<optional_alias>", "aggregation": null}}
  
  The "name" field should match:
    1. A KNOWN METRIC name from the AVAILABLE METRICS list (preferred)
    2. OR a column name from AVAILABLE COLUMNS
    3. OR a plain-English term for what they're asking about
  
  Set "aggregation" ONLY if the user explicitly specifies it:
    "sum of revenue" → "sum"
    "average price" → "mean"
    "how many orders" → "count"
  If not specified, leave as null (the governed default will be used).

DIMENSIONS — Identify how to GROUP/BREAK DOWN the data:
  Examples: "by month", "per region", "by category", "over time"
  → Output: {{"column": "<column_name>", "grain": null|"month"|"year"|"day", "alias": null}}
  
  For time dimensions, set grain:
    "by month" → grain: "month"
    "per year" → grain: "year"
    "daily" → grain: "day"

FILTERS — Identify any CONDITIONS/WHRER clauses:
  Examples: "for 2024", "where status is active", "revenue > 1000"
  → Output: {{"column": "<column_name>", "operator": "="|">"|"<"|"in"|"like"|...}}
  
  Common patterns:
    "in 2024" or "for 2024"       → {{"column": "year", "operator": "=", "value": 2024}}
    "greater than 100"             → {{"column": "...", "operator": ">", "value": 100}}
    "in the US and UK"            → {{"column": "country", "operator": "in", "value": ["US", "UK"]}}
    "last month"                  → {{"column": "date", "operator": "between", "value": [...]}}
    "that contain 'premium'"      → {{"column": "...", "operator": "ilike", "value": "%premium%"}}

ORDER — Identify sorting requirements:
  Examples: "highest first", "sorted by revenue", "top 10"
  → Output: {{"column": null, "metric": "<metric_name>", "direction": "desc"}}

LIMIT — Identify row limits:
  Examples: "top 10" → limit: 10
  "show me 5" → limit: 5

══════════════════════════════════════════════════════════════
OUTPUT FORMAT — return ONLY valid JSON
══════════════════════════════════════════════════════════════

{{"intent": {{
    "metrics": [
        {{"name": "revenue", "alias": "total_revenue", "aggregation": null}}
    ],
    "dimensions": [
        {{"column": "month", "grain": "month", "alias": null}},
        {{"column": "region", "grain": null, "alias": null}}
    ],
    "filters": [
        {{"column": "year", "operator": "=", "value": 2024}}
    ],
    "order": [
        {{"metric": "revenue", "direction": "desc"}}
    ],
    "limit": 10,
    "offset": null,
    "distinct": false,
    "has_aggregations": true,
    "confidence": 0.95,
    "raw_query": "{query}"
}}}}

RULES:
- "has_aggregations": true if user is asking for summaries, totals, averages, etc.
- "has_aggregations": false if user wants raw data records
- "confidence": how sure you are this intent matches the question (0.0-1.0)
  - 0.95+ for clear, well-specified questions
  - 0.70-0.90 for reasonable interpretations of ambiguous questions
  - < 0.50 for very vague questions where you're guessing
- Use EXACT column names from AVAILABLE COLUMNS
- If you cannot extract ANY meaningful intent, return: {{"intent": null, "error": "Could not understand the query"}}
- Return ONLY valid JSON. No markdown. No explanation.
"""


# ── Intent extractor ───────────────────────────────────────────────────────


class IntentExtractor:
    """Extracts structured QueryIntent from natural language queries using an LLM.

    This replaces the LLM's role from "write SQL" to "extract structured intent".
    The LLM NEVER writes SQL through this path.
    """

    def __init__(self):
        self._max_retries = 2

    async def extract(
        self,
        query: str,
        column_schema: str,
        available_metrics: Optional[List[Dict[str, str]]] = None,
        sample_data: Optional[str] = None,
    ) -> QueryIntent:
        """Extract a structured QueryIntent from a natural language query.

        Args:
            query: The user's natural language query
            column_schema: Formatted column schema string
            available_metrics: List of available metric definitions
            sample_data: Optional sample data for context

        Returns:
            QueryIntent — the structured representation. If extraction fails,
            returns a fallback intent with confidence=0.0
        """
        if not query or not query.strip():
            return QueryIntent(raw_query=query or "", confidence=0.0)

        available_metrics = available_metrics or []

        prompt = _build_intent_extraction_prompt(
            query=query,
            column_schema=column_schema,
            available_metrics=available_metrics,
            sample_data=sample_data,
        )

        for attempt in range(self._max_retries + 1):
            try:
                raw = await llm_router.call(
                    prompt=prompt,
                    model_role="intent_engine",
                    expect_json=True,
                    temperature=0.1,
                    max_tokens=800,
                )

                # Parse the response
                intent_data = self._parse_response(raw)
                if intent_data is not None:
                    return intent_data

                logger.warning(f"[IntentExtractor] Parse failed on attempt {attempt + 1}")
            except Exception as e:
                logger.warning(f"[IntentExtractor] LLM call failed on attempt {attempt + 1}: {e}")

        # Fallback: return a minimal intent from the raw query
        logger.warning(
            f"[IntentExtractor] All attempts failed. Returning fallback for: {query[:60]}"
        )
        return QueryIntent.from_raw_query(query)

    def _parse_response(self, raw: Any) -> Optional[QueryIntent]:
        """Parse the LLM response into a QueryIntent."""
        if raw is None:
            return None

        # Handle string responses
        if isinstance(raw, str):
            raw = raw.strip()
            # Remove markdown code fences
            if raw.startswith("```"):
                lines = raw.split("\n")
                content = "\n".join(
                    lines[1:-1] if len(lines) > 1 and lines[-1].strip() == "```" else lines[1:]
                )
            else:
                content = raw
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                return None
        elif isinstance(raw, dict):
            data = raw
        else:
            return None

        # Extract intent from response
        intent_data = data.get("intent")
        if intent_data is None:
            if data.get("error"):
                return None
            intent_data = data
        if not isinstance(intent_data, dict):
            return None

        # Check for error
        if intent_data.get("error"):
            return None

        return self._dict_to_intent(intent_data)

    def _dict_to_intent(self, data: dict) -> Optional[QueryIntent]:
        """Convert a validated dict to a QueryIntent."""
        try:
            metrics_raw = data.get("metrics", []) or []
            dimensions_raw = data.get("dimensions", []) or []
            filters_raw = data.get("filters", []) or []
            order_raw = data.get("order", []) or []

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
                filters.append(FilterIntent(column=col, operator=operator, value=f.get("value")))

            order = [
                OrderIntent(
                    column=o.get("column"),
                    metric=o.get("metric"),
                    direction=OrderDirection(o.get("direction", "desc")),
                )
                for o in order_raw
            ]

            return QueryIntent(
                metrics=metrics,
                dimensions=dimensions,
                filters=filters,
                order=order,
                limit=data.get("limit"),
                offset=data.get("offset"),
                distinct=bool(data.get("distinct", False)),
                raw_query=data.get("raw_query", ""),
                confidence=float(data.get("confidence", 0.5)),
                has_aggregations=bool(data.get("has_aggregations", True)),
            )

        except Exception as e:
            logger.warning(f"[IntentExtractor] Failed to convert dict to intent: {e}")
            return None


# Singleton
intent_extractor = IntentExtractor()

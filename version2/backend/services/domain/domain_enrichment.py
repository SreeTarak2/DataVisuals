"""
Domain Enrichment — Stage 2 Semantic Profile
===============================================
Runs AFTER domain detection (Stage 1) succeeds. Produces a rich, structured
semantic profile of the dataset that downstream agents (QUIS, chat, SRG, executor)
use to calibrate query strategy, metric discovery, and intent routing.

Stage 2 fires only when Stage 1 identifies a matching domain template.
Uses Mistral Small 3.2 (stronger model) for reliable structured JSON output.

Flow:
  1. Stage 1: domain detection (LLM + data stats, Flash Lite) → domain_id
  2. Stage 2: enrichment (Mistral Small 3.2) → DomainEnrichmentOutput
  3. Downstream agents consume the enrichment profile

Usage:
    from services.domain.domain_enrichment import enrich_domain
    profile = await enrich_domain(profiles, df, domain_id)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import polars as pl

from services.ai.intelligent_kpi_generator import ColumnProfile, ColumnRole, dtype_abbrev

logger = logging.getLogger(__name__)


# ── Output Schema ─────────────────────────────────────────────────────────────

class ColumnSemantic:
    """Semantic annotation for a single column."""
    __slots__ = ("column", "semantic_type", "description", "aggregations", "pii_risk")

    def __init__(
        self,
        column: str,
        semantic_type: str,
        description: str,
        aggregations: Optional[List[str]] = None,
        pii_risk: bool = False,
    ):
        self.column = column
        self.semantic_type = semantic_type  # metric, dimension, timestamp, entity_id, etc.
        self.description = description
        self.aggregations = aggregations or ["sum"]
        self.pii_risk = pii_risk

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column": self.column,
            "semantic_type": self.semantic_type,
            "description": self.description,
            "aggregations": self.aggregations,
            "pii_risk": self.pii_risk,
        }


class MetricSuggestion:
    """A named metric this dataset can answer."""
    __slots__ = ("name", "columns", "formula", "description", "aggregation")

    def __init__(
        self,
        name: str,
        columns: List[str],
        description: str,
        formula: Optional[str] = None,
        aggregation: str = "sum",
    ):
        self.name = name
        self.columns = columns
        self.formula = formula
        self.description = description
        self.aggregation = aggregation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "columns": self.columns,
            "formula": self.formula,
            "description": self.description,
            "aggregation": self.aggregation,
        }


class AnalyticalIntent:
    """A type of question this dataset can answer."""
    __slots__ = ("intent", "example_query", "complexity", "requires_columns")

    def __init__(
        self,
        intent: str,
        example_query: str,
        complexity: str = "simple",
        requires_columns: Optional[List[str]] = None,
    ):
        self.intent = intent
        self.example_query = example_query
        self.complexity = complexity  # simple, moderate, complex
        self.requires_columns = requires_columns or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "example_query": self.example_query,
            "complexity": self.complexity,
            "requires_columns": self.requires_columns,
        }


class DomainEnrichmentOutput:
    """
    Rich domain profile produced by Stage 2 enrichment.
    Attached to dataset metadata and made available to downstream agents.
    """
    __slots__ = ("domain_id", "column_semantics", "suggested_metrics",
                 "analytical_intents", "natural_language_summary",
                 "schema_version")

    def __init__(
        self,
        domain_id: str,
        column_semantics: List[ColumnSemantic],
        suggested_metrics: List[MetricSuggestion],
        analytical_intents: List[AnalyticalIntent],
        natural_language_summary: str,
    ):
        self.domain_id = domain_id
        self.column_semantics = column_semantics
        self.suggested_metrics = suggested_metrics
        self.analytical_intents = analytical_intents
        self.natural_language_summary = natural_language_summary
        self.schema_version = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "domain_id": self.domain_id,
            "column_semantics": [cs.to_dict() for cs in self.column_semantics],
            "suggested_metrics": [m.to_dict() for m in self.suggested_metrics],
            "analytical_intents": [i.to_dict() for i in self.analytical_intents],
            "natural_language_summary": self.natural_language_summary,
        }


# ── Prompt Builder ────────────────────────────────────────────────────────────

def _build_enrichment_prompt(
    profiles: List[ColumnProfile],
    df: pl.DataFrame,
    domain_id: str,
) -> str:
    """Build the Stage 2 enrichment prompt with rich column statistics."""

    col_lines = []
    for p in profiles:
        role = p.role.value
        null_pct = p.null_pct

        samples = []
        if p.name in df.columns:
            raw = df[p.name].drop_nulls().head(3).to_list()
            samples = [str(v)[:60] for v in raw if v is not None]
        sample_str = f"  samples: {', '.join(samples)}" if samples else "  (all null)"

        if role in ("measure", "rate", "count") and p.col_min is not None:
            stats_line = (
                f"  range: [{p.col_min:.2f}, {p.col_max:.2f}]  "
                f"mean: {p.col_mean:.2f}  med: {p.col_median:.2f}  "
                f"cardinality: {p.n_unique}/{p.n_rows}  nulls: {null_pct:.0f}%"
            )
        else:
            stats_line = (
                f"  cardinality: {p.n_unique}/{p.n_rows}  nulls: {null_pct:.0f}%"
            )

        col_lines.append(f"- {p.name} [{dtype_abbrev(str(df[p.name].dtype))}]")
        col_lines.append(f"  role: {role}")
        col_lines.append(stats_line)
        col_lines.append(sample_str)

    columns_str = "\n".join(col_lines)

    prompt = f"""You are a data domain analyst. A dataset has been classified as "{domain_id}". 
Now produce a rich semantic profile so downstream agents can understand what this data means.

DATASET COLUMNS:
{columns_str}

Your job is to produce a JSON object with:

1. **column_semantics** (array): For EVERY column, describe:
   - semantic_type: one of "metric" (numeric, aggregatable), "dimension" (categorical, groupable), 
     "timestamp" (datetime), "entity_id" (primary key / FK), "percentage", "currency", 
     "score_rank", "flag", "free_text", "geolocation"
   - description: What this column MEANS in business context (domain-specific, not generic)
   - aggregations: valid SQL aggregations for this column (sum, avg, count, min, max, count_distinct)
   - pii_risk: true if column likely contains PII (email, phone, name, address, SSN, IP)

2. **suggested_metrics** (array): 3-8 named metrics this dataset can answer, each with:
   - name: short metric name
   - columns: which real columns are involved
   - formula: SQL expression (e.g. "SUM(revenue) / COUNT(DISTINCT order_id)")
   - description: plain English explanation
   - aggregation: "sum", "avg", "count", "ratio", "growth"

3. **analytical_intents** (array): 3-6 questions a user might ask, each with:
   - intent: short snake_case label
   - example_query: natural language question
   - complexity: "simple", "moderate", or "complex"
   - requires_columns: which columns are needed

4. **natural_language_summary**: 2-4 sentence plain English summary of the dataset
   (what it contains, what domain, what business process it supports)

OUTPUT FORMAT — valid JSON only:
{{
  "column_semantics": [
    {{"column": "col_name", "semantic_type": "metric", "description": "What this column means", "aggregations": ["sum", "avg"], "pii_risk": false}}
  ],
  "suggested_metrics": [
    {{"name": "example_metric", "columns": ["col1"], "formula": "expression", "description": "explanation", "aggregation": "sum"}}
  ],
  "analytical_intents": [
    {{"intent": "trend_analysis", "example_query": "question", "complexity": "simple", "requires_columns": ["col1"]}}
  ],
  "natural_language_summary": "plain english description"
}}

Return ONLY the JSON object. No markdown fences. No text before or after."""
    return prompt


# ── Response Parser ───────────────────────────────────────────────────────────

def _parse_enrichment_response(raw: str) -> Optional[DomainEnrichmentOutput]:
    """Parse and validate the LLM's enrichment response."""
    import re as _re

    content = raw.strip()

    # Strip markdown fences if present
    fence_match = _re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if fence_match:
        content = fence_match.group(1).strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Try extracting first { ... } block
        brace_match = _re.search(r"\{[\s\S]*\}", content)
        if not brace_match:
            logger.warning(f"[Enrichment] No JSON found in response: {raw[:200]}")
            return None
        try:
            data = json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            logger.warning(f"[Enrichment] Failed to parse JSON from response: {raw[:200]}")
            return None

    # Parse column semantics
    col_semantics_raw = data.get("column_semantics", [])
    if not col_semantics_raw:
        logger.warning("[Enrichment] No column_semantics in response")
        return None

    column_semantics = [
        ColumnSemantic(
            column=cs.get("column", ""),
            semantic_type=cs.get("semantic_type", "unknown"),
            description=cs.get("description", ""),
            aggregations=cs.get("aggregations", ["sum"]),
            pii_risk=cs.get("pii_risk", False),
        )
        for cs in col_semantics_raw
    ]

    # Parse suggested metrics
    metrics_raw = data.get("suggested_metrics", [])
    suggested_metrics = [
        MetricSuggestion(
            name=m.get("name", ""),
            columns=m.get("columns", []),
            description=m.get("description", ""),
            formula=m.get("formula"),
            aggregation=m.get("aggregation", "sum"),
        )
        for m in metrics_raw
    ]

    # Parse analytical intents
    intents_raw = data.get("analytical_intents", [])
    analytical_intents = [
        AnalyticalIntent(
            intent=i.get("intent", ""),
            example_query=i.get("example_query", ""),
            complexity=i.get("complexity", "simple"),
            requires_columns=i.get("requires_columns", []),
        )
        for i in intents_raw
    ]

    summary = data.get("natural_language_summary", "")

    return DomainEnrichmentOutput(
        domain_id="",  # filled by caller
        column_semantics=column_semantics,
        suggested_metrics=suggested_metrics,
        analytical_intents=analytical_intents,
        natural_language_summary=summary,
    )


# ── Main Enrichment Function ─────────────────────────────────────────────────

async def enrich_domain(
    profiles: List[ColumnProfile],
    df: pl.DataFrame,
    domain_id: str,
) -> Optional[DomainEnrichmentOutput]:
    """
    Stage 2 enrichment: produce a rich semantic profile after domain detection.

    Args:
        profiles: Column profiles from the KPI generator
        df: The raw DataFrame
        domain_id: The domain template ID from Stage 1

    Returns:
        DomainEnrichmentOutput with column semantics, metrics, intents, and summary.
        Returns None if enrichment fails (e.g. LLM unavailable).
    """
    if not domain_id or not profiles:
        return None

    prompt = _build_enrichment_prompt(profiles, df, domain_id)

    try:
        from services.llm_router import llm_router

        response = await llm_router.call(
            prompt=prompt,
            model_role="enrichment_engine",
            expect_json=True,
            temperature=0.2,
            is_conversational=False,
            max_tokens=2048,
        )

        if isinstance(response, str):
            output = _parse_enrichment_response(response)
        elif isinstance(response, dict):
            # Already parsed by router
            output = _parse_enrichment_response(json.dumps(response))
        else:
            logger.warning(f"[Enrichment] Unexpected response type: {type(response)}")
            return None

        if output:
            output.domain_id = domain_id
            logger.info(
                f"[Enrichment] Success: {len(output.column_semantics)} columns, "
                f"{len(output.suggested_metrics)} metrics, "
                f"{len(output.analytical_intents)} intents"
            )
            return output

        return None

    except Exception as e:
        logger.warning(f"[Enrichment] Failed: {e}")
        return None

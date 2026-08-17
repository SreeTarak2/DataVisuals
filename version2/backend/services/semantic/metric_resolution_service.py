"""
semantic/metric_resolution_service.py — Metric Resolution Middleware
====================================================================

The critical bridge between "what the user says" and "what the data means".

Pipeline:
  1. Extract potential metric references from the NLQ
  2. Resolve each reference against MetricDefinitionStore
  3. Build resolved context with column mappings, aggregations, formulas
  4. Inject governed context into SQL generation prompt
  5. If no definition found → fall back to original LLM-guessed behavior

This is the Ferrari engine. Before this, the LLM guessed what "revenue" meant
EVERY SINGLE TIME. After this, the LLM receives the GOVERNED definition:
  "Revenue = SUM(price * quantity) WHERE status != 'refunded'"
and generates SQL that matches it exactly.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .metric_definition_store import (
    MetricDefinition,
    MetricDefinitionStore,
    MetricDefinitionSource,
    metric_definition_store,
)

logger = logging.getLogger(__name__)


# ── Data models ───────────────────────────────────────────────────────────────


@dataclass
class ResolvedMetric:
    """
    A metric reference that was resolved against a governed definition.

    If resolve() fails to find a definition, the metric is still listed
    with resolve_status="unresolved" so the caller can fall back gracefully.
    """

    query_term: str                               # What the user said — "revenue", "profit"
    canonical_name: str                           # Resolved metric name
    display_name: str = ""                        # Human-readable name
    source_column: Optional[str] = None           # Actual column in the dataset
    aggregation: str = "sum"                      # Governed aggregation
    formula: Optional[str] = None                 # Governed formula expression
    filters: List[str] = field(default_factory=list)  # Governed WHERE conditions
    confidence: float = 0.0                       # Resolution confidence
    source: str = "unresolved"                    # Source of the definition
    resolve_status: str = "resolved"              # "resolved" | "unresolved" | "partial"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_prompt_injection(self) -> str:
        """Format as a prompt instruction for SQL generation."""
        if self.resolve_status == "unresolved":
            return ""

        parts = [f"  • \"{self.query_term}\" → {self.display_name}"]
        if self.source_column:
            parts.append(f"    Column: `{self.source_column}`")
        parts.append(f"    Aggregation: {self.aggregation.upper()}")
        if self.formula:
            parts.append(f"    Expression: {self.formula}")
        if self.filters:
            parts.append(f"    Filters: {' AND '.join(self.filters)}")
        parts.append(f"    Confidence: {self.confidence:.0%}")
        return "\n".join(parts)


@dataclass
class MetricResolutionResult:
    """
    Full result of metric resolution for a single NLQ.

    Contains resolved metrics, the governance context block for prompt
    injection, and metadata about what was/wasn't resolved.
    """

    original_query: str                                # The original NLQ
    resolved_metrics: Dict[str, ResolvedMetric] = field(default_factory=dict)  # term → ResolvedMetric
    unresolved_terms: List[str] = field(default_factory=list)  # Terms we couldn't resolve
    has_governed_definitions: bool = False             # True if ≥1 metric was resolved
    total_resolved: int = 0
    total_unresolved: int = 0

    def to_governance_block(self) -> str:
        """
        Build the prompt block to inject into SQL generation context.

        This is the critical output — it tells the LLM:
          "The user said 'revenue'. Revenue is defined as SUM(price * quantity).
           Use this definition. Do not guess."
        """
        if not self.has_governed_definitions:
            return ""

        lines = [
            "══════════════════════════════════════════════════════════════",
            "GOVERNED METRIC DEFINITIONS — These are AUTHORITATIVE.",
            "The user's query references these metrics. Use the EXACT definitions below.",
            "Do NOT guess column names, aggregations, or formulas for these metrics.",
            "══════════════════════════════════════════════════════════════",
        ]

        resolved_list = [r for r in self.resolved_metrics.values() if r.resolve_status == "resolved"]
        if not resolved_list:
            return ""

        for r in resolved_list:
            lines.append(r.to_prompt_injection())

        if self.unresolved_terms:
            lines.append("")
            lines.append("⚠ Unresolved terms (no governed definition — use column name inference):")
            for term in self.unresolved_terms:
                lines.append(f"  • \"{term}\" — infer from DATASET SCHEMA below")

        lines.append("══════════════════════════════════════════════════════════════")
        return "\n".join(lines)

    def to_sql_engine_block(self) -> str:
        """
        Build a compact SQL engine instruction block.

        This goes directly into the SQL generation prompt when metrics
        are resolved. It tells the engine exactly which columns and
        aggregations to use for each governed metric.
        """
        if not self.has_governed_definitions:
            return ""

        resolved_list = [r for r in self.resolved_metrics.values() if r.resolve_status == "resolved"]
        if not resolved_list:
            return ""

        lines = [
            "## GOVERNED METRIC MAP — Use these EXACT mappings in your SQL",
        ]
        for r in resolved_list:
            # Simple case: column + aggregation
            if r.source_column and not r.formula:
                lines.append(
                    f"  \"{r.query_term}\" → {r.aggregation.upper()}(`{r.source_column}`)"
                )
            # Formula case: use the expression
            elif r.formula:
                lines.append(
                    f"  \"{r.query_term}\" → {r.formula} (with {r.aggregation.upper()} aggregation)"
                )
            # Column-only: use plain column
            elif r.source_column:
                lines.append(
                    f"  \"{r.query_term}\" → `{r.source_column}` ({r.aggregation.upper()})"
                )

        if self.unresolved_terms:
            unresolved_str = ", ".join(f"\"{t}\"" for t in self.unresolved_terms)
            lines.append(f"  Terms without definitions (infer from schema): {unresolved_str}")

        return "\n".join(lines)


# ── Metric reference extractors ──────────────────────────────────────────────

# Known business metric names — these are what we look for in NLQs
_METRIC_KEYWORDS: Set[str] = {
    # Revenue & Profit
    "revenue", "sales", "income", "profit", "gross profit", "net profit",
    "margin", "gross margin", "net margin", "profit margin",
    # Cost
    "cost", "costs", "expense", "expenses", "cogs", "spend", "spending",
    "burn rate", "burn_rate", "opex", "capex",
    # SaaS
    "mrr", "arr", "churn", "churn rate", "churn_rate", "ltv", "cac",
    "ltv/cac", "ltv_cac", "arpu", "nrr", "runway",
    # Volume
    "volume", "orders", "transactions", "units", "quantity",
    "count", "headcount", "enrollment", "students",
    # Users
    "users", "customers", "subscribers", "members", "clients",
    "visitors", "traffic", "impressions", "clicks", "conversions",
    # Rates
    "conversion rate", "conversion_rate", "retention", "retention rate",
    "growth rate", "growth", "rate", "percentage",
    # Averages
    "average", "aov", "avg", "median", "mean",
    "average order value", "average revenue per user",
    # Performance
    "score", "rating", "nps", "csat", "satisfaction",
    "performance", "quality", "defect rate", "yield",
    # Time-based
    "duration", "latency", "response time", "cycle time",
    "delivery time", "days", "tenure", "age",
    # E-commerce specific
    "gmv", "aov", "cart abandonment", "sell through",
    # Financial
    "ebitda", "cash flow", "cash_flow", "balance", "assets",
    "liabilities", "equity", "roi", "roas", "cac",
}

# Common column name patterns that indicate a metric
_COLUMN_METRIC_PATTERNS = [
    re.compile(r"\b(?:total|sum|net|gross|avg|average|mean|median)_?(.+)$", re.I),
    re.compile(r"^(.+?)_?(?:amount|value|total|sum|count|rate|pct|percent)$", re.I),
    re.compile(r"\b(?:revenue|sales|profit|cost|income|expense)\b", re.I),
]


def _extract_metric_references(query: str) -> List[str]:
    """
    Extract potential metric references from a natural language query.

    Uses a combination of:
    - Known business metric keyword matching
    - Column name pattern matching
    - Simple noun phrase extraction (single words that look data-like)

    Returns a list of lowercase candidate terms, ordered by confidence.
    """
    query_lower = query.lower().strip()
    candidates: List[str] = []
    seen: Set[str] = set()

    # Strategy 1: Direct keyword matches (highest confidence)
    words = query_lower.split()
    for i in range(len(words)):
        # Single word
        word = words[i].strip(",.!?;:'\"()[]{}")
        if word in _METRIC_KEYWORDS and word not in seen:
            candidates.append(word)
            seen.add(word)

        # Two-word phrases
        if i < len(words) - 1:
            phrase = f"{words[i]} {words[i+1]}".strip(",.!?;:'\"()[]{}")
            if phrase in _METRIC_KEYWORDS and phrase not in seen:
                candidates.append(phrase)
                seen.add(phrase)

    # Strategy 2: Column-name-like terms (snake_case in the query)
    snake_case = re.findall(r"\b[a-z]+_[a-z]+\b", query_lower)
    for term in snake_case:
        if term not in seen:
            candidates.append(term)
            seen.add(term)

    # Strategy 3: Generic metric-like words not in _METRIC_KEYWORDS
    # Covers very common ambiguous terms that users naturally use
    generic_metric_words = {
        "total", "sum", "ratio",
    }
    for word in words:
        cleaned = word.strip(",.!?;:'\"()[]{}")
        if cleaned in generic_metric_words and cleaned not in seen:
            candidates.append(cleaned)
            seen.add(cleaned)

    return candidates


# ── Metric resolution service ────────────────────────────────────────────────


class MetricResolutionService:
    """
    Resolves NLQ metric references against governed definitions.

    This is the bridge between "what the user says" and "what the data means."
    It extracts metric names from the user's query, resolves them against the
    MetricDefinitionStore, and returns a context block that the SQL generation
    engine uses to produce governed SQL — instead of guessing.
    """

    def __init__(self, store: Optional[MetricDefinitionStore] = None):
        self._store = store or metric_definition_store

    async def resolve(
        self,
        query: str,
        dataset_id: str,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        available_columns: Optional[List[str]] = None,
    ) -> MetricResolutionResult:
        """
        Resolve metric references in a query against governed definitions.

        Args:
            query: The user's natural language query
            dataset_id: Dataset to resolve against
            user_id: Optional user ID for user-specific definitions
            workspace_id: Optional workspace ID for workspace-level definitions
            available_columns: Optional list of column names for column-based fallback

        Returns:
            MetricResolutionResult with resolved + unresolved metrics
        """
        if not query or not query.strip():
            return MetricResolutionResult(original_query=query or "")

        # Step 1: Extract metric references from the query
        metric_terms = _extract_metric_references(query)

        if not metric_terms:
            return MetricResolutionResult(original_query=query)

        # Step 2: Get all governed definitions for this dataset
        definitions = await self._store.get_definitions(
            dataset_id=dataset_id,
            user_id=user_id,
            workspace_id=workspace_id,
        )

        # Step 3: Resolve each term against definitions
        resolved: Dict[str, ResolvedMetric] = {}
        unresolved: List[str] = []
        columns_lower = {c.lower(): c for c in (available_columns or [])}

        for term in metric_terms:
            term_lower = term.lower().strip()

            # Try exact match against definition names
            if term_lower in definitions:
                defn = definitions[term_lower]
                resolved[term_lower] = self._definition_to_resolved(term_lower, defn)
                continue

            # Try fuzzy match: term starts with definition or vice versa
            fuzzy_found = False
            for def_name, defn in definitions.items():
                if term_lower in def_name or def_name in term_lower:
                    resolved[term_lower] = self._definition_to_resolved(term_lower, defn)
                    fuzzy_found = True
                    break
            if fuzzy_found:
                continue

            # Try: does the term match a column name directly?
            # This handles cases where the user says "show me price" and "price" is a column
            if term_lower in columns_lower:
                actual_col = columns_lower[term_lower]
                resolved[term_lower] = ResolvedMetric(
                    query_term=term,
                    canonical_name=term_lower,
                    display_name=actual_col.replace("_", " ").title(),
                    source_column=actual_col,
                    aggregation="sum",
                    confidence=0.60,
                    source="column_name",
                    resolve_status="partial",
                )
                continue

            # Try snake_case variants
            term_as_snake = term_lower.replace(" ", "_")
            if term_as_snake in columns_lower:
                actual_col = columns_lower[term_as_snake]
                resolved[term_lower] = ResolvedMetric(
                    query_term=term,
                    canonical_name=term_lower,
                    display_name=actual_col.replace("_", " ").title(),
                    source_column=actual_col,
                    aggregation="sum",
                    confidence=0.55,
                    source="column_name",
                    resolve_status="partial",
                )
                continue

            # Could not resolve
            unresolved.append(term)

        result = MetricResolutionResult(
            original_query=query,
            resolved_metrics=resolved,
            unresolved_terms=unresolved,
            has_governed_definitions=len(resolved) > 0,
            total_resolved=len(resolved),
            total_unresolved=len(unresolved),
        )

        if result.has_governed_definitions:
            logger.info(
                f"[MetricResolution] Resolved {len(resolved)} metrics "
                f"({len(unresolved)} unresolved): "
                f"{', '.join(resolved.keys())}"
            )

        return result

    def _definition_to_resolved(
        self,
        query_term: str,
        defn: MetricDefinition,
    ) -> ResolvedMetric:
        """Convert a MetricDefinition to a ResolvedMetric."""
        return ResolvedMetric(
            query_term=query_term,
            canonical_name=defn.name,
            display_name=defn.display_name,
            source_column=defn.source_column,
            aggregation=defn.aggregation,
            formula=defn.formula,
            filters=defn.filters,
            confidence=defn.confidence,
            source=defn.source.value if hasattr(defn.source, 'value') else str(defn.source),
            resolve_status="resolved",
            metadata={
                "business_category": defn.business_category,
                "polarity": defn.polarity,
                "format_hint": defn.format_hint,
            },
        )

    async def enhance_sql_prompt(
        self,
        query: str,
        dataset_id: str,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        available_columns: Optional[List[str]] = None,
    ) -> Tuple[str, MetricResolutionResult]:
        """
        Resolve metrics and return a prompt block for SQL injection.

        This is the primary entry point for the QueryExecutor. It returns:
          (governance_block, resolution_result)

        The governance_block should be injected into the SQL generation prompt.

        Fast-path: if the dataset has NO governed definitions at all, skip
        extraction and resolution entirely to avoid unnecessary overhead.
        """
        if not query or not query.strip():
            return "", MetricResolutionResult(original_query=query or "")

        # Fast-path: no definitions at all for this dataset → skip
        has_defs = await self._store.has_definitions(
            dataset_id=dataset_id,
            user_id=user_id,
            workspace_id=workspace_id,
        )
        if not has_defs:
            logger.debug(
                f"[MetricResolution] No definitions for dataset={dataset_id[:8]}, skipping"
            )
            return "", MetricResolutionResult(original_query=query)

        result = await self.resolve(
            query=query,
            dataset_id=dataset_id,
            user_id=user_id,
            workspace_id=workspace_id,
            available_columns=available_columns,
        )

        governance_block = result.to_sql_engine_block()
        return governance_block, result


# Singleton
metric_resolution_service = MetricResolutionService()

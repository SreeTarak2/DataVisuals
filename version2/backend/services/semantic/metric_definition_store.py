"""
semantic/metric_definition_store.py — Unified Metric Definition Repository
===========================================================================

Aggregates metric definitions from ALL sources into a single, prioritized view:

  Source                    | Priority | What it provides
  --------------------------|----------|-----------------------------------------------
  MetricCorrectionStore     | highest  | User-submitted column role overrides
  CorrectionRule (semantic) | high     | "revenue means SUM(price * quantity) filtered by X"
  MetricMapping             | high     | Explicit term → column + formula mappings
  BeliefService rules       | high     | Business rules like "Revenue must exclude refunds"
  Domain template KPIs      | medium   | Pre-built formulas (MRR = SUM(revenue), Churn = ...)
  SemanticClassifier        | medium   | Column role + business category detection
  Column name patterns      | lowest   | Column name heuristic patterns (revenue, cost)

On every query, the store merges all sources into a single prioritized list
per dataset. Higher-priority sources override lower-priority ones for the
same metric name.

Cache: In-memory per dataset, TTL 60 seconds. Invalidated on correction write.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Source type enum ─────────────────────────────────────────────────────────


class MetricDefinitionSource(str, Enum):
    """Source of a metric definition — determines priority during resolution."""

    CORRECTION_ROLE = "correction_role"        # MetricCorrectionStore override
    CORRECTION_SEMANTIC = "correction_semantic"  # CorrectionRule with MetricSemantic
    METRIC_MAPPING = "metric_mapping"           # Explicit term → column mapping
    BELIEF_RULE = "belief_rule"                  # Business rule from BeliefService
    DOMAIN_TEMPLATE = "domain_template"          # Pre-built KPI template
    SEMANTIC_CLASSIFIER = "semantic_classifier"  # Automatic column classification
    COLUMN_NAME = "column_name"                  # Column name heuristic fallback


# Priority order — lower number = higher priority (overrides lower)
_SOURCE_PRIORITY: Dict[MetricDefinitionSource, int] = {
    MetricDefinitionSource.CORRECTION_ROLE: 10,
    MetricDefinitionSource.CORRECTION_SEMANTIC: 20,
    MetricDefinitionSource.METRIC_MAPPING: 30,
    MetricDefinitionSource.BELIEF_RULE: 40,
    MetricDefinitionSource.DOMAIN_TEMPLATE: 50,
    MetricDefinitionSource.SEMANTIC_CLASSIFIER: 60,
    MetricDefinitionSource.COLUMN_NAME: 70,
}


# ── Data model ────────────────────────────────────────────────────────────────


@dataclass
class MetricDefinition:
    """
    A single governed metric definition.

    This is the canonical representation that the MetricResolutionService
    resolves user queries against. Every metric in the system is represented
    as one of these, regardless of its original source.
    """

    # Identity
    name: str                                  # Canonical name, lowercase — "revenue", "churn_rate"
    display_name: str                          # Human-readable — "Total Revenue", "Churn Rate"
    description: str = ""                      # What this metric represents

    # Source tracking
    source: MetricDefinitionSource = MetricDefinitionSource.COLUMN_NAME
    source_details: str = ""                   # e.g. "template:kpi_definitions" or "user:correction:abc123"
    confidence: float = 0.5                    # 0.0-1.0

    # Data mapping
    source_column: Optional[str] = None        # The actual column name in the dataset
    aggregation: str = "sum"                   # sum, mean, median, count, count_unique, min, max
    formula: Optional[str] = None              # Optional SQL expression or formula string
    filters: List[str] = field(default_factory=list)  # Optional WHERE conditions
    joins: List[Dict[str, str]] = field(default_factory=list)  # Optional joins

    # Business metadata
    business_category: str = "unknown"         # revenue, cost, users, rate, etc.
    polarity: str = "higher_is_better"         # higher_is_better | lower_is_better
    format_hint: str = "number"                # number, currency, percentage, decimal

    # Governance
    owner: str = "system"                      # Who defined this
    status: str = "active"                     # active | draft | deprecated
    created_at: str = ""                       # ISO timestamp
    updated_at: str = ""                       # ISO timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "source": self.source.value,
            "source_details": self.source_details,
            "confidence": self.confidence,
            "source_column": self.source_column,
            "aggregation": self.aggregation,
            "formula": self.formula,
            "filters": self.filters,
            "business_category": self.business_category,
            "polarity": self.polarity,
            "format_hint": self.format_hint,
            "owner": self.owner,
            "status": self.status,
        }

    def to_prompt_block(self) -> str:
        """Format as a prompt block for injection into SQL generation context."""
        parts = [f"  - {self.display_name} ({self.name})"]
        if self.source_column:
            parts.append(f"    Column: {self.source_column}")
        parts.append(f"    Aggregation: {self.aggregation.upper()}")
        if self.formula:
            parts.append(f"    Formula: {self.formula}")
        if self.filters:
            parts.append(f"    Filters: {'; '.join(self.filters)}")
        parts.append(f"    Confidence: {self.confidence:.0%} (source: {self.source.value})")
        return "\n".join(parts)

    @property
    def priority(self) -> int:
        return _SOURCE_PRIORITY.get(self.source, 99)


# ── Metric definition store ──────────────────────────────────────────────────


class MetricDefinitionStore:
    """
    Unified repository for all metric definitions across all sources.

    Cache structure:
      _cache[dataset_id] = {
          "definitions": {metric_name: MetricDefinition},
          "by_column": {column_name: [MetricDefinition]},
          "timestamp": time.time(),
      }
    """

    CACHE_TTL = 60  # seconds

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        # has_definitions cache: cache_key -> (timestamp, has_defs: bool)
        # Positive results cached for 300s, negative results for 60s
        self._has_definitions_cache: Dict[str, tuple] = {}
        self._definitions_exist_ttl: float = 300.0
        self._definitions_absent_ttl: float = 60.0
        self._initialized_stores: bool = False

    # ── Public API ──────────────────────────────────────────────────────────

    async def has_definitions(
        self,
        dataset_id: str,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> bool:
        """
        Fast check if a dataset has any governed metric definitions.

        Uses a separate cache with asymmetric TTL:
        - Positive results (definitions exist): cached 300 seconds
        - Negative results (no definitions): cached  60 seconds

        This avoids paying the 4-async-DB-call merge cost on datasets
        that have never had definitions defined.
        """
        cache_key = f"{dataset_id}:{user_id or 'none'}:{workspace_id or 'none'}"

        now = time.time()
        cached = self._has_definitions_cache.get(cache_key)
        if cached is not None:
            cached_time, cached_value = cached
            ttl = self._definitions_exist_ttl if cached_value else self._definitions_absent_ttl
            if now - cached_time < ttl:
                return cached_value

        definitions = await self.get_definitions(dataset_id, user_id, workspace_id)
        has_any = len(definitions) > 0

        self._has_definitions_cache[cache_key] = (now, has_any)

        return has_any

    async def get_definitions(
        self,
        dataset_id: str,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, MetricDefinition]:
        """
        Get ALL metric definitions for a dataset, merged from all sources.

        Returns dict of {canonical_metric_name: MetricDefinition}.
        Higher-priority sources override lower-priority ones for the same name.

        Uses in-memory cache with 60s TTL. Set force_refresh=True to bypass.
        """
        cache_key = f"{dataset_id}:{user_id or 'none'}"

        # Check cache
        if not force_refresh and cache_key in self._cache:
            entry = self._cache[cache_key]
            if time.time() - entry["timestamp"] < self.CACHE_TTL:
                return entry["definitions"]

        # Build from all sources
        definitions: Dict[str, MetricDefinition] = {}

        # Source 1: MetricCorrectionStore (highest priority)
        await self._merge_correction_store(definitions, dataset_id)

        # Source 2: Correction rules with metric semantics
        if workspace_id:
            await self._merge_correction_rules(definitions, workspace_id)

        # Source 3: Metric mappings
        if workspace_id:
            await self._merge_metric_mappings(definitions, workspace_id)

        # Source 4: Belief service rules
        if user_id and dataset_id:
            await self._merge_belief_rules(definitions, user_id, dataset_id)

        # Source 5: Domain template KPIs
        await self._merge_domain_templates(definitions, dataset_id)

        # Cache
        self._cache[cache_key] = {
            "definitions": definitions,
            "timestamp": time.time(),
        }

        logger.info(
            f"[MetricDefinitionStore] Built {len(definitions)} definitions "
            f"for dataset={dataset_id[:8]}"
        )
        return definitions

    async def get_definitions_for_columns(
        self,
        dataset_id: str,
        column_names: List[str],
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, List[MetricDefinition]]:
        """
        Get all definitions that reference any of the given columns.

        Returns dict of {column_name: [MetricDefinition]} — helpful for
        identifying which columns have governed definitions.
        """
        definitions = await self.get_definitions(dataset_id, user_id, workspace_id)

        result: Dict[str, List[MetricDefinition]] = {}
        for metric_name, defn in definitions.items():
            if defn.source_column and defn.source_column in column_names:
                result.setdefault(defn.source_column, []).append(defn)

        return result

    def invalidate_cache(self, dataset_id: Optional[str] = None):
        """Invalidate cache for a specific dataset or all datasets."""
        if dataset_id:
            keys_to_remove = [k for k in self._cache if k.startswith(dataset_id)]
            for k in keys_to_remove:
                del self._cache[k]
            # Also clear has_definitions cache entries for this dataset
            has_def_keys = [k for k in self._has_definitions_cache if k.startswith(dataset_id)]
            for k in has_def_keys:
                del self._has_definitions_cache[k]
            logger.info(f"[MetricDefinitionStore] Invalidated cache for dataset={dataset_id[:8]}")
        else:
            self._cache.clear()
            self._has_definitions_cache.clear()
            logger.info("[MetricDefinitionStore] Invalidated all caches")

    # ── Source merge methods ────────────────────────────────────────────────

    async def _merge_correction_store(
        self,
        definitions: Dict[str, MetricDefinition],
        dataset_id: str,
    ):
        """Merge user role corrections from MetricCorrectionStore."""
        try:
            from services.corrections.metric_correction_store import metric_correction_store

            corrections = await metric_correction_store.get_corrections(dataset_id)
            for column, corr in corrections.items():
                metric_name = corr.corrected_role.lower()
                if not metric_name or metric_name == "unknown":
                    metric_name = column.lower().replace("_", " ")

                # Map boolean aggregation overrides to actual aggregation strings
                # Check in specificity order: count_unique → median → mean → count → max → min → sum
                agg_overrides = corr.aggregation_overrides or {}
                if agg_overrides.get("count_unique_allowed"):
                    inferred_agg = "count_unique"
                elif agg_overrides.get("median_allowed"):
                    inferred_agg = "median"
                elif agg_overrides.get("avg_allowed"):
                    inferred_agg = "mean"
                elif agg_overrides.get("count_allowed"):
                    inferred_agg = "count"
                elif agg_overrides.get("max_allowed"):
                    inferred_agg = "max"
                elif agg_overrides.get("min_allowed"):
                    inferred_agg = "min"
                else:
                    inferred_agg = "sum"

                defn = MetricDefinition(
                    name=metric_name,
                    display_name=column.replace("_", " ").title(),
                    description=f"User-corrected classification for column '{column}'",
                    source=MetricDefinitionSource.CORRECTION_ROLE,
                    source_details=f"correction:role:{column}",
                    confidence=0.99,
                    source_column=column,
                    aggregation=inferred_agg,
                    business_category=metric_name,
                    owner="user",
                    status="active",
                )

                self._upsert_definition(definitions, metric_name, defn)
        except Exception as e:
            logger.debug(f"[MetricDefinitionStore] CorrectionStore merge failed: {e}")

    async def _merge_correction_rules(
        self,
        definitions: Dict[str, MetricDefinition],
        workspace_id: str,
    ):
        """Merge correction rules with metric semantics from ContextStore."""
        try:
            from services.feedback.context_store import context_store

            rules = await context_store.get_correction_rules(workspace_id)
            for rule in rules:
                if not rule.metric_semantic:
                    continue

                sem = rule.metric_semantic
                metric_name = sem.metric_name.lower().strip()
                if not metric_name:
                    continue

                defn = MetricDefinition(
                    name=metric_name,
                    display_name=metric_name.replace("_", " ").title(),
                    description=sem.definition or rule.interpretation,
                    source=MetricDefinitionSource.CORRECTION_SEMANTIC,
                    source_details=f"correction:rule:{rule.id}",
                    confidence=rule.confidence or 0.85,
                    source_column=sem.source_columns[0] if sem.source_columns else None,
                    aggregation=sem.aggregation or "sum",
                    formula=sem.formula,
                    filters=[],
                    business_category=metric_name,
                    owner="user",
                    status="active",
                )

                self._upsert_definition(definitions, metric_name, defn)
        except Exception as e:
            logger.debug(f"[MetricDefinitionStore] CorrectionRules merge failed: {e}")

    async def _merge_metric_mappings(
        self,
        definitions: Dict[str, MetricDefinition],
        workspace_id: str,
    ):
        """Merge explicit metric mappings from ContextStore."""
        try:
            from services.feedback.context_store import context_store

            mappings = await context_store.get_metric_mappings(workspace_id)
            for mapping in mappings:
                metric_name = mapping.term.lower().strip()
                if not metric_name:
                    continue

                defn = MetricDefinition(
                    name=metric_name,
                    display_name=metric_name.replace("_", " ").title(),
                    description=mapping.definition,
                    source=MetricDefinitionSource.METRIC_MAPPING,
                    source_details=f"mapping:{mapping.id}",
                    confidence=0.95,
                    source_column=mapping.source_column,
                    aggregation="sum",
                    formula=mapping.formula,
                    filters=[],
                    business_category=metric_name,
                    owner="user",
                    status="active",
                )

                self._upsert_definition(definitions, metric_name, defn)
        except Exception as e:
            logger.debug(f"[MetricDefinitionStore] MetricMappings merge failed: {e}")

    async def _merge_belief_rules(
        self,
        definitions: Dict[str, MetricDefinition],
        user_id: str,
        dataset_id: str,
    ):
        """Merge business rules from BeliefService."""
        try:
            from services.memory.belief_service import BeliefService
            from db.database import get_database

            db = get_database()
            belief_service = BeliefService(db)
            beliefs = await belief_service.get_active_beliefs(user_id, dataset_id)

            for belief in beliefs:
                content = belief.get("content", "")
                rule_type = belief.get("rule_type", "business_logic")
                applies_to = belief.get("applies_to", []) or []

                # Only process metric_definition type beliefs
                if rule_type not in ("metric_definition", "business_logic"):
                    continue

                # Try to extract a metric name from the rule
                metric_name = self._extract_metric_name(content, applies_to)
                if not metric_name:
                    continue

                defn = MetricDefinition(
                    name=metric_name,
                    display_name=metric_name.replace("_", " ").title(),
                    description=content,
                    source=MetricDefinitionSource.BELIEF_RULE,
                    source_details=f"belief:{belief.get('_id', 'unknown')}",
                    confidence=belief.get("confidence", 0.7),
                    source_column=None,
                    aggregation="sum",
                    formula=None,
                    filters=[],
                    business_category=metric_name,
                    owner="user",
                    status="active",
                )

                self._upsert_definition(definitions, metric_name, defn)
        except Exception as e:
            logger.debug(f"[MetricDefinitionStore] BeliefRules merge failed: {e}")

    async def _merge_domain_templates(
        self,
        definitions: Dict[str, MetricDefinition],
        dataset_id: str,
    ):
        """Merge domain template KPIs from kpi/definitions.py."""
        try:
            from services.kpi.definitions import ALL_KPIS

            for kpi_id, kpi_def in ALL_KPIS.items():
                formula = kpi_def.formula
                metric_name = kpi_id.lower().strip()

                # Determine source column and aggregation
                source_column = None
                aggregation = "sum"

                if formula:
                    aggregation = formula.aggregation.value if formula.aggregation else "sum"
                    if formula.column:
                        source_column = formula.column
                    elif formula.numerator_column:
                        source_column = formula.numerator_column

                defn = MetricDefinition(
                    name=metric_name,
                    display_name=kpi_def.name,
                    description=kpi_def.description or "",
                    source=MetricDefinitionSource.DOMAIN_TEMPLATE,
                    source_details=f"template:{kpi_id}",
                    confidence=0.80,
                    source_column=source_column,
                    aggregation=aggregation,
                    formula=formula.custom_expression if formula else None,
                    filters=[],
                    business_category=kpi_def.category.value if kpi_def.category else "unknown",
                    owner="system",
                    status="active",
                )

                self._upsert_definition(definitions, metric_name, defn)
        except Exception as e:
            logger.debug(f"[MetricDefinitionStore] DomainTemplates merge failed: {e}")

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _upsert_definition(
        self,
        definitions: Dict[str, MetricDefinition],
        metric_name: str,
        new_defn: MetricDefinition,
    ):
        """Insert or update a definition — higher priority wins on conflict."""
        existing = definitions.get(metric_name)
        if existing is None or new_defn.priority < existing.priority:
            definitions[metric_name] = new_defn

    @staticmethod
    def _extract_metric_name(
        content: str,
        applies_to: List[str],
    ) -> Optional[str]:
        """Extract a canonical metric name from a belief rule."""
        if applies_to and len(applies_to) > 0:
            return applies_to[0].lower().strip()

        # Try to extract from content: "Revenue must exclude refunds" → "revenue"
        content_lower = content.lower()
        for word in content_lower.split()[:5]:
            if word in {
                "revenue", "profit", "cost", "margin", "churn", "ltv", "cac",
                "mrr", "arr", "aov", "arpu", "sales", "volume", "count",
            }:
                return word

        # First word that's a data-like term
        import re
        match = re.match(r"\b([a-z][a-z_]+)\b", content_lower)
        if match:
            return match.group(1)

        return None


# Singleton
metric_definition_store = MetricDefinitionStore()

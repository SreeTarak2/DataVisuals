"""
intelligence/entity_aware_profile.py — Entity-Aware Column Profiling (Layer 4)

Merges three layers into one unified profile per column:
  Layer 1: RawColumnProfile (pure stats from profiling/)
  Layer 2: ColumnIntelligence (semantic role, behavioral role, business category)
  Layer 3: EntityInfo + EntityDetector (entity type, entity relationships)

Output: EntityAwareProfile — every column knows:
  - Its statistical profile (mean, median, std, etc.)
  - Its semantic meaning (MEASURE, DIMENSION, TIME, IDENTITY, etc.)
  - Which business entity it belongs to (Customer, Product, Order, etc.)
  - Its entity-level statistics (concentration, per-entity averages)

No LLM calls. All deterministic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from services.intelligence.engine import intelligence_engine, IntelligenceEngine
from services.intelligence.models import (
    BusinessCategory,
    ColumnIntelligence,
    EntityInfo,
    SemanticRole,
    UnifiedIntelligenceResult,
)
from services.profiling.models import RawProfilingResult

logger = logging.getLogger(__name__)


# ── Patterns for entity column detection ──────────────────────────────────────

# Patterns to detect which entity type a column likely describes
_ENTITY_ATTRIBUTE_PATTERNS: list[tuple[str, str]] = [
    # (entity_type, regex pattern)
    ("Customer", r"\b(customer|client|buyer|member|subscriber)\b"),
    ("Product", r"\b(product|item|sku|part)\b"),
    ("Order", r"\b(order|transaction|purchase|invoice)\b"),
    ("Employee", r"\b(employee|staff|worker|personnel|manager)\b"),
    ("Patient", r"\b(patient|doctor|physician|nurse|diagnosis)\b"),
    ("Student", r"\b(student|teacher|professor|course|enrollment|grade)\b"),
    ("Vehicle", r"\b(vehicle|car|truck|fleet|mileage|engine|fuel)\b"),
    ("Property", r"\b(property|house|apartment|building|listing|rent)\b"),
    ("Company", r"\b(company|vendor|supplier|organization|brand|partner)\b"),
    ("Shipment", r"\b(shipment|delivery|parcel|carrier|tracking)\b"),
    ("Region", r"\b(region|country|city|state|territory|zone|area)\b"),
    ("Campaign", r"\b(campaign|ad|promotion|marketing|channel)\b"),
    ("Subscription", r"\b(subscription|plan|tier|package|billing)\b"),
]


# ── EntityAwareProfile — the unified column profile ───────────────────────────


@dataclass
class EntityAwareProfile:
    """Everything known about a column: stats + semantics + entity.

    This is the single unified profile consumed by the KPI generator,
    chart recommendation engine, insight engine, and root cause analysis.
    """

    # ── Identity ──
    name: str                                    # Raw column name (e.g. "customer_id")
    display_name: str = ""                       # Human-readable (e.g. "Customer")

    # ── Entity ──
    entity_type: str = "Unknown"                 # "Customer", "Product", "Order", etc.
    entity_column: Optional[str] = None          # Which column is the entity ID (self if IS entity ID)
    is_entity_id: bool = False                   # True if this IS an entity ID column
    is_entity_reference: bool = False            # True if this references another entity (foreign key)
    is_entity_attribute: bool = False            # True if this is a measure/attribute of an entity
    entity_confidence: float = 0.0               # Confidence in entity assignment

    # ── Statistical Profile (from profiling layer) ──
    dtype: str = "unknown"
    n_rows: int = 0
    n_nulls: int = 0
    n_unique: int = 0
    null_pct: float = 0.0
    cardinality_ratio: float = 0.0

    col_sum: Optional[float] = None
    col_mean: Optional[float] = None
    col_median: Optional[float] = None
    col_std: Optional[float] = None
    col_min: Optional[float] = None
    col_max: Optional[float] = None
    col_p25: Optional[float] = None
    col_p75: Optional[float] = None
    col_p90: Optional[float] = None
    cv: Optional[float] = None
    skewness: Optional[float] = None
    is_bounded_01: bool = False
    is_integer_valued: bool = False

    # ── Semantic Classification (from intelligence layer) ──
    semantic_role: str = "dimension"             # measure, rate, count, dimension, time, identity
    behavioral_role: str = "unknown"
    business_category: str = "unknown"
    polarity: str = "higher_is_better"           # higher_is_better | lower_is_better
    classification_confidence: float = 0.0

    # ── Aggregation ──
    aggregation: str = "sum"                     # Selected aggregation for KPI computation
    recommended_aggregation: str = "sum"

    # ── Entity-Level Stats (NEW — this is what makes it entity-aware) ──
    entity_cardinality: Optional[int] = None      # Number of unique entities
    avg_records_per_entity: Optional[float] = None  # Avg rows per entity
    entity_concentration_pct: Optional[float] = None  # Top entity's % of total (if top-1 found)
    top_entity_value: Optional[str] = None         # Name/label of the dominant entity
    top_entity_pct: Optional[float] = None         # Top entity's share (same as concentration_pct)

    # ── Raw Metadata (for lineage/trust layer) ──
    source_table: str = "unknown"
    formula: Optional[str] = None                 # If derived (e.g. "revenue - cogs")


def _infer_entity_from_name(col_name: str) -> Optional[str]:
    """Infer entity type from column name patterns.

    E.g. "customer_name" → "Customer", "order_date" → "Order", "product_price" → "Product"
    """
    base = col_name.lower().replace("_", " ").replace("-", " ").strip()
    for entity_type, pattern in _ENTITY_ATTRIBUTE_PATTERNS:
        import re
        if re.search(pattern, base, re.I):
            return entity_type
    return None


def _infer_entity_for_column(
    col_name: str,
    semantic_role: SemanticRole,
    detected_entities: List[EntityInfo],
) -> Tuple[str, Optional[str], bool, bool, float]:
    """Determine which entity a column belongs to.

    Returns:
        (entity_type, entity_column, is_entity_id, is_entity_reference, confidence)
    """
    col_lower = col_name.lower().replace("_", " ").replace("-", " ").strip()

    # Case 1: This column IS a detected entity ID
    for ent in detected_entities:
        if ent.entity_column == col_name:
            return ent.entity_type, col_name, True, False, ent.confidence

    # Case 2: This column references a detected entity (FK-like)
    for ent in detected_entities:
        entity_base = ent.entity_type.lower()
        # Check if column name contains the entity type name
        if entity_base in col_lower.split():
            return ent.entity_type, ent.entity_column, False, True, 0.75
        # Check if entity column name is a substring
        ref_base = ent.entity_column.lower().replace("_id", "").replace("_key", "").strip()
        if ref_base and ref_base in col_lower:
            return ent.entity_type, ent.entity_column, False, True, 0.70

    # Case 3: Infer entity from column name patterns
    inferred = _infer_entity_from_name(col_name)
    if inferred:
        # Find if this entity type has a corresponding ID column
        for ent in detected_entities:
            if ent.entity_type == inferred:
                return inferred, ent.entity_column, False, True, 0.65
        return inferred, None, False, True, 0.55

    # Case 4: Time columns belong to the primary entity
    if semantic_role == SemanticRole.TIME and detected_entities:
        primary = detected_entities[0]
        return primary.entity_type, primary.entity_column, False, False, 0.50

    # Case 5: Unknown / generic
    if semantic_role == SemanticRole.MEASURE and detected_entities:
        # Measures default to the primary (first) entity
        primary = detected_entities[0]
        return primary.entity_type, primary.entity_column, False, True, 0.45

    return "Unknown", None, False, False, 0.0


def _compute_entity_concentration(
    df: pl.DataFrame,
    col_name: str,
    entity_id_col: str,
) -> Tuple[Optional[float], Optional[str], Optional[float]]:
    """Compute entity concentration: what % does the top entity contribute?

    For example: "Top 1 Customer accounts for 34% of Revenue"

    Returns:
        (entity_cardinality, top_entity_value, top_entity_pct)
    """
    try:
        if col_name not in df.columns or entity_id_col not in df.columns:
            return None, None, None

        clean = df.drop_nulls(subset=[col_name, entity_id_col])
        if len(clean) < 5:
            return None, None, None

        # Group by entity, sum the measure
        grouped = (
            clean.group_by(entity_id_col)
            .agg(pl.col(col_name).sum().alias("_total"))
            .sort("_total", descending=True)
        )

        total = grouped["_total"].sum()
        if not total or total == 0:
            return None, None, None

        top_row = grouped.head(1)
        top_val = float(top_row["_total"].to_list()[0])
        top_entity = str(top_row[entity_id_col].to_list()[0])
        top_pct = round((top_val / abs(total)) * 100, 1)
        entity_card = len(grouped)

        return entity_card, top_entity, top_pct
    except Exception as e:
        logger.debug(f"[EntityAware] Concentration failed for '{col_name}': {e}")
        return None, None, None


def _compute_display_name(col_name: str) -> str:
    """Convert raw column name to human-readable display name."""
    # Strip entity suffixes
    name = col_name.replace("_", " ").replace("-", " ").strip().title()
    # Remove common suffixes for cleaner display
    for suffix in (" Id", " Ids", " Key", " Uuid"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    return name.strip()


def _build_entity_aware_profile(
    col_intel: ColumnIntelligence,
    entity_info: Optional[EntityInfo],
    raw_stats: Dict[str, Any],
    df: pl.DataFrame,
    detected_entities: List[EntityInfo],
    unified: UnifiedIntelligenceResult,
) -> EntityAwareProfile:
    """Build a single EntityAwareProfile from all available information."""
    col_name = col_intel.name

    # ── Determine entity assignment ──
    entity_type, entity_col, is_eid, is_ref, ent_conf = _infer_entity_for_column(
        col_name, col_intel.semantic_role, detected_entities,
    )

    # ── Build profile ──
    profile = EntityAwareProfile(
        name=col_name,
        display_name=_compute_display_name(col_name),
        entity_type=entity_type,
        entity_column=entity_col,
        is_entity_id=is_eid,
        is_entity_reference=is_ref,
        is_entity_attribute=not is_eid and col_intel.semantic_role in (
            SemanticRole.MEASURE, SemanticRole.RATE, SemanticRole.COUNT,
        ),
        entity_confidence=ent_conf,
        dtype=raw_stats.get("dtype", "unknown"),
        n_rows=raw_stats.get("n_rows", 0),
        n_nulls=raw_stats.get("n_nulls", 0),
        n_unique=raw_stats.get("n_unique", 0),
        null_pct=raw_stats.get("null_pct", 0.0),
        cardinality_ratio=raw_stats.get("cardinality_ratio", 0.0),
        col_sum=raw_stats.get("col_sum"),
        col_mean=raw_stats.get("col_mean"),
        col_median=raw_stats.get("col_median"),
        col_std=raw_stats.get("col_std"),
        col_min=raw_stats.get("col_min"),
        col_max=raw_stats.get("col_max"),
        col_p25=raw_stats.get("col_p25"),
        col_p75=raw_stats.get("col_p75"),
        col_p90=raw_stats.get("col_p90"),
        cv=raw_stats.get("cv"),
        skewness=raw_stats.get("skewness"),
        is_bounded_01=raw_stats.get("is_bounded_01", False),
        is_integer_valued=raw_stats.get("is_integer_valued", False),
        semantic_role=col_intel.semantic_role.value,
        behavioral_role=col_intel.behavioral_role.value,
        business_category=col_intel.business_category.value,
        polarity=col_intel.polarity,
        classification_confidence=col_intel.classification_confidence,
        aggregation=_pick_aggregation(col_intel, raw_stats),
        recommended_aggregation=col_intel.aggregation_suitability.recommended_aggregation,
        source_table="upload",
    )

    # ── Compute entity-level stats for measure/count columns that have an entity ──
    if entity_col and entity_col != col_name and entity_col in df.columns:
        if profile.semantic_role in ("measure", "rate", "count"):
            card, top_val, top_pct = _compute_entity_concentration(df, col_name, entity_col)
            profile.entity_cardinality = card
            profile.top_entity_value = top_val
            profile.top_entity_pct = top_pct
            if top_pct is not None:
                profile.entity_concentration_pct = top_pct

    # ── Entity info from intelligence layer ──
    if entity_info:
        profile.entity_cardinality = profile.entity_cardinality or entity_info.unique_count
        profile.avg_records_per_entity = entity_info.avg_records_per_entity

    return profile


def _pick_aggregation(col_intel: ColumnIntelligence, raw_stats: Dict[str, Any]) -> str:
    """Pick the best aggregation for this column based on its semantics."""
    role = col_intel.semantic_role

    if role == SemanticRole.IDENTITY:
        return "count_unique"
    if role == SemanticRole.TIME:
        return "none"
    if role == SemanticRole.DIMENSION:
        return "count_unique"

    if role == SemanticRole.RATE:
        return "mean"

    if role == SemanticRole.COUNT:
        return "sum"

    # MEASURE: pick based on business category + skewness
    cat = col_intel.business_category
    skewness = raw_stats.get("skewness", 0) or 0
    cv = raw_stats.get("cv", 0) or 0

    if cat in (BusinessCategory.REVENUE, BusinessCategory.COST, BusinessCategory.VOLUME):
        return "sum"

    if cat == BusinessCategory.PRICE:
        return "median" if abs(skewness) > 1.5 else "mean"

    if cat == BusinessCategory.USERS:
        return "count_unique"

    if cat in (BusinessCategory.RATE_METRIC, BusinessCategory.PERFORMANCE):
        return "mean"

    # Default: sum for high-variance, mean for low-variance
    return "sum" if cv > 0.8 else "mean"


def _extract_raw_column_stats(
    df: pl.DataFrame,
    col_profile: "RawColumnProfile",
) -> Dict[str, Any]:
    """Extract raw column stats from a DataFrame and ColumnProfile."""
    stats_dict: Dict[str, Any] = {
        "dtype": col_profile.dtype,
        "n_rows": len(df),
        "n_nulls": col_profile.cardinality.null_count,
        "n_unique": col_profile.cardinality.unique_count,
        "cardinality_ratio": col_profile.cardinality.cardinality_ratio,
        "null_pct": col_profile.cardinality.null_pct,
    }

    if col_profile.stats:
        s = col_profile.stats
        stats_dict.update({
            "col_sum": s.col_sum,
            "col_mean": s.col_mean,
            "col_median": s.col_median,
            "col_std": s.col_std,
            "col_min": s.col_min,
            "col_max": s.col_max,
            "col_p25": s.col_p25,
            "col_p75": s.col_p75,
            "col_p90": s.col_p90,
            "cv": s.cv,
            "skewness": s.skewness,
            "is_bounded_01": s.is_bounded_01,
            "is_integer_valued": s.is_integer_valued,
        })

    return stats_dict


# ── Public API ────────────────────────────────────────────────────────────────


def build_entity_aware_profiles(
    df: pl.DataFrame,
    profiling_result: Optional[RawProfilingResult] = None,
    intelligence_result: Optional[UnifiedIntelligenceResult] = None,
) -> List[EntityAwareProfile]:
    """Build entity-aware profiles for every column in the DataFrame.

    This is the main entry point. It:
    1. Runs the intelligence engine (if not provided) to get semantic classification,
       entity detection, geo detection, and domain hypotheses
    2. Maps each column to its inferred entity
    3. Computes entity-level statistics (concentration, per-entity averages)
    4. Returns EntityAwareProfile objects ordered by semantic significance

    Args:
        df: The DataFrame to profile.
        profiling_result: Optional pre-computed RawProfilingResult.
            If None, one will be computed from the DataFrame.
        intelligence_result: Optional pre-computed UnifiedIntelligenceResult.
            If None, one will be computed from the profiling result.

    Returns:
        List of EntityAwareProfile objects, one per column.
    """
    from services.profiling.column_profiler import ColumnProfiler
    from services.profiling.models import DatasetInfo, RawProfilingResult

    # ── Step 1: Compute profiling result if not provided ──
    if profiling_result is None:
        profiler = ColumnProfiler()
        raw_cols = profiler.profile_dataframe(df)
        profiling_result = RawProfilingResult(
            dataset=DatasetInfo(
                row_count=len(df),
                column_count=len(df.columns),
            ),
            columns=raw_cols,
        )

    # ── Step 2: Run intelligence engine if not provided ──
    if intelligence_result is None:
        intelligence_result = intelligence_engine.run(profiling_result, df)

    # ── Step 3: Build entity-aware profiles ──
    detected_entities = intelligence_result.entities
    col_intel_by_name = {c.name: c for c in intelligence_result.columns}
    entity_by_col = {e.entity_column: e for e in detected_entities}

    profiles: List[EntityAwareProfile] = []
    for raw_col in profiling_result.columns:
        col_intel = col_intel_by_name.get(raw_col.name)
        if col_intel is None:
            continue

        raw_stats = _extract_raw_column_stats(df, raw_col)
        entity_info = entity_by_col.get(raw_col.name)

        profile = _build_entity_aware_profile(
            col_intel=col_intel,
            entity_info=entity_info,
            raw_stats=raw_stats,
            df=df,
            detected_entities=detected_entities,
            unified=intelligence_result,
        )
        profiles.append(profile)

    # ── Step 4: Sort by semantic significance ──
    # MEASURE/RATE/COUNT first, then DIMENSION, then TIME, then IDENTITY
    role_priority = {
        "measure": 0, "rate": 0, "count": 0,
        "dimension": 1, "time": 2, "identity": 3, "unknown": 4,
    }
    profiles.sort(key=lambda p: (role_priority.get(p.semantic_role, 5), p.name))

    logger.info(
        f"[EntityAware] Built {len(profiles)} profiles "
        f"({len(detected_entities)} entities detected)"
    )
    return profiles


def profiles_by_entity(profiles: List[EntityAwareProfile]) -> Dict[str, List[EntityAwareProfile]]:
    """Group profiles by their entity type.

    Returns:
        { "Customer": [profile, ...], "Order": [profile, ...], "Unknown": [...] }
    """
    result: Dict[str, List[EntityAwareProfile]] = {}
    for p in profiles:
        key = p.entity_type
        if key not in result:
            result[key] = []
        result[key].append(p)
    return result


def primary_entity(profiles: List[EntityAwareProfile]) -> Optional[str]:
    """Determine the primary entity type — the one with the most measure columns."""
    from collections import Counter

    entity_counts: Counter = Counter()
    for p in profiles:
        if p.semantic_role in ("measure", "rate", "count") and p.entity_type != "Unknown":
            entity_counts[p.entity_type] += 1

    if entity_counts:
        return entity_counts.most_common(1)[0][0]
    return None

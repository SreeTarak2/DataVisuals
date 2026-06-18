"""
IntelligentKPIGenerator — Production v5 (Deterministic + Domain-Aware)
======================================================================
Thinks like a data scientist:
  1. Profile every column statistically
  2. Classify column roles (MEASURE / RATE / COUNT / DIMENSION / TIME / IDENTITY)
  3. Detect business domain from column patterns (SaaS / Ecom / Finance)
  4. Generate template KPIs if domain is detected (MRR, Churn, AOV, etc.)
  5. Gate candidates: decision-relevance + direction-clarity + non-redundancy
  6. Select hero + primaries
  7. Compute all values, comparisons, sparklines from real data
  8. Generate deterministic insights — NO LLM calls, purely data-driven
  9. Return production-ready KPI card dicts

No LLM dependency. Selection, aggregation, comparison, narrative — all deterministic Python.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

# Entity-Aware Profiling import
from services.intelligence.entity_aware_profile import (
    build_entity_aware_profiles,
    EntityAwareProfile,
    profiles_by_entity,
)

# Root Cause Chain import
from services.intelligence.root_cause_chain import (
    compute_chains_for_kpis,
    compute_chain,
    RootCauseChain,
)

# Decision Engine import
from services.intelligence.decision_engine import (
    compute_decisions_for_kpis,
)

# Metric Relationship Graph import
from services.intelligence.metric_graph import (
    build_metric_graph,
    attach_metric_decompositions,
)

# DatasetMemo import for domain cache lookups
from services.intelligence.dataset_memo import DatasetMemo, DatasetMemoCache

logger = logging.getLogger(__name__)


# ── Memory Management Defaults ────────────────────────────────────────────────

# Maximum DataFrame size in MB before automatic downsampling kicks in.
# Beyond this, the generator downsamples to `MAX_SAFE_ROWS` rows.
# This prevents OOM crashes on large datasets while maintaining statistical
# accuracy for KPI computation (means, medians, comparisons converge well
# before 200K rows).
DEFAULT_MAX_MEMORY_MB = 500
DEFAULT_MAX_SAFE_ROWS = 200000

# Small dataset threshold: datasets with fewer rows than this skip expensive
# stages that require statistical mass (entity detection, LLM classification,
# synthetic profiles, root cause analysis, surprising patterns, etc.)
SMALL_DATASET_THRESHOLD = 100


# ── Column Classification ─────────────────────────────────────────────────────

# Explicit numeric dtype tuples to replace deprecated pl.NUMERIC_DTYPES / pl.INTEGER_DTYPES
_NUMERIC_DTYPES: tuple = (
    pl.Float32, pl.Float64,
    pl.Int8, pl.Int16, pl.Int32, pl.Int64,
    pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
)
_INTEGER_DTYPES: tuple = (
    pl.Int8, pl.Int16, pl.Int32, pl.Int64,
    pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
)


class ColumnRole(str, Enum):
    MEASURE = "measure"  # numeric, summable  — revenue, cost, salary
    RATE = "rate"  # numeric ratio/pct  — conversion_rate, margin
    COUNT = "count"  # integer counts     — order_count, num_users
    DIMENSION = "dimension"  # categorical        — region, product, status
    TIME = "time"  # datetime           — date, created_at
    IDENTITY = "identity"  # IDs, skip          — customer_id, uuid


# Column name patterns for classification
_ID_RE = re.compile(r"\b(id|uuid|guid|key|hash|token|code|zip|postal|phone|ip|sku|barcode)\b", re.I)
_TIME_RE = re.compile(
    r"\b(date|time|year|month|day|created|updated|timestamp|period|week|quarter)\b",
    re.I,
)
_RATE_RE = re.compile(
    r"\b(rate|ratio|percent|pct|margin|efficiency|factor|score|index|grade|accuracy|precision|recall|auc|ctr)\b",
    re.I,
)
_COUNT_RE = re.compile(
    r"\b(count|num|number|qty|quantity|units|items|orders|transactions|sessions|visits|clicks|impressions|requests)\b",
    re.I,
)

# Business category → polarity mapping
_CATEGORY_PATTERNS: List[Tuple[str, str, str]] = [
    # (category, pattern, polarity)
    (
        "revenue",
        r"\b(revenue|sales|gmv|income|earnings|gross|mrr|arr|net_sales|turnover|proceeds|receipts)\b",
        "higher_is_better",
    ),
    (
        "cost",
        r"\b(cost|expense|opex|capex|cogs|spend|expenditure|loss|burn|overhead|tax|fee|charge|penalty|discount)\b",
        "lower_is_better",
    ),
    (
        "volume",
        r"\b(orders|transactions|purchases|bookings|units|items|shipments|deliveries|installs)\b",
        "higher_is_better",
    ),
    (
        "users",
        r"\b(users|customers|subscribers|members|accounts|clients|visitors|leads|prospects|buyers)\b",
        "higher_is_better",
    ),
    (
        "rate_metric",
        r"\b(rate|ratio|percent|pct|margin|conversion|retention|satisfaction|engagement|utilization)\b",
        "higher_is_better",
    ),
    (
        "churn_risk",
        r"\b(churn|attrition|cancellation|dropout|refund|return|complaint|defect|error|failure|bug|issue)\b",
        "lower_is_better",
    ),
    (
        "price",
        r"\b(price|amount|value|aov|arpu|arpc|ltv|cac|worth|bid|ask)\b",
        "higher_is_better",
    ),
    (
        "performance",
        r"\b(score|rating|nps|csat|satisfaction|quality|performance|rank|grade)\b",
        "higher_is_better",
    ),
    (
        "duration",
        r"\b(duration|latency|age|tenure|days|hours|minutes|seconds|ms|response_time|wait_time|cycle_time)\b",
        "lower_is_better",
    ),
    (
        "quantity",
        r"\b(count|num|qty|quantity|volume|capacity|inventory|stock|supply)\b",
        "higher_is_better",
    ),
]


@dataclass
class ColumnProfile:
    name: str
    role: ColumnRole
    n_rows: int
    n_nulls: int
    n_unique: int

    # Numeric stats (None for non-numeric)
    col_sum: Optional[float] = None
    col_mean: Optional[float] = None
    col_median: Optional[float] = None
    col_std: Optional[float] = None
    col_min: Optional[float] = None
    col_max: Optional[float] = None
    col_p25: Optional[float] = None
    col_p75: Optional[float] = None
    col_p90: Optional[float] = None
    cv: Optional[float] = None  # coefficient of variation
    skewness: Optional[float] = None
    is_bounded_01: bool = False
    is_integer_valued: bool = False

    # Derived classification
    aggregation: str = "sum"
    polarity: str = "higher_is_better"  # or "lower_is_better"
    business_category: str = "unknown"
    importance: str = "medium"  # "hero", "high", "medium"

    @property
    def null_pct(self) -> float:
        return (self.n_nulls / self.n_rows * 100) if self.n_rows > 0 else 0

    @property
    def primary_value(self) -> Optional[float]:
        """The computed KPI value based on aggregation."""
        if self.aggregation == "sum":
            return self.col_sum
        if self.aggregation == "mean":
            return self.col_mean
        if self.aggregation == "median":
            return self.col_median
        if self.aggregation == "max":
            return self.col_max
        if self.aggregation == "min":
            return self.col_min
        return self.col_mean


# ── Column Profiler ───────────────────────────────────────────────────────────


def _profile_numeric(col: pl.Series) -> Dict[str, Any]:
    clean = col.drop_nulls().cast(pl.Float64)
    if len(clean) == 0:
        return {}
    n = len(clean)
    mean = float(clean.mean())
    std = float(clean.std()) if n > 1 else 0.0
    mn = float(clean.min())
    mx = float(clean.max())
    p25 = float(clean.quantile(0.25))
    p75 = float(clean.quantile(0.75))
    p90 = float(clean.quantile(0.90))
    med = float(clean.median())
    cv = abs(std / mean) if mean != 0 else 0.0

    skew = float(clean.skew()) if n >= 3 else 0.0

    sample = clean.sample(min(1000, n), seed=42).to_list()
    return {
        "col_sum": round(float(clean.sum()), 4),
        "col_mean": round(mean, 4),
        "col_median": round(med, 4),
        "col_std": round(std, 4),
        "col_min": round(mn, 4),
        "col_max": round(mx, 4),
        "col_p25": round(p25, 4),
        "col_p75": round(p75, 4),
        "col_p90": round(p90, 4),
        "cv": round(cv, 4),
        "skewness": round(skew, 4),
        "is_bounded_01": mn >= 0 and mx <= 1,
        "is_integer_valued": all(v == int(v) for v in sample),
    }


# ── String Column Coercion (parse numeric & date strings) ──────────────────

_DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y",
    "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
    "%d-%m-%Y", "%m-%d-%Y", "%d/%m/%y",
    "%Y%m%d", "%b %d, %Y", "%d %b %Y", "%B %d, %Y", "%d %B %Y",
]


def _coerce_string_columns(df: pl.DataFrame) -> pl.DataFrame:
    """
    Pre-processing step: attempt to cast string columns to more specific types.

    1. Numeric detection: if a string column looks like numbers (handles commas,
       dollar signs, whitespace), cast to Float64.
    2. Date detection: if a string column looks like dates (tries common formats),
       cast to Date.

    Only recasts if >80% of non-null values parse successfully, to avoid
    corrupting genuinely textual columns.
    """
    for col in df.columns:
        if df[col].dtype != pl.Utf8:
            continue

        clean = df[col].drop_nulls()
        if len(clean) < 5:
            continue

        # ── Try numeric first ────────────────────────────────────────────
        stripped = clean.str.strip_chars()
        cleaned_str = stripped.str.replace_all(r"[$, ]", "", literal=False)
        parsed_num = cleaned_str.cast(pl.Float64, strict=False)
        valid_ratio = parsed_num.is_not_null().sum() / len(clean)

        if valid_ratio > 0.80:
            # Looks numeric — cast the whole column
            full_stripped = df[col].str.strip_chars()
            full_cleaned = full_stripped.str.replace_all(r"[$, ]", "", literal=False)
            df = df.with_columns(full_cleaned.cast(pl.Float64).alias(col))
            logger.info(f"[KPI] Coerced string column '{col}' to Float64 ({valid_ratio:.0%} parse rate)")
            continue

        # ── Try date parsing ────────────────────────────────────────────
        for fmt in _DATE_FORMATS:
            try:
                parsed_date = clean.str.to_date(fmt, strict=False)
                valid_ratio = parsed_date.is_not_null().sum() / len(clean)
                if valid_ratio > 0.80:
                    full_parsed = df[col].str.to_date(fmt, strict=False)
                    df = df.with_columns(full_parsed.alias(col))
                    logger.info(f"[KPI] Coerced string column '{col}' to Date (format={fmt}, {valid_ratio:.0%} parse rate)")
                    break
            except Exception:
                continue

    return df


def _classify_role(
    name: str, dtype_str: str, n_unique: int, n_rows: int, numeric_stats: Dict[str, Any]
) -> ColumnRole:
    is_numeric = any(t in dtype_str for t in ("Int", "Float", "UInt"))
    is_datetime = any(t in dtype_str for t in ("Date", "Datetime", "Duration"))
    # Normalise column name so _word_ boundaries work with \b patterns
    norm = name.lower().replace("_", " ").replace("-", " ")

    # TIME: datetime dtypes OR time-like name
    if is_datetime or _TIME_RE.search(norm):
        return ColumnRole.TIME

    # IDENTITY: ID-named column with high cardinality
    if _ID_RE.search(norm):
        if not is_numeric or (n_unique / max(n_rows, 1)) > 0.5:
            return ColumnRole.IDENTITY

    # Non-numeric
    if not is_numeric:
        if n_unique / max(n_rows, 1) > 0.5:
            return ColumnRole.IDENTITY
        return ColumnRole.DIMENSION

    # Numeric → further classify
    is_b01 = numeric_stats.get("is_bounded_01", False)
    col_min = numeric_stats.get("col_min", 0)
    col_max = numeric_stats.get("col_max", 0)

    # RATE: bounded 0–1, or percentage-like name
    if is_b01 or _RATE_RE.search(norm):
        if col_max <= 100 and col_min >= 0 and _RATE_RE.search(norm):
            return ColumnRole.RATE
        if is_b01:
            return ColumnRole.RATE

    # COUNT: integer-valued count-like column
    if _COUNT_RE.search(norm) and numeric_stats.get("is_integer_valued", False):
        return ColumnRole.COUNT

    # Low cardinality numeric → treat as ordinal dimension
    if n_rows >= 50 and n_unique <= 10 and (n_unique / n_rows) < 0.05:
        return ColumnRole.DIMENSION

    return ColumnRole.MEASURE


def _get_business_category(name: str) -> Tuple[str, str]:
    """Returns (category, polarity)."""
    searchable = name.lower().replace("_", " ").replace("-", " ")
    for cat, pattern, polarity in _CATEGORY_PATTERNS:
        if re.search(pattern, searchable, re.I):
            return cat, polarity
    return "unknown", "higher_is_better"


def _select_aggregation(role: ColumnRole, name: str, skewness: float, cv: float) -> str:
    if role == ColumnRole.RATE:
        return "median" if abs(skewness) > 1.5 else "mean"
    if role == ColumnRole.COUNT:
        return "sum"
    # MEASURE
    total_patterns = re.compile(
        r"\b(revenue|sales|cost|expense|amount|value|profit|income|gmv|total)\b", re.I
    )
    if total_patterns.search(name):
        return "sum"
    price_patterns = re.compile(r"\b(price|aov|arpu|arpc|ltv|cac|average|avg|salary|wage)\b", re.I)
    if price_patterns.search(name):
        return "median" if abs(skewness) > 1.5 else "mean"
    return "sum" if cv > 0.8 else "mean"


def _profile_column(df: pl.DataFrame, col_name: str) -> Optional[ColumnProfile]:
    try:
        col = df[col_name]
        dtype_str = str(col.dtype)
        n_rows = len(df)
        n_nulls = col.null_count()
        n_unique = col.n_unique()

        is_numeric = col.dtype in _NUMERIC_DTYPES
        numeric_stats = _profile_numeric(col) if is_numeric else {}
        role = _classify_role(col_name, dtype_str, n_unique, n_rows, numeric_stats)

        skewness = numeric_stats.get("skewness", 0.0) or 0.0
        cv = numeric_stats.get("cv", 0.0) or 0.0
        aggregation = (
            _select_aggregation(role, col_name, skewness, cv) if is_numeric else "count_unique"
        )

        category, polarity = _get_business_category(col_name)

        return ColumnProfile(
            name=col_name,
            role=role,
            n_rows=n_rows,
            n_nulls=n_nulls,
            n_unique=n_unique,
            aggregation=aggregation,
            polarity=polarity,
            business_category=category,
            **numeric_stats,
        )
    except Exception as e:
        logger.debug(f"[KPI] Column profiling failed for '{col_name}': {e}")
        return None


# ── KPI Candidate Selection ───────────────────────────────────────────────────


def _passes_gate(profile: ColumnProfile, selected_categories: Dict[str, int]) -> Tuple[bool, str]:
    """Three-gate KPI selection."""
    # Gate 1: Must be a meaningful numeric role
    if profile.role not in (ColumnRole.MEASURE, ColumnRole.RATE, ColumnRole.COUNT):
        return False, f"role={profile.role.value}"

    # Gate 2: Not too many nulls
    if profile.null_pct > 40:
        return False, f"nulls={profile.null_pct:.0f}%"

    # Gate 3: Value must be non-trivial
    val = profile.primary_value
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return False, "NaN/Inf value"
    if abs(val) < 1e-9 and profile.aggregation == "sum":
        return False, "zero sum"

    # Gate 4: Business category
    if profile.business_category == "unknown":
        polarity = "higher_is_better"
        category = "neutral"
    else:
        polarity = profile.polarity
        category = profile.business_category

    # Gate 5: Non-redundancy
    category_counts = selected_categories
    max_allowed = {"revenue": 2, "cost": 2, "users": 1, "churn_risk": 1}
    max_per = max_allowed.get(category, 1)
    count = category_counts.get(category, 0)
    if count >= max_per:
        return False, f"redundant with {category}"
    category_counts[category] = count + 1

    return True, category


def _select_hero(candidates: List[ColumnProfile]) -> Optional[ColumnProfile]:
    """Hero = the single number a CEO asks for first.

    Priority order:
      1. Revenue column (sum is meaningful)
      2. COUNT columns (entity counts are universally meaningful)
      3. RATE/percentage columns (scores, rates are universally meaningful)
      4. MEASURE columns with MEAN aggregation (per-unit averages beat raw sums)
      5. MEASURE columns with SUM aggregation (fallback)
      6. First remaining candidate
    """
    # 1. Revenue always wins
    for c in candidates:
        if c.business_category == "revenue":
            return c
    # 2. Count metrics (users, orders, customers) — universally meaningful
    for c in candidates:
        if c.role == ColumnRole.COUNT:
            return c
    # 3. Rate/percentage metrics — universally meaningful
    for c in candidates:
        if c.role == ColumnRole.RATE:
            return c
    # 4. Prefer MEAN over SUM for non-revenue measure columns
    #    (summing per-customer income is meaningless; the average is insightful)
    means = [c for c in candidates
             if c.role == ColumnRole.MEASURE
             and c.aggregation in ("mean", "median")
             and c.col_mean is not None]
    if means:
        return max(means, key=lambda c: abs(c.col_mean or 0))
    # 5. Fallback to SUM
    sums = [c for c in candidates if c.role == ColumnRole.MEASURE and c.col_sum]
    if sums:
        return max(sums, key=lambda c: abs(c.col_sum or 0))
    return candidates[0] if candidates else None


def _select_candidates(profiles: List[ColumnProfile], max_kpis: int) -> List[ColumnProfile]:
    """Apply the gate, pick hero + 1-3 primaries."""
    selected_categories: Dict[str, int] = {}
    passed: List[ColumnProfile] = []

    def sort_key(p: ColumnProfile) -> Tuple[int, float]:
        priority = {
            "revenue": 0, "volume": 1, "users": 2, "price": 3,
            "rate_metric": 4, "performance": 5, "cost": 6,
            "churn_risk": 7, "duration": 8, "quantity": 9, "neutral": 11,
        }
        prio = priority.get(p.business_category, 10)
        val = abs(p.primary_value or 0)
        return (prio, -val)

    sorted_profiles = sorted(profiles, key=sort_key)

    for profile in sorted_profiles:
        if len(passed) >= max_kpis:
            break
        ok, reason = _passes_gate(profile, selected_categories)
        if ok:
            passed.append(profile)
        else:
            logger.debug(f"[KPI] Gate rejected '{profile.name}': {reason}")

    hero = _select_hero(passed)
    for i, p in enumerate(passed):
        p.importance = "hero" if p is hero else ("high" if i <= 2 else "medium")

    if hero and passed[0] is not hero:
        passed.remove(hero)
        passed.insert(0, hero)

    return passed


# ── Value & Comparison ────────────────────────────────────────────────────────


def _compute_kpi_value(df: pl.DataFrame, profile: ColumnProfile) -> Any:
    try:
        col = df[profile.name].drop_nulls()
        if len(col) == 0:
            return 0
        agg = profile.aggregation
        if agg == "sum":
            return round(float(col.sum()), 2)
        if agg == "mean":
            return round(float(col.mean()), 2)
        if agg == "median":
            return round(float(col.median()), 2)
        if agg == "max":
            return round(float(col.max()), 2)
        if agg == "min":
            return round(float(col.min()), 2)
        return round(float(col.sum()), 2)
    except Exception:
        return profile.primary_value or 0


def _find_time_column(df: pl.DataFrame) -> Optional[str]:
    for col in df.columns:
        if df[col].dtype in (pl.Date, pl.Datetime):
            return col
    for col in df.columns:
        if _TIME_RE.search(col) and df[col].dtype in _NUMERIC_DTYPES:
            return col
    return None


def _compute_comparison(
    df: pl.DataFrame, profile: ColumnProfile, time_col: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Time-sorted first-half vs second-half comparison."""
    try:
        col = profile.name
        if col not in df.columns:
            return None
        clean = df.drop_nulls(subset=[col])
        if len(clean) < 10:
            return None

        if time_col and time_col in df.columns:
            try:
                sorted_df = clean.sort(time_col)
                label = "vs first half (time-sorted)"
                is_temporal = True
            except Exception:
                return None
        else:
            return None

        mid = len(sorted_df) // 2
        first_half = sorted_df[:mid]
        second_half = sorted_df[mid:]

        def agg_half(half: pl.DataFrame) -> Optional[float]:
            c = half[col].drop_nulls()
            if len(c) == 0:
                return None
            agg = profile.aggregation
            if agg == "sum":
                return float(c.sum())
            if agg == "mean":
                return float(c.mean())
            if agg == "median":
                return float(c.median())
            return float(c.sum())

        v1 = agg_half(first_half)
        v2 = agg_half(second_half)

        if v1 is None or v2 is None or abs(v1) < 1e-9:
            return None

        delta_pct = round(((v2 - v1) / abs(v1)) * 100, 1)
        direction = "up" if delta_pct > 0 else ("down" if delta_pct < 0 else "neutral")
        is_positive = profile.polarity == "higher_is_better"
        is_good = (direction == "up" and is_positive) or (direction == "down" and not is_positive)

        return {
            "comparison_value": round(v1, 2),
            "comparison_label": label,
            "delta_percent": delta_pct,
            "delta_direction": direction,
            "is_delta_positive": is_positive,
            "is_good": is_good,
            "is_temporal": is_temporal,
        }
    except Exception as e:
        logger.debug(f"[KPI] Comparison failed for '{profile.name}': {e}")
        return None


def _compute_sparkline(
    df: pl.DataFrame,
    profile: ColumnProfile,
    time_col: Optional[str],
    max_points: int = 12,
) -> Dict[str, Any]:
    """Time-binned sparkline (preferred) or row-sampled fallback."""
    col = profile.name
    try:
        if time_col and time_col in df.columns and df[time_col].dtype in (pl.Date, pl.Datetime):
            try:
                binned = (
                    df.sort(time_col)
                    .with_columns(pl.col(time_col).cast(pl.Date).alias("_d"))
                    .group_by_dynamic("_d", every="1mo")
                    .agg(pl.col(col).mean().alias("_v"))
                    .sort("_d")
                    .tail(max_points)
                )
                vals = binned["_v"].drop_nulls().to_list()
                if len(vals) >= 3:
                    return {"data": [round(v, 2) for v in vals], "type": "time_series"}
            except Exception:
                pass

            # No time column — return empty sparkline instead of row-sampled fallback
        return {"data": [], "type": "distribution"}
    except Exception:
        return {"data": [], "type": "distribution"}


def _compute_accent_color(importance: str, delta_direction: Optional[str], polarity: str) -> str:
    if importance == "hero":
        return "teal"
    if not delta_direction or delta_direction == "neutral":
        return "neutral"
    is_positive = polarity == "higher_is_better"
    if is_positive:
        return "green" if delta_direction == "up" else "red"
    else:
        return "green" if delta_direction == "down" else "red"


# ── Time Period Detection ─────────────────────────────────────────────────────


def _detect_time_period(
    df: pl.DataFrame, profile: ColumnProfile, time_col: Optional[str]
) -> Dict[str, Any]:
    """Detect current and previous time periods from data."""
    try:
        col = profile.name
        if col not in df.columns:
            return {}

        clean = df.drop_nulls(subset=[col])
        if len(clean) < 10:
            return {}

        if time_col and time_col in df.columns and df[time_col].dtype in (pl.Date, pl.Datetime):
            try:
                sorted_df = clean.sort(time_col)
                binned = (
                    sorted_df.with_columns(pl.col(time_col).cast(pl.Date).alias("_d"))
                    .group_by_dynamic("_d", every="1mo")
                    .agg(pl.col(col).mean().alias("_v"))
                    .sort("_d")
                )
                periods = binned.filter(pl.col("_v").is_not_null())
                if len(periods) < 2:
                    return {}

                last_periods = periods.tail(4)
                current = last_periods[-1]
                previous = last_periods[-2] if len(last_periods) >= 2 else None
                current_date = current["_d"].to_list()[0]
                period_label = _format_period_label(current_date, "month")
                prev_date = previous["_d"].to_list()[0] if previous else None
                prev_period_label = _format_period_label(prev_date, "month") if prev_date else "previous period"
                period_values = last_periods["_v"].drop_nulls().to_list()

                return {
                    "period_label": period_label,
                    "previous_period_label": prev_period_label,
                    "period_type": "month",
                    "current_period_value": float(current["_v"].to_list()[0]),
                    "previous_period_value": float(previous["_v"].to_list()[0]) if previous else None,
                    "period_values": [round(v, 2) for v in period_values],
                }
            except Exception:
                return {}

        # No time column available — return empty instead of row-split fallback
        return {}
    except Exception as e:
        logger.debug(f"[KPI] Time period detection failed for '{profile.name}': {e}")
        return {}





def _format_period_label(date_val, period_type: str) -> str:
    try:
        if hasattr(date_val, "strftime"):
            if period_type == "month":
                return date_val.strftime("%B %Y")
            if period_type == "quarter":
                quarter = (date_val.month - 1) // 3 + 1
                return f"Q{quarter} {date_val.year}"
            if period_type == "year":
                return str(date_val.year)
            if period_type == "week":
                return date_val.strftime("Week %W, %Y")
        return str(date_val)
    except Exception:
        return str(date_val)


# ── Rolling Baseline Computation ──────────────────────────────────────────────


def _compute_rolling_baseline(period_values: List[float], window: int = 3) -> Dict[str, Any]:
    try:
        if not period_values or len(period_values) < 2:
            return {}
        baseline_periods = period_values[-min(window, len(period_values)):]
        if len(baseline_periods) < 2:
            return {}

        mean_val = sum(baseline_periods) / len(baseline_periods)
        variance = sum((x - mean_val) ** 2 for x in baseline_periods) / len(baseline_periods)
        std_val = math.sqrt(variance)

        if std_val < 1e-9:
            std_val = abs(mean_val) * 0.01 if mean_val != 0 else 1.0

        return {
            "baseline_value": round(mean_val, 2),
            "baseline_std": round(std_val, 2),
            "normal_range_low": round(mean_val - std_val, 2),
            "normal_range_high": round(mean_val + std_val, 2),
            "period_count": len(baseline_periods),
        }
    except Exception as e:
        logger.debug(f"[KPI] Baseline computation failed: {e}")
        return {}


# ── Anomaly Detection ─────────────────────────────────────────────────────────


def _detect_anomaly(current_value: float, baseline_mean: float, baseline_std: float) -> Dict[str, Any]:
    """Z-score based anomaly detection."""
    try:
        if baseline_std < 1e-9:
            return {"is_anomaly": False, "anomaly_direction": "normal", "z_score": 0.0, "anomaly_severity": "normal"}

        z_score = (current_value - baseline_mean) / baseline_std

        if abs(z_score) > 3:
            direction = "above_normal" if z_score > 0 else "below_normal"
            return {"is_anomaly": True, "anomaly_direction": direction, "z_score": round(z_score, 2), "anomaly_severity": "critical"}
        elif abs(z_score) > 2:
            direction = "above_normal" if z_score > 0 else "below_normal"
            return {"is_anomaly": True, "anomaly_direction": direction, "z_score": round(z_score, 2), "anomaly_severity": "warning"}
        else:
            return {"is_anomaly": False, "anomaly_direction": "normal", "z_score": round(z_score, 2), "anomaly_severity": "normal"}
    except Exception:
        return {"is_anomaly": False, "anomaly_direction": "normal", "z_score": 0.0, "anomaly_severity": "normal"}


# ── Top Driver Detection ──────────────────────────────────────────────────────


def _compute_top_driver(df: pl.DataFrame, metric_col: str, max_dimensions: int = 3) -> Optional[Dict[str, Any]]:
    """Find which dimension segment contributes most to the metric.

    Finds dimension columns (string, categorical, low-cardinality numeric, boolean)
    then groups the metric column by each dimension and computes the aggregation
    matching the profile's natural aggregation (sum for summable, mean otherwise).

    Returns the dimension+segment pair that contributes the highest percentage.
    """
    try:
        if metric_col not in df.columns:
            return None

        # ── Find dimension columns (broad detection) ──
        dimension_cols = []
        _ALL_DTYPES = _NUMERIC_DTYPES + (pl.Boolean,)
        for col in df.columns:
            if col == metric_col or col.startswith("_"):
                continue
            dtype = df[col].dtype
            unique_count = df[col].n_unique()

            # Utf8 / Categorical: 2-50 unique values (was 2-15, broadened)
            if dtype in (pl.Utf8, pl.Categorical):
                if 2 <= unique_count <= 50:
                    dimension_cols.append(col)
            # Integer: 2-30 unique values (was 2-10, broadened)
            elif dtype in _INTEGER_DTYPES:
                if 2 <= unique_count <= 30:
                    dimension_cols.append(col)
            # Float: low-cardinality numeric (2-20 unique)
            elif dtype in (pl.Float32, pl.Float64):
                if 2 <= unique_count <= 20 and unique_count <= len(df) * 0.05:
                    dimension_cols.append(col)
            # Boolean: always a dimension (2 unique)
            elif dtype == pl.Boolean:
                if unique_count == 2:
                    dimension_cols.append(col)

        if not dimension_cols:
            logger.debug(f"[KPI] No dimension columns found for '{metric_col}' — all columns have >50 unique values or are numeric with >20 unique")
            return None

        # Prefer lower-cardinality dimensions (more meaningful drivers)
        dimension_cols.sort(key=lambda c: df[c].n_unique())
        dimension_cols = dimension_cols[:max_dimensions]

        best_driver = None
        best_pct = 0.0

        for dim_col in dimension_cols:
            try:
                # Use MEAN aggregation for top-driver computation (more robust than SUM
                # for rate/score/count columns, and still meaningful for summable columns)
                grouped = (
                    df.drop_nulls(subset=[metric_col, dim_col])
                    .group_by(dim_col)
                    .agg(pl.col(metric_col).mean().alias("_agg"))
                    .sort("_agg", descending=True)
                )
                if len(grouped) < 2:
                    continue
                total = grouped["_agg"].sum()
                if total == 0:
                    continue
                top_row = grouped.head(1)
                segment_val = float(top_row["_agg"].to_list()[0])
                segment_name = str(top_row[dim_col].to_list()[0])
                pct_of_total = (segment_val / abs(total)) * 100

                if pct_of_total > best_pct:
                    best_pct = pct_of_total
                    best_driver = {
                        "dimension": dim_col,
                        "segment": segment_name,
                        "segment_value": round(segment_val, 2),
                        "pctOfTotal": round(pct_of_total, 1),
                        "pct_of_total": round(pct_of_total, 1),
                    }
            except Exception:
                continue

        if best_driver:
            logger.info(f"[KPI] Top driver for '{metric_col}': {best_driver['segment']} ({best_driver['dimension']}) = {best_driver['pctOfTotal']:.0f}%")

        return best_driver
    except Exception as e:
        logger.debug(f"[KPI] Top driver detection failed for '{metric_col}': {e}")
        return None


# ── Trend Forecast ────────────────────────────────────────────────────────────


def _compute_trend_forecast(period_values: List[float]) -> Dict[str, Any]:
    """Simple linear regression to forecast expected value."""
    try:
        if not period_values or len(period_values) < 2:
            return {}

        n = len(period_values)
        x_mean = (n - 1) / 2.0
        y_mean = sum(period_values) / n

        numerator = sum((i - x_mean) * (period_values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator < 1e-9:
            return {"expected_value": round(y_mean, 2), "trend_direction": "flat", "trend_slope": 0.0}

        slope = numerator / denominator
        intercept = y_mean - slope * x_mean
        expected = intercept + slope * (n - 1)

        if abs(slope) < abs(y_mean) * 0.01:
            direction = "flat"
        elif slope > 0:
            direction = "up"
        else:
            direction = "down"

        return {"expected_value": round(expected, 2), "trend_direction": direction, "trend_slope": round(slope, 2)}
    except Exception as e:
        logger.debug(f"[KPI] Trend forecast failed: {e}")
        return {}


# ── Trust / Provenance Layer ───────────────────────────────────────────


@dataclass
class ProvenanceInfo:
    """Provenance and lineage information attached to every KPI card.

    Answers "Where did this number come from?" with:
    - Which source table / column
    - What formula was applied
    - How many records were used
    - How much data was missing
    - Whether the data was downsampled
    - Overall trust score
    """
    source_table: str = "upload"
    column: str = ""
    aggregation: str = "sum"
    formula_description: str = ""                 # "SUM(revenue) across 128K records"
    record_count: int = 0
    null_count: int = 0
    null_pct: float = 0.0
    total_rows: int = 0
    downsampled: bool = False
    downsample_ratio: Optional[float] = None
    confidence_score: float = 1.0                  # 0.0 - 1.0, based on data quality
    confidence_label: str = "High"                 # "High" | "Medium" | "Low"
    refreshed_at: str = ""                         # ISO timestamp if available

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_table": self.source_table,
            "column": self.column,
            "aggregation": self.aggregation,
            "formula_description": self.formula_description,
            "record_count": self.record_count,
            "null_count": self.null_count,
            "null_pct": round(self.null_pct, 1),
            "total_rows": self.total_rows,
            "downsampled": self.downsampled,
            "downsample_ratio": self.downsample_ratio,
            "confidence_score": round(self.confidence_score, 2),
            "confidence_label": self.confidence_label,
            "refreshed_at": self.refreshed_at,
        }


def build_provenance(
    profile: ColumnProfile,
    df: pl.DataFrame,
    column: str,
    aggregation: str = "sum",
    is_estimated: bool = False,
    estimate_ratio: Optional[float] = None,
    source_table: str = "upload",
    formula_override: Optional[str] = None,
) -> ProvenanceInfo:
    """Build provenance info for a KPI card.

    Computes:
    - Formula description: e.g. "SUM(revenue) across 128K records"
    - Null count and percentage
    - Confidence score based on data quality
    - Downsampling metadata

    Args:
        profile: ColumnProfile for the metric
        df: DataFrame
        column: Column name
        aggregation: Aggregation used
        is_estimated: Whether data was downsampled
        estimate_ratio: Ratio of rows retained
        source_table: Source table/dataset name
        formula_override: Optional custom formula string

    Returns:
        ProvenanceInfo dataclass
    """
    if formula_override:
        formula_desc = formula_override
    else:
        formula_desc = f"{aggregation.upper()}({column})"

    null_count = profile.n_nulls
    total_rows = len(df)
    rec_count = total_rows - null_count
    null_pct = (null_count / total_rows * 100) if total_rows > 0 else 0

    # Compute confidence score based on:
    # - Null percentage (penalty ≥30% nulls)
    # - Downsampling (penalty if <50% of rows retained)
    # - Total rows (penalty if <100 rows)
    confidence = 1.0
    if null_pct > 30:
        confidence -= min(0.3, null_pct / 100)
    if is_estimated and estimate_ratio and estimate_ratio < 0.5:
        confidence -= 0.15
    if total_rows < 100:
        confidence -= 0.2
    elif total_rows < 1000:
        confidence -= 0.05
    confidence = max(0.0, min(1.0, confidence))

    if confidence >= 0.8:
        label = "High"
    elif confidence >= 0.5:
        label = "Medium"
    else:
        label = "Low"

    formula_with_rows = f"{formula_desc} across {rec_count:,} records"

    return ProvenanceInfo(
        source_table=source_table,
        column=column,
        aggregation=aggregation,
        formula_description=formula_with_rows,
        record_count=rec_count,
        null_count=null_count,
        null_pct=null_pct,
        total_rows=total_rows,
        downsampled=is_estimated,
        downsample_ratio=estimate_ratio,
        confidence_score=confidence,
        confidence_label=label,
        refreshed_at="",  # Set externally if timestamp available
    )


# ── Display Helpers ───────────────────────────────────────────────────


def _infer_format(profile: ColumnProfile, value: Any) -> str:
    name = profile.name.lower()
    if any(t in name for t in ("revenue", "sales", "cost", "amount", "price", "value", "profit", "income", "expense", "budget", "salary", "fee", "gmv")):
        return "currency"
    if profile.role == ColumnRole.RATE or profile.is_bounded_01:
        return "percentage"
    if any(t in name for t in ("rate", "ratio", "percent", "pct", "margin")):
        return "percentage"
    if any(t in name for t in ("duration", "latency", "days", "hours", "ms", "seconds")):
        return "decimal"
    if profile.is_integer_valued or profile.role == ColumnRole.COUNT:
        return "integer"
    if isinstance(value, float) and 0 <= value <= 1:
        return "percentage"
    return "decimal"


def _infer_icon(profile: ColumnProfile) -> str:
    cat = profile.business_category
    icon_map = {
        "revenue": "DollarSign", "cost": "Activity", "volume": "ShoppingCart",
        "users": "Users", "rate_metric": "Percent", "churn_risk": "Activity",
        "price": "DollarSign", "performance": "Target", "duration": "Clock", "quantity": "Package",
    }
    return icon_map.get(cat, "BarChart3")


def _build_subtitle(profile: ColumnProfile, n_rows: int, time_col: Optional[str], domain: Optional[str]) -> str:
    agg_word = {"sum": "Total", "mean": "Average", "median": "Median", "max": "Peak", "min": "Floor"}.get(profile.aggregation, profile.aggregation.title())
    domain_part = f" · {domain.replace('_', ' ').title()}" if domain and domain != "general" else ""
    return f"{agg_word} across {n_rows:,} records{domain_part}"


# ── Domain Detection (from KPIService patterns) ────────────────────────────


def _compute_domain_scores(
    profiles: List[ColumnProfile],
) -> tuple[dict[str, float], Optional[str], float]:
    """
    Compute domain template scores from column patterns.

    Returns:
        (scores_dict, best_template_id, best_score)
    """
    from services.kpi.patterns import COLUMN_PATTERNS
    from services.kpi.templates import ALL_TEMPLATES

    column_names = [p.name for p in profiles]
    detected_types: set = set()

    for col_name in column_names:
        col_lower = col_name.lower().replace("_", " ").replace("-", " ")
        for col_type, patterns in COLUMN_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, col_lower, re.IGNORECASE):
                    detected_types.add(col_type)
                    break

    scores: dict[str, float] = {}
    for template_id, template in ALL_TEMPLATES.items():
        required_found = sum(1 for r in template.required_columns if r in detected_types)
        optional_found = sum(1 for o in template.optional_columns if o in detected_types)

        if required_found == len(template.required_columns):
            scores[template_id] = 50.0 + 10.0 * required_found + 5.0 * optional_found
        elif required_found > 0:
            scores[template_id] = 15.0 * required_found + 3.0 * optional_found

    if scores:
        best = max(scores, key=scores.get)
        return scores, best, scores[best]
    return {}, None, 0.0



def dtype_abbrev(dtype_str: str) -> str:
    """Shorten dtype string for prompt display."""
    if "Int" in dtype_str or "UInt" in dtype_str or "Float" in dtype_str:
        return "numeric"
    if "Date" in dtype_str or "Datetime" in dtype_str or "Duration" in dtype_str:
        return "datetime"
    if "Utf8" in dtype_str or "String" in dtype_str or "Categorical" in dtype_str:
        return "text"
    if "Bool" in dtype_str:
        return "boolean"
    return dtype_str[:12]


# ── LLM-First Domain Classification (with Data Stats) ────────────────────


async def _llm_classify_domain(
    profiles: List[ColumnProfile],
    df: pl.DataFrame,
) -> tuple[Optional[str], Optional[dict[str, str]]]:
    """
    Use an LLM to classify the dataset domain using column names, types,
    sample values, AND data statistics (value ranges, cardinality,
    distributions, typical values).

    Returns:
        (domain_template_id, column_mapping) where column_mapping maps
        template column types (e.g. "revenue", "date") to actual column names.
        Returns (None, None) if classification fails.
    """
    from services.kpi.templates import ALL_TEMPLATES

    # ── Build rich column info with data stats ──
    col_lines = []
    for p in profiles:
        # Skip synthetic profiles (prefixed with _) — they don't exist as real DataFrame columns
        if p.name.startswith("_"):
            continue
        role = p.role.value
        null_pct = p.null_pct

        # Sample values + categorical distribution
        samples = []
        dist_str = ""
        if p.name in df.columns:
            raw = df[p.name].drop_nulls().head(3).to_list()
            samples = [str(v)[:60] for v in raw if v is not None]

            # For low-cardinality text columns: compute value distribution percentages
            if role == "dimension" and p.n_unique <= 15 and p.n_unique > 0 and df[p.name].dtype in (pl.Utf8, pl.Categorical):
                try:
                    vc = df[p.name].drop_nulls().value_counts(name="_count", normalize=False)
                    if "_count" in vc.columns and len(vc) > 0:
                        total = vc["_count"].sum()
                        pairs = []
                        for row in vc.sort("_count", descending=True).head(8).iter_rows():
                            val, cnt = row
                            pct = int(round(cnt / total * 100)) if total > 0 else 0
                            pairs.append(f"{val}({pct}%)")
                        if pairs:
                            dist_str = f"  distribution: {', '.join(pairs)}"
                except Exception:
                    pass

        sample_str = f"  samples: {', '.join(samples)}" if samples else "  (all null)"

        # Stats line differs by role
        if role in ("measure", "rate", "count") and p.col_min is not None:
            stats_line = (
                f"  range: [{p.col_min:.2f}, {p.col_max:.2f}]  "
                f"mean: {p.col_mean:.2f}  med: {p.col_median:.2f}  "
                f"cardinality: {p.n_unique}/{p.n_rows}  nulls: {null_pct:.0f}%"
            )
        else:
            # Categorical / ID / Time
            stats_line = (
                f"  cardinality: {p.n_unique}/{p.n_rows}  nulls: {null_pct:.0f}%"
            )

        col_lines.append(f"- {p.name} [{dtype_abbrev(str(df[p.name].dtype))}]")
        col_lines.append(f"  role: {role}")
        col_lines.append(stats_line)
        col_lines.append(sample_str)
        if dist_str:
            col_lines.append(dist_str)

    columns_str = "\n".join(col_lines)

    prompt = f"""You are a data domain classifier. Your job is to analyze a dataset's columns and describe what domain it belongs to.

HOW TO REASON:
1. Sample values and VALUE RANGES are your strongest signal — trust them over column names.
   - A "value" column with samples [32000, 28500, 48000] and range [5000, 180000] is NOT the same as "value" with samples [0.023, -0.015, 0.009]
   - A "score" column that ranges [0, 100] with samples [85, 72, 91] is an exam/test score, not a medical score
2. For categorical columns, the VALUE DISTRIBUTION tells you more than the category names.
   - fuelType: Petrol(65%), Diesel(25%) is clearly different from fuelType: E10(40%), E85(30%), Diesel(30%)
3. Column NAMES are your weakest signal — disambiguate using the actual data values.
4. Describe what the data IS — what business process it captures, what entities it records.
5. If you cannot determine the domain with high confidence, set domain_id to "unknown" and explain what single piece of information would resolve the ambiguity.
6. If the data matches a well-known pattern, include a domain_id (e.g. "automotive-metrics", "ecommerce-metrics", "healthcare-metrics"). Otherwise set domain_id to "unknown".

Output a JSON object with these fields:
- domain: a SHORT description of what this data is (3-8 words, never a full sentence). This is the primary output.
- domain_id: optional standard identifier if one clearly matches (use "unknown" if none fits)
- confidence: 0.0-1.0 score
- reasoning: 1-2 sentences explaining the key signals that determined the classification
- column_mapping: dictionary mapping template column types to actual column names (empty object if uncertain)

DATASET COLUMNS:
{columns_str}

OUTPUT (valid JSON only):
{{
  "domain": "vehicle listings with pricing and specs",
  "domain_id": "automotive-metrics",
  "confidence": 0.92,
  "reasoning": "Price range $5K-$185K with mileage, engine_size, transmission, and fuel type distribution (Petrol 65%, Diesel 25%) — standard vehicle listing columns.",
  "column_mapping": {{
    "mileage": "mileage",
    "price": "price"
  }}
}}

Return ONLY valid JSON. No markdown fences. No text before or after."""

    try:
        from services.llm_router import llm_router

        response = await llm_router.call(
            prompt=prompt,
            model_role="intent_engine",
            expect_json=True,
            temperature=0.1,
            is_conversational=False,
            max_tokens=800,
        )

        if isinstance(response, dict) and "domain_id" in response:
            domain_id = response.get("domain_id", "")
            confidence = response.get("confidence", 0.0)
            column_mapping = response.get("column_mapping", {}) or {}
            domain_desc = response.get("domain", "")

            # Validate it's a known template
            if domain_id in ALL_TEMPLATES and confidence >= 0.5:
                col_names_lower = {c.lower(): c for c in df.columns}
                valid_mapping = {}
                for k, v in column_mapping.items():
                    if v in df.columns:
                        valid_mapping[k] = v
                    elif v.lower() in col_names_lower:
                        valid_mapping[k] = col_names_lower[v.lower()]
                logger.info(
                    f"[KPI] LLM classified domain: {domain_id} "
                    f"(desc='{domain_desc}', confidence={confidence}, "
                    f"reasoning={response.get('reasoning', 'N/A')[:80]}, "
                    f"mapped={len(valid_mapping)} columns)"
                )
                return domain_id, valid_mapping

            # No template match — log the free-form description for visibility
            logger.info(
                f"[KPI] LLM returned: desc='{domain_desc}' (domain_id='{domain_id}', "
                f"confidence={confidence}) — no template match, using fallback"
            )
            return None, None

        logger.warning(f"[KPI] LLM domain classification returned invalid or unparseable response")
        return None, None

    except Exception as e:
        logger.warning(f"[KPI] LLM domain classification failed: {e}")
        return None, None



async def _detect_domain_hybrid(
    profiles: List[ColumnProfile],
    df: pl.DataFrame,
) -> tuple[Optional[str], Optional[dict[str, str]]]:
    """
    LLM-first hybrid domain detection with data stats.

    1. Call LLM with rich data statistics (value ranges, cardinality, samples)
    2. If LLM returns a valid domain with confidence >= 0.6 → use it
    3. If LLM fails or low confidence → fall back to pattern matching
    4. Returns (domain_id, column_mapping)
    """
    # ── Step 1: LLM first ──
    llm_domain, llm_mapping = await _llm_classify_domain(profiles, df)

    if llm_domain:
        logger.info(f"[KPI] LLM selected domain: {llm_domain}")
        return llm_domain, llm_mapping

    # ── Step 2: Pattern matching fallback ──
    _, best_template, best_score = _compute_domain_scores(profiles)
    if best_template and best_score >= 30:
        logger.info(
            f"[KPI] LLM failed, pattern fallback: {best_template} "
            f"(score={best_score})"
        )
        return best_template, None

    logger.warning("[KPI] Domain detection failed completely \u2014 no template matched")
    return None, None



# ── Deterministic KPI Insights (replaces LLM enrichment) ─────────────────


def _rotate_phrasing(seed: str, variants: List[str]) -> str:
    """Pick a phrasing variant deterministically based on a seed string."""
    idx = abs(hash(seed)) % len(variants)
    return variants[idx]


def _direction_word(is_up: bool) -> str:
    return "increase" if is_up else "decrease"


_DELTA_VARIANTS = [
    "{icon} {abs_delta:.1f}% {direction}",
    "{direction_word} by {abs_delta:.1f}% {icon}",
    "showing {direction_word} of {abs_delta:.1f}%",
    "{abs_delta:.1f}% {direction} from prior period",
]

_ANOMALY_VARIANTS = [
    "{severity}: {abs_z:.1f}\u03c3 deviation from baseline",
    "\u26a0 {severity} \u2014 {abs_z:.1f} standard deviations from norm",
    "{abs_z:.1f}\u03c3 outlier \u2014 {severity} alert",
]

_TREND_VARIANTS = [
    "{arrow} projected {expected_fmt}",
    "trending toward {expected_fmt}",
    "on track for {expected_fmt}",
    "forecast: {expected_fmt}",
]

_DRIVER_VARIANTS = [
    "top segment: {driver_name} ({driver_pct:.0f}%)",
    "{driver_name} leads ({driver_pct:.0f}% of total)",
    "{driver_pct:.0f}% driven by {driver_name}",
    "{driver_name} accounts for {driver_pct:.0f}%",
]

_ENTITY_CONCENTRATION_VARIANTS = [
    "top {entity_type} '{entity_value}' accounts for {pct:.0f}%",
    "concentrated: {entity_value} is {pct:.0f}% of total ({entity_type})",
    "{pct:.0f}% comes from the top {entity_type}: {entity_value}",
    "{entity_value} ({entity_type}) drives {pct:.0f}% of overall",
]

_ACTION_VARIANTS = [
    "What caused the {severity} change in {title}?",
    "Drill into what drove the {severity} {title} shift.",
    "Investigate the {severity} {title} movement.",
    "Analyze {title} fluctuation drivers.",
]

_ACTION_VARIANTS_DRIVER = [
    "How does {title} break down across {dim}?",
    "Break {title} down by {dim}.",
    "Show {title} split by {dim}.",
    "Analyze {title} across {dim} segments.",
]

_ACTION_VARIANTS_DELTA = [
    "Which segments drove the {delta:+.0f}% change in {title}?",
    "Dig into what caused the {delta:+.0f}% {title} shift.",
    "Which {title} segments changed the most?",
]

_ACTION_VARIANTS_DEFAULT = [
    "Show me {title} breakdown by month.",
    "Break down {title} over time.",
    "Trend {title} monthly.",
]



def _compute_segment_comparison(
    df: pl.DataFrame,
    metric_col: str,
    polarity: str = "higher_is_better",
) -> Optional[Dict[str, Any]]:
    """Compute cross-segment comparison when no time column exists.
    
    Looks for low-cardinality dimension columns (like Gender, Region, Plan)
    and compares mean metric values across segments.
    
    Returns a comparison dict similar to _compute_comparison output:
      {comparison_value, delta_percent, delta_direction, label}
    """
    try:
        if metric_col not in df.columns:
            return None
        clean = df.drop_nulls(subset=[metric_col])
        if len(clean) < 20:
            return None
        # Find low-cardinality dimensions (2-10 unique values)
        dims = []
        for col in df.columns:
            if col == metric_col:
                continue
            dtype = df[col].dtype
            if dtype in (pl.Utf8, pl.Categorical):
                n = df[col].n_unique()
                if 2 <= n <= 10:
                    dims.append(col)
            elif dtype in _INTEGER_DTYPES:
                n = df[col].n_unique()
                if 2 <= n <= 10:
                    dims.append(col)
        if not dims:
            return None
        dim = dims[0]
        # Compare mean of each segment, pick the two extremes
        segments = (
            clean.group_by(dim)
            .agg(pl.col(metric_col).mean().alias("_avg"))
            .sort("_avg", descending=True)
        )
        if len(segments) < 2:
            return None
        top = segments.row(0)
        bottom = segments.row(-1)
        top_seg, top_val = str(top[0]), float(top[1])
        bottom_seg, bottom_val = str(bottom[0]), float(bottom[1])
        if abs(top_val) < 1e-9 or abs(bottom_val) < 1e-9:
            return None
        delta_pct = round(((top_val - bottom_val) / abs(bottom_val)) * 100, 1)
        if abs(delta_pct) < 5:
            return None  # Skip trivial differences
        return {
            "comparison_value": round(bottom_val, 2),
            "comparison_label": f"{top_seg} vs {bottom_seg} ({dim})",
            "delta_percent": delta_pct,
            "delta_direction": "up" if delta_pct > 0 else "down",
            "is_delta_positive": delta_pct > 0,
            "is_good": delta_pct > 0 if polarity == "higher_is_better" else delta_pct < 0,
            "is_temporal": False,
            "segment_dimension": dim,
            "top_segment": top_seg,
            "bottom_segment": bottom_seg,
        }
    except Exception as e:
        logger.debug(f"[KPI] Segment comparison failed for '{metric_col}': {e}")
        return None


def _generate_deterministic_insight(
    profile: ColumnProfile,
    value: float,
    comparison: Optional[Dict[str, Any]],
    anomaly: Dict[str, Any],
    trend: Dict[str, Any],
    top_driver: Optional[Dict[str, Any]],
    fmt: str,
    entity_info: Optional[Dict[str, Any]] = None,
    segment_compare: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """
    Generate an insight sentence + action prompt from computed data alone.
    Phrasing varies per column name hash to avoid sounding formulaic.

    Args:
        entity_info: Optional dict with entity_type, entity_concentration_pct,
                     top_entity_value, entity_cardinality from entity-aware profiling.
    """
    title = _humanize_title(profile)
    seed = profile.name or title
    fmt_value = _fmt_val(value, fmt)

    signals: list[str] = []

    if comparison:
        delta = comparison.get("delta_percent")
        direction = comparison.get("delta_direction")
        if direction and direction != "neutral" and delta is not None:
            is_good = comparison.get("is_good", True)
            icon = "\U0001f4c8" if is_good else "\U0001f4c9"
            is_up = direction == "up"
            template = _rotate_phrasing(f"delta:{seed}", _DELTA_VARIANTS)
            signals.append(
                template.format(
                    icon=icon, abs_delta=abs(delta), direction=direction,
                    direction_word=_direction_word(is_up),
                )
            )

    if anomaly.get("is_anomaly"):
        severity = anomaly.get("anomaly_severity", "noticeable")
        z = anomaly.get("z_score", 0)
        template = _rotate_phrasing(f"anomaly:{seed}", _ANOMALY_VARIANTS)
        signals.append(
            template.format(severity=severity.upper(), abs_z=abs(z))
        )

    trend_dir = trend.get("trend_direction", "flat")
    expected = trend.get("expected_value")
    if trend_dir != "flat" and expected is not None:
        expected_fmt = _fmt_val(expected, fmt)
        arrow = "\u2197" if trend_dir == "up" else "\u2198"
        template = _rotate_phrasing(f"trend:{seed}", _TREND_VARIANTS)
        signals.append(
            template.format(arrow=arrow, expected_fmt=expected_fmt)
        )

    if top_driver:
        driver_name = top_driver.get("segment", "")
        driver_pct = top_driver.get("pct_of_total", 0)
        if driver_name and driver_pct:
            template = _rotate_phrasing(f"driver:{seed}", _DRIVER_VARIANTS)
            signals.append(
                template.format(driver_name=driver_name, driver_pct=driver_pct)
            )

    # ── Entity-concentration signal (NEW) ──
    if entity_info:
        conc_pct = entity_info.get("entity_concentration_pct")
        top_val = entity_info.get("top_entity_value")
        ent_type = entity_info.get("entity_type", "entity")
        if conc_pct is not None and top_val and conc_pct >= 20:
            # Only include if concentration is meaningful (>=20%)
            template = _rotate_phrasing(f"entity_conc:{seed}", _ENTITY_CONCENTRATION_VARIANTS)
            signals.append(
                template.format(
                    entity_type=ent_type,
                    entity_value=top_val,
                    pct=conc_pct,
                )
            )
    
    # ── Cross-segment comparison signal ──
    if segment_compare and not comparison:
        seg_val = segment_compare.get("delta_percent")
        seg_dir = segment_compare.get("delta_direction")
        top_seg = segment_compare.get("top_segment", "")
        bottom_seg = segment_compare.get("bottom_segment", "")
        dim = segment_compare.get("segment_dimension", "segment")
        if seg_val is not None and seg_dir and seg_val != 0:
            icon = "📈" if seg_val > 0 else "📉"
            seg_signal = f"{icon} {top_seg}s average {abs(seg_val):.0f}% {'higher' if seg_val > 0 else 'lower'} than {bottom_seg}s ({dim})"
            signals.append(seg_signal)

    if signals:
        insight = f"{title}: {fmt_value} \u2014 {'; '.join(signals)}."
    else:
        insight = f"{title} is {fmt_value}."

    action = _generate_action_prompt(title, profile, top_driver, comparison, anomaly, seed)

    return insight, action


def _generate_action_prompt(
    title: str,
    profile: ColumnProfile,
    top_driver: Optional[Dict[str, Any]],
    comparison: Optional[Dict[str, Any]],
    anomaly: Dict[str, Any],
    seed: str = "",
) -> str:
    """Generate a specific drill-down follow-up question with rotated phrasing."""
    if anomaly.get("is_anomaly"):
        severity = anomaly.get("anomaly_severity", "recent")
        template = _rotate_phrasing(f"action_anomaly:{seed}", _ACTION_VARIANTS)
        return template.format(severity=severity, title=title)
    if top_driver:
        dim = top_driver.get("dimension", "")
        if dim:
            template = _rotate_phrasing(f"action_driver:{seed}", _ACTION_VARIANTS_DRIVER)
            return template.format(title=title, dim=dim)
    if comparison and comparison.get("delta_percent"):
        delta = comparison["delta_percent"]
        if abs(delta) > 10:
            template = _rotate_phrasing(f"action_delta:{seed}", _ACTION_VARIANTS_DELTA)
            return template.format(title=title, delta=delta)
    template = _rotate_phrasing(f"action_default:{seed}", _ACTION_VARIANTS_DEFAULT)
    return template.format(title=title)



def _generate_dashboard_story(kpis: List[Dict[str, Any]], domain: str) -> str:
    """Generate a 1-2 sentence CEO-level summary from computed KPI data."""
    hero = next((k for k in kpis if k.get("importance") == "hero"), None)
    anomalies = [k for k in kpis if k.get("is_anomaly")]
    top_changes = sorted(
        [k for k in kpis if k.get("delta_percent") is not None],
        key=lambda k: abs(k["delta_percent"]),
        reverse=True,
    )[:2]

    parts: list[str] = []

    if hero:
        fmt_val = _fmt_val(hero.get("value", 0), hero.get("format", "number"))
        delta = hero.get("delta_percent")
        if delta:
            direction = "growing" if delta > 0 else "declining"
            parts.append(f"{hero['title']} at {fmt_val}, {direction} {abs(delta):.1f}%")
        else:
            parts.append(f"{hero['title']} at {fmt_val}")

    if anomalies:
        a = anomalies[0]
        parts.append(f"{a['title']} showing {a.get('anomaly_severity', 'unusual')} deviation ({abs(a.get('z_score', 0)):.1f}\u03c3)")

    for k in top_changes:
        if hero and k.get("column") == hero.get("column"):
            continue
        direction = "up" if k["delta_percent"] > 0 else "down"
        parts.append(f"{k['title']} {direction} {abs(k['delta_percent']):.1f}%")

    if not parts:
        return f"Dashboard showing {len(kpis)} key metrics for your {domain} data."

    domain_prefix = f"{domain.replace('_', ' ').title()}: " if domain and domain != "general" else ""
    return domain_prefix + "; ".join(parts[:3]) + "."


# ── Template KPI Generation (from KPIService domain templates) ───────────


def _generate_template_kpis(
    df: pl.DataFrame,
    template_id: str,
    profiles: List[ColumnProfile],
    time_col: Optional[str],
    llm_column_mapping: Optional[dict[str, str]] = None,
    is_estimated: bool = False,
    estimate_ratio: Optional[float] = None,
    entity_profile_by_col: Optional[Dict[str, 'EntityAwareProfile']] = None,
) -> List[Dict[str, Any]]:
    """
    Generate KPI cards from a domain template definition by mapping column
    names via COLUMN_PATTERNS and computing each template KPI using its
    formula (simple / ratio / custom).

    Args:
        llm_column_mapping: Optional mapping from template column types to
            actual column names, provided by LLM classification. These
            take priority over pattern-based detection.
    """
    from services.kpi.patterns import COLUMN_PATTERNS
    from services.kpi.templates import ALL_TEMPLATES
    from services.kpi.definitions import (
        SAAS_KPIS, ECOMMERCE_KPIS, FINANCE_KPIS,
        HEALTHCARE_KPIS, REAL_ESTATE_KPIS, HR_KPIS,
        MARKETING_KPIS, EDUCATION_KPIS, MANUFACTURING_KPIS, LOGISTICS_KPIS,
        AUTOMOTIVE_KPIS,
    )

    CATEGORY_KPIS_MAP: dict[str, dict] = {
        "saas-metrics": SAAS_KPIS,
        "ecommerce-metrics": ECOMMERCE_KPIS,
        "finance-metrics": FINANCE_KPIS,
        "healthcare-metrics": HEALTHCARE_KPIS,
        "real-estate-metrics": REAL_ESTATE_KPIS,
        "hr-metrics": HR_KPIS,
        "marketing-metrics": MARKETING_KPIS,
        "education-metrics": EDUCATION_KPIS,
        "manufacturing-metrics": MANUFACTURING_KPIS,
        "logistics-metrics": LOGISTICS_KPIS,
        "automotive-metrics": AUTOMOTIVE_KPIS,
    }

    template = ALL_TEMPLATES.get(template_id)
    kpi_defs = CATEGORY_KPIS_MAP.get(template_id, {})
    if not template or not kpi_defs:
        return []

    # Detect column types via pattern matching
    detected_types: dict[str, str] = {}
    for p in profiles:
        col_lower = p.name.lower().replace("_", " ").replace("-", " ")
        for col_type, patterns in COLUMN_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, col_lower, re.IGNORECASE):
                    detected_types[p.name] = col_type
                    break

    # Build reverse mapping: col_type -> column_name
    type_to_col: dict[str, str] = {}
    for col_name, col_type in detected_types.items():
        if col_type not in type_to_col:
            type_to_col[col_type] = col_name

    # LLM column mapping takes priority over pattern-based detection
    if llm_column_mapping:
        for col_type, col_name in llm_column_mapping.items():
            if col_name in df.columns:
                type_to_col[col_type] = col_name

    # Map common synonyms that COLUMN_PATTERNS might miss
    for p in profiles:
        nl = p.name.lower().replace("_", " ").replace("-", " ")
        if "revenue" in nl and "revenue" not in type_to_col:
            type_to_col["revenue"] = p.name
        if "date" in nl or "time" in nl:
            if "date" not in type_to_col:
                type_to_col["date"] = p.name
        if "customer" in nl or "user" in nl or "client" in nl:
            if "customer_id" not in type_to_col and "customer_count" not in type_to_col:
                if "count" in nl or "number" in nl or "total" in nl:
                    type_to_col["customer_count"] = p.name
        if "cost" in nl or "expense" in nl or "spend" in nl:
            if "cost" not in type_to_col:
                type_to_col["cost"] = p.name
        if "order" in nl or "transaction" in nl or "invoice" in nl:
            if "transaction_id" not in type_to_col:
                type_to_col["transaction_id"] = p.name

    kpis: list[Dict[str, Any]] = []

    for component in template.kpis:
        kpi_id = component.kpi_id
        kpi_def = kpi_defs.get(kpi_id)
        if not kpi_def or not kpi_def.formula:
            continue

        try:
            value: Optional[float] = None
            used_column: Optional[str] = None
            used_profile: Optional[ColumnProfile] = None
            formula = kpi_def.formula

            if formula.formula_type == "simple":
                fc = formula.column or "revenue"
                mapped = type_to_col.get(fc)
                if mapped and mapped in df.columns:
                    used_column = mapped
                    used_profile = next((p for p in profiles if p.name == mapped), None)
                    if used_profile:
                        value = _compute_kpi_value(df, used_profile)

            elif formula.formula_type == "ratio":
                num_type = formula.numerator_column or ""
                den_type = formula.denominator_column or ""
                num_col = type_to_col.get(num_type)
                den_col = type_to_col.get(den_type)

                if num_col and den_col and num_col in df.columns and den_col in df.columns:
                    num_prof = next((p for p in profiles if p.name == num_col), None)
                    den_prof = next((p for p in profiles if p.name == den_col), None)
                    if num_prof and den_prof:
                        numerator = _compute_kpi_value(df, num_prof)
                        denominator = _compute_kpi_value(df, den_prof)
                        if denominator and denominator != 0:
                            value = numerator / denominator
                            if kpi_def.format == "percentage":
                                value *= 100
                            used_column = num_col
                            used_profile = num_prof

            elif formula.formula_type == "custom" and formula.custom_expression:
                value = _evaluate_template_formula(formula.custom_expression, type_to_col, df)
                first_col = next(iter(type_to_col.values()), None)
                if first_col and first_col in df.columns:
                    used_column = first_col
                    used_profile = next((p for p in profiles if p.name == first_col), None)

            if value is not None:
                card = _build_template_kpi_card(
                    kpi_def=kpi_def,
                    value=value,
                    used_column=used_column,
                    used_profile=used_profile,
                    profiles=profiles,
                    df=df,
                    time_col=time_col,
                    component_position=component.position,
                    is_estimated=is_estimated,
                    estimate_ratio=estimate_ratio,
                    entity_profile_by_col=entity_profile_by_col,
                )
                if card:
                    kpis.append(card)

        except Exception as e:
            logger.debug(f"[KPI] Template KPI '{kpi_id}' failed: {e}")
            continue

    return kpis


def _evaluate_template_formula(expr: str, column_mappings: dict[str, str], df: pl.DataFrame) -> Optional[float]:
    """Evaluate a simple arithmetic expression (e.g. 'revenue - cogs') using safe AST evaluation."""
    context: dict[str, float] = {}
    for var_name, col_name in column_mappings.items():
        if col_name in df.columns:
            try:
                context[var_name] = float(df[col_name].drop_nulls().sum())
            except Exception:
                context[var_name] = 0.0

    try:
        eval_expr = expr
        for var, val in context.items():
            eval_expr = re.sub(rf"\b{re.escape(var)}\b", str(val), eval_expr)

        from services.kpi.evaluator import safe_eval as safe_arithmetic_eval

        if re.match(r"^[\d\s\+\-\*\/\(\)\.]+$", eval_expr):
            return safe_arithmetic_eval(eval_expr)
    except Exception:
        pass
    return None


def _build_template_kpi_card(
    kpi_def,
    value: float,
    used_column: Optional[str],
    used_profile: Optional[ColumnProfile],
    profiles: List[ColumnProfile],
    df: pl.DataFrame,
    time_col: Optional[str],
    component_position: int = 0,
    is_estimated: bool = False,
    estimate_ratio: Optional[float] = None,
    entity_profile_by_col: Optional[Dict[str, 'EntityAwareProfile']] = None,
) -> Optional[Dict[str, Any]]:
    """Build a KPI card dict from a template definition."""
    if value is None:
        return None

    fmt_map = {"currency": "currency", "percentage": "percentage", "number": "decimal"}
    fmt = fmt_map.get(kpi_def.format, "decimal")

    from db.schemas_kpi import TrendDirection

    polarity = "higher_is_better"
    if kpi_def.trend_direction == TrendDirection.DOWN_IS_GOOD:
        polarity = "lower_is_better"

    profile = used_profile or next((p for p in profiles if p.name == used_column), None)

    if profile:
        comparison = _compute_comparison(df, profile, time_col)
        sparkline = _compute_sparkline(df, profile, time_col)
        time_period = _detect_time_period(df, profile, time_col)
        period_values = time_period.get("period_values", [])
        baseline = _compute_rolling_baseline(period_values, window=3)
        baseline_value = baseline.get("baseline_value")
        baseline_std = baseline.get("baseline_std")
        anomaly = _detect_anomaly(value, baseline_value or 0, baseline_std or 0)
        trend = _compute_trend_forecast(period_values)
        top_driver = _compute_top_driver(df, profile.name)
    else:
        comparison = None
        sparkline = {"data": [], "type": "distribution"}
        time_period = {}
        baseline = {}
        anomaly = {"is_anomaly": False, "anomaly_direction": "normal", "z_score": 0.0, "anomaly_severity": "normal"}
        trend = {}
        top_driver = None
        baseline_value = None

    delta_dir = comparison["delta_direction"] if comparison else None
    accent = _compute_accent_color("hero" if component_position < 3 else "high", delta_dir, polarity)

    dummy_profile = profile or ColumnProfile(
        name=used_column or kpi_def.id or kpi_def.name,
        role=ColumnRole.MEASURE,
        n_rows=len(df),
        n_nulls=0,
        n_unique=0,
    )
    # ── Entity info for template KPIs ──
    entity_info_for_insight = None
    entity_type_val = "Unknown"
    entity_conc = None
    top_entity_val = None
    entity_card = None
    if entity_profile_by_col and used_column:
        ep = entity_profile_by_col.get(used_column)
        if ep:
            entity_type_val = ep.entity_type
            entity_conc = ep.entity_concentration_pct
            top_entity_val = ep.top_entity_value
            entity_card = ep.entity_cardinality
            entity_info_for_insight = {
                "entity_type": entity_type_val,
                "entity_concentration_pct": entity_conc,
                "top_entity_value": top_entity_val,
                "entity_cardinality": entity_card,
            }

    insight, action = _generate_deterministic_insight(
        dummy_profile, value, comparison, anomaly, trend, top_driver, fmt,
        entity_info=entity_info_for_insight,
    )

    bench_val = dummy_profile.col_p75 if dummy_profile else None
    bench_label = "Top 25%" if bench_val else None

    cat_str = "general"
    if hasattr(kpi_def, "category"):
        c = kpi_def.category
        if hasattr(c, "value"):
            cat_str = c.value
        elif isinstance(c, str):
            cat_str = c

    provenance = build_provenance(
        profile=dummy_profile,
        df=df,
        column=used_column or kpi_def.id or kpi_def.name.lower().replace(" ", "_"),
        aggregation=kpi_def.formula.formula_type if kpi_def.formula else "sum",
        is_estimated=is_estimated,
        estimate_ratio=estimate_ratio,
        source_table="upload",
        formula_override=kpi_def.name,
    )

    return {
        "type": "kpi",
        "column": used_column or kpi_def.id or kpi_def.name.lower().replace(" ", "_"),
        "provenance": provenance.to_dict(),
        "entity_type": entity_type_val,
        "entity_concentration_pct": entity_conc,
        "top_entity_value": top_entity_val,
        "entity_cardinality": entity_card,
        "aggregation": kpi_def.formula.formula_type if kpi_def.formula else "sum",
        "importance": "hero" if component_position < 2 else "high",
        "business_category": cat_str,
        "template_kpi": True,
        "template_id": kpi_def.id,
        "is_estimated": is_estimated,
        "estimate_ratio": estimate_ratio,
        "title": kpi_def.name,
        "subtitle": kpi_def.description[:80] if kpi_def.description else "",
        "value": round(value, 4),
        "format": fmt,
        "icon": _template_icon_name(kpi_def.icon),
        "record_count": len(df),
        "comparison_value": comparison["comparison_value"] if comparison else None,
        "comparison_label": comparison["comparison_label"] if comparison else None,
        "delta_percent": comparison["delta_percent"] if comparison else None,
        "delta_direction": comparison["delta_direction"] if comparison else None,
        "is_delta_positive": comparison["is_delta_positive"] if comparison else (polarity == "higher_is_better"),
        "accent_color": accent,
        "sparkline_data": sparkline,
        "benchmark_value": round(bench_val, 2) if bench_val else None,
        "benchmark_label": bench_label,
        "benchmark_text": f"{bench_label}: {_fmt_val(bench_val, fmt)}" if bench_val and bench_label else None,
        "ai_suggestion": insight,
        "action_prompt": action,
        "dashboard_story": "",
        "archetype": cat_str,
        "col_p75": dummy_profile.col_p75 if dummy_profile else None,
        "col_median": dummy_profile.col_median if dummy_profile else None,
        "polarity": polarity,
        "period_label": time_period.get("period_label", ""),
        "previous_period_label": time_period.get("previous_period_label", ""),
        "period_type": time_period.get("period_type", ""),
        "baseline_value": baseline_value,
        "baseline_label": "3-month avg" if time_period.get("period_type") == "month" else "baseline",
        "vs_baseline_pct": (
            round(((value - (baseline_value or 0)) / abs(baseline_value or 1)) * 100, 1)
            if baseline_value and baseline_value != 0 else None
        ),
        "baseline_std": baseline.get("baseline_std"),
        "normal_range_low": baseline.get("normal_range_low"),
        "normal_range_high": baseline.get("normal_range_high"),
        "is_anomaly": anomaly.get("is_anomaly", False),
        "anomaly_direction": anomaly.get("anomaly_direction", "normal"),
        "z_score": anomaly.get("z_score", 0.0),
        "anomaly_severity": anomaly.get("anomaly_severity", "normal"),
        "expected_value": trend.get("expected_value"),
        "trend_direction": trend.get("trend_direction", "flat"),
        "top_driver": top_driver,
        "vs_previous_pct": (
            round(((value - (time_period.get("previous_period_value") or 0)) / abs(time_period.get("previous_period_value") or 1)) * 100, 1)
            if time_period.get("previous_period_value") else None
        ),
    }


def _template_icon_name(icon: Optional[str]) -> str:
    """Map KPIService icon names to Lucide icon names."""
    mapping = {
        "dollar-sign": "DollarSign", "trending-up": "TrendingUp",
        "user-minus": "UserMinus", "users": "Users", "target": "Target",
        "scale": "Scale", "refresh-cw": "RefreshCw", "flame": "Flame",
        "clock": "Clock", "user": "User", "shopping-cart": "ShoppingCart",
        "receipt": "Receipt", "package": "Package", "credit-card": "CreditCard",
        "activity": "Activity", "calendar": "Calendar", "line-chart": "LineChart",
        "shopping-bag": "ShoppingBag", "bar-chart-2": "BarChart3",
        "user-check": "UserCheck", "mouse-pointer": "MousePointer",
        "book-open": "BookOpen", "truck": "Truck", "home": "Home",
        "alert-triangle": "AlertTriangle", "percent": "Percent",
    }
    return mapping.get(icon or "", "BarChart3")


# ── Main Generator ────────────────────────────────────────────────────────────


class IntelligentKPIGenerator:
    """
    Production KPI generator. Thinks like a data scientist.
    Output format maps 1:1 to EnterpriseKpiCard props.

    Memory management: automatically downsamples DataFrames that exceed
    ``max_memory_mb`` to prevent OOM crashes on large datasets.
    """

    def __init__(
        self,
        max_memory_mb: int = DEFAULT_MAX_MEMORY_MB,
        max_safe_rows: int = DEFAULT_MAX_SAFE_ROWS,
    ):
        self.max_memory_mb = max_memory_mb
        self.max_safe_rows = max_safe_rows

    def _downsample_if_needed(
        self, df: pl.DataFrame
    ) -> Tuple[pl.DataFrame, bool, Optional[float]]:
        """Check if the DataFrame exceeds the memory limit and downsample if so.

        Uses Polars' ``estimated_size()`` to check memory usage (it's fast,
        O(1) — reads an internal buffer counter). If the DataFrame exceeds
        ``max_memory_mb``, downsamples to ``max_safe_rows`` using stratified
        sampling (preserves distribution of categorical columns) or random
        sampling as fallback.

        This is the primary OOM guard for the KPI generator. All entry points
        (``generate_intelligent_kpis``, ``generate_single_kpi``) call this
        before any computation.

        Returns:
            Tuple of (DataFrame, is_estimated, estimate_ratio).
            ``is_estimated`` is True if the data was downsampled.
            ``estimate_ratio`` is the fraction of rows retained (None if not downsampled).
        """
        try:
            memory_mb = df.estimated_size() / (1024 * 1024)
        except Exception:
            return df, False, None

        if memory_mb <= self.max_memory_mb:
            return df, False, None

        rows = len(df)
        logger.warning(
            f"[KPI] DataFrame is {memory_mb:.0f}MB ({rows:,} rows) — "
            f"exceeds {self.max_memory_mb}MB limit. Downsampling to "
            f"{self.max_safe_rows:,} rows for OOM safety."
        )

        if rows <= self.max_safe_rows:
            return df, False, None

        # ── Stratified sampling: preserve category distributions ──────────
        try:
            cat_col = None
            for col in df.columns:
                dtype = df[col].dtype
                if dtype in (pl.Utf8, pl.Categorical):
                    n_unique = df[col].n_unique()
                    if 2 <= n_unique <= min(100, rows // 10):
                        cat_col = col
                        break
                elif dtype in _INTEGER_DTYPES:
                    n_unique = df[col].n_unique()
                    if 2 <= n_unique <= min(20, rows // 10):
                        cat_col = col
                        break

            if cat_col:
                n_categories = df[cat_col].n_unique()
                samples_per_cat = max(self.max_safe_rows // n_categories, 2)

                sampled_frames = []
                for category in df[cat_col].unique().to_list():
                    group = df.filter(pl.col(cat_col) == category)
                    n_to_sample = min(samples_per_cat, len(group))
                    if n_to_sample > 0:
                        sampled_frames.append(group.sample(n=n_to_sample, seed=42))

                if sampled_frames:
                    sampled = pl.concat(sampled_frames)
                    if len(sampled) < self.max_safe_rows * 0.9:
                        remaining = self.max_safe_rows - len(sampled)
                        extra = df.sample(n=min(remaining, len(df)), seed=42)
                        sampled = pl.concat([sampled, extra])
                    if len(sampled) > self.max_safe_rows:
                        sampled = sampled.sample(n=self.max_safe_rows, seed=42)
                    ratio = round(len(sampled) / rows, 4) if rows > 0 else None
                    return sampled, True, ratio
        except Exception as e:
            logger.debug(f"[KPI] Stratified sampling failed, using random: {e}")

        # ── Fallback: random sampling ─────────────────────────────────────
        sampled = df.sample(n=self.max_safe_rows, seed=42)
        ratio = round(self.max_safe_rows / rows, 4) if rows > 0 else None
        return sampled, True, ratio

    async def generate_intelligent_kpis(
        self,
        df: pl.DataFrame,
        domain: Optional[str] = None,
        max_kpis: int = 6,
        dataset_metadata: Optional[Dict[str, Any]] = None,
        dataset_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        metadata = dataset_metadata or {}
        domain = domain or metadata.get("domain_intelligence", {}).get("domain", "general")

        # ── 0a. Memory guard: prevent OOM on large datasets ────────────────────
        df, is_estimated, estimate_ratio = self._downsample_if_needed(df)

        # ── 0b. Coerce string columns: parse numeric strings (with commas, $)
        #      and date strings into proper typed columns so the profiler can
        #      detect sales/revenue columns and time columns correctly.
        df = _coerce_string_columns(df)

        # ── 1. Profile all columns ───────────────────────────────────────────
        profiles: List[ColumnProfile] = []
        for col in df.columns:
            p = _profile_column(df, col)
            if p is not None:
                profiles.append(p)

        if not profiles:
            logger.warning("[KPI] No column profiles built \u2014 empty dataset?")
            return []

        # ── 1b. Determine if this is a small dataset (skip heavy stages) ──
        # Datasets with fewer than SMALL_DATASET_THRESHOLD rows don't have enough
        # statistical mass for entity detection, LLM classification, or synthetic
        # profile injection. Running these stages wastes time and money.
        is_small_dataset = len(df) < SMALL_DATASET_THRESHOLD
        if is_small_dataset:
            logger.info(
                f"[KPI] Small dataset detected ({len(df)} rows < {SMALL_DATASET_THRESHOLD}) — "
                f"skipping entity-aware profiles, LLM domain classification, and synthetic injection"
            )

        # ── 1c. Build entity-aware profiles (adds entity type, concentration, etc.) ──
        # Skipped for small datasets — entity detection needs statistical mass
        entity_aware_profiles: List[EntityAwareProfile] = []
        entity_profile_by_col: Dict[str, 'EntityAwareProfile'] = {}
        if not is_small_dataset:
            try:
                entity_aware_profiles = build_entity_aware_profiles(df)
                logger.info(
                    f"[KPI] Built {len(entity_aware_profiles)} entity-aware profiles "
                    f"({len(profiles_by_entity(entity_aware_profiles))} entity groups)"
                )
            except Exception as e:
                logger.warning(f"[KPI] Entity-aware profiling skipped: {e}")
            entity_profile_by_col = {p.name: p for p in entity_aware_profiles}

        # ── 1d. Inject entity-derived synthetic profiles for richer KPI selection ──
        # These are derived KPIs like "Total Customers", "Avg X per Customer",
        # "High Spender Ratio", etc. that don't have a direct column.
        # Skipped for small datasets — no statistical basis for derived KPIs.
        if not is_small_dataset:
            synthetic_profiles_added = _inject_entity_synthetic_profiles(
                df, profiles, entity_aware_profiles, logger,
            )

        # ── 2. Detect domain ─────────────────────────────────────────────────
        # For small datasets: use pattern matching only (no LLM call — saves $)
        # For normal datasets: LLM-first with pattern matching fallback
        time_col = _find_time_column(df)
        if is_small_dataset:
            # Pattern-matching only — no LLM call for small datasets
            _, domain_template_id, _ = _compute_domain_scores(profiles)
            column_mapping = None
            if domain_template_id:
                logger.info(
                    f"[KPI] Small dataset: pattern-only domain = {domain_template_id}"
                )
        else:
            # ── Check DatasetMemo cache first (avoids redundant LLM call) ──
            cached_memo = DatasetMemoCache.get(dataset_id) if dataset_id else None
            if cached_memo and cached_memo.domain_detected:
                domain_template_id = cached_memo.domain_id
                column_mapping = cached_memo.column_mapping
                logger.info(
                    f"[KPI] Using cached domain from DatasetMemo: {domain_template_id} "
                    f"(saved LLM call — originally detected via {cached_memo.domain_method})"
                )
            else:
                domain_template_id, column_mapping = await _detect_domain_hybrid(profiles, df)

        # ── 2b. Build Metric Relationship Graph (discovers component relationships) ──
        # Skipped for small datasets — no meaningful relationships to discover
        metric_graph = None
        if not is_small_dataset:
            try:
                metric_graph = build_metric_graph(
                    df, profiles, domain_template_id=domain_template_id
                )
                if not metric_graph.empty:
                    logger.info(
                        f"[KPI] Metric graph built: {metric_graph.metric_count} metrics, "
                        f"{len(metric_graph.edges)} relationships"
                    )
            except Exception as e:
                logger.debug(f"[KPI] Metric graph skipped: {e}")
                metric_graph = None

        # ── 3. Generate template KPIs if domain detected ─────────────────────
        template_kpis: List[Dict[str, Any]] = []
        enrichment_profile = None
        if domain_template_id:
            logger.info(f"[KPI] Domain detected: {domain_template_id} \u2014 generating template KPIs")
            template_kpis = _generate_template_kpis(
                df, domain_template_id, profiles, time_col,
                llm_column_mapping=column_mapping,
                is_estimated=is_estimated, estimate_ratio=estimate_ratio,
                entity_profile_by_col=entity_profile_by_col,
            )
            for tk in template_kpis:
                tk["_template"] = domain_template_id

            # ── Stage 2 enrichment: rich semantic profile ────────────────────
            if not is_small_dataset:
                try:
                    from services.domain.domain_enrichment import enrich_domain
                    enrichment_profile = await enrich_domain(profiles, df, domain_template_id)
                    if enrichment_profile:
                        profile_dict = enrichment_profile.to_dict()
                        for tk in template_kpis:
                            tk["_domain_profile"] = profile_dict
                        logger.info(
                            f"[KPI] Stage 2 enrichment attached: "
                            f"{len(profile_dict['column_semantics'])} semantics, "
                            f"{len(profile_dict['suggested_metrics'])} metrics, "
                            f"{len(profile_dict['analytical_intents'])} intents"
                        )
                except Exception as e:
                    logger.warning(f"[KPI] Stage 2 enrichment skipped: {e}")

        # ── 4. Select candidates via the gate ────────────────────────────────
        # (profiles may have been augmented by _inject_entity_synthetic_profiles in step 1d)
        candidates = _select_candidates(profiles, max_kpis)

        if not candidates:
            if template_kpis:
                logger.info(f"[KPI] No gate-passed candidates, using {len(template_kpis)} template KPIs")
                dash_story = _generate_dashboard_story(template_kpis, domain or "general")
                return _attach_story(template_kpis, dash_story, domain)
            logger.warning("[KPI] No candidates passed the KPI gate")
            return self._domain_aware_fallback(
                df, profiles, domain, max_kpis, metadata,
                is_estimated=is_estimated, estimate_ratio=estimate_ratio,
            )

        # ── 5. Run surprising patterns engine (Tier 2 & 3 hidden insights) ───
        # Skipped for small datasets — no surprising patterns to find with <100 rows
        surprise_cards: List[Dict[str, Any]] = []
        if not is_small_dataset:
            # Lazy import to break circular dependency
            from .surprising_patterns import SurprisingPatternsEngine
            surprising_patterns_engine = SurprisingPatternsEngine(max_insights=4)
            surprise_insights = surprising_patterns_engine.discover_all(df, profiles, time_col)
            surprise_cards = [insight.to_card() for insight in surprise_insights]

        # ── 6. Build final KPI card dicts (deterministic insights, no LLM) ───
        kpis: List[Dict[str, Any]] = []
        for profile in candidates:
            try:
                # Synthetic profiles (prefixed with _) store computed values in the profile itself
                is_synthetic = profile.name.startswith("_")
                if is_synthetic:
                    value = profile.primary_value or 0
                else:
                    value = _compute_kpi_value(df, profile)
                comparison = _compute_comparison(df, profile, time_col)
                sparkline = _compute_sparkline(df, profile, time_col)
                fmt = _infer_format(profile, value)
                icon = _infer_icon(profile)
                subtitle = _build_subtitle(profile, len(df), time_col, domain)

                delta_dir = comparison["delta_direction"] if comparison else None
                accent = _compute_accent_color(profile.importance, delta_dir, profile.polarity)

                time_period = _detect_time_period(df, profile, time_col)
                period_values = time_period.get("period_values", [])

                baseline = _compute_rolling_baseline(period_values, window=3)
                baseline_value = baseline.get("baseline_value")
                baseline_std = baseline.get("baseline_std")

                anomaly = _detect_anomaly(value, baseline_value or 0, baseline_std or 0)
                trend = _compute_trend_forecast(period_values)
                top_driver = _compute_top_driver(df, profile.name) if not is_synthetic else None

                vs_baseline_pct = None
                if baseline_value and baseline_value != 0:
                    vs_baseline_pct = round(((value - baseline_value) / abs(baseline_value)) * 100, 1)

                vs_previous_pct = None
                prev_period_value = time_period.get("previous_period_value")
                if prev_period_value and prev_period_value != 0:
                    vs_previous_pct = round(((value - prev_period_value) / abs(prev_period_value)) * 100, 1)

                # ── Provenance / Trust Layer ────────────────────────────────
                provenance = build_provenance(
                    profile=profile,
                    df=df,
                    column=profile.name,
                    aggregation=profile.aggregation,
                    is_estimated=is_estimated,
                    estimate_ratio=estimate_ratio,
                    source_table=metadata.get("name", "upload"),
                )

                # ── Entity-aware fields ────────────────────────────────────
                entity_prof = entity_profile_by_col.get(profile.name)
                entity_type = entity_prof.entity_type if entity_prof else "Unknown"
                entity_concentration = entity_prof.entity_concentration_pct if entity_prof else None
                top_entity = entity_prof.top_entity_value if entity_prof else None
                entity_cardinality = entity_prof.entity_cardinality if entity_prof else None
                is_entity_attribute = entity_prof.is_entity_attribute if entity_prof else False

                # Deterministic insight (no LLM) — now with entity awareness
                entity_info_for_insight = {
                    "entity_type": entity_type,
                    "entity_concentration_pct": entity_concentration,
                    "top_entity_value": top_entity,
                    "entity_cardinality": entity_cardinality,
                } if entity_prof else None

                # ── Cross-segment comparison insight (when no time series exists) ──
                segment_comparison = _compute_segment_comparison(
                    df, profile.name, profile.polarity,
                ) if not comparison and not is_synthetic else None
                
                insight, action = _generate_deterministic_insight(
                    profile, value, comparison, anomaly, trend, top_driver, fmt,
                    entity_info=entity_info_for_insight,
                    segment_compare=segment_comparison,
                )

                bench_val = profile.col_p75
                bench_label = "Top 25%" if bench_val else None

                kpi = {
                    "type": "kpi",
                    "column": profile.name,
                    "aggregation": profile.aggregation,
                    "importance": profile.importance,
                    "business_category": profile.business_category,
                    "title": _humanize_title(profile),
                    "subtitle": subtitle,
                    "value": value,
                    "format": fmt,
                    "icon": icon,
                    "record_count": len(df) - profile.n_nulls,
                    "comparison_value": comparison["comparison_value"] if comparison else None,
                    "comparison_label": comparison["comparison_label"] if comparison else None,
                    "delta_percent": comparison["delta_percent"] if comparison else None,
                    "delta_direction": comparison["delta_direction"] if comparison else None,
                    "is_delta_positive": comparison["is_delta_positive"] if comparison else (profile.polarity == "higher_is_better"),
                    "accent_color": accent,
                    "sparkline_data": sparkline,
                    "benchmark_value": round(bench_val, 2) if bench_val else None,
                    "benchmark_label": bench_label,
                    "benchmark_text": f"{bench_label}: {_fmt_val(bench_val, fmt)}" if bench_val and bench_label else None,
                    "ai_suggestion": insight,
                    "action_prompt": action,
                    "dashboard_story": "",
                    "archetype": domain or "general",
                    "col_p75": profile.col_p75,
                    "col_median": profile.col_median,
                    "polarity": profile.polarity,
                    "period_label": time_period.get("period_label", ""),
                    "previous_period_label": time_period.get("previous_period_label", ""),
                    "period_type": time_period.get("period_type", ""),
                    "baseline_value": baseline_value,
                    "baseline_label": "3-month avg" if time_period.get("period_type") == "month" else "baseline",
                    "vs_baseline_pct": vs_baseline_pct,
                    "baseline_std": baseline_std,
                    "normal_range_low": baseline.get("normal_range_low"),
                    "normal_range_high": baseline.get("normal_range_high"),
                    "is_anomaly": anomaly.get("is_anomaly", False),
                    "anomaly_direction": anomaly.get("anomaly_direction", "normal"),
                    "z_score": anomaly.get("z_score", 0.0),
                    "anomaly_severity": anomaly.get("anomaly_severity", "normal"),
                    "expected_value": trend.get("expected_value"),
                    "trend_direction": trend.get("trend_direction", "flat"),
                    "top_driver": top_driver,
                    "vs_previous_pct": vs_previous_pct,
                    # ── Entity-aware fields ──
                    "entity_type": entity_type,
                    "entity_concentration_pct": entity_concentration,
                    "top_entity_value": top_entity,
                    "entity_cardinality": entity_cardinality,
                    "is_entity_attribute": is_entity_attribute,
                }
                kpi["is_estimated"] = is_estimated
                kpi["estimate_ratio"] = estimate_ratio
                kpi["provenance"] = provenance.to_dict()
                kpis.append(kpi)
            except Exception as e:
                logger.error(f"[KPI] Failed to build card for '{profile.name}': {e}")

        # ── 7. Merge template KPIs with auto-detected KPIs ──────────────────
        # Template KPIs take priority slots, auto-detected fill remaining
        merged = _merge_template_and_auto_kpis(template_kpis, kpis, max_kpis)

        # ── 8. Run root cause chain computation for every KPI with a delta ──
        # Skipped for small datasets — no meaningful chains with <100 rows
        if not is_small_dataset:
            try:
                merged = compute_chains_for_kpis(df, merged, time_col=time_col)
                root_cause_count = sum(1 for k in merged if k.get("root_cause_chain"))
                if root_cause_count:
                    logger.info(f"[KPI] Root cause chains: {root_cause_count}/{len(merged)} KPIs")
            except Exception as e:
                logger.warning(f"[KPI] Root cause chain computation skipped: {e}")

        # ── 9. Run decision engine for every KPI with a meaningful delta ──
        # Skipped for small datasets
        if not is_small_dataset:
            try:
                merged = compute_decisions_for_kpis(merged)
                decision_count = sum(1 for k in merged if k.get("decision"))
                if decision_count:
                    logger.info(f"[KPI] Decisions: {decision_count}/{len(merged)} KPIs")
            except Exception as e:
                logger.warning(f"[KPI] Decision engine skipped: {e}")

        # ── 9b. Attach metric decomposition (component-level breakdown) ──
        # metric_graph is None for small datasets, so guard against None here
        if metric_graph is not None and not metric_graph.empty:
            try:
                merged = attach_metric_decompositions(
                    merged, metric_graph, df, time_col=time_col
                )
                decomp_count = sum(
                    1 for k in merged if k.get("metric_decomposition")
                )
                if decomp_count:
                    logger.info(
                        f"[KPI] Metric decompositions: {decomp_count}/{len(merged)} KPIs"
                    )
            except Exception as e:
                logger.warning(f"[KPI] Metric decomposition skipped: {e}")

        # ── 10. Attach enrichment profile to hero KPI ────────────────────────
        if enrichment_profile and merged:
            profile_dict = enrichment_profile.to_dict()
            merged[0]["domain_profile"] = profile_dict
            merged[0]["nl_summary"] = profile_dict.get("natural_language_summary", "")

        dash_story = _generate_dashboard_story(merged, domain or "general")
        for k in merged:
            if k.get("importance") == "hero":
                k["dashboard_story"] = dash_story

        # ── 8. Append surprising insight cards ───────────────────────────────
        # These are non-obvious patterns discovered by the correlation mining,
        # segment decomposition, concentration risk, and ratio anomaly engines.
        merged.extend(surprise_cards)

        logger.info(
            f"[KPI] Generated {len(merged)} items (template={len(template_kpis)}, "
            f"auto={len(kpis)}, surprising={len(surprise_cards)}) for domain='{domain}'"
        )
        return merged

    # ── Fallback ─────────────────────────────────────────────────────────────

    def _domain_aware_fallback(
        self,
        df: pl.DataFrame,
        profiles: List[ColumnProfile],
        domain: str,
        max_kpis: int,
        metadata: Dict[str, Any],
        is_estimated: bool = False,
        estimate_ratio: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Last-resort: pick top numeric columns by absolute value."""
        logger.info("[KPI] Using domain-aware fallback")
        numeric = [
            p
            for p in profiles
            if p.role in (ColumnRole.MEASURE, ColumnRole.COUNT, ColumnRole.RATE)
            and p.null_pct < 50
            and p.primary_value is not None
        ]
        if not numeric:
            return []

        numeric.sort(key=lambda p: abs(p.primary_value or 0), reverse=True)
        top = numeric[:max_kpis]
        top[0].importance = "hero"
        for p in top[1:]:
            p.importance = "high"

        time_col = _find_time_column(df)
        kpis = []
        for p in top:
            try:
                value = _compute_kpi_value(df, p)
                comparison = _compute_comparison(df, p, time_col)
                sparkline = _compute_sparkline(df, p, time_col)
                fmt = _infer_format(p, value)
                delta_dir = comparison["delta_direction"] if comparison else None
                accent = _compute_accent_color(p.importance, delta_dir, p.polarity)

                # Deterministic insight for fallback too
                insight, action = _generate_deterministic_insight(
                    p, value, comparison,
                    {"is_anomaly": False, "anomaly_direction": "normal", "z_score": 0.0, "anomaly_severity": "normal"},
                    {}, None, fmt,
                )

                provenance = build_provenance(
                    profile=p,
                    df=df,
                    column=p.name,
                    aggregation=p.aggregation,
                    is_estimated=is_estimated,
                    estimate_ratio=estimate_ratio,
                    source_table="upload",
                )

                kpis.append({
                    "type": "kpi",
                    "column": p.name,
                    "provenance": provenance.to_dict(),
                    "aggregation": p.aggregation,
                    "importance": p.importance,
                    "is_estimated": is_estimated,
                    "estimate_ratio": estimate_ratio,
                    # DEPRECATED: confidence_score is deprecated. Use z_score + is_estimated instead.
                    "title": _humanize_title(p),
                    "subtitle": _build_subtitle(p, len(df), time_col, domain),
                    "value": value,
                    "format": fmt,
                    "icon": _infer_icon(p),
                    "record_count": len(df) - p.n_nulls,
                    "comparison_value": comparison["comparison_value"] if comparison else None,
                    "comparison_label": comparison["comparison_label"] if comparison else None,
                    "delta_percent": comparison["delta_percent"] if comparison else None,
                    "delta_direction": comparison["delta_direction"] if comparison else None,
                    "is_delta_positive": p.polarity == "higher_is_better",
                    "accent_color": accent,
                    "sparkline_data": sparkline,
                    "ai_suggestion": insight,
                    "action_prompt": action,
                })
            except Exception:
                continue

        dash_story = _generate_dashboard_story(kpis, domain)
        return _attach_story(kpis, dash_story, domain)

    # ── Single KPI Generation (for chat-driven addition) ──────────────────

    async def generate_single_kpi(
        self,
        df: pl.DataFrame,
        column: str,
        aggregation: str = "sum",
        custom_title: Optional[str] = None,
        dataset_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate a single KPI card for a specific column (chat-driven addition)."""
        try:
            # Memory guard: prevent OOM on large datasets
            df, is_estimated, estimate_ratio = self._downsample_if_needed(df)

            # Coerce string columns so sales/date columns are properly typed
            df = _coerce_string_columns(df)

            if column not in df.columns:
                return None

            clean = df[column].drop_nulls()
            if len(clean) == 0:
                return None

            value = _agg_series(df[column], aggregation)

            fmt = "number"
            if any(kw in column.lower() for kw in ["revenue", "cost", "price", "amount", "total"]):
                fmt = "currency"
            elif any(kw in column.lower() for kw in ["rate", "percent", "ratio"]):
                fmt = "percentage"

            polarity = "higher_is_better"
            if any(kw in column.lower() for kw in ["cost", "churn", "error", "loss", "defect"]):
                polarity = "lower_is_better"

            profile = ColumnProfile(
                name=column,
                aggregation=aggregation,
                role=ColumnRole.MEASURE,
                importance="medium",
                business_category="general",
                polarity=polarity,
                col_p75=None,
                col_median=None,
                n_nulls=int(df[column].null_count()),
                n_rows=len(df),
                n_unique=int(df[column].n_unique()),
            )
            title = custom_title or _humanize_title(profile)

            time_col = _find_time_column(df)
            sparkline = _compute_sparkline(df, profile, time_col)

            mid = len(df) // 2
            v1_val = _agg_series(df[:mid][column], aggregation)
            v2_val = _agg_series(df[mid:][column], aggregation)
            delta_pct = round(((v2_val - v1_val) / abs(v1_val)) * 100, 1) if v1_val != 0 else None

            sparkline_vals = sparkline.get("data", [])
            baseline = _compute_rolling_baseline(sparkline_vals, window=3)
            baseline_value = baseline.get("baseline_value")
            baseline_std = baseline.get("baseline_std")
            vs_baseline_pct = (
                round(((value - baseline_value) / abs(baseline_value)) * 100, 1)
                if baseline_value and baseline_value != 0 else None
            )

            anomaly = _detect_anomaly(value, baseline_value or 0, baseline_std or 0)
            trend = _compute_trend_forecast(sparkline_vals)
            top_driver = _compute_top_driver(df, column)
            time_period = _detect_time_period(df, profile, time_col)

            # Deterministic insight
            comparison = {
                "comparison_value": v1_val,
                "comparison_label": "vs previous period",
                "delta_percent": delta_pct,
                "delta_direction": "up" if delta_pct and delta_pct > 0 else ("down" if delta_pct and delta_pct < 0 else "neutral"),
                "is_delta_positive": polarity == "higher_is_better",
                "is_good": (delta_pct or 0) > 0 if polarity == "higher_is_better" else (delta_pct or 0) < 0,
            } if delta_pct is not None else None

            insight, action = _generate_deterministic_insight(
                profile, value, comparison, anomaly, trend, top_driver, fmt,
            )

            return {
                "type": "kpi",
                "column": column,
                "aggregation": aggregation,
                "importance": "medium",
                "business_category": "general",
                "title": title,
                "subtitle": time_period.get("period_label", ""),
                "value": value,
                "format": fmt,
                "icon": "BarChart3",
                "record_count": len(clean),
                "is_estimated": is_estimated,
                "estimate_ratio": estimate_ratio,
                "comparison_value": v1_val,
                "comparison_label": "vs previous period",
                "delta_percent": delta_pct,
                "delta_direction": "up" if delta_pct and delta_pct > 0 else ("down" if delta_pct and delta_pct < 0 else "neutral"),
                "is_delta_positive": polarity == "higher_is_better" if delta_pct else True,
                "accent_color": _compute_accent_color("medium", "up" if delta_pct and delta_pct > 0 else "down", polarity),
                "sparkline_data": sparkline,
                "benchmark_value": None,
                "benchmark_label": None,
                "benchmark_text": None,
                "ai_suggestion": insight,
                "action_prompt": action,
                "dashboard_story": "",
                "archetype": "general",
                "col_p75": None,
                "col_median": None,
                "polarity": polarity,
                "period_label": time_period.get("period_label", ""),
                "previous_period_label": time_period.get("previous_period_label", ""),
                "period_type": time_period.get("period_type", ""),
                "baseline_value": baseline_value,
                "baseline_label": "baseline",
                "vs_baseline_pct": vs_baseline_pct,
                "baseline_std": baseline_std,
                "normal_range_low": baseline.get("normal_range_low"),
                "normal_range_high": baseline.get("normal_range_high"),
                "is_anomaly": anomaly.get("is_anomaly", False),
                "anomaly_direction": anomaly.get("anomaly_direction", "normal"),
                "z_score": anomaly.get("z_score", 0.0),
                "anomaly_severity": anomaly.get("anomaly_severity", "normal"),
                "expected_value": trend.get("expected_value"),
                "trend_direction": trend.get("trend_direction", "flat"),
                "top_driver": top_driver,
                "vs_previous_pct": delta_pct,
            }
        except Exception as e:
            logger.debug(f"[KPI] Single KPI generation failed for '{column}': {e}")
            return None


# ── Merge helpers ─────────────────────────────────────────────────────────────


def _merge_template_and_auto_kpis(
    template_kpis: List[Dict[str, Any]],
    auto_kpis: List[Dict[str, Any]],
    max_kpis: int,
) -> List[Dict[str, Any]]:
    """
    Merge template KPIs with auto-detected KPIs.

    Template KPIs go first (preserving their hero/high importance),
    auto-detected KPIs fill remaining slots. Duplicates by column name
    are deduplicated (template wins).
    """
    result: List[Dict[str, Any]] = []
    seen_columns: set = set()

    # Template KPIs first
    for k in template_kpis:
        col = k.get("column", "")
        if col and col not in seen_columns:
            result.append(k)
            seen_columns.add(col)

    # Auto-detected KPIs fill remaining
    for k in auto_kpis:
        if len(result) >= max_kpis:
            break
        col = k.get("column", "")
        if col and col not in seen_columns:
            result.append(k)
            seen_columns.add(col)

    # Ensure hero is first
    hero_idx = next((i for i, k in enumerate(result) if k.get("importance") == "hero"), None)
    if hero_idx and hero_idx > 0:
        result.insert(0, result.pop(hero_idx))

    return result


def _attach_story(kpis: List[Dict[str, Any]], story: str, domain: str) -> List[Dict[str, Any]]:
    """Attach dashboard story to hero KPI."""
    for k in kpis:
        if k.get("importance") == "hero":
            k["dashboard_story"] = story
            break
    return kpis


# ── Helpers ───────────────────────────────────────────────────────────────────

_AGG_PREFIX = {
    "sum": "Total",
    "mean": "Average",
    "median": "Median",
    "max": "Peak",
    "min": "Lowest",
    "count": "Count of",
}


def _inject_entity_synthetic_profiles(
    df: pl.DataFrame,
    profiles: List[ColumnProfile],
    entity_aware_profiles: List['EntityAwareProfile'],
    log: logging.Logger,
) -> int:
    """Inject entity-derived synthetic profiles for richer KPI selection.
    
    If entity ID columns exist, adds synthetic profiles for:
      - Entity count (unique customers/products/etc.)
      - Average per-entity for numeric measure columns
    Modifies profiles in place. Returns count added.
    """
    added = 0
    if not entity_aware_profiles:
        return 0
    # Find entity ID columns
    entity_id_cols = [p for p in entity_aware_profiles if p.is_entity_id]
    if not entity_id_cols:
        return 0
    primary = entity_id_cols[0]
    entity_col = primary.name
    entity_type = primary.entity_type
    if entity_col not in df.columns:
        return 0
    unique_count = float(df[entity_col].n_unique())
    # 1. Entity count
    existing = [p for p in profiles if p.role == ColumnRole.COUNT and entity_type.lower() in p.name.lower()]
    if not existing:
        profiles.append(ColumnProfile(
            name=f"_{entity_type.lower()}_count_synthetic",
            role=ColumnRole.COUNT,
            n_rows=len(df), n_nulls=0, n_unique=int(unique_count),
            col_sum=unique_count, col_mean=unique_count,
            col_median=unique_count, col_min=unique_count, col_max=unique_count,
            cv=0.0, aggregation="sum", polarity="higher_is_better",
            business_category="users",
        ))
        added += 1
        log.info(f"[KPI] Injected synthetic: {entity_type} Count = {int(unique_count)}")
    # 2. Per-entity averages for numeric columns
    attrs = [p for p in entity_aware_profiles if p.is_entity_attribute 
             and p.semantic_role in ("measure","rate") and p.name in df.columns
             and p.entity_column == entity_col][:2]
    for ep in attrs:
        try:
            avg = df.group_by(entity_col).agg(pl.col(ep.name).mean().alias("_v")).get_column("_v").mean()
            if avg is not None:
                col_display = ep.name.replace("_"," ").replace("-"," ").strip().title()
                col_display = re.sub(r'\s*\([^)]*\)', '', col_display).strip()
                profiles.append(ColumnProfile(
                    name=f"_{entity_type.lower()}_avg_{ep.name}_synthetic",
                    role=ColumnRole.MEASURE,
                    n_rows=len(df), n_nulls=0, n_unique=int(unique_count),
                    col_sum=float(avg) * unique_count, col_mean=float(avg),
                    col_median=float(avg), col_min=float(avg), col_max=float(avg),
                    cv=0.0, aggregation="mean", polarity="higher_is_better",
                    business_category="price",
                ))
                added += 1
                log.info(f"[KPI] Injected per-entity avg: Avg {col_display} per {entity_type} = {float(avg):.2f}")
        except Exception as e:
            log.debug(f"[KPI] Per-entity avg failed: {e}")
    if added:
        log.info(f"[KPI] Injected {added} synthetic entity-derived profiles")
    return added


def _humanize_title(profile: ColumnProfile) -> str:
    name = profile.name.replace("_", " ").replace("-", " ").strip().title()
    # Strip unit suffixes: (k$), ($), (1-100), (%), (USD)
    name = re.sub(r'\s*\([^)]*\)\s*$', '', name).strip()
    name = re.sub(r'\s*\([^)]*\)', '', name).strip()
    name = re.sub(r'\s+', ' ', name).strip()
    prefix = _AGG_PREFIX.get(profile.aggregation, "")
    if prefix:
        if name.lower().startswith(prefix.lower()):
            return name
        return f"{prefix} {name}"
    return name


def _agg_series(series: pl.Series, aggregation: str) -> float:
    """Apply an aggregation to a polars Series."""
    clean = series.drop_nulls()
    if len(clean) == 0:
        return 0.0
    if aggregation == "sum":
        return float(clean.sum())
    elif aggregation == "mean":
        return float(clean.mean())
    elif aggregation == "median":
        return float(clean.median())
    elif aggregation == "count":
        return float(len(clean))
    elif aggregation == "max":
        return float(clean.max())
    elif aggregation == "min":
        return float(clean.min())
    else:
        return float(clean.sum())


def _fmt_val(val: Optional[float], fmt: str) -> str:
    if val is None:
        return "N/A"
    if fmt == "currency":
        if abs(val) >= 1e9:
            return f"${val / 1e9:.1f}B"
        if abs(val) >= 1e6:
            return f"${val / 1e6:.1f}M"
        if abs(val) >= 1e3:
            return f"${val / 1e3:.1f}K"
        return f"${val:,.0f}"
    if fmt == "percentage":
        # Raw values for bounded-0-1 columns (discount, rate, ratio) are stored as
        # fractions (e.g. 0.156 for 15.6%). Multiply by 100 when the value is a
        # plausible fraction (0 < |val| < 1) so it displays as "15.6%" not "0.1%".
        # Multiply by 100 except when val is 0 (stays 0) or >1 (already percentage scale)
        display_val = val * 100 if 0 <= abs(val) < 1 else val
        return f"{display_val:.1f}%"
    if abs(val) >= 1e6:
        return f"{val / 1e6:.1f}M"
    if abs(val) >= 1e3:
        return f"{val / 1e3:.1f}K"
    return f"{val:,.1f}"


# Singleton
intelligent_kpi_generator = IntelligentKPIGenerator()

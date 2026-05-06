"""
IntelligentKPIGenerator — Production v4 (Data Scientist Edition)
=================================================================
Thinks like a data scientist:
  1. Profile every column statistically
  2. Classify column roles (MEASURE / RATE / COUNT / DIMENSION / TIME / IDENTITY)
  3. Gate candidates: decision-relevance + direction-clarity + non-redundancy
  4. Select hero + 1-3 primaries
  5. Compute all values, comparisons, sparklines from real data
  6. Call LLM once for insight sentences + action prompts
  7. Return production-ready KPI card dicts

LLM is used ONLY for narrative (insight_sentence, action_prompt, archetype).
Selection, aggregation, and comparison are 100% deterministic Python.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

logger = logging.getLogger(__name__)


# ── Column Classification ─────────────────────────────────────────────────────

class ColumnRole(str, Enum):
    MEASURE   = "measure"    # numeric, summable  — revenue, cost, salary
    RATE      = "rate"       # numeric ratio/pct  — conversion_rate, margin
    COUNT     = "count"      # integer counts     — order_count, num_users
    DIMENSION = "dimension"  # categorical        — region, product, status
    TIME      = "time"       # datetime           — date, created_at
    IDENTITY  = "identity"   # IDs, skip          — customer_id, uuid


# Column name patterns for classification
_ID_RE   = re.compile(r'\b(id|uuid|guid|key|hash|token|code|zip|postal|phone|ip|sku|barcode)\b', re.I)
_TIME_RE = re.compile(r'\b(date|time|year|month|day|created|updated|timestamp|period|week|quarter)\b', re.I)
_RATE_RE = re.compile(r'\b(rate|ratio|percent|pct|margin|efficiency|factor|score|index|grade|accuracy|precision|recall|auc|ctr)\b', re.I)
_COUNT_RE = re.compile(r'\b(count|num|number|qty|quantity|units|items|orders|transactions|sessions|visits|clicks|impressions|requests)\b', re.I)

# Business category → polarity mapping
_CATEGORY_PATTERNS: List[Tuple[str, str, str]] = [
    # (category, pattern, polarity)
    ("revenue",     r'\b(revenue|sales|gmv|income|earnings|gross|mrr|arr|net_sales|turnover|proceeds|receipts)\b', "higher_is_better"),
    ("cost",        r'\b(cost|expense|opex|capex|cogs|spend|expenditure|loss|burn|overhead|tax|fee|charge|penalty|discount)\b', "lower_is_better"),
    ("volume",      r'\b(orders|transactions|purchases|bookings|units|items|shipments|deliveries|installs)\b', "higher_is_better"),
    ("users",       r'\b(users|customers|subscribers|members|accounts|clients|visitors|leads|prospects|buyers)\b', "higher_is_better"),
    ("rate_metric", r'\b(rate|ratio|percent|pct|margin|conversion|retention|satisfaction|engagement|utilization)\b', "higher_is_better"),
    ("churn_risk",  r'\b(churn|attrition|cancellation|dropout|refund|return|complaint|defect|error|failure|bug|issue)\b', "lower_is_better"),
    ("price",       r'\b(price|amount|value|aov|arpu|arpc|ltv|cac|worth|bid|ask)\b', "higher_is_better"),
    ("performance", r'\b(score|rating|nps|csat|satisfaction|quality|performance|rank|grade)\b', "higher_is_better"),
    ("duration",    r'\b(duration|latency|age|tenure|days|hours|minutes|seconds|ms|response_time|wait_time|cycle_time)\b', "lower_is_better"),
    ("quantity",    r'\b(count|num|qty|quantity|volume|capacity|inventory|stock|supply)\b', "higher_is_better"),
]


@dataclass
class ColumnProfile:
    name: str
    role: ColumnRole
    n_rows: int
    n_nulls: int
    n_unique: int

    # Numeric stats (None for non-numeric)
    col_sum:    Optional[float] = None
    col_mean:   Optional[float] = None
    col_median: Optional[float] = None
    col_std:    Optional[float] = None
    col_min:    Optional[float] = None
    col_max:    Optional[float] = None
    col_p25:    Optional[float] = None
    col_p75:    Optional[float] = None
    col_p90:    Optional[float] = None
    cv:         Optional[float] = None      # coefficient of variation
    skewness:   Optional[float] = None
    is_bounded_01: bool = False
    is_integer_valued: bool = False

    # Derived classification
    aggregation:       str = "sum"
    polarity:          str = "higher_is_better"  # or "lower_is_better"
    business_category: str = "unknown"
    importance:        str = "medium"            # "hero", "high", "medium"

    @property
    def null_pct(self) -> float:
        return (self.n_nulls / self.n_rows * 100) if self.n_rows > 0 else 0

    @property
    def primary_value(self) -> Optional[float]:
        """The computed KPI value based on aggregation."""
        if self.aggregation == "sum":    return self.col_sum
        if self.aggregation == "mean":   return self.col_mean
        if self.aggregation == "median": return self.col_median
        if self.aggregation == "max":    return self.col_max
        if self.aggregation == "min":    return self.col_min
        return self.col_mean


# ── Column Profiler ───────────────────────────────────────────────────────────

def _profile_numeric(col: pl.Series) -> Dict[str, Any]:
    clean = col.drop_nulls().cast(pl.Float64)
    if len(clean) == 0:
        return {}
    vals = clean.to_list()
    n = len(vals)
    mean = float(clean.mean())
    std  = float(clean.std()) if n > 1 else 0.0
    mn   = float(clean.min())
    mx   = float(clean.max())
    # Polars quantile returns scalar
    p25  = float(clean.quantile(0.25))
    p75  = float(clean.quantile(0.75))
    p90  = float(clean.quantile(0.90))
    med  = float(clean.median())
    cv   = abs(std / mean) if mean != 0 else 0.0

    # Skewness (Pearson's moment coefficient)
    if std > 0 and n >= 3:
        skew = sum((v - mean) ** 3 for v in vals) / (n * std ** 3)
    else:
        skew = 0.0

    return {
        "col_sum":    round(float(clean.sum()), 4),
        "col_mean":   round(mean, 4),
        "col_median": round(med, 4),
        "col_std":    round(std, 4),
        "col_min":    round(mn, 4),
        "col_max":    round(mx, 4),
        "col_p25":    round(p25, 4),
        "col_p75":    round(p75, 4),
        "col_p90":    round(p90, 4),
        "cv":         round(cv, 4),
        "skewness":   round(skew, 4),
        "is_bounded_01":      mn >= 0 and mx <= 1,
        "is_integer_valued":  all(v == int(v) for v in vals[:200]),
    }


def _classify_role(name: str, dtype_str: str, n_unique: int, n_rows: int,
                   numeric_stats: Dict[str, Any]) -> ColumnRole:
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
    # Requires: ≥50 rows AND n_unique ≤ 10 AND < 5% of rows are unique
    # (guards against small samples where continuous vars look low-cardinality)
    if n_rows >= 50 and n_unique <= 10 and (n_unique / n_rows) < 0.05:
        return ColumnRole.DIMENSION

    return ColumnRole.MEASURE


def _get_business_category(name: str) -> Tuple[str, str]:
    """Returns (category, polarity).
    Column names use _ as separator so we replace _ with space before
    applying \b word-boundary patterns.
    """
    # "conversion_rate" → "conversion rate" so \brate\b works
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
    total_patterns = re.compile(r'\b(revenue|sales|cost|expense|amount|value|profit|income|gmv|total)\b', re.I)
    if total_patterns.search(name):
        return "sum"
    price_patterns = re.compile(r'\b(price|aov|arpu|arpc|ltv|cac|average|avg|salary|wage)\b', re.I)
    if price_patterns.search(name):
        return "median" if abs(skewness) > 1.5 else "mean"
    # High CV → individual values vary a lot → sum is meaningful
    return "sum" if cv > 0.8 else "mean"


def _profile_column(df: pl.DataFrame, col_name: str) -> Optional[ColumnProfile]:
    try:
        col = df[col_name]
        dtype_str = str(col.dtype)
        n_rows = len(df)
        n_nulls = col.null_count()
        n_unique = col.n_unique()

        is_numeric = col.dtype in pl.NUMERIC_DTYPES
        numeric_stats = _profile_numeric(col) if is_numeric else {}
        role = _classify_role(col_name, dtype_str, n_unique, n_rows, numeric_stats)

        skewness = numeric_stats.get("skewness", 0.0) or 0.0
        cv = numeric_stats.get("cv", 0.0) or 0.0
        aggregation = _select_aggregation(role, col_name, skewness, cv) if is_numeric else "count_unique"

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

def _passes_gate(profile: ColumnProfile, selected_categories: set) -> Tuple[bool, str]:
    """Three-gate KPI selection — same as the Fortune 500 prompt logic."""
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

    # Gate 4: Must have a known business category (direction clarity)
    if profile.business_category == "unknown":
        return False, "unclear business direction"

    # Gate 5: Non-redundancy — one KPI per business category
    if profile.business_category in selected_categories:
        return False, f"redundant with {profile.business_category}"

    return True, profile.business_category


def _select_hero(candidates: List[ColumnProfile]) -> Optional[ColumnProfile]:
    """Hero = the single number a CEO asks for first."""
    # Revenue column wins
    for c in candidates:
        if c.business_category == "revenue":
            return c
    # Highest absolute sum among MEASURE columns
    measures = [c for c in candidates if c.role == ColumnRole.MEASURE and c.col_sum]
    if measures:
        return max(measures, key=lambda c: abs(c.col_sum or 0))
    # Fallback
    return candidates[0] if candidates else None


def _select_candidates(profiles: List[ColumnProfile], max_kpis: int) -> List[ColumnProfile]:
    """Apply the gate, pick hero + 1-3 primaries."""
    selected_categories: set = set()
    passed: List[ColumnProfile] = []

    # Sort: revenue first, then by absolute value descending
    def sort_key(p: ColumnProfile) -> Tuple[int, float]:
        priority = {"revenue": 0, "volume": 1, "users": 2, "price": 3,
                    "rate_metric": 4, "performance": 5, "cost": 6,
                    "churn_risk": 7, "duration": 8, "quantity": 9}
        prio = priority.get(p.business_category, 10)
        val = abs(p.primary_value or 0)
        return (prio, -val)

    sorted_profiles = sorted(profiles, key=sort_key)

    for profile in sorted_profiles:
        if len(passed) >= max_kpis:
            break
        ok, reason = _passes_gate(profile, selected_categories)
        if ok:
            selected_categories.add(reason)
            passed.append(profile)
        else:
            logger.debug(f"[KPI] Gate rejected '{profile.name}': {reason}")

    # Assign importance
    hero = _select_hero(passed)
    for i, p in enumerate(passed):
        p.importance = "hero" if p is hero else ("high" if i <= 2 else "medium")

    # Hero always first
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
        if agg == "sum":    return round(float(col.sum()), 2)
        if agg == "mean":   return round(float(col.mean()), 2)
        if agg == "median": return round(float(col.median()), 2)
        if agg == "max":    return round(float(col.max()), 2)
        if agg == "min":    return round(float(col.min()), 2)
        return round(float(col.sum()), 2)
    except Exception:
        return profile.primary_value or 0


def _find_time_column(df: pl.DataFrame) -> Optional[str]:
    for col in df.columns:
        if df[col].dtype in (pl.Date, pl.Datetime):
            return col
    # Fallback: name-based
    for col in df.columns:
        if _TIME_RE.search(col) and df[col].dtype in pl.NUMERIC_DTYPES:
            return col
    return None


def _compute_comparison(
    df: pl.DataFrame, profile: ColumnProfile, time_col: Optional[str]
) -> Optional[Dict[str, Any]]:
    """
    Returns comparison dict or None.
    Strategy: time-sorted first-half vs second-half (preferred),
              or top quartile vs bottom quartile (fallback).
    """
    try:
        col = profile.name
        if col not in df.columns:
            return None
        clean = df.drop_nulls(subset=[col])
        if len(clean) < 10:
            return None

        # Time-sorted split
        if time_col and time_col in df.columns:
            try:
                sorted_df = clean.sort(time_col)
                label = "vs first half (time-sorted)"
                is_temporal = True
            except Exception:
                sorted_df = clean
                label = "vs first half (row order)"
                is_temporal = False
        else:
            sorted_df = clean
            label = "vs first half (row order)"
            is_temporal = False

        mid = len(sorted_df) // 2
        first_half  = sorted_df[:mid]
        second_half = sorted_df[mid:]

        def agg_half(half: pl.DataFrame) -> Optional[float]:
            c = half[col].drop_nulls()
            if len(c) == 0:
                return None
            agg = profile.aggregation
            if agg == "sum":    return float(c.sum())
            if agg == "mean":   return float(c.mean())
            if agg == "median": return float(c.median())
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
            "delta_percent":    delta_pct,
            "delta_direction":  direction,
            "is_delta_positive": is_positive,
            "is_good":           is_good,
            "is_temporal":       is_temporal,
        }
    except Exception as e:
        logger.debug(f"[KPI] Comparison failed for '{profile.name}': {e}")
        return None


def _compute_sparkline(
    df: pl.DataFrame, profile: ColumnProfile, time_col: Optional[str], max_points: int = 12
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

        # Row-sampled fallback
        raw = df[col].drop_nulls().cast(pl.Float64).to_list()
        numeric = [v for v in raw if not (math.isnan(v) or math.isinf(v))]
        if len(numeric) < 3:
            return {"data": [], "type": "distribution"}
        step = max(1, len(numeric) // max_points)
        sampled = numeric[::step][:max_points]
        # 3-point moving average for smoother sparklines
        if len(sampled) >= 5:
            sampled = [
                sum(sampled[max(0, i-1):i+2]) / len(sampled[max(0, i-1):i+2])
                for i in range(len(sampled))
            ]
        return {"data": [round(v, 2) for v in sampled], "type": "distribution"}
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


def _infer_format(profile: ColumnProfile, value: Any) -> str:
    name = profile.name.lower()
    if any(t in name for t in ("revenue", "sales", "cost", "amount", "price", "value",
                                "profit", "income", "expense", "budget", "salary", "fee", "gmv")):
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
        "revenue":     "DollarSign",
        "cost":        "Activity",
        "volume":      "ShoppingCart",
        "users":       "Users",
        "rate_metric": "Percent",
        "churn_risk":  "Activity",
        "price":       "DollarSign",
        "performance": "Target",
        "duration":    "Clock",
        "quantity":    "Package",
    }
    return icon_map.get(cat, "BarChart3")


def _build_subtitle(profile: ColumnProfile, n_rows: int, time_col: Optional[str],
                    domain: Optional[str]) -> str:
    agg_word = {
        "sum": "Sum", "mean": "Average", "median": "Median",
        "max": "Peak", "min": "Floor",
    }.get(profile.aggregation, profile.aggregation.title())
    domain_part = f" · {domain.replace('_', ' ').title()}" if domain and domain != "general" else ""
    return f"{agg_word} across {n_rows:,} records{domain_part}"


# ── LLM Enrichment ────────────────────────────────────────────────────────────

async def _enrich_with_llm(
    candidates: List[ColumnProfile],
    domain: Optional[str],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Single LLM call for all selected KPIs.
    Returns: {col_name: {insight_sentence, action_prompt}, archetype, dashboard_story}
    """
    from services.llm.router import llm_router

    domain_intel = metadata.get("domain_intelligence", {})
    raw_stat_findings = metadata.get("statistical_findings", {})
    stat_findings = raw_stat_findings if isinstance(raw_stat_findings, dict) else {}

    kpi_lines = []
    for i, p in enumerate(candidates):
        val = p.primary_value or 0
        kpi_lines.append(
            f"  {i+1}. {p.name} | role={p.role.value} | agg={p.aggregation} "
            f"| value={val:,.2f} | polarity={p.polarity} | category={p.business_category}"
        )

    top_corr = (stat_findings.get("correlations") or [])[:3]
    corr_lines = [
        f"  {c.get('column_a','?')} ↔ {c.get('column_b','?')}: r={c.get('correlation', 0):.2f}"
        for c in top_corr
    ]

    prompt = f"""You are a senior data analyst writing KPI card narratives for an executive dashboard.

DATASET DOMAIN: {domain or 'general'}
KEY METRICS SELECTED:
{chr(10).join(kpi_lines)}

TOP CORRELATIONS:
{chr(10).join(corr_lines) or '  None'}

DOMAIN CONTEXT:
  key_metrics: {domain_intel.get('key_metrics', [])[:5]}
  dimensions:  {domain_intel.get('dimensions', [])[:5]}

For EACH metric, write:
  1. insight_sentence: ONE sentence (max 30 words), plain English, with at least one number.
     Must explain WHY or WHAT the metric means for this specific domain.
     Never start with "This KPI" or "This card". State the signal directly.
  2. action_prompt: ONE specific follow-up question ending with "?".
     Must reference a specific column or pattern visible in the data.

Also write:
  3. archetype: The dataset domain in 2-3 words (e.g. "automotive_fleet", "ecommerce", "hr_analytics")
  4. dashboard_story: 2-sentence CEO-level summary of what this dataset reveals.

Respond with ONLY valid JSON (no markdown):
{{
  "archetype": "...",
  "dashboard_story": "...",
  "kpi_narratives": {{
    "column_name_1": {{"insight_sentence": "...", "action_prompt": "...?"}},
    "column_name_2": {{"insight_sentence": "...", "action_prompt": "...?"}}
  }}
}}"""

    try:
        result = await llm_router.call(
            prompt=prompt,
            model_role="insight_generation",
            expect_json=True,
            temperature=0.3,
            max_tokens=1024,
        )
        if isinstance(result, dict):
            return result
    except Exception as e:
        logger.warning(f"[KPI] LLM enrichment failed: {e}")

    return {"archetype": domain or "general", "dashboard_story": "", "kpi_narratives": {}}


# ── Main Generator ────────────────────────────────────────────────────────────

class IntelligentKPIGenerator:
    """
    Production KPI generator. Thinks like a data scientist.
    Output format maps 1:1 to EnterpriseKpiCard props.
    """

    async def generate_intelligent_kpis(
        self,
        df: pl.DataFrame,
        domain: Optional[str] = None,
        max_kpis: int = 4,
        dataset_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        metadata = dataset_metadata or {}
        domain = domain or metadata.get("domain_intelligence", {}).get("domain", "general")

        # ── 1. Profile all columns ───────────────────────────────────────────
        profiles: List[ColumnProfile] = []
        for col in df.columns:
            p = _profile_column(df, col)
            if p is not None:
                profiles.append(p)

        if not profiles:
            logger.warning("[KPI] No column profiles built — empty dataset?")
            return []

        # ── 2. Select candidates via the gate ────────────────────────────────
        candidates = _select_candidates(profiles, max_kpis)

        if not candidates:
            logger.warning("[KPI] No candidates passed the KPI gate")
            return self._domain_aware_fallback(df, profiles, domain, max_kpis, metadata)

        # ── 3. Find time column for comparisons + sparklines ─────────────────
        time_col = _find_time_column(df)

        # ── 4. LLM enrichment (single call for all KPIs) ─────────────────────
        llm_data = await _enrich_with_llm(candidates, domain, metadata)
        narratives   = llm_data.get("kpi_narratives", {})
        archetype    = llm_data.get("archetype", domain or "general")
        dash_story   = llm_data.get("dashboard_story", "")

        # ── 5. Build final KPI card dicts ────────────────────────────────────
        kpis: List[Dict[str, Any]] = []
        for profile in candidates:
            try:
                value      = _compute_kpi_value(df, profile)
                comparison = _compute_comparison(df, profile, time_col)
                sparkline  = _compute_sparkline(df, profile, time_col)
                fmt        = _infer_format(profile, value)
                icon       = _infer_icon(profile)
                subtitle   = _build_subtitle(profile, len(df), time_col, domain)

                narrative   = narratives.get(profile.name, {})
                insight     = narrative.get("insight_sentence", "")
                action      = narrative.get("action_prompt", "")

                delta_dir   = comparison["delta_direction"] if comparison else None
                accent      = _compute_accent_color(profile.importance, delta_dir, profile.polarity)

                # Benchmark: p75 as aspirational reference
                bench_val   = profile.col_p75
                bench_label = "Top 25%" if bench_val else None

                kpi = {
                    # Identity
                    "type":            "kpi",
                    "column":          profile.name,
                    "aggregation":     profile.aggregation,
                    "importance":      profile.importance,
                    "business_category": profile.business_category,

                    # Display
                    "title":           _humanize_title(profile),
                    "subtitle":        subtitle,
                    "value":           value,
                    "format":          fmt,
                    "icon":            icon,
                    "record_count":    len(df) - profile.n_nulls,

                    # Comparison
                    "comparison_value": comparison["comparison_value"] if comparison else None,
                    "comparison_label": comparison["comparison_label"] if comparison else None,
                    "delta_percent":    comparison["delta_percent"]    if comparison else None,
                    "delta_direction":  comparison["delta_direction"]  if comparison else None,
                    "is_delta_positive": comparison["is_delta_positive"] if comparison else (profile.polarity == "higher_is_better"),

                    # Accent / color
                    "accent_color":    accent,

                    # Sparkline
                    "sparkline_data":  sparkline,

                    # Benchmark
                    "benchmark_value": round(bench_val, 2) if bench_val else None,
                    "benchmark_label": bench_label,
                    "benchmark_text":  f"{bench_label}: {_fmt_val(bench_val, fmt)}" if bench_val and bench_label else None,

                    # Narrative (LLM)
                    "ai_suggestion":   insight,
                    "action_prompt":   action,
                    "dashboard_story": dash_story if profile.importance == "hero" else "",
                    "archetype":       archetype,

                    # Extra stats for advanced cards
                    "col_p75":         profile.col_p75,
                    "col_median":      profile.col_median,
                    "polarity":        profile.polarity,
                }
                kpis.append(kpi)
            except Exception as e:
                logger.error(f"[KPI] Failed to build card for '{profile.name}': {e}")

        logger.info(f"[KPI] Generated {len(kpis)} cards for archetype='{archetype}'")
        return kpis

    # ── Fallback ─────────────────────────────────────────────────────────────

    def _domain_aware_fallback(
        self, df: pl.DataFrame, profiles: List[ColumnProfile],
        domain: str, max_kpis: int, metadata: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Last-resort: pick top numeric columns by absolute value."""
        logger.info("[KPI] Using domain-aware fallback")
        numeric = [
            p for p in profiles
            if p.role in (ColumnRole.MEASURE, ColumnRole.COUNT, ColumnRole.RATE)
            and p.null_pct < 50
            and p.primary_value is not None
        ]
        if not numeric:
            return []

        # Sort by absolute value descending
        numeric.sort(key=lambda p: abs(p.primary_value or 0), reverse=True)
        top = numeric[:max_kpis]
        top[0].importance = "hero"
        for p in top[1:]:
            p.importance = "high"

        time_col = _find_time_column(df)
        kpis = []
        for p in top:
            try:
                value      = _compute_kpi_value(df, p)
                comparison = _compute_comparison(df, p, time_col)
                sparkline  = _compute_sparkline(df, p, time_col)
                fmt        = _infer_format(p, value)
                delta_dir  = comparison["delta_direction"] if comparison else None
                accent     = _compute_accent_color(p.importance, delta_dir, p.polarity)

                kpis.append({
                    "type":            "kpi",
                    "column":          p.name,
                    "aggregation":     p.aggregation,
                    "importance":      p.importance,
                    "title":           _humanize_title(p),
                    "subtitle":        _build_subtitle(p, len(df), time_col, domain),
                    "value":           value,
                    "format":          fmt,
                    "icon":            _infer_icon(p),
                    "record_count":    len(df) - p.n_nulls,
                    "comparison_value": comparison["comparison_value"] if comparison else None,
                    "comparison_label": comparison["comparison_label"] if comparison else None,
                    "delta_percent":   comparison["delta_percent"] if comparison else None,
                    "delta_direction": comparison["delta_direction"] if comparison else None,
                    "is_delta_positive": p.polarity == "higher_is_better",
                    "accent_color":    accent,
                    "sparkline_data":  sparkline,
                    "ai_suggestion":   "",
                    "action_prompt":   "",
                })
            except Exception:
                continue
        return kpis


# ── Helpers ───────────────────────────────────────────────────────────────────

_AGG_PREFIX = {
    "sum":    "Total",
    "mean":   "Average",
    "median": "Median",
    "max":    "Peak",
    "min":    "Lowest",
    "count":  "Count of",
}


def _humanize_title(profile: ColumnProfile) -> str:
    name = profile.name.replace("_", " ").replace("-", " ").strip().title()
    prefix = _AGG_PREFIX.get(profile.aggregation, "")
    if prefix:
        # Avoid double prefix ("Total Total Revenue")
        if name.lower().startswith(prefix.lower()):
            return name
        return f"{prefix} {name}"
    return name


def _fmt_val(val: Optional[float], fmt: str) -> str:
    if val is None:
        return "N/A"
    if fmt == "currency":
        if abs(val) >= 1e9: return f"${val/1e9:.1f}B"
        if abs(val) >= 1e6: return f"${val/1e6:.1f}M"
        if abs(val) >= 1e3: return f"${val/1e3:.1f}K"
        return f"${val:,.0f}"
    if fmt == "percentage":
        return f"{val:.1f}%"
    if abs(val) >= 1e6: return f"{val/1e6:.1f}M"
    if abs(val) >= 1e3: return f"{val/1e3:.1f}K"
    return f"{val:,.1f}"


# Singleton
intelligent_kpi_generator = IntelligentKPIGenerator()

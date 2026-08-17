"""
semantic_types — Flint-inspired semantic typing + auto-layout for charts
=========================================================================

Absorbs the design philosophy of Microsoft's Flint visualization language
into our Python chart pipeline:

  1. **Semantic types** — instead of the LLM writing raw Plotly tickformat /
     prefix / suffix strings, we infer what a column *is* (currency,
     percentage, date, duration, rank, ...) from its name, dtype and sample
     values. The renderer owns all presentation details.
  2. **Auto-layout** — a deterministic pass that turns semantic types into
     professional axis configuration: labeled axes, formatted ticks,
     zero baselines for bars, sensible label rotation, and readable tick
     density — with zero extra LLM tokens.

The AI may still *declare* semantic types in `chart_config["semantic_types"]`
(they win over inference). Everything else is inferred at render time.
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any, Dict, List, Optional

import polars as pl

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# SEMANTIC TYPE ENUM
# ═══════════════════════════════════════════════════════════════════════

class SemanticType(str, Enum):
    CURRENCY = "currency"
    PERCENTAGE = "percentage"        # values are 0–100
    RATIO = "ratio"                  # values are 0–1 fractions
    TEMPERATURE = "temperature"
    DURATION = "duration"            # ms / seconds
    DATE = "date"
    DATETIME = "datetime"
    YEAR_MONTH = "year_month"
    RANK = "rank"
    SCORE = "score"
    QUANTITY = "quantity"            # generic counts / units
    IDENTIFIER = "identifier"
    DIMENSION = "dimension"          # low-cardinality categorical
    BOOLEAN = "boolean"
    NUMBER = "number"                # generic numeric fallback
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════════════
# NAME-BASED KEYWORD BANKS
# ═══════════════════════════════════════════════════════════════════════

_CURRENCY_TERMS = re.compile(
    r"\b(price|pricing|cost|revenue|income|sales|amount|salary|wage|profit|"
    r"margin_amount|fee|budget|spend|spending|expense|expenditure|balance|"
    r"payment|refund|deposit|withdrawal|revenue_growth|arpa|arr|mrr|"
    r"cac|ltv|lifetime_value|deal_size|invoice|subscription)\b",
    re.I,
)
_PERCENTAGE_TERMS = re.compile(
    r"\b(percent|percentage|pct|rate|ratio|margin_rate|growth_rate|conversion|"
    r"efficiency|occupancy|utilization|share|yield|return_rate|ctr|cvr|roas|"
    r"interest_rate|tax_rate|discount_rate|churn_rate)\b",
    re.I,
)
_RATIO_TERMS = re.compile(
    r"\b(ratio|fraction|coefficient|correlation|index_value|beta)\b",
    re.I,
)
_TEMP_TERMS = re.compile(r"\b(temp|temperature|temp_c|temp_f|celsius|fahrenheit)\b", re.I)
_DURATION_TERMS = re.compile(
    r"\b(duration|latency|response|processing|time|seconds|minutes|hours|ms|"
    r"ttfb|ttft|wait|hold|dwell)\b",
    re.I,
)
_RANK_TERMS = re.compile(
    r"\b(rank|ranking|position|place|percentile|tier|quartile|decile)\b",
    re.I,
)
_SCORE_TERMS = re.compile(
    r"\b(score|rating|grade|points|kpi_score|nps|csat|health_score|quality_score)\b",
    re.I,
)
_QUANTITY_TERMS = re.compile(
    r"\b(count|qty|quantity|units|volume|total|number_of|num_|headcount|"
    r"frequency|occurrences|visits|sessions|orders|units_sold|requests)\b",
    re.I,
)
_IDENTIFIER_TERMS = re.compile(
    r"^(id|uuid|guid|hash|token|code|sku|key|pk|row_id|record_id)$|"
    r"(_id|_key|_uuid|_guid|_code|_sku|_hash|_token)$",
    re.I,
)
_DATE_NAME_TERMS = re.compile(
    r"\b(date|day|month|year|quarter|week|fiscal|period|time)\b",
    re.I,
)

# Value-based signals
_CURRENCY_SYMBOL = re.compile(r"^[\$€£¥₹]\s?|[\$€£¥₹]\s?$")
_PERCENT_SUFFIX = re.compile(r"%$")
_DATE_ISO = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")
_YEAR_ONLY = re.compile(r"^\d{4}$")


# ═══════════════════════════════════════════════════════════════════════
# DTYPE HELPERS
# ═══════════════════════════════════════════════════════════════════════

# Numeric dtype names as stringified by Polars 1.x. Both the class form
# (pl.Float64) and the instance form (df[col].dtype) stringify to "Float64",
# so string comparison is robust across Polars versions.
_NUMERIC_DTYPE_NAMES = {
    "Float16", "Float32", "Float64",
    "Int8", "Int16", "Int32", "Int64", "Int128",
    "UInt8", "UInt16", "UInt32", "UInt64", "UInt128",
    "Decimal",
}


def _is_numeric_dtype(dtype: Any) -> bool:
    """
    True if `dtype` is a numeric Polars dtype.

    Accepts both the class form (`pl.Float64`) used in tests and the
    instance form (`df[col].dtype`) used at render time.
    """
    return str(dtype) in _NUMERIC_DTYPE_NAMES


# ═══════════════════════════════════════════════════════════════════════
# INFERENCE
# ═══════════════════════════════════════════════════════════════════════

def _sample_is_currency(sample: List[Any]) -> bool:
    """True if the majority of sample strings carry a currency symbol."""
    if not sample:
        return False
    hits = 0
    checked = 0
    for v in sample:
        if isinstance(v, str):
            checked += 1
            if _CURRENCY_SYMBOL.search(v):
                hits += 1
    return checked > 0 and hits / checked >= 0.6


def _sample_is_percent(sample: List[Any]) -> bool:
    if not sample:
        return False
    hits = 0
    checked = 0
    for v in sample:
        if isinstance(v, str) and _PERCENT_SUFFIX.search(v):
            checked += 1
            hits += 1
    return checked > 0 and hits / checked >= 0.6


def _sample_is_fraction(sample: List[Any]) -> bool:
    """Numeric values all within [0, 1] — likely a ratio."""
    vals = [float(v) for v in sample if isinstance(v, (int, float))]
    if not vals or len(vals) < 3:
        return False
    return all(0.0 <= v <= 1.0 for v in vals)


def infer_column_semantic_type(
    col_name: str,
    dtype: Any,
    sample_values: Optional[List[Any]] = None,
    cardinality: Optional[int] = None,
    row_count: Optional[int] = None,
) -> SemanticType:
    """
    Infer the semantic type of a single column.

    Priority:
      1. Explicit dtype signals (temporal, boolean)
      2. Value-based signals (currency symbol, % suffix, fraction range)
      3. Name-based keyword banks
      4. Structural fallbacks (identifier vs dimension vs quantity)

    Args:
        col_name: Exact column name (used for keyword matching)
        dtype: Polars dtype
        sample_values: Optional sample of raw values (strings or numbers)
        cardinality: Optional unique-value count
        row_count: Optional total row count

    Returns:
        SemanticType value
    """
    raw_name = (col_name or "").strip().lower()
    # Underscores/hyphens separate words in column names ("total_revenue" →
    # "total revenue") so that `\bword\b` keyword banks actually match.
    name = re.sub(r"[\s_\-/]+", " ", raw_name)
    sample = list(sample_values or [])

    # ── 1. dtype signals ──────────────────────────────────────────────
    dtype_str = str(dtype)
    is_numeric = _is_numeric_dtype(dtype)
    if dtype_str == "Date":
        return SemanticType.DATE
    if "datetime" in dtype_str.lower():
        return SemanticType.DATETIME
    if dtype_str == "Duration":
        return SemanticType.DURATION
    if "bool" in dtype_str.lower():
        return SemanticType.BOOLEAN

    # ── 2. value signals ──────────────────────────────────────────────
    # String columns that hold ISO dates (e.g. "2024-01-15" as text)
    if (
        not is_numeric
        and sample
        and _DATE_NAME_TERMS.search(name)
        and any(isinstance(v, str) and _DATE_ISO.match(v.strip()) for v in sample[:3])
    ):
        # Prefer DATETIME when samples carry a time component ("2024-01-15T10:30:00")
        if any(isinstance(v, str) and len(v.strip()) > 10 for v in sample[:3]):
            return SemanticType.DATETIME
        return SemanticType.DATE
    if not is_numeric and _sample_is_currency(sample):
        return SemanticType.CURRENCY
    if _sample_is_percent(sample):
        return SemanticType.PERCENTAGE

    # ── 3. name signals ───────────────────────────────────────────────
    # Numeric-format types (currency, %, duration, ...) require a numeric
    # dtype — a categorical string named "price" (low/mid/high) must NOT
    # become CURRENCY and get its counts formatted as "$1.2K".
    if is_numeric and _CURRENCY_TERMS.search(name):
        return SemanticType.CURRENCY
    if is_numeric and _TEMP_TERMS.search(name):
        return SemanticType.TEMPERATURE
    if is_numeric and _DURATION_TERMS.search(name):
        return SemanticType.DURATION
    if is_numeric and _RANK_TERMS.search(name):
        return SemanticType.RANK
    if is_numeric and _SCORE_TERMS.search(name):
        return SemanticType.SCORE
    if is_numeric and (_PERCENTAGE_TERMS.search(name) or _RATIO_TERMS.search(name)):
        if _sample_is_fraction(sample):
            return SemanticType.RATIO
        return SemanticType.PERCENTAGE
    if is_numeric and _QUANTITY_TERMS.search(name):
        return SemanticType.QUANTITY

    # Year-only numeric columns (2012, 2023) → date-ish
    if is_numeric and sample and all(
        isinstance(v, (int, float)) and _YEAR_ONLY.match(str(int(v))) for v in sample[:5]
    ):
        return SemanticType.YEAR_MONTH

    # ── 4. structural fallbacks ───────────────────────────────────────
    # Identifier detection needs the raw (un-normalized) name for suffix
    # matching like "_id" / "_key".
    if _IDENTIFIER_TERMS.search(raw_name):
        return SemanticType.IDENTIFIER

    if is_numeric:
        return SemanticType.NUMBER

    # String fallback
    if cardinality is not None and row_count:
        ratio = cardinality / max(row_count, 1)
        if ratio < 0.5:
            return SemanticType.DIMENSION
    return SemanticType.DIMENSION


def infer_semantic_types(
    df: pl.DataFrame,
    chart_config: Dict[str, Any],
) -> Dict[str, SemanticType]:
    """
    Infer semantic types for every column referenced by a chart config.

    Explicit `chart_config["semantic_types"]` (AI-provided) always win.
    Otherwise infer from the DataFrame's dtypes + samples + cardinality.

    Args:
        df: Polars DataFrame
        chart_config: Chart config dict

    Returns:
        Mapping of column name → SemanticType
    """
    overrides: Dict[str, str] = chart_config.get("semantic_types") or {}
    results: Dict[str, SemanticType] = {}

    # Columns of interest: all config columns plus group_by columns
    columns = list(chart_config.get("columns") or [])
    group_by = chart_config.get("group_by") or []
    if isinstance(group_by, str):
        group_by = [group_by]
    for g in group_by:
        if g not in columns:
            columns.append(g)
    # x / y / color short-form keys
    for k in ("x", "y", "color", "size", "labels", "values", "z"):
        v = chart_config.get(k)
        if isinstance(v, str) and v not in columns:
            columns.append(v)
        elif isinstance(v, list):
            columns.extend(c for c in v if isinstance(c, str) and c not in columns)

    for col in columns:
        if not isinstance(col, str) or col not in df.columns:
            continue
        # AI-declared override wins
        if col in overrides and isinstance(overrides[col], str):
            try:
                results[col] = SemanticType(overrides[col])
                continue
            except ValueError:
                pass
        dtype = df[col].dtype
        try:
            sample = df[col].drop_nulls().head(5).to_list()
        except Exception:
            sample = []
        cardinality = df[col].n_unique()
        results[col] = infer_column_semantic_type(
            col_name=col,
            dtype=dtype,
            sample_values=sample,
            cardinality=cardinality,
            row_count=len(df),
        )
    return results


# ═══════════════════════════════════════════════════════════════════════
# FORMAT SPECS (Plotly layout hints)
# ═══════════════════════════════════════════════════════════════════════

def format_spec_for(st: SemanticType) -> Dict[str, Any]:
    """
    Return Plotly-friendly axis formatting hints for a semantic type.

    Keys follow Plotly axis conventions so they can be merged straight
    into `layout.yaxis` / `layout.xaxis`:
      - tickformat (d3-format string)
      - tickprefix / ticksuffix
      - tickmode (density hint)

    Examples:
        CURRENCY → {"tickprefix": "$", "tickformat": ",.2s"}
        PERCENTAGE → {"ticksuffix": "%", "tickformat": ",.1f"}
        DATE → {"tickformat": "%b %Y", "tickmode": "auto"}
    """
    if st == SemanticType.CURRENCY:
        return {"tickprefix": "$", "tickformat": ",.2s", "tickmode": "auto"}
    if st == SemanticType.PERCENTAGE:
        return {"ticksuffix": "%", "tickformat": ",.1f", "tickmode": "auto"}
    if st == SemanticType.RATIO:
        return {"tickformat": ".2f", "tickmode": "auto"}
    if st == SemanticType.TEMPERATURE:
        return {"ticksuffix": "°", "tickformat": ",.0f", "tickmode": "auto"}
    if st == SemanticType.DURATION:
        # ms durations — human-readable compact ticks
        return {"tickformat": "~s", "ticksuffix": "s", "tickmode": "auto"}
    if st in (SemanticType.DATE, SemanticType.DATETIME):
        return {"tickformat": "%b %Y", "tickmode": "auto", "type": "date"}
    if st == SemanticType.YEAR_MONTH:
        return {"tickformat": "d", "tickmode": "auto"}
    if st == SemanticType.RANK:
        return {"tickformat": "d", "tickmode": "auto"}
    if st == SemanticType.SCORE:
        return {"tickformat": ",.1f", "tickmode": "auto"}
    if st == SemanticType.QUANTITY:
        return {"tickformat": "~s", "tickmode": "auto"}
    if st == SemanticType.NUMBER:
        return {"tickformat": "~s", "tickmode": "auto"}
    return {}


# ═══════════════════════════════════════════════════════════════════════
# AUTO-LAYOUT PASS
# ═══════════════════════════════════════════════════════════════════════

BAR_LIKE_TYPES = {"bar", "grouped_bar", "stacked_bar", "histogram", "waterfall"}


def _clean_title(text: str) -> str:
    """Humanize a column name for use as an axis title."""
    text = (text or "").replace("_", " ").replace("-", " ").strip()
    return " ".join(w.capitalize() for w in text.split())


def apply_auto_layout(
    layout: Dict[str, Any],
    semantic_types: Dict[str, SemanticType],
    chart_config: Dict[str, Any],
    traces: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Apply Flint-style auto-layout based on inferred semantic types.

    Mutates and returns `layout`. Best-effort: every rule is guarded so a
    failure can never break chart rendering.

    Rules applied:
      1. Axis titles from x/y column names (Flint: always label axes)
      2. y-axis tickformat/tickprefix/ticksuffix from y semantic type
      3. x-axis date/datetime → Plotly date axis with friendly format
      4. Zero baseline for bar-like charts (Flint: bars start at zero)
      5. Label rotation + tick density for dense categorical x-axes
      6. Axis metadata attached to traces for the frontend ECharts adapter
    """
    try:
        columns = chart_config.get("columns") or []
        x_col = columns[0] if columns else chart_config.get("x")
        # Prefer the second explicit column; fall back to the `y` key when
        # the config provides it (covers one-column lists + x/y keyed configs)
        y_col = columns[1] if len(columns) > 1 else chart_config.get("y")
        chart_type = str(chart_config.get("chart_type", "")).lower()

        xaxis = layout.setdefault("xaxis", {})
        yaxis = layout.setdefault("yaxis", {})

        # ── 1. Axis titles ────────────────────────────────────────────
        if x_col and not xaxis.get("title", {}).get("text"):
            xaxis["title"] = {"text": _clean_title(x_col)}
        if y_col and not yaxis.get("title", {}).get("text"):
            yaxis["title"] = {"text": _clean_title(y_col)}

        # ── 2. y-axis formatting ──────────────────────────────────────
        if y_col and y_col in semantic_types:
            spec = format_spec_for(semantic_types[y_col])
            for k, v in spec.items():
                yaxis.setdefault(k, v)

        # ── 3. x-axis temporal handling ───────────────────────────────
        x_st = semantic_types.get(x_col) if x_col else None
        if x_st in (SemanticType.DATE, SemanticType.DATETIME):
            xaxis.setdefault("type", "date")
            xaxis.setdefault("tickformat", "%b %Y")
            xaxis.setdefault("tickmode", "auto")
        elif x_st == SemanticType.YEAR_MONTH:
            xaxis.setdefault("tickformat", "d")
            xaxis.setdefault("tickmode", "auto")
        elif x_col and x_st == SemanticType.NUMBER:
            # Numeric x-axis (e.g. age, bin) — keep compact ticks
            xaxis.setdefault("tickformat", "~s")

        # ── 4. Zero baseline for bars (Flint principle) ───────────────
        if chart_type in BAR_LIKE_TYPES:
            # Only when the payload hasn't already computed a zoomed range
            if "range" not in yaxis:
                yaxis.setdefault("rangemode", "tozero")

        # ── 5. Categorical density handling ───────────────────────────
        if x_col and x_st in (None, SemanticType.DIMENSION, SemanticType.UNKNOWN):
            x_categories = None
            for t in traces:
                if t.get("x") and isinstance(t["x"], list):
                    x_categories = t["x"]
                    break
            if x_categories:
                n_cats = len(x_categories)
                max_len = max((len(str(c)) for c in x_categories), default=0)
                if n_cats > 8 or max_len > 14:
                    xaxis.setdefault("tickangle", -35)
                    xaxis.setdefault("automargin", True)
                if n_cats > 12:
                    # Keep readable: show a sensible subset
                    xaxis.setdefault("nticks", min(12, n_cats))
                    xaxis.setdefault("tickmode", "auto")

        # ── 6. Attach semantic metadata to traces ─────────────────────
        for t in traces:
            meta = t.setdefault("_axis_metadata", {})
            if y_col and y_col in semantic_types:
                meta.setdefault("y", {})["semantic_type"] = semantic_types[y_col].value
            if x_col and x_col in semantic_types:
                meta.setdefault("x", {})["semantic_type"] = semantic_types[x_col].value

    except Exception as e:  # noqa: BLE001 — auto-layout must never break render
        logger.warning(f"Auto-layout pass failed (non-fatal): {e}")

    return layout


__all__ = [
    "SemanticType",
    "infer_column_semantic_type",
    "infer_semantic_types",
    "format_spec_for",
    "apply_auto_layout",
]

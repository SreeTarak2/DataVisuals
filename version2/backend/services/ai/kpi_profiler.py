"""
KPI Profiler
============
Column profiling, role classification, and string coercion.
Extracted from intelligent_kpi_generator.py.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from .kpi_types import (
    _CATEGORY_PATTERNS,
    _COUNT_RE,
    _DATE_FORMATS,
    _ID_RE,
    _INTEGER_DTYPES,
    _NUMERIC_DTYPES,
    _RATE_RE,
    _TIME_RE,
    ColumnProfile,
    ColumnRole,
)

logger = logging.getLogger(__name__)


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


def _coerce_string_columns(df: pl.DataFrame) -> pl.DataFrame:
    for col in df.columns:
        if df[col].dtype != pl.Utf8:
            continue

        clean = df[col].drop_nulls()
        if len(clean) < 5:
            continue

        # Try numeric first
        stripped = clean.str.strip_chars()
        cleaned_str = stripped.str.replace_all(r"[$, ]", "", literal=False)
        parsed_num = cleaned_str.cast(pl.Float64, strict=False)
        valid_ratio = parsed_num.is_not_null().sum() / len(clean)

        if valid_ratio > 0.80:
            full_stripped = df[col].str.strip_chars()
            full_cleaned = full_stripped.str.replace_all(r"[$, ]", "", literal=False)
            df = df.with_columns(full_cleaned.cast(pl.Float64).alias(col))
            logger.info(f"[KPI] Coerced string column '{col}' to Float64 ({valid_ratio:.0%} parse rate)")
            continue

        # Try date parsing
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
    norm = name.lower().replace("_", " ").replace("-", " ")

    if is_datetime or _TIME_RE.search(norm):
        return ColumnRole.TIME

    if _ID_RE.search(norm):
        if not is_numeric or (n_unique / max(n_rows, 1)) > 0.5:
            return ColumnRole.IDENTITY

    if not is_numeric:
        if n_unique / max(n_rows, 1) > 0.5:
            return ColumnRole.IDENTITY
        return ColumnRole.DIMENSION

    is_b01 = numeric_stats.get("is_bounded_01", False)
    col_min = numeric_stats.get("col_min", 0)
    col_max = numeric_stats.get("col_max", 0)

    if is_b01 or _RATE_RE.search(norm):
        if col_max <= 100 and col_min >= 0 and _RATE_RE.search(norm):
            return ColumnRole.RATE
        if is_b01:
            return ColumnRole.RATE

    if _COUNT_RE.search(norm) and numeric_stats.get("is_integer_valued", False):
        return ColumnRole.COUNT

    if n_rows >= 50 and n_unique <= 10 and (n_unique / n_rows) < 0.05:
        return ColumnRole.DIMENSION

    return ColumnRole.MEASURE


def get_business_category(name: str) -> Tuple[str, str]:
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

        category, polarity = get_business_category(col_name)

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

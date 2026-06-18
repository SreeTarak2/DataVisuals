"""
profiling/column_profiler.py — Per-column statistical profiler (Layer 1)

Computes:
  - Data type inference
  - Cardinality / uniqueness
  - Numeric statistics (min, max, mean, median, p25/p75/p90, std, skew, CV)
  - Pattern detection (email, phone, UUID, ZIP, URL, IP, SSN, credit card)
  - Value distribution (top N values with counts)
  - String coercion (parse numeric strings with $/commas, date strings)

Zero interpretation. Zero LLM calls. Pure Polars.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import polars as pl

from .models import (
    ColumnStats,
    CardinalityInfo,
    PatternMatch,
    ValueCount,
    ColumnQualityInfo,
    RawColumnProfile,
)

logger = logging.getLogger(__name__)


# ── Numeric Dtype Constants ───────────────────────────────────────────────────

_NUMERIC_DTYPES: tuple = (
    pl.Float32, pl.Float64,
    pl.Int8, pl.Int16, pl.Int32, pl.Int64,
    pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
)


# ── Pattern Detection ─────────────────────────────────────────────────────────

_PATTERNS: dict[str, str] = {
    "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    "phone": r'^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}$',
    "url": r"^https?://[^\s]+$",
    "zip_code": r"^\d{5}(-\d{4})?$",
    "uuid": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    "ip_address": r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$",
    "credit_card": r"^\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}$",
    "ssn": r"^\d{3}-\d{2}-\d{4}$",
}


# ── Date Format Set ───────────────────────────────────────────────────────────

_DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y",
    "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
    "%d-%m-%Y", "%m-%d-%Y", "%d/%m/%y",
    "%Y%m%d", "%b %d, %Y", "%d %b %Y", "%B %d, %Y", "%d %B %Y",
]


class ColumnProfiler:
    """Profiles a single column or an entire DataFrame — pure facts only."""

    # ── Numeric Profiling ─────────────────────────────────────────────────

    def _profile_numeric(self, col: pl.Series) -> ColumnStats:
        """Compute full numeric statistics for a column."""
        clean = col.drop_nulls().cast(pl.Float64)
        n = len(clean)
        if n == 0:
            return ColumnStats()

        mean = float(clean.mean())
        std = float(clean.std()) if n > 1 else 0.0
        mn = float(clean.min())
        mx = float(clean.max())
        cv = abs(std / mean) if mean != 0 else 0.0
        skew = float(clean.skew()) if n >= 3 else 0.0

        sample = clean.sample(min(1000, n), seed=42).to_list()

        return ColumnStats(
            col_sum=round(float(clean.sum()), 4),
            col_mean=round(mean, 4),
            col_median=round(float(clean.median()), 4),
            col_std=round(std, 4),
            col_min=round(mn, 4),
            col_max=round(mx, 4),
            col_p25=round(float(clean.quantile(0.25)), 4),
            col_p75=round(float(clean.quantile(0.75)), 4),
            col_p90=round(float(clean.quantile(0.90)), 4),
            cv=round(cv, 4),
            skewness=round(skew, 4),
            is_bounded_01=(mn >= 0 and mx <= 1),
            is_integer_valued=all(v == int(v) for v in sample),
        )

    # ── Cardinality ───────────────────────────────────────────────────────

    def _compute_cardinality(
        self, col_data: pl.Series, total_count: int
    ) -> CardinalityInfo:
        """Compute cardinality info for a column."""
        unique_count = col_data.n_unique()
        null_count = col_data.null_count()
        non_null = max(total_count - null_count, 1)
        cardinality_ratio = unique_count / non_null

        if cardinality_ratio >= 0.95:
            level = "very_high"
        elif cardinality_ratio >= 0.5:
            level = "high"
        elif cardinality_ratio >= 0.1:
            level = "medium"
        else:
            level = "low"

        return CardinalityInfo(
            unique_count=unique_count,
            total_count=total_count,
            null_count=null_count,
            cardinality_ratio=round(cardinality_ratio, 4),
            cardinality_level=level,
        )

    # ── Pattern Detection ─────────────────────────────────────────────────

    def _detect_patterns(self, col_data: pl.Series) -> list[PatternMatch]:
        """Detect common data patterns (email, phone, URL, etc.)."""
        sample = col_data.drop_nulls().head(100).to_list()
        if not sample:
            return []

        detected: list[PatternMatch] = []
        for pattern_name, pattern_regex in _PATTERNS.items():
            matches = sum(
                1 for v in sample
                if isinstance(v, str) and re.match(pattern_regex, v.strip(), re.IGNORECASE)
            )
            match_ratio = matches / len(sample)
            if match_ratio >= 0.7:
                detected.append(PatternMatch(pattern=pattern_name, confidence=round(match_ratio, 2)))

        return detected

    # ── Value Distribution ────────────────────────────────────────────────

    def _compute_distribution(
        self, col_data: pl.Series, max_values: int = 10
    ) -> list[ValueCount]:
        """Compute top values with counts for low-cardinality columns."""
        if col_data.dtype not in (pl.Utf8, pl.Categorical, pl.Boolean) and col_data.n_unique() > 100:
            return []

        try:
            vc = col_data.drop_nulls().value_counts(name="_count", normalize=False)
            if "_count" not in vc.columns:
                return []
            sorted_vc = vc.sort("_count", descending=True).head(max_values)
            result = []
            for row in sorted_vc.iter_rows():
                val, cnt = row
                result.append(ValueCount(value=str(val), count=int(cnt)))
            return result
        except Exception:
            return []

    # ── Quality ───────────────────────────────────────────────────────────

    def _compute_quality(self, col_data: pl.Series) -> ColumnQualityInfo:
        """Compute quality metrics for a column."""
        total = len(col_data)
        null_count = col_data.null_count()
        completeness = (total - null_count) / max(total, 1)

        empty_count = 0
        if col_data.dtype in (pl.Utf8, pl.String):
            try:
                empty_count = int((col_data == "").sum() + (col_data == " ").sum())
            except Exception:
                pass

        effective = (total - null_count - empty_count) / max(total, 1)

        return ColumnQualityInfo(
            null_count=null_count,
            null_percentage=round((null_count / max(total, 1)) * 100, 2),
            empty_count=empty_count,
            completeness=round(completeness, 4),
            effective_completeness=round(effective, 4),
            quality_score=round(effective, 4),
        )

    # ── Single Column Profile ─────────────────────────────────────────────

    def profile_column(self, df: pl.DataFrame, col_name: str) -> Optional[RawColumnProfile]:
        """Profile a single column — pure facts, no interpretation.

        Returns None if profiling fails.
        """
        try:
            if col_name not in df.columns:
                return None

            col_data = df[col_name]
            n_rows = len(df)
            dtype_str = str(col_data.dtype)

            cardinality = self._compute_cardinality(col_data, n_rows)

            is_numeric = col_data.dtype in _NUMERIC_DTYPES
            stats = self._profile_numeric(col_data) if is_numeric else None

            sample = [
                str(v) for v in col_data.drop_nulls().head(5).to_list()
            ]

            patterns = self._detect_patterns(col_data)
            quality = self._compute_quality(col_data)
            distribution = self._compute_distribution(col_data)

            return RawColumnProfile(
                name=col_name,
                dtype=dtype_str,
                cardinality=cardinality,
                stats=stats,
                sample_values=sample,
                top_values=distribution,
                patterns=patterns,
                quality=quality,
            )

        except Exception as e:
            logger.debug(f"[Profiler] Column profiling failed for '{col_name}': {e}")
            return None

    # ── Full DataFrame Profile ────────────────────────────────────────────

    def profile_dataframe(self, df: pl.DataFrame) -> list[RawColumnProfile]:
        """Profile all columns in a DataFrame."""
        profiles: list[RawColumnProfile] = []
        for col_name in df.columns:
            p = self.profile_column(df, col_name)
            if p is not None:
                profiles.append(p)
        logger.info(
            f"[Profiler] Profiled {len(profiles)}/{len(df.columns)} columns"
        )
        return profiles


# Singleton
column_profiler = ColumnProfiler()

"""
profiling/engine.py — Profiling Engine Orchestrator (Layer 1)

Runs all profiling sub-engines in order and returns a single
RawProfilingResult containing only facts (no interpretation).

Steps:
  1. Optionally coerce string columns (parse $, commas, dates)
  2. Profile every column (stats, cardinality, patterns, distribution, quality)
  3. Compute dataset-level quality summary

Zero LLM calls. Zero interpretation. Pure Polars.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

import polars as pl

from .models import (
    DatasetInfo,
    RawColumnProfile,
    RawProfilingResult,
)
from .column_profiler import column_profiler, ColumnProfiler
from .quality_scorer import quality_scorer, QualityScorer

logger = logging.getLogger(__name__)


# ── String Coercion (parse numeric & date strings) ───────────────────────────

_DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y",
    "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
    "%d-%m-%Y", "%m-%d-%Y", "%d/%m/%y",
    "%Y%m%d", "%b %d, %Y", "%d %b %Y", "%B %d, %Y", "%d %B %Y",
]


def coerce_string_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Pre-processing: cast string columns to more specific types.

    1. Numeric detection: strings that look like numbers (with $/commas)
       are cast to Float64.
    2. Date detection: strings that look like dates are cast to Date.

    Only recasts if >80% of non-null values parse successfully.
    """
    for col in df.columns:
        if df[col].dtype != pl.Utf8:
            continue

        clean = df[col].drop_nulls()
        if len(clean) < 5:
            continue

        # ── Try numeric first ──
        stripped = clean.str.strip_chars()
        cleaned_str = stripped.str.replace_all(r"[$, ]", "", literal=False)
        parsed_num = cleaned_str.cast(pl.Float64, strict=False)
        valid_ratio = parsed_num.is_not_null().sum() / len(clean)

        if valid_ratio > 0.80:
            full_stripped = df[col].str.strip_chars()
            full_cleaned = full_stripped.str.replace_all(r"[$, ]", "", literal=False)
            df = df.with_columns(full_cleaned.cast(pl.Float64).alias(col))
            logger.info(f"[Profiler] Coerced '{col}' to Float64 ({valid_ratio:.0%} parse rate)")
            continue

        # ── Try date parsing ──
        for fmt in _DATE_FORMATS:
            try:
                parsed_date = clean.str.to_date(fmt, strict=False)
                valid_ratio = parsed_date.is_not_null().sum() / len(clean)
                if valid_ratio > 0.80:
                    df = df.with_columns(
                        df[col].str.to_date(fmt, strict=False).alias(col)
                    )
                    logger.info(f"[Profiler] Coerced '{col}' to Date (format={fmt}, {valid_ratio:.0%})")
                    break
            except Exception:
                continue

    return df


class ProfilingEngine:
    """Orchestrates all profiling sub-engines.

    Usage:
        result = await profiling_engine.run(df)
        # result is RawProfilingResult — pure facts, no interpretation
    """

    def __init__(
        self,
        column_profiler_impl: Optional[ColumnProfiler] = None,
        quality_scorer_impl: Optional[QualityScorer] = None,
        max_memory_mb: int = 500,
        max_safe_rows: int = 200000,
    ):
        self._column_profiler = column_profiler_impl or column_profiler
        self._quality_scorer = quality_scorer_impl or quality_scorer
        self.max_memory_mb = max_memory_mb
        self.max_safe_rows = max_safe_rows

    def _downsample_if_needed(
        self, df: pl.DataFrame
    ) -> pl.DataFrame:
        """Downsample large DataFrames to prevent OOM.

        Returns the original df if under the memory limit.
        """
        try:
            memory_mb = df.estimated_size() / (1024 * 1024)
        except Exception:
            return df

        if memory_mb <= self.max_memory_mb:
            return df

        rows = len(df)
        if rows <= self.max_safe_rows:
            return df

        logger.warning(
            f"[Profiler] DataFrame is {memory_mb:.0f}MB ({rows:,} rows) — "
            f"downsampling to {self.max_safe_rows:,} for OOM safety"
        )

        # Stratified sampling by first categorical column
        try:
            for col in df.columns:
                dtype = df[col].dtype
                if dtype in (pl.Utf8, pl.Categorical):
                    n_unique = df[col].n_unique()
                    if 2 <= n_unique <= min(100, rows // 10):
                        n_categories = n_unique
                        samples_per_cat = max(self.max_safe_rows // n_categories, 2)
                        sampled_frames = []
                        for category in df[col].unique().to_list():
                            group = df.filter(pl.col(col) == category)
                            n_to_sample = min(samples_per_cat, len(group))
                            if n_to_sample > 0:
                                sampled_frames.append(group.sample(n=n_to_sample, seed=42))
                        if sampled_frames:
                            sampled = pl.concat(sampled_frames)
                            if len(sampled) > self.max_safe_rows:
                                sampled = sampled.sample(n=self.max_safe_rows, seed=42)
                            return sampled
        except Exception:
            pass

        return df.sample(n=self.max_safe_rows, seed=42)

    def _compute_schema_hash(self, profiles: list[RawColumnProfile]) -> str:
        """Deterministic hash of column names + types."""
        raw = json.dumps([(c.name, c.dtype) for c in profiles])
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def run(self, df: pl.DataFrame, file_type: str = "unknown") -> RawProfilingResult:
        """Run all profiling engines and return a unified result.

        Args:
            df: Polars DataFrame to profile.
            file_type: Source file type ("csv", "xlsx", etc.).

        Returns:
            RawProfilingResult with all computed facts.
        """
        # ── 0. Memory guard ──
        df = self._downsample_if_needed(df)

        # ── 0b. String coercion ──
        df = coerce_string_columns(df)

        # ── 1. Profile all columns ──
        profiles = self._column_profiler.profile_dataframe(df)

        # ── 2. Build dataset info ──
        dataset = DatasetInfo(
            row_count=len(df),
            column_count=len(df.columns),
            file_type=file_type,
            schema_hash=self._compute_schema_hash(profiles),
        )

        # ── 3. Quality summary ──
        result = RawProfilingResult(
            dataset=dataset,
            columns=profiles,
        )
        quality = self._quality_scorer.score(result)

        return result


# Singleton
profiling_engine = ProfilingEngine()

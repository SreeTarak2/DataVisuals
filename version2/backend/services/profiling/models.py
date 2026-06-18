"""
profiling/models.py — Pure statistical column profile (Layer 1: Facts)

No semantic interpretation. No classification. No domain matching.
Every value here is a direct computation from the raw data.

This is consumed by:
  - intelligence/ (adds semantic meaning)
  - process.py (pipeline orchestrator)
  - Frontend API (raw data view)
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Numeric Statistics ────────────────────────────────────────────────────────


class ColumnStats(BaseModel):
    """Statistical moments for a numeric column. None for non-numeric."""

    col_sum: Optional[float] = None
    col_mean: Optional[float] = None
    col_median: Optional[float] = None
    col_std: Optional[float] = None
    col_min: Optional[float] = None
    col_max: Optional[float] = None
    col_p25: Optional[float] = None
    col_p75: Optional[float] = None
    col_p90: Optional[float] = None
    cv: Optional[float] = None          # Coefficient of variation = std/mean
    skewness: Optional[float] = None     # Skew (measure of asymmetry)
    is_bounded_01: bool = False          # All values in [0, 1]
    is_integer_valued: bool = False      # All values are integers


# ── Cardinality ───────────────────────────────────────────────────────────────


class CardinalityInfo(BaseModel):
    """Cardinality analysis for a column."""

    unique_count: int = 0
    total_count: int = 0
    null_count: int = 0
    cardinality_ratio: float = 0.0       # unique / max(non-null, 1)
    cardinality_level: str = "unknown"   # very_high | high | medium | low

    @property
    def null_pct(self) -> float:
        return (self.null_count / max(self.total_count, 1)) * 100


# ── Pattern Detection ─────────────────────────────────────────────────────────


class PatternMatch(BaseModel):
    """A detected data pattern (e.g. email, phone, UUID)."""

    pattern: str          # "email", "phone", "uuid", "ip_address", etc.
    confidence: float     # 0.0 - 1.0 ratio of values matching


class ValueCount(BaseModel):
    """A single value and its frequency in the column."""

    value: str
    count: int


# ── Column Quality ────────────────────────────────────────────────────────────


class ColumnQualityInfo(BaseModel):
    """Data quality metrics for a column."""

    null_count: int = 0
    null_percentage: float = 0.0
    empty_count: int = 0
    completeness: float = 0.0           # (non-null) / total
    effective_completeness: float = 0.0 # (non-null - empty) / total
    quality_score: float = 0.0          # Overall 0-1


# ── Raw Column Profile (Layer 1 — no interpretation) ─────────────────────────


class RawColumnProfile(BaseModel):
    """Everything computed from the column data alone — zero interpretation.

    This is the single source of truth for a column's *statistical* profile.
    It does NOT contain:
      - semantic role (measure / dimension / etc.)
      - business category (revenue / cost / etc.)
      - domain classification
      - entity type (Customer / Product / etc.)

    Those are added by the intelligence layer.
    """

    # ── Identity ──
    name: str
    dtype: str                       # e.g. "Int64", "Float64", "Utf8", "Date"

    # ── Cardinality & Nulls ──
    cardinality: CardinalityInfo

    # ── Numeric Stats (None for non-numeric) ──
    stats: Optional[ColumnStats] = None

    # ── Sampling ──
    sample_values: list[str] = Field(default_factory=list)
    top_values: list[ValueCount] = Field(default_factory=list)

    # ── Detected Patterns ──
    patterns: list[PatternMatch] = Field(default_factory=list)

    # ── Quality ──
    quality: ColumnQualityInfo = Field(default_factory=ColumnQualityInfo)


# ── Dataset Overview ──────────────────────────────────────────────────────────


class DatasetInfo(BaseModel):
    """Basic information about the dataset being profiled."""

    row_count: int = 0
    column_count: int = 0
    file_type: str = "unknown"           # "csv", "xlsx", "parquet", "json"
    file_name: str = ""                  # Original filename
    schema_hash: str = ""                # Deterministic hash of [name, dtype]


# ── Raw Profiling Result (output of the profiling layer) ─────────────────────


class RawProfilingResult(BaseModel):
    """The complete output of the profiling layer — pure facts.

    This is consumed by:
      1. The intelligence layer (adds semantic meaning)
      2. The pipeline orchestrator (process.py)
      3. Frontend API endpoints

    No interpretation has been applied. Every value is a direct
    computation from the raw data.
    """

    dataset: DatasetInfo
    columns: list[RawColumnProfile] = Field(default_factory=list)
    processed_at: Optional[str] = None   # ISO 8601 timestamp

    def column_by_name(self, name: str) -> Optional[RawColumnProfile]:
        """Look up a column profile by name."""
        for c in self.columns:
            if c.name == name:
                return c
        return None

    def numeric_columns(self) -> list[RawColumnProfile]:
        """Return columns with numeric dtypes."""
        return [
            c for c in self.columns
            if c.stats is not None
        ]

    def string_columns(self) -> list[RawColumnProfile]:
        """Return string/text columns."""
        return [
            c for c in self.columns
            if "Utf8" in c.dtype or "String" in c.dtype or "Categorical" in c.dtype
        ]

    def column_metadata_list(self) -> list[dict[str, Any]]:
        """Return column metadata in the legacy dict format for backward compat.

        Used by process.py and downstream consumers that expect the old format.
        """
        result = []
        for c in self.columns:
            entry: dict[str, Any] = {
                "name": c.name,
                "type": c.dtype,
                "null_count": c.cardinality.null_count,
                "null_percentage": round(c.cardinality.null_pct, 2),
                "unique_count": c.cardinality.unique_count,
            }
            if c.stats:
                entry["numeric_summary"] = {
                    "min": c.stats.col_min,
                    "max": c.stats.col_max,
                    "mean": c.stats.col_mean,
                }
            if c.top_values:
                entry["top_values"] = [
                    {"value": v.value, "count": v.count}
                    for v in c.top_values[:10]
                ]
            result.append(entry)
        return result

    def cardinality_map(self) -> dict[str, CardinalityInfo]:
        """Return cardinality info by column name."""
        return {c.name: c.cardinality for c in self.columns}

"""
profiling — Layer 1: Facts about data
======================================

Pure statistical profiling with zero interpretation.
No LLM calls. No semantic classification. No domain matching.

Output: RawProfilingResult — facts only.
"""

from .models import (
    ColumnStats,
    CardinalityInfo,
    PatternMatch,
    ValueCount,
    ColumnQualityInfo,
    RawColumnProfile,
    RawProfilingResult,
    DatasetInfo,
)
from .column_profiler import ColumnProfiler
from .quality_scorer import QualityScorer
from .engine import ProfilingEngine

__all__ = [
    "ColumnStats",
    "CardinalityInfo",
    "PatternMatch",
    "ValueCount",
    "ColumnQualityInfo",
    "RawColumnProfile",
    "RawProfilingResult",
    "DatasetInfo",
    "ColumnProfiler",
    "QualityScorer",
    "ProfilingEngine",
]

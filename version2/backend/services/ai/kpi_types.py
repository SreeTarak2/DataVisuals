"""
KPI Types & Constants
=====================
Shared enums, dataclasses, constants, and regex patterns for the KPI generation
pipeline. This module has zero dependencies on other internal modules.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

logger = logging.getLogger(__name__)


# ── Memory Management Defaults ────────────────────────────────────────────────

DEFAULT_MAX_MEMORY_MB = 500
DEFAULT_MAX_SAFE_ROWS = 200000
SMALL_DATASET_THRESHOLD = 100


# ── Column Classification ─────────────────────────────────────────────────────

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
    MEASURE = "measure"
    RATE = "rate"
    COUNT = "count"
    DIMENSION = "dimension"
    TIME = "time"
    IDENTITY = "identity"


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
    ("revenue", r"\b(revenue|sales|gmv|income|earnings|gross|mrr|arr|net_sales|turnover|proceeds|receipts)\b", "higher_is_better"),
    ("cost", r"\b(cost|expense|opex|capex|cogs|spend|expenditure|loss|burn|overhead|tax|fee|charge|penalty|discount)\b", "lower_is_better"),
    ("volume", r"\b(orders|transactions|purchases|bookings|units|items|shipments|deliveries|installs)\b", "higher_is_better"),
    ("users", r"\b(users|customers|subscribers|members|accounts|clients|visitors|leads|prospects|buyers)\b", "higher_is_better"),
    ("rate_metric", r"\b(rate|ratio|percent|pct|margin|conversion|retention|satisfaction|engagement|utilization)\b", "higher_is_better"),
    ("churn_risk", r"\b(churn|attrition|cancellation|dropout|refund|return|complaint|defect|error|failure|bug|issue)\b", "lower_is_better"),
    ("price", r"\b(price|amount|value|aov|arpu|arpc|ltv|cac|worth|bid|ask)\b", "higher_is_better"),
    ("performance", r"\b(score|rating|nps|csat|satisfaction|quality|performance|rank|grade)\b", "higher_is_better"),
    ("duration", r"\b(duration|latency|age|tenure|days|hours|minutes|seconds|ms|response_time|wait_time|cycle_time)\b", "lower_is_better"),
    ("quantity", r"\b(count|num|qty|quantity|volume|capacity|inventory|stock|supply)\b", "higher_is_better"),
]

# Date format patterns for string coercion
_DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y",
    "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
    "%d-%m-%Y", "%m-%d-%Y", "%d/%m/%y",
    "%Y%m%d", "%b %d, %Y", "%d %b %Y", "%B %d, %Y", "%d %B %Y",
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
    cv: Optional[float] = None
    skewness: Optional[float] = None
    is_bounded_01: bool = False
    is_integer_valued: bool = False

    # Derived classification
    aggregation: str = "sum"
    polarity: str = "higher_is_better"
    business_category: str = "unknown"
    importance: str = "medium"

    @property
    def null_pct(self) -> float:
        return (self.n_nulls / self.n_rows * 100) if self.n_rows > 0 else 0

    @property
    def primary_value(self) -> Optional[float]:
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


@dataclass
class ProvenanceInfo:
    source_table: str = "upload"
    column: str = ""
    aggregation: str = "sum"
    formula_description: str = ""
    record_count: int = 0
    null_count: int = 0
    null_pct: float = 0.0
    total_rows: int = 0
    downsampled: bool = False
    downsample_ratio: Optional[float] = None
    confidence_score: float = 1.0
    confidence_label: str = "High"
    refreshed_at: str = ""

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

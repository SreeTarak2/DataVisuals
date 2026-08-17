"""
semantic/query_intent.py — Structured Intent Schema
===================================================

The core data model for the "LLM as translator" architecture.

Instead of the LLM writing SQL, it outputs a QueryIntent — a structured
description of what the user wants. The SQL compiler then generates
deterministic SQL from this intent + governed metric definitions.

Intent extraction flow:
  User: "Show me revenue by month for 2024, sorted by revenue descending"
    → LLM outputs:
      {
        "metrics": [{"name": "revenue", "alias": "total_revenue"}],
        "dimensions": [{"column": "month", "grain": "month"}],
        "filters": [{"column": "year", "operator": "=", "value": 2024}],
        "order": [{"metric": "revenue", "direction": "desc"}],
        "limit": 10
      }
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ── Enums ───────────────────────────────────────────────────────────────────


class FilterOperator(str, Enum):
    EQ = "="
    NEQ = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    IN = "in"
    NOT_IN = "not_in"
    LIKE = "like"
    ILIKE = "ilike"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    BETWEEN = "between"


class OrderDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class TimeGrain(str, Enum):
    """Granularity for time-based dimensions."""

    YEAR = "year"
    QUARTER = "quarter"
    MONTH = "month"
    WEEK = "week"
    DAY = "day"
    HOUR = "hour"
    RAW = "raw"  # No truncation — use the column as-is


# ── Data models ─────────────────────────────────────────────────────────────


@dataclass
class MetricIntent:
    """A single metric the user wants to compute.

    The LLM identifies the metric by name. The compiler resolves it
    against governed definitions to get the actual column, aggregation,
    and formula.
    """

    name: str                         # "revenue", "profit", "churn_rate"
    alias: Optional[str] = None       # Optional display alias (e.g. "total_revenue")
    aggregation: Optional[str] = None # Only set if user EXPLICITLY specified
                                      # (e.g., "sum of revenue" → "sum")
                                      # Otherwise None — compiler uses governed default

    def __post_init__(self):
        if self.alias is None:
            self.alias = self.name.replace(" ", "_")


@dataclass
class DimensionIntent:
    """A dimension to group or break down by."""

    column: str                       # Column name or "month", "year", etc.
    grain: Optional[str] = None       # "year" | "quarter" | "month" | "week" | "day"
    alias: Optional[str] = None


@dataclass
class FilterIntent:
    """A filter/WHERE clause."""

    column: str                       # Column name
    operator: FilterOperator = FilterOperator.EQ
    value: Any = None                 # Value(s) for the filter
    # For BETWEEN: [lower, upper]
    # For IN/NOT_IN: list of values

    def to_sql(self) -> str:
        """Convert to a SQL WHERE fragment."""
        col = f"`{self.column}`"

        if self.operator == FilterOperator.EQ:
            return f"{col} = {self._format_value(self.value)}"
        elif self.operator == FilterOperator.NEQ:
            return f"{col} != {self._format_value(self.value)}"
        elif self.operator == FilterOperator.GT:
            return f"{col} > {self._format_value(self.value)}"
        elif self.operator == FilterOperator.GTE:
            return f"{col} >= {self._format_value(self.value)}"
        elif self.operator == FilterOperator.LT:
            return f"{col} < {self._format_value(self.value)}"
        elif self.operator == FilterOperator.LTE:
            return f"{col} <= {self._format_value(self.value)}"
        elif self.operator == FilterOperator.IN:
            if isinstance(self.value, list):
                formatted = ", ".join(self._format_value(v) for v in self.value)
                return f"{col} IN ({formatted})"
            return f"{col} IN ({self._format_value(self.value)})"
        elif self.operator == FilterOperator.NOT_IN:
            if isinstance(self.value, list):
                formatted = ", ".join(self._format_value(v) for v in self.value)
                return f"{col} NOT IN ({formatted})"
            return f"{col} NOT IN ({self._format_value(self.value)})"
        elif self.operator == FilterOperator.LIKE:
            return f"{col} LIKE {self._format_value(self.value)}"
        elif self.operator == FilterOperator.ILIKE:
            return f"{col} ILIKE {self._format_value(self.value)}"
        elif self.operator == FilterOperator.IS_NULL:
            return f"{col} IS NULL"
        elif self.operator == FilterOperator.IS_NOT_NULL:
            return f"{col} IS NOT NULL"
        elif self.operator == FilterOperator.BETWEEN:
            if isinstance(self.value, (list, tuple)) and len(self.value) == 2:
                return f"{col} BETWEEN {self._format_value(self.value[0])} AND {self._format_value(self.value[1])}"
            return f"{col} = {self._format_value(self.value)}"
        else:
            return f"{col} = {self._format_value(self.value)}"

    @staticmethod
    def _format_value(val: Any) -> str:
        if val is None:
            return "NULL"
        if isinstance(val, bool):
            return "TRUE" if val else "FALSE"
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, str):
            escaped = val.replace("'", "''")
            return f"'{escaped}'"
        return str(val)


@dataclass
class OrderIntent:
    """ORDER BY clause."""

    column: Optional[str] = None      # Column name to sort by
    metric: Optional[str] = None      # OR: metric name to sort by
    direction: OrderDirection = OrderDirection.DESC


@dataclass
class QueryIntent:
    """The complete structured intent — what the LLM outputs instead of SQL.

    This is the core data model of the "LLM as translator" architecture.
    The LLM receives the user's question and produces this structured
    representation. The SQL compiler then generates deterministic SQL.
    """

    metrics: List[MetricIntent] = field(default_factory=list)
    dimensions: List[DimensionIntent] = field(default_factory=list)
    filters: List[FilterIntent] = field(default_factory=list)
    order: List[OrderIntent] = field(default_factory=list)
    limit: Optional[int] = None
    offset: Optional[int] = None
    distinct: bool = False

    # Metadata about extraction
    raw_query: str = ""
    confidence: float = 0.0  # 0.0-1.0 — how confident the LLM is in this intent
    has_aggregations: bool = True  # False if the user just wants raw data

    def is_empty(self) -> bool:
        """Check if this intent has any meaningful content."""
        return (
            len(self.metrics) == 0
            and len(self.dimensions) == 0
            and len(self.filters) == 0
            and not self.limit
        )

    def is_metric_query(self) -> bool:
        """Whether this intent requires metric resolution (aggregations)."""
        return self.has_aggregations and len(self.metrics) > 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for logging/API transport."""
        result: Dict[str, Any] = {
            "metrics": [asdict(m) for m in self.metrics],
            "dimensions": [asdict(d) for d in self.dimensions],
            "filters": [{"column": f.column, "operator": f.operator.value, "value": f.value} for f in self.filters],
            "order": [{"column": o.column or o.metric or "", "direction": o.direction.value} for o in self.order],
            "limit": self.limit,
            "has_aggregations": self.has_aggregations,
            "confidence": self.confidence,
        }
        return result

    @classmethod
    def from_raw_query(cls, query: str) -> QueryIntent:
        """Fallback: treat a raw query as a single metric intent.

        Used when the LLM-based intent extraction fails — the system
        creates a minimal intent that will be resolved against definitions.
        """
        return cls(
            metrics=[MetricIntent(name=query.lower().strip())],
            raw_query=query,
            confidence=0.0,
            has_aggregations=True,
        )


# ── Intent validation ───────────────────────────────────────────────────────


@dataclass
class IntentValidationResult:
    """Result of validating a QueryIntent against available schema + definitions."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    resolved_metric_names: Dict[str, str] = field(default_factory=dict)
    # Maps: user-facing metric name → canonical definition name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "resolved_metric_names": self.resolved_metric_names,
        }


def validate_intent(
    intent: QueryIntent,
    available_columns: Optional[List[str]] = None,
    defined_metrics: Optional[Set[str]] = None,
) -> IntentValidationResult:
    """Validate a QueryIntent against available columns and metric definitions.

    Args:
        intent: The structured intent to validate
        available_columns: Column names available in the dataset
        defined_metrics: Metric names that have governed definitions

    Returns:
        IntentValidationResult with errors, warnings, and resolution info
    """
    errors: List[str] = []
    warnings: List[str] = []
    resolved: Dict[str, str] = {}
    cols_lower = {c.lower(): c for c in (available_columns or [])}
    defined_lower = {d.lower(): d for d in (defined_metrics or set())} if defined_metrics else {}

    # Validate each metric
    for m in intent.metrics:
        name_lower = m.name.lower().strip()

        # Check if this metric has a governed definition
        if name_lower in defined_lower:
            resolved[m.name] = defined_lower[name_lower]
        elif name_lower in cols_lower:
            resolved[m.name] = cols_lower[name_lower]
            warnings.append(f"Metric '{m.name}' matched column name but has no governed definition")
        else:
            # Might still match via column name — not an error yet
            warnings.append(f"Metric '{m.name}' not found in definitions or columns")

        # Validate explicitly specified aggregation
        if m.aggregation:
            valid_aggs = {"sum", "mean", "median", "count", "count_unique", "min", "max"}
            if m.aggregation.lower() not in valid_aggs:
                errors.append(
                    f"Invalid aggregation '{m.aggregation}' for metric '{m.name}'. "
                    f"Must be one of: {', '.join(sorted(valid_aggs))}"
                )

    # Validate each dimension column exists
    for d in intent.dimensions:
        col_lower = d.column.lower().strip()
        if col_lower not in cols_lower and col_lower not in defined_lower:
            # Time-based dimensions (month, year, quarter) might not be direct columns
            if d.grain:
                pass  # Grain dimensions are handled by the compiler with DATE_TRUNC
            else:
                warnings.append(f"Dimension column '{d.column}' not found in available columns")

    # Validate each filter column exists
    for f in intent.filters:
        col_lower = f.column.lower().strip()
        if col_lower not in cols_lower:
            warnings.append(f"Filter column '{f.column}' not found in available columns")

    return IntentValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        resolved_metric_names=resolved,
    )

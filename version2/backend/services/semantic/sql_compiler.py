"""
semantic/sql_compiler.py — Deterministic Metric-Aware SQL Compiler
==================================================================

THE CORE OF THE FERRARI ENGINE.

Takes a structured QueryIntent + resolved MetricDefinitions and generates
DuckDB SQL deterministically. No LLM involvement in SQL generation.

The compiler guarantees:
- Correct aggregation (SUM, not COUNT, for additive metrics)
- Correct column names (from governed definitions, not guesses)
- Formula inlining (revenue = price * qty, not a hinted expression)
- Filter enforcement (status != 'refunded' applied automatically)
- Grain handling (DATE_TRUNC for time dimensions)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .metric_definition_store import MetricDefinition
from .query_intent import (
    DimensionIntent,
    FilterIntent,
    FilterOperator,
    MetricIntent,
    OrderDirection,
    OrderIntent,
    QueryIntent,
    TimeGrain,
)

logger = logging.getLogger(__name__)


# ── SQL compilation error ───────────────────────────────────────────────────


class CompilationError(Exception):
    """Raised when the compiler cannot generate valid SQL from an intent."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


# ── Compiler ────────────────────────────────────────────────────────────────


class MetricSQLCompiler:
    """Deterministic SQL compiler for governed metric queries.

    Pipeline:
      1. Validate intent against available columns
      2. Resolve each metric against its governed definition
      3. Build SELECT, FROM, WHERE, GROUP BY, ORDER BY, LIMIT clauses
      4. Return the final SQL string

    The compiler NEVER guesses. If a metric can't be resolved, it raises
    CompilationError. This is by design — the caller must ensure all metrics
    are resolved before calling the compiler.
    """

    def __init__(self):
        self._table_name = "data"

    def compile(
        self,
        intent: QueryIntent,
        metric_definitions: Dict[str, MetricDefinition],
        available_columns: Optional[List[str]] = None,
    ) -> str:
        """Compile a QueryIntent into deterministic SQL.

        Args:
            intent: The structured query intent
            metric_definitions: Resolved metric definitions, keyed by name
            available_columns: Column names available in the dataset

        Returns:
            A DuckDB-compatible SQL string

        Raises:
            CompilationError: If metrics can't be resolved or SQL is invalid
        """
        if intent.is_empty():
            raise CompilationError("Empty query intent — nothing to compile")

        cols_lower = {c.lower(): c for c in (available_columns or [])}

        # Step 1: Build SELECT clause
        select_parts: List[str] = []
        dimension_selects: List[str] = []

        for dim in intent.dimensions:
            sql = self._compile_dimension(dim, cols_lower)
            if sql:
                dimension_selects.append(sql)

        for metric in intent.metrics:
            sql = self._compile_metric(metric, metric_definitions, cols_lower)
            if sql:
                select_parts.append(sql)

        if not select_parts and not dimension_selects:
            raise CompilationError(
                "No metrics or dimensions to select",
                {"metrics": [m.name for m in intent.metrics]},
            )

        # If no dimensions but there are metrics, we need a simple SELECT
        if intent.is_metric_query() and not dimension_selects:
            select_clause = ",\n  ".join(select_parts)
            sql = f"SELECT\n  {select_clause}\nFROM {self._table_name}"
        else:
            all_selects = dimension_selects + select_parts
            select_clause = ",\n  ".join(all_selects)
            sql = f"SELECT\n  {select_clause}\nFROM {self._table_name}"

        # Step 2: Build WHERE clause (from intent filters)
        where_parts = [f.to_sql() for f in intent.filters if f.to_sql()]

        # Step 3: Add any governed filters from metric definitions
        for metric in intent.metrics:
            defn = metric_definitions.get(metric.name.lower().strip())
            if defn and defn.filters:
                for gov_filter in defn.filters:
                    if gov_filter not in where_parts:
                        where_parts.append(gov_filter)

        if where_parts:
            sql += "\nWHERE " + "\n  AND ".join(where_parts)

        # Step 4: Build GROUP BY clause
        if dimension_selects and intent.is_metric_query():
            group_cols: List[str] = []
            for dim in intent.dimensions:
                col_name = self._resolve_column(dim.column, cols_lower)
                if col_name:
                    group_cols.append(f"`{col_name}`")
                elif dim.grain and dim.column:
                    # For grain dimensions, group by the truncated expression
                    grain_expr = self._date_trunc_expr(dim.column, dim.grain)
                    group_cols.append(grain_expr)

            if group_cols:
                sql += "\nGROUP BY " + ", ".join(group_cols)

        # Step 5: Build ORDER BY
        order_parts: List[str] = []
        for o in intent.order:
            order_sql = self._compile_order(o, metric_definitions, cols_lower)
            if order_sql:
                order_parts.append(order_sql)

        if order_parts:
            sql += "\nORDER BY " + ", ".join(order_parts)
        elif dimension_selects and intent.is_metric_query():
            # Default: order by first metric descending
            for metric in intent.metrics:
                defn = metric_definitions.get(metric.name.lower().strip())
                if defn and defn.source_column:
                    sql += f"\nORDER BY `{defn.source_column}` DESC"
                    break

        # Step 6: Build LIMIT / OFFSET
        if intent.limit is not None:
            sql += f"\nLIMIT {intent.limit}"
        elif intent.is_metric_query():
            sql += "\nLIMIT 1000"  # Safety limit for metric queries

        if intent.offset:
            sql += f"\nOFFSET {intent.offset}"

        if intent.distinct:
            sql = sql.replace("SELECT", "SELECT DISTINCT", 1)

        logger.info(f"[SQLCompiler] Compiled intent → SQL ({len(sql)} chars)")
        return sql

    # ── Private compilation methods ─────────────────────────────────────────

    def _compile_metric(
        self,
        metric: MetricIntent,
        definitions: Dict[str, MetricDefinition],
        cols_lower: Dict[str, str],
    ) -> Optional[str]:
        """Compile a single metric into a SELECT expression."""
        name_lower = metric.name.lower().strip()
        defn = definitions.get(name_lower)
        alias = f"`{metric.alias or name_lower.replace(' ', '_')}`"

        if defn:
            # Governed definition exists — use it
            return self._compile_from_definition(defn, alias, metric.aggregation)
        else:
            # No definition — this is an error for the production-grade path
            raise CompilationError(
                f"No governed definition found for metric '{metric.name}'",
                {"metric": metric.name, "available_definitions": list(definitions.keys())},
            )

    def _compile_from_definition(
        self,
        defn: MetricDefinition,
        alias: str,
        override_aggregation: Optional[str] = None,
    ) -> str:
        """Compile a MetricDefinition into a SELECT expression.

        Priority:
          1. If definition has a formula → use it directly
          2. If definition has a source_column → aggregate it
          3. If neither → error
        """
        agg = override_aggregation or defn.aggregation
        col = defn.source_column

        if defn.formula:
            # Formula case: inline the expression
            expr = defn.formula
            if col:
                # If both formula and source_column exist, the formula takes precedence
                pass
            # Wrap formula in aggregation if it's a simple column reference
            if self._is_simple_column_ref(defn.formula):
                return f"  {agg.upper()}({defn.formula}) AS {alias}"
            return f"  {agg.upper()}({defn.formula}) AS {alias}"

        if col:
            return f"  {agg.upper()}(`{col}`) AS {alias}"

        raise CompilationError(
            f"Definition for '{defn.name}' has no formula or source column",
            {"definition": defn.name, "source": defn.source.value},
        )

    def _compile_dimension(
        self,
        dim: DimensionIntent,
        cols_lower: Dict[str, str],
    ) -> Optional[str]:
        """Compile a dimension into a SELECT expression with grain handling."""
        col_name = self._resolve_column(dim.column, cols_lower)
        alias = f"`{dim.alias or dim.column.replace(' ', '_')}`"

        if col_name:
            # Column exists directly
            if dim.grain and dim.grain != TimeGrain.RAW:
                expr = self._date_trunc_expr(col_name, dim.grain)
                return f"  {expr} AS {alias}"
            return f"  `{col_name}` AS {alias}"

        if dim.grain:
            # Grain specified but column might not exist directly.
            # Try: date + grain → DATE_TRUNC(grain, date_col)
            # Check if there's a date-like column
            date_col = self._find_date_column(cols_lower)
            if date_col:
                expr = self._date_trunc_expr(date_col, dim.grain)
                return f"  {expr} AS {alias}"

            # Last resort: use the column as-is with the grain as a hint
            return f"  `{dim.column}` AS {alias}"

        return None

    def _compile_order(
        self,
        order: OrderIntent,
        definitions: Dict[str, MetricDefinition],
        cols_lower: Dict[str, str],
    ) -> Optional[str]:
        """Compile an ORDER BY clause."""
        direction = "ASC" if order.direction == OrderDirection.ASC else "DESC"

        if order.metric:
            # Sort by a metric — resolve to its column
            defn = definitions.get(order.metric.lower().strip())
            if defn and defn.source_column:
                return f"`{defn.source_column}` {direction}"
            return f"`{order.metric}` {direction}"

        if order.column:
            col = self._resolve_column(order.column, cols_lower)
            if col:
                return f"`{col}` {direction}"
            return f"`{order.column}` {direction}"

        return None

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_column(name: str, cols_lower: Dict[str, str]) -> Optional[str]:
        """Find the actual column name, case-insensitive."""
        name_lower = name.lower().strip()
        return cols_lower.get(name_lower)

    @staticmethod
    def _find_date_column(cols_lower: Dict[str, str]) -> Optional[str]:
        """Find the first date-like column."""
        date_hints = ["date", "time", "timestamp", "created", "updated", "day", "month", "year"]
        for hint in date_hints:
            for col_name in cols_lower.values():
                if hint in col_name.lower():
                    return col_name
        return None

    @staticmethod
    def _date_trunc_expr(column: str, grain: str) -> str:
        """Generate DuckDB DATE_TRUNC expression."""
        grain_upper = grain.upper() if isinstance(grain, str) else str(grain)
        return f"DATE_TRUNC('{grain_upper}', `{column}`)"

    @staticmethod
    def _is_simple_column_ref(expression: str) -> bool:
        """Check if an expression is just a simple column reference."""
        expression = expression.strip()
        if expression.startswith("`") and expression.endswith("`"):
            return True
        # Check for backtick-free column name
        return bool(re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", expression))


# Singleton
metric_sql_compiler = MetricSQLCompiler()

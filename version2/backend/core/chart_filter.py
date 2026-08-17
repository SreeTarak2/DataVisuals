"""
chart_filter.py
===============
Cross-filter helpers for chart rendering.

Standalone module (no heavy imports) so it can be unit-tested in isolation
and imported by API routes without pulling in the AI service stack.
"""

import logging

import polars as pl

logger = logging.getLogger(__name__)


def apply_df_filters(df: pl.DataFrame, filters) -> pl.DataFrame:
    """
    Apply a multi-select, multi-field cross-filter context to a DataFrame.

    Composition rules (Power BI / Tableau multi-select semantics):
      - Multiple values on the SAME field compose as OR  (an IN clause)
        — clicking "West" then "North" keeps both rows.
      - Different fields compose as AND — filtering by Region=West AND
        Product=A returns only rows matching both.

    Cross-filtering only propagates to charts that share the filtered
    field. Unknown fields are ignored; values are compared as strings so a
    clicked chart label matches regardless of the column's dtype.

    Args:
        df: Source DataFrame (unchanged when no filters are provided).
        filters: List of {"field": str, "value": any} or
            {"field": str, "values": [any, ...]} dicts. A single-entry list
            is backward-compatible with the old {field, value} shape.

    Returns:
        A filtered DataFrame (the same reference when nothing matched/unknown).
    """
    if not filters:
        return df

    # Group values by field — OR within a field, AND across fields.
    grouped: dict[str, list] = {}
    for f in filters:
        if not isinstance(f, dict):
            continue
        field = f.get("field")
        if not field or field not in df.columns:
            continue
        values = f.get("values")
        if values is None:
            value = f.get("value")
            if value is None:
                continue
            values = [value]
        if not isinstance(values, (list, tuple, set)):
            values = [values]
        grouped.setdefault(field, []).extend(values)

    if not grouped:
        return df

    filtered = df
    for field, values in grouped.items():
        str_values = {str(v) for v in values if v is not None}
        if not str_values:
            continue
        try:
            filtered = filtered.filter(pl.col(field).cast(pl.String).is_in(str_values))
        except Exception as exc:  # noqa: BLE001 — never break rendering on a bad filter
            logger.warning(f"[chart-filter] failed to apply filter on {field}: {exc}")
            continue
    return filtered

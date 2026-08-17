# services/charts/hydrate.py
"""
Unified Chart Hydration Service — Production Version 2.0

- Input: Polars DF + ChartConfig
- Output: Plotly traces (as dicts)
- Predictable, validated, schema-driven
- Modular handlers for each chart type
"""

import polars as pl
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple
import logging
import time
import math

from db.schemas_dashboard import (
    ChartConfig,
    AggregationType,
    ChartType,
    KpiConfig,
    TableConfig,
)
from services.charts.chart_definitions import CHART_DEFINITIONS_BY_ID

logger = logging.getLogger(__name__)

NUMERIC_DTYPES = pl.NUMERIC_DTYPES
CATEGORICAL_DTYPES = {pl.Utf8, pl.Categorical, pl.Boolean}
TEMPORAL_DTYPES = {pl.Datetime, pl.Date}

MULTI_SERIES_COLORS = [
    "#0ED2D2",  # teal   — primary
    "#22D3EE",  # cyan
    "#34D399",  # green
    "#FCD34D",  # amber
    "#F87171",  # red
    "#818CF8",  # indigo
    "#FB923C",  # orange
    "#A78BFA",  # violet
]
MAX_GROUP_SERIES = 5


def _get_col_format(col_name: str) -> str:
    """Helper to detect enterprise format for a column name."""
    import re

    c = (col_name or "").lower()
    if any(kw in c for kw in ("price", "cost", "revenue", "amount", "salary", "profit")):
        return "currency"
    if re.search(r"\b(rate|ratio|percent|pct|efficiency|growth)\b", c):
        return "percentage"
    if any(kw in c for kw in ("duration", "ms", "seconds", "sec", "time_spent")):
        return "duration"
    return "number"


class HydrationError(Exception):
    pass


def _auto_bin_numeric_col(df: pl.DataFrame, col: str, n_bins: int = 7) -> pl.DataFrame:
    """
    When a bar/line chart uses a continuous numeric column as its x-axis,
    bin the values into labeled ranges so bars are meaningful.
    Returns df with the col replaced by a string bin label, ordered naturally.
    """
    series = df[col].drop_nulls()
    if series.is_empty():
        return df

    min_val = float(series.min())
    max_val = float(series.max())
    if min_val == max_val:
        return df

    span = max_val - min_val
    raw_step = span / n_bins

    # Round step to a "nice" number for clean labels
    magnitude = 10 ** int(np.floor(np.log10(raw_step))) if raw_step > 0 else 1
    nice_steps = [magnitude * m for m in [1, 2, 2.5, 5, 10]]
    step = min(nice_steps, key=lambda s: abs(s - raw_step))
    step = max(step, 0.5)

    bin_start = np.floor(min_val / step) * step
    edges = []
    v = bin_start
    while v < max_val + step:
        edges.append(round(float(v), 4))
        v += step

    def fmt(x):
        return str(int(x)) if float(x) == int(float(x)) else f"{x:.1f}"

    def label(v):
        if v is None:
            return None
        for i in range(len(edges) - 1):
            lo, hi = edges[i], edges[i + 1]
            if lo <= v < hi or (i == len(edges) - 2 and v <= hi):
                return f"{fmt(lo)}–{fmt(hi)}"
        return f"{fmt(edges[-2])}+"

    bin_labels = [label(v) for v in df[col].to_list()]
    # Build an ordering map so bins sort naturally (not alphabetically)
    order_map = {label(edges[i]): i for i in range(len(edges) - 1)}

    df = df.with_columns(pl.Series(col, bin_labels, dtype=pl.Utf8))
    logger.info(f"Auto-binned '{col}': {len(edges) - 1} bins from {min_val:.1f} to {max_val:.1f}")
    return df, order_map


def _should_auto_bin(df: pl.DataFrame, col: str, threshold: int = 15) -> bool:
    """Return True if col is numeric with high cardinality — needs binning for bar/line."""
    if col not in df.columns:
        return False
    if df[col].dtype not in NUMERIC_DTYPES:
        return False
    n_unique = df[col].n_unique()
    return n_unique > threshold


def _lttb_downsample(x: List[Any], y: List[Any], threshold: int) -> Tuple[List[Any], List[Any]]:
    """
    Largest-Triangle-Three-Buckets downsampling.

    Picks, per bucket, the point that forms the largest triangle with the
    previously selected point and the average of the next bucket — preserving
    the visual shape (peaks/troughs) of a series far better than naive
    every-nth-point sampling.

    Dates, datetimes, and string labels cannot be float()-ed, so those are
    mapped to their index position as the triangle-math coordinate (order
    is preserved, geometry stays valid). Original x values are returned
    unchanged.

    Returns (sampled_x, sampled_y) with at most `threshold` points.
    """
    n = len(x)
    if threshold >= n or threshold < 3 or n < 3:
        return x, y

    # Numeric coordinate per point for triangle geometry (fallback: index).
    x_num: List[float] = []
    for k, xv in enumerate(x):
        try:
            x_num.append(float(xv))
        except (TypeError, ValueError):
            x_num.append(float(k))

    sampled_x: List[Any] = [x[0]]
    sampled_y: List[Any] = [y[0]]

    every = (n - 2) / (threshold - 2)
    a = 0  # index of the last chosen point

    for i in range(threshold - 2):
        # ── Average point of the NEXT bucket (defines triangle height) ──
        next_start = int((i + 1) * every) + 1
        next_end = min(int((i + 2) * every) + 1, n)
        avg_x = 0.0
        avg_y = 0.0
        if next_start < next_end:
            for k in range(next_start, next_end):
                avg_x += x_num[k]
                avg_y += float(y[k])
            count = next_end - next_start
            avg_x /= count
            avg_y /= count
        else:
            avg_x = x_num[a]
            avg_y = float(y[a])

        # ── Points in the CURRENT bucket ──
        range_start = int(i * every) + 1
        range_end = min(int((i + 1) * every) + 1, n)

        point_a_x = x_num[a]
        point_a_y = float(y[a])

        max_area = -1.0
        chosen = a
        for k in range(range_start, range_end):
            # Triangle area between (a), (k), and the next-bucket average
            area = abs(
                (point_a_x - avg_x) * (float(y[k]) - point_a_y)
                - (point_a_x - x_num[k]) * (avg_y - point_a_y)
            )
            if area > max_area:
                max_area = area
                chosen = k

        sampled_x.append(x[chosen])
        sampled_y.append(y[chosen])
        a = chosen

    sampled_x.append(x[n - 1])
    sampled_y.append(y[n - 1])
    return sampled_x, sampled_y


def _lttb_downsample_df(
    agg_df: pl.DataFrame, max_points: int
) -> Tuple[pl.DataFrame, int]:
    """
    Downsample a 2-column (x, y) aggregated polars DataFrame via LTTB.

    Returns (downsampled_df, original_count). No-op when already within limit.
    """
    n = len(agg_df)
    if n <= max_points:
        return agg_df, n
    sx, sy = _lttb_downsample(agg_df["x"].to_list(), agg_df["y"].to_list(), max_points)
    return pl.DataFrame({"x": sx, "y": sy}), n


def aggregate_sampling_metadata(traces: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """
    Collapse per-trace `_sampled` hints into one chart-level summary.

    Returns None when no trace was downsampled (callers can skip the badge).
    Structure: {"shown": int, "original_count": int, "method": str}
    """
    shown = 0
    original = 0
    method = None
    for t in traces:
        s = t.get("_sampled") if isinstance(t, dict) else None
        if not isinstance(s, dict):
            continue
        shown += int(s.get("shown", 0) or 0)
        original = max(original, int(s.get("original_count", 0) or 0))
        if s.get("method"):
            method = s["method"]
    if shown <= 0 or original <= 0 or original <= shown:
        return None
    return {"shown": shown, "original_count": original, "method": method or "sampled"}


def validate_config(df: pl.DataFrame, config: ChartConfig) -> None:
    """
    Permissive validation: strip invalid columns, warn on mismatches,
    but NEVER raise — let the handler decide if it can render.

    Every handler already has graceful degradation:
      - grouped_bar → bar   |  stacked_bar → bar
      - multi_line  → line  |  stacked_area → area
      - bubble → scatter    |  candlestick → line
      - heatmap → correlation heatmap (0-col fallback)
      - pie/histogram/treemap → 1-col value_counts

    Raising here kills the ENTIRE /charts endpoint for one bad chart.
    """
    # Guard: default to "bar" if chart_type is None
    if config.chart_type is None:
        logger.warning("chart_type is None — defaulting to 'bar'")
        config.chart_type = "bar"

    # Handle both string and enum types
    chart_type_str = (
        config.chart_type.value if hasattr(config.chart_type, "value") else config.chart_type
    )

    # Strip columns that don't exist in the dataframe
    safe_cols = [c for c in config.columns if c in df.columns]
    if len(safe_cols) < len(config.columns):
        dropped = set(config.columns) - set(safe_cols)
        logger.warning(f"validate_config({chart_type_str}): dropped missing columns {dropped}")
        config.columns = safe_cols

    # Only hard-fail if there are ZERO columns AND the chart type genuinely
    # cannot operate without any (heatmap can → correlation fallback)
    ZERO_COL_OK = {"heatmap"}
    if not config.columns and chart_type_str not in ZERO_COL_OK:
        raise HydrationError("No valid columns after safety check.")

    # Soft warnings (informational only — handlers will degrade gracefully)
    chart_def = CHART_DEFINITIONS_BY_ID.get(chart_type_str, {})
    rules = chart_def.get("rules", {})
    num_needed = sum(1 for req in rules.get("data_types", []) if req["type"] == "numeric")
    actual_num = sum(1 for c in config.columns if df[c].dtype in NUMERIC_DTYPES)
    if actual_num < num_needed:
        logger.info(
            f"validate_config({chart_type_str}): {actual_num} numeric cols "
            f"< {num_needed} ideal — handler will degrade gracefully"
        )


def _safe_aggregate(
    df: pl.DataFrame,
    group_col: str,
    value_col: str,
    agg: AggregationType,
    sort_mode: str = "y_desc",
) -> pl.DataFrame:
    if group_col not in df.columns or value_col not in df.columns:
        raise HydrationError(f"Missing agg cols: {group_col}, {value_col}")

    agg_upper = agg.value.upper() if hasattr(agg, "value") else str(agg).upper()
    if agg_upper in {
        "SUM",
        "MEAN",
        "MAX",
        "MIN",
        "MEDIAN",
        "STD",
        "PERCENTILE_25",
        "PERCENTILE_75",
    }:
        if df[value_col].dtype not in NUMERIC_DTYPES:
            # Attempt automatic cast — handles numeric values stored as strings
            original_dtype = df[value_col].dtype
            try:
                cast_series = df[value_col].cast(pl.Float64, strict=False)
                null_count_before = df[value_col].null_count()
                null_count_after = cast_series.null_count()
                # Only accept the cast if it didn't introduce too many new nulls (< 20%)
                new_nulls = null_count_after - null_count_before
                if new_nulls / max(len(df), 1) < 0.2:
                    df = df.with_columns(cast_series.alias(value_col))
                    logger.info(
                        f"Auto-cast '{value_col}' from {original_dtype} to Float64 "
                        f"({new_nulls} new nulls from non-numeric values)"
                    )
                else:
                    raise HydrationError(
                        f"Column '{value_col}' is type {original_dtype} and cannot be "
                        f"cast to numeric (too many non-numeric values). "
                        f"Try using 'count' or 'nunique' instead."
                    )
            except HydrationError:
                raise
            except Exception:
                raise HydrationError(
                    f"Column '{value_col}' is type {original_dtype}, "
                    f"but aggregation '{agg}' requires numeric data. "
                    f"Try using 'count' or 'nunique' instead."
                )

    data = df.filter(pl.col(group_col).is_not_null() & pl.col(value_col).is_not_null())
    if data.is_empty():
        return pl.DataFrame()

    if agg == AggregationType.COUNT:
        expr = pl.count()
    elif agg == AggregationType.SUM:
        expr = pl.sum(value_col)
    elif agg == AggregationType.MEAN:
        expr = pl.mean(value_col)
    elif agg == AggregationType.MEDIAN:
        expr = pl.median(value_col)
    elif agg == AggregationType.STD:
        expr = pl.std(value_col)
    elif agg == AggregationType.PERCENTILE_25:
        expr = pl.col(value_col).quantile(0.25)
    elif agg == AggregationType.PERCENTILE_75:
        expr = pl.col(value_col).quantile(0.75)
    elif agg == AggregationType.MAX:
        expr = pl.max(value_col)
    elif agg == AggregationType.MIN:
        expr = pl.min(value_col)
    elif agg == AggregationType.NUNIQUE:
        expr = pl.n_unique(value_col)
    else:
        expr = pl.first(value_col)

    agg_df = data.group_by(group_col).agg(expr)
    agg_df = agg_df.rename({group_col: "x", agg_df.columns[-1]: "y"})
    if sort_mode == "x_asc":
        agg_df = agg_df.sort("x", descending=False)
    elif sort_mode == "x_desc":
        agg_df = agg_df.sort("x", descending=True)
    elif sort_mode == "none":
        pass  # caller will apply custom ordering (e.g. bin_order_map)
    else:
        agg_df = agg_df.sort("y", descending=True)
    return agg_df


def hydrate_kpi(df: pl.DataFrame, config: KpiConfig) -> Dict[str, Any]:
    """
    Hydrate a KPI component with real computed data from the full DataFrame.

    Returns a rich dict:
      value, label, sparkline_data, comparison_value, comparison_label,
      delta_percent, format, min_value, max_value, record_count, top_values
    """
    start = time.time()
    try:
        col = config.column
        agg = config.aggregation

        # --- Primary value ---
        if agg == AggregationType.COUNT:
            value = len(df)
        elif col == "__all__" or col not in df.columns:
            # Fallback for count-all or missing column
            value = len(df)
            agg = AggregationType.COUNT
        else:
            agg_str = agg.value if hasattr(agg, "value") else agg
            if agg_str == "nunique":
                agg_str = "n_unique"
            elif agg_str in ("max", "min"):
                pass  # polars uses 'max' and 'min' directly

            if df[col].dtype in (pl.Utf8, pl.Categorical) and agg_str in (
                "sum",
                "mean",
                "median",
                "max",
                "min",
                "std",
                "percentile_25",
                "percentile_75",
            ):
                agg_str = "n_unique" if agg_str in ("sum", "max") else "count"

            if agg_str in (
                "sum",
                "mean",
                "max",
                "min",
                "median",
                "std",
                "percentile_25",
                "percentile_75",
            ):
                if df[col].dtype not in NUMERIC_DTYPES:
                    agg_str = "count"
                    value = len(df)
                else:
                    if agg_str == "percentile_25":
                        value = df.select(pl.col(col).quantile(0.25)).item()
                    elif agg_str == "percentile_75":
                        value = df.select(pl.col(col).quantile(0.75)).item()
                    else:
                        value = df.select(getattr(pl, agg_str)(col)).item()
            else:
                value = df.select(getattr(pl, agg_str)(col)).item()

        # --- Format detection from column name (Enterprise Edition) ---
        kpi_format = _get_col_format(col)
        if agg == AggregationType.COUNT:
            kpi_format = "integer"

        # Humanize Value if Duration
        display_value = value
        if kpi_format == "duration" and isinstance(value, (int, float)):
            # Assume milliseconds if value > 1000 and name has 'ms'
            ms = value if "ms" in col.lower() or value > 10000 else value * 1000
            seconds = int((ms / 1000) % 60)
            minutes = int((ms / (1000 * 60)) % 60)
            hours = int((ms / (1000 * 60 * 60)) % 24)

            if hours > 0:
                display_value = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                display_value = f"{minutes}:{seconds:02d}"

        result: Dict[str, Any] = {
            "value": value,
            "display_value": display_value,
            "label": config.title,
            "format": kpi_format,
        }

        # --- Only enrich if we have a real numeric column ---
        if col != "__all__" and col in df.columns and df[col].dtype in NUMERIC_DTYPES:
            series = df[col].drop_nulls()
            n = len(series)

            # Record count / Definitions
            col_mean = series.mean()
            col_std = series.std() if n > 1 else 0

            result["min_value"] = float(series.min()) if n > 0 else 0
            result["max_value"] = float(series.max()) if n > 0 else 0
            result["record_count"] = n

            # --- Generate Enterprise Context (Tooltips & Anomalies) ---
            agg_name = agg.value if hasattr(agg, "value") else str(agg).upper()
            result["definition"] = (
                f"Calculated as the {agg_name.lower()} of '{col}' across {n:,} records."
            )

            # Simple Outlier Detection (Is the current value > 2 std dev from mean?)
            if col_std > 0 and abs(value - col_mean) > (2 * col_std):
                result["isOutlier"] = True
                result["benchmarkText"] = "Significant deviation from mean"
            else:
                # Format benchmark text according to KPI format
                if kpi_format == "duration":
                    ms = col_mean
                    seconds = int((ms / 1000) % 60)
                    minutes = int((ms / (1000 * 60)) % 60)
                    hours = int((ms / (1000 * 60 * 60)) % 24)
                    fmt_mean = (
                        f"{hours}:{minutes:02d}:{seconds:02d}"
                        if hours > 0
                        else f"{minutes}:{seconds:02d}"
                    )
                    result["benchmarkText"] = f"Dataset Average: {fmt_mean}"
                else:
                    result["benchmarkText"] = (
                        f"Dataset Average: {round(col_mean, 2) if col_mean else 0}"
                    )

            # ─── TIME-AWARE SORTING & TRENDING ───
            # Locate a temporal column for meaningful splitting
            date_col = None
            for col_name in df.columns:
                if df[col_name].dtype in (pl.Date, pl.Datetime):
                    date_col = col_name
                    break

            if date_col and n >= 8:
                # Sort by time for true chronological trend
                df_sorted = df.sort(date_col)
                time_series = df_sorted[col].drop_nulls()

                # Sparkline — bucket into 16 points (rolling chronological trend)
                vals = time_series.to_list()
                bucket_count = min(16, n)
                bucket_size = n // bucket_count
                sparkline = []
                for i in range(bucket_count):
                    chunk = vals[i * bucket_size : (i + 1) * bucket_size]
                    if chunk:
                        sparkline.append(round(sum(chunk) / len(chunk), 2))
                result["sparkline_data"] = sparkline

                # Comparison — earlier period vs later period
                mid = n // 2
                first_vals = time_series.slice(0, mid)
                second_vals = time_series.slice(mid)

                if agg == AggregationType.SUM:
                    prev = float(first_vals.sum())
                    curr = float(second_vals.sum())
                elif agg == AggregationType.MEAN:
                    prev = float(first_vals.mean())
                    curr = float(second_vals.mean())
                else:
                    prev = float(first_vals.sum())
                    curr = float(second_vals.sum())

                result["comparison_value"] = round(prev, 2)
                result["comparison_label"] = "vs earlier period (time-sorted)"

                if prev != 0:
                    delta = ((curr - prev) / abs(prev)) * 100
                    result["delta_percent"] = round(delta, 1)

                    # AI Suggestion based on chronological polarity
                    polarity = (
                        "expense"
                        if any(k in col.lower() for k in ["cost", "discount", "loss", "tax"])
                        else "revenue"
                    )
                    if delta <= -15:
                        result["aiSuggestion"] = (
                            f"Sharp over-time drop in {col}. Review contributing segments."
                            if polarity == "revenue"
                            else f"Great cost reduction in {col}."
                        )
                    elif delta >= 15:
                        result["aiSuggestion"] = (
                            f"Strong growth in {col} recently!"
                            if polarity == "revenue"
                            else f"Warning: {col} is surging over time. Investigate root causes."
                        )
                    else:
                        result["aiSuggestion"] = f"{col} is stable compared to the earlier period."

            else:
                # ─── NO TIME COLUMN FALLBACK ───
                # Omit strictly chronological comparisons (delta / sparkline)
                logger.info(
                    f"No date column found for {col} – skipping time-based delta, relying on benchmarkText."
                )

                # But we can still offer a non-temporal AI Context
                polarity = (
                    "expense"
                    if any(k in col.lower() for k in ["cost", "discount", "loss", "tax"])
                    else "revenue"
                )
                if result.get("isOutlier"):
                    result["aiSuggestion"] = (
                        f"The overall {col} shows extreme variance. Investigate top drivers."
                    )
                else:
                    result["aiSuggestion"] = (
                        f"Overall {col} is relatively distributed around {round(col_mean, 1)}."
                    )

        elif col in df.columns and df[col].dtype in (CATEGORICAL_DTYPES | {pl.Utf8}):
            # For categorical KPIs (count/nunique) — provide top value distribution
            result["format"] = "integer"
            result["record_count"] = len(df)
            try:
                top = (
                    df.group_by(col)
                    .agg(pl.count().alias("cnt"))
                    .sort("cnt", descending=True)
                    .head(5)
                )
                result["top_values"] = [
                    {"name": str(row[col]), "count": int(row["cnt"])}
                    for row in top.iter_rows(named=True)
                ]
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"KPI hydration failed: {e}")
        return {"value": "N/A", "label": config.title, "error": str(e)[:60]}
    finally:
        logger.info(f"KPI hydrated in {time.time() - start:.2f}s")


def hydrate_table(df: pl.DataFrame, config: TableConfig) -> List[Dict]:
    start = time.time()
    try:
        safe_cols = [c for c in config.columns if c in df.columns]
        if not safe_cols:
            raise HydrationError("No valid table columns.")
        limit = min(config.limit, 1000)
        return df.select(safe_cols).head(limit).to_dicts()
    except Exception as e:
        logger.error(f"Table hydration failed: {e}")
        return []
    finally:
        logger.info(f"Table hydrated in {time.time() - start:.2f}s")


def hydrate_chart(df: pl.DataFrame, config: ChartConfig) -> Tuple[List[Dict[str, Any]], int]:
    """
    Hydrate chart configuration into Plotly traces.

    Returns:
        tuple: (traces, rows_used) where traces is a list of Plotly trace dicts
               and rows_used is the number of data points used
    """
    start = time.time()

    # Validation is now permissive — only raises for truly impossible configs
    # (e.g. zero columns on a non-heatmap). All other issues are warnings.
    try:
        validate_config(df, config)
    except HydrationError as e:
        logger.warning(f"Validation failed for {config.chart_type}: {e} — returning empty")
        chart_type = (
            config.chart_type.value
            if hasattr(config.chart_type, "value")
            else config.chart_type or "bar"
        )
        return ([{"type": chart_type, "x": [], "y": [], "error": str(e)[:100]}], 0)

    rows_used = len(df)

    # Guard: default to "bar" if chart_type is None
    if config.chart_type is None:
        logger.warning("chart_type is None in hydrate_chart — defaulting to 'bar'")
        config.chart_type = "bar"

    # Handle both string and enum types
    chart_type = (
        config.chart_type.value if hasattr(config.chart_type, "value") else config.chart_type
    )
    handler = _get_handler(chart_type)

    try:
        traces = handler(df, config)
        if not traces:
            return ([{"type": chart_type, "x": [], "y": [], "error": "No data"}], 0)
        return (traces, rows_used)
    except Exception as e:
        logger.error(f"{chart_type} hydration failed: {e}")
        return ([{"type": chart_type, "x": [], "y": [], "error": str(e)[:100]}], 0)
    finally:
        logger.info(f"{chart_type} hydrated in {time.time() - start:.2f}s")


def _get_handler(chart_type: str):
    handlers = {
        "bar": _hydrate_bar,
        "line": _hydrate_line,
        "pie": _hydrate_pie,
        "histogram": _hydrate_histogram,
        "box_plot": _hydrate_box,
        "scatter": _hydrate_scatter,
        "heatmap": _hydrate_heatmap,
        "treemap": _hydrate_treemap,
        "grouped_bar": _hydrate_grouped_bar,
        "stacked_bar": _hydrate_stacked_bar,
        "area": _hydrate_area,
        # Multi-series charts
        "multi_line": _hydrate_multi_line,
        "stacked_area": _hydrate_stacked_area,
        # New chart types
        "radar": _hydrate_radar,
        "bubble": _hydrate_bubble,
        "waterfall": _hydrate_waterfall,
        "funnel": _hydrate_funnel,
        "candlestick": _hydrate_candlestick,
        "violin": _hydrate_violin,
        "violin_plot": _hydrate_violin,
        "sunburst": _hydrate_sunburst,
        "gauge": _hydrate_gauge,
        "bullet": _hydrate_bullet,
        "choropleth": _hydrate_choropleth,
        # ECharts-native types with Plotly fallback hydration
        "donut": _hydrate_donut,
        "map": _hydrate_map,
        "pictorial_bar": _hydrate_pictorial_bar,
        "effect_scatter": _hydrate_effect_scatter,
        "graph": _hydrate_graph,
        "sankey": _hydrate_sankey,
        "parallel": _hydrate_parallel,
        "lines": _hydrate_lines,
        "tree": _hydrate_tree,
        "theme_river": _hydrate_theme_river,
    }
    if chart_type not in handlers:
        logger.warning(f"Unknown chart type: {chart_type}, using fallback")
    return handlers.get(chart_type, _hydrate_fallback)


def _resolve_group_by(config):
    """Safely extract the first group_by column from a config."""
    gb = getattr(config, "group_by", None)
    if not gb:
        return None
    if isinstance(gb, list):
        return gb[0] if gb else None
    if isinstance(gb, str) and gb.strip():
        return gb.strip()
    return None


def _build_grouped_bar_traces(df, x_col, y_col, group_col, config):
    """Build multi-trace grouped bar chart. One bar trace per group value."""
    if x_col not in df.columns or y_col not in df.columns or group_col not in df.columns:
        logger.warning(f"grouped_bar: missing columns x={x_col} y={y_col} group={group_col}")
        return []

    group_totals = (
        df.group_by(group_col)
        .agg(
            pl.sum(y_col).alias("_total")
            if df[y_col].dtype in NUMERIC_DTYPES
            else pl.count().alias("_total")
        )
        .sort("_total", descending=True)
        .head(MAX_GROUP_SERIES)
    )
    top_groups = group_totals[group_col].to_list()
    if not top_groups:
        return []

    top_x = (
        df.group_by(x_col)
        .agg(pl.count().alias("_cnt"))
        .sort("_cnt", descending=True)
        .head(20)[x_col]
        .to_list()
    )

    traces = []
    for i, grp_val in enumerate(top_groups):
        grp_df = df.filter(pl.col(group_col) == grp_val)
        try:
            agg_df = _safe_aggregate(grp_df, x_col, y_col, config.aggregation)
        except HydrationError:
            try:
                agg_df = _safe_aggregate(grp_df, x_col, y_col, AggregationType.COUNT)
            except HydrationError:
                continue
        agg_map = {str(row["x"]): row["y"] for row in agg_df.iter_rows(named=True)}
        y_vals = [agg_map.get(str(cat), 0) for cat in top_x]
        traces.append(
            {
                "type": "bar",
                "name": str(grp_val),
                "x": [str(c) for c in top_x],
                "y": y_vals,
                "marker": {"color": MULTI_SERIES_COLORS[i % len(MULTI_SERIES_COLORS)]},
                "_axis_metadata": {
                    "x": {"format": "categorical"},
                    "y": {"format": _get_col_format(y_col)},
                },
                "_group_by": group_col,
            }
        )
    logger.info(f"grouped_bar: {len(traces)} series for group_col='{group_col}'")
    return traces


def _build_multi_line_traces(df, x_col, y_col, group_col, config, max_points=1000):
    """Build multi-trace line chart. One line per group value."""
    if x_col not in df.columns or y_col not in df.columns or group_col not in df.columns:
        logger.warning(f"multi_line: missing columns x={x_col} y={y_col} group={group_col}")
        return []

    x_is_year = False
    if df[x_col].dtype in NUMERIC_DTYPES:
        x_min, x_max = df[x_col].min(), df[x_col].max()
        if (
            x_min is not None
            and x_max is not None
            and 1900 <= x_min <= 2030
            and 1900 <= x_max <= 2030
        ):
            x_is_year = True

    group_totals = (
        df.group_by(group_col)
        .agg(
            pl.sum(y_col).alias("_total")
            if df[y_col].dtype in NUMERIC_DTYPES
            else pl.count().alias("_total")
        )
        .sort("_total", descending=True)
        .head(MAX_GROUP_SERIES)
    )
    top_groups = group_totals[group_col].to_list()
    if not top_groups:
        return []

    traces = []
    for i, grp_val in enumerate(top_groups):
        grp_df = df.filter(pl.col(group_col) == grp_val)
        try:
            agg_df = _safe_aggregate(grp_df, x_col, y_col, config.aggregation, sort_mode="x_asc")
        except HydrationError:
            continue
        if agg_df.is_empty():
            continue
        total_pts = len(agg_df)
        sampled_meta = None
        if total_pts > max_points:
            agg_df, _ = _lttb_downsample_df(agg_df, max_points)
            sampled_meta = {
                "original_count": total_pts,
                "shown": len(agg_df),
                "method": "lttb",
            }
        x_data = agg_df["x"].to_list()
        if x_is_year:
            x_data = [f"{int(v)}-01-01" for v in x_data]
        color = MULTI_SERIES_COLORS[i % len(MULTI_SERIES_COLORS)]
        traces.append(
            {
                "type": "scatter",
                "mode": "lines+markers",
                "name": str(grp_val),
                "x": x_data,
                "y": agg_df["y"].to_list(),
                "line": {"color": color, "width": 2},
                "marker": {"color": color, "size": 4},
                "_axis_metadata": {
                    "x": {
                        "format": "date"
                        if (x_is_year or df[x_col].dtype in TEMPORAL_DTYPES)
                        else "number"
                    },
                    "y": {"format": _get_col_format(y_col)},
                },
                "_group_by": group_col,
            }
        )
        if sampled_meta:
            traces[-1]["_sampled"] = sampled_meta
    logger.info(
        f"multi_line: {len(traces)} series for group_col='{group_col}' year_mode={x_is_year}"
    )
    return traces


def _hydrate_bar(df, config):
    MAX_BAR_CATEGORIES = 25
    if len(config.columns) < 2:
        return []
    x, y = config.columns[0], config.columns[1]

    # Auto-bin continuous numeric x-axis (e.g. sleep_duration, study_time_per_week)
    bin_order_map = None
    if _should_auto_bin(df, x):
        result = _auto_bin_numeric_col(df, x)
        if isinstance(result, tuple):
            df, bin_order_map = result

    group_col = _resolve_group_by(config)
    if group_col and group_col in df.columns:
        return _build_grouped_bar_traces(df, x, y, group_col, config)

    try:
        agg_df = _safe_aggregate(df, x, y, config.aggregation)
    except HydrationError as e:
        logger.error(f"bar hydration failed: {e}")
        try:
            agg_df = _safe_aggregate(df, x, y, AggregationType.COUNT)
            logger.info(f"Bar chart fell back to COUNT aggregation for column '{y}'")
        except HydrationError:
            return []

    # Cap categories: keep top-N by value, aggregate remainder as "Other"
    total_categories = len(agg_df)
    if total_categories > MAX_BAR_CATEGORIES:
        top_df = agg_df.sort("y", descending=True).head(MAX_BAR_CATEGORIES - 1)
        other_sum = (
            agg_df.sort("y", descending=True)
            .tail(total_categories - (MAX_BAR_CATEGORIES - 1))["y"]
            .sum()
        )
        other_row = pl.DataFrame(
            {
                "x": [f"Other ({total_categories - MAX_BAR_CATEGORIES + 1} more)"],
                "y": [other_sum],
            }
        )
        agg_df = pl.concat([top_df, other_row])
        logger.info(f"Bar chart capped: {total_categories} → {MAX_BAR_CATEGORIES} categories")

    # Sort bins in natural order (not by value) when auto-binned
    if bin_order_map:
        agg_df = (
            agg_df.with_columns(
                pl.col("x")
                .map_elements(lambda v: bin_order_map.get(v, 999), return_dtype=pl.Int32)
                .alias("_bin_order")
            )
            .sort("_bin_order")
            .drop("_bin_order")
        )

    x_data = agg_df["x"].to_list()
    y_data = agg_df["y"].to_list()
    logger.info(f"Bar chart data - X: {x_data[:5]}... (total: {len(x_data)})")
    logger.info(f"Bar chart data - Y: {y_data[:5]}... (total: {len(y_data)})")
    trace = {
        "type": "bar",
        "x": x_data,
        "y": y_data,
        "name": config.title or y,
        "marker": {"color": MULTI_SERIES_COLORS[0]},
        "_axis_metadata": {
            "x": {"format": "categorical"},
            "y": {"format": _get_col_format(y)},
        },
    }
    if total_categories > MAX_BAR_CATEGORIES:
        trace["_sampled"] = {
            "original_count": total_categories,
            "shown": MAX_BAR_CATEGORIES,
        }
    return [trace]


def _hydrate_line(df, config):
    MAX_LINE_POINTS = 1000
    if len(config.columns) < 2:
        return []
    x, y = config.columns[0], config.columns[1]

    group_col = _resolve_group_by(config)
    if group_col and group_col in df.columns:
        return _build_multi_line_traces(df, x, y, group_col, config, MAX_LINE_POINTS)

    # Auto-bin continuous numeric x (e.g. sleep_duration, study_time) → readable intervals
    bin_order_map_line = None
    if _should_auto_bin(df, x):
        result = _auto_bin_numeric_col(df, x)
        if isinstance(result, tuple):
            df, bin_order_map_line = result

    if df[x].dtype in TEMPORAL_DTYPES:
        df = df.sort(x)
    # Critical: line charts must be ordered on x-axis, not by y magnitude.
    sort_mode = "x_asc" if not bin_order_map_line else "none"
    agg_df = _safe_aggregate(df, x, y, config.aggregation, sort_mode=sort_mode)

    # Re-order bins naturally when auto-binned
    if bin_order_map_line:
        agg_df = (
            agg_df.with_columns(
                pl.col("x")
                .map_elements(lambda v: bin_order_map_line.get(v, 999), return_dtype=pl.Int32)
                .alias("_bin_order")
            )
            .sort("_bin_order")
            .drop("_bin_order")
        )

    # Downsample line charts via LTTB — preserves the shape (peaks/troughs)
    # far better than every-nth-point sampling.
    total_points = len(agg_df)
    if total_points > MAX_LINE_POINTS:
        agg_df, _ = _lttb_downsample_df(agg_df, MAX_LINE_POINTS)
        logger.info(f"Line chart downsampled via LTTB: {total_points} → {len(agg_df)} points")

    # Detect numeric years (e.g., 2012) to prevent Plotly from misinterpreting them as Unix epoch seconds (1970)
    x_is_year = False
    if df[x].dtype in NUMERIC_DTYPES:
        x_min = df[x].min()
        x_max = df[x].max()
        if x_min is not None and x_max is not None:
            # Heuristic: integers between 1900 and 2030 are likely years
            if 1900 <= x_min <= 2030 and 1900 <= x_max <= 2030:
                x_is_year = True

    # Enterprise Fix: Convert years to real dates for true temporal rendering (kills 1970 bug)
    x_data = agg_df["x"].to_list()
    if x_is_year:
        # Convert 2012 -> "2012-01-01"
        x_data = [f"{int(v)}-01-01" for v in x_data]

    trace = {
        "type": "scatter",
        "mode": "lines",
        "x": x_data,
        "y": agg_df["y"].to_list(),
        "name": config.title or y,
        "line": {"color": MULTI_SERIES_COLORS[0], "width": 2},
    }

    # Add axis hints for the frontend
    trace["_axis_metadata"] = {
        "x": {"format": "date" if (df[x].dtype in TEMPORAL_DTYPES or x_is_year) else "number"},
        "y": {"format": _get_col_format(y)},
    }

    if total_points > MAX_LINE_POINTS:
        trace["_sampled"] = {
            "original_count": total_points,
            "shown": len(agg_df),
            "method": "lttb",
        }
    return [trace]


def _hydrate_pie(df, config):
    if len(config.columns) == 1:
        # Single column → categorical distribution (group by + count)
        col = config.columns[0]
        if col not in df.columns:
            return []
        counts = (
            df.select(col)
            .drop_nulls()
            .group_by(col)
            .agg(pl.count().alias("cnt"))
            .sort("cnt", descending=True)
            .head(10)  # Top 10 slices to keep pie readable
        )
        if counts.is_empty():
            return []
        labels = [str(v) for v in counts[col].to_list()]
        values = counts["cnt"].to_list()
        return [
            {
                "type": "pie",
                "labels": labels,
                "values": values,
                "name": config.title or col,
            }
        ]
    elif len(config.columns) >= 2:
        labels, values = config.columns[0], config.columns[1]
        agg_df = _safe_aggregate(df, labels, values, config.aggregation)
        if agg_df.is_empty():
            return []
        return [
            {
                "type": "pie",
                "labels": agg_df["x"].to_list(),
                "values": agg_df["y"].to_list(),
                "name": config.title or labels,
            }
        ]
    return []


def _hydrate_histogram(df, config):
    col = config.columns[0]
    if col not in df.columns:
        return []
    # For categorical columns → value counts as bar chart
    if df[col].dtype not in NUMERIC_DTYPES:
        counts = (
            df.select(col)
            .drop_nulls()
            .group_by(col)
            .agg(pl.count().alias("cnt"))
            .sort("cnt", descending=True)
            .head(20)
        )
        if counts.is_empty():
            return []
        return [
            {
                "type": "bar",
                "x": [str(v) for v in counts[col].to_list()],
                "y": counts["cnt"].to_list(),
                "name": config.title or col,
            }
        ]
    vals = df[col].drop_nulls().to_numpy()
    if len(vals) == 0:
        return []
    hist, bins = np.histogram(vals, bins=min(20, max(5, len(vals) // 10)))
    # Humanize bin labels if it's a duration/currency
    col_format = _get_col_format(col)

    def format_bin(v):
        if col_format == "duration":
            ms = v if "ms" in col.lower() or v > 10000 else v * 1000
            s = int((ms / 1000) % 60)
            m = int((ms / (1000 * 60)) % 60)
            return f"{m}:{s:02d}"
        if col_format == "currency":
            return f"${v:,.0f}"
        return f"{v:.1f}"

    bin_labels = [format_bin(bins[i]) for i in range(len(hist))]

    return [
        {
            "type": "bar",
            "x": bin_labels,
            "y": hist.tolist(),
            "name": config.title or col,
            "_axis_metadata": {"x": {"format": col_format}, "y": {"format": "integer"}},
        }
    ]


def _hydrate_box(df, config):
    if len(config.columns) < 2:
        return []
    cat, num = config.columns[0], config.columns[1]
    traces = []
    for c in df[cat].unique().to_list()[:20]:
        group = df.filter(pl.col(cat) == c)[num].drop_nulls().to_list()
        if group:
            traces.append(
                {
                    "type": "box",
                    "name": str(c),
                    "y": group,
                    "boxpoints": "outliers",
                    "whiskerwidth": 0.5,
                }
            )
    return traces


def _build_scatter_multi_y(df, config, numeric_cols):
    """Build scatter chart with multiple Y columns as separate traces."""
    x_col = config.columns[0]
    max_points = 500

    traces = []
    for i, y_col in enumerate(numeric_cols[:MAX_GROUP_SERIES]):
        df_clean = df.select([x_col, y_col]).drop_nulls()
        if len(df_clean) > max_points:
            df_clean = df_clean.sample(n=max_points, seed=42)

        pairs = [(row[x_col], row[y_col]) for row in df_clean.iter_rows(named=True)]
        if not pairs:
            continue
        xs, ys = zip(*pairs)
        color = MULTI_SERIES_COLORS[i % len(MULTI_SERIES_COLORS)]
        traces.append(
            {
                "type": "scatter",
                "mode": "markers",
                "name": y_col,
                "x": list(xs),
                "y": list(ys),
                "marker": {"color": color, "size": 6},
                "_axis_metadata": {
                    "x": {"format": _get_col_format(x_col)},
                    "y": {"format": _get_col_format(y_col)},
                },
            }
        )
    logger.info(f"scatter_multi_y: {len(traces)} traces for {numeric_cols}")
    return traces


def _build_scatter_by_group(df, config, group_col):
    """Build scatter chart with points colored by group column."""
    x_col = config.columns[0]
    y_col = config.columns[1] if len(config.columns) > 1 else None
    if not y_col or y_col not in df.columns:
        return []

    group_totals = (
        df.group_by(group_col)
        .agg(pl.count().alias("_cnt"))
        .sort("_cnt", descending=True)
        .head(MAX_GROUP_SERIES)
    )
    top_groups = group_totals[group_col].to_list()
    if not top_groups:
        return []

    max_points = 500
    traces = []
    for i, grp_val in enumerate(top_groups):
        grp_df = df.filter(pl.col(group_col) == grp_val).select([x_col, y_col]).drop_nulls()
        if len(grp_df) > max_points:
            grp_df = grp_df.sample(n=max_points, seed=42)

        pairs = [(row[x_col], row[y_col]) for row in grp_df.iter_rows(named=True)]
        if not pairs:
            continue
        xs, ys = zip(*pairs)
        color = MULTI_SERIES_COLORS[i % len(MULTI_SERIES_COLORS)]
        traces.append(
            {
                "type": "scatter",
                "mode": "markers",
                "name": str(grp_val),
                "x": list(xs),
                "y": list(ys),
                "marker": {"color": color, "size": 6},
                "_axis_metadata": {
                    "x": {"format": _get_col_format(x_col)},
                    "y": {"format": _get_col_format(y_col)},
                },
                "_group_by": group_col,
            }
        )
    logger.info(f"scatter_by_group: {len(traces)} traces for group_col='{group_col}'")
    return traces


def _hydrate_scatter(df, config):
    MAX_SCATTER_POINTS = 2000

    group_col = _resolve_group_by(config)
    if group_col and group_col in df.columns:
        return _build_scatter_by_group(df, config, group_col)

    if len(config.columns) >= 3:
        numeric_cols = [
            c for c in config.columns[1:] if c in df.columns and df[c].dtype in NUMERIC_DTYPES
        ]
        if len(numeric_cols) >= 2:
            return _build_scatter_multi_y(df, config, numeric_cols)

    x, y = config.columns[0], config.columns[1]
    color = config.columns[2] if len(config.columns) > 2 else None

    total_rows = len(df)
    if total_rows > MAX_SCATTER_POINTS:
        df = df.sample(n=MAX_SCATTER_POINTS, seed=42)
        logger.info(f"Scatter chart sampled: {total_rows:,} → {MAX_SCATTER_POINTS} points")

    if color:
        triples = [
            (xv, yv, cv)
            for xv, yv, cv in zip(df[x], df[y], df[color])
            if pd.notna(xv) and pd.notna(yv) and pd.notna(cv)
        ]
        if not triples:
            return []
        xs, ys, cs = zip(*triples)
        trace = {
            "type": "scatter",
            "mode": "markers",
            "x": list(xs),
            "y": list(ys),
            "marker": {"color": list(cs)},
            "name": config.title or f"{y} vs {x}",
            "_axis_metadata": {
                "x": {"format": _get_col_format(x)},
                "y": {"format": _get_col_format(y)},
                "color": {"format": _get_col_format(color)},
            },
        }
    else:
        pairs = [(xv, yv) for xv, yv in zip(df[x], df[y]) if pd.notna(xv) and pd.notna(yv)]
        if not pairs:
            return []
        xs, ys = zip(*pairs)
        xs_list, ys_list = list(xs), list(ys)

        # Add jitter when axis values are low-cardinality integers (vertical stripes problem)
        rng = np.random.default_rng(42)
        x_unique = len(set(xs_list))
        if x_unique < len(xs_list) * 0.3 and all(
            isinstance(v, (int, float)) and float(v) == int(float(v)) for v in xs_list[:100]
        ):
            jitter_scale = max(0.2, (max(xs_list) - min(xs_list)) / x_unique * 0.15)
            xs_list = [v + rng.uniform(-jitter_scale, jitter_scale) for v in xs_list]
        y_unique = len(set(ys_list))
        if y_unique < len(ys_list) * 0.3 and all(
            isinstance(v, (int, float)) and float(v) == int(float(v)) for v in ys_list[:100]
        ):
            jitter_scale = max(0.2, (max(ys_list) - min(ys_list)) / y_unique * 0.15)
            ys_list = [v + rng.uniform(-jitter_scale, jitter_scale) for v in ys_list]

        trace = {
            "type": "scatter",
            "mode": "markers",
            "x": xs_list,
            "y": ys_list,
            "name": config.title or f"{y} vs {x}",
            "_axis_metadata": {
                "x": {"format": _get_col_format(x)},
                "y": {"format": _get_col_format(y)},
            },
        }

    if total_rows > MAX_SCATTER_POINTS:
        trace["_sampled"] = {"original_count": total_rows, "shown": MAX_SCATTER_POINTS}
    return [trace]


def _hydrate_heatmap(df, config):
    # Supports:
    # 1) x + y + z (numeric z) -> aggregated matrix
    # 2) x + y only -> frequency/count matrix
    # 3) fallback -> numeric correlation heatmap
    if not config.columns:
        return _hydrate_correlation_heatmap(df)

    x = config.columns[0] if len(config.columns) >= 1 else None
    y = config.columns[1] if len(config.columns) >= 2 else None
    z = config.columns[2] if len(config.columns) >= 3 else None

    if not x or not y or x not in df.columns or y not in df.columns:
        return _hydrate_correlation_heatmap(df)

    # Keep matrix size bounded for readability/performance.
    MAX_X_CATEGORIES = 35
    MAX_Y_CATEGORIES = 35

    try:
        base = df.select([c for c in [x, y, z] if c in df.columns]).drop_nulls(subset=[x, y])
        if base.is_empty():
            return []

        # Trim very high-cardinality dimensions to top categories by frequency.
        x_counts = base.group_by(x).agg(pl.count().alias("cnt")).sort("cnt", descending=True)
        y_counts = base.group_by(y).agg(pl.count().alias("cnt")).sort("cnt", descending=True)
        top_x = x_counts.head(MAX_X_CATEGORIES)[x].to_list()
        top_y = y_counts.head(MAX_Y_CATEGORIES)[y].to_list()
        base = base.filter(pl.col(x).is_in(top_x) & pl.col(y).is_in(top_y))
        if base.is_empty():
            return []

        use_numeric_z = bool(z and z in base.columns and base[z].dtype in NUMERIC_DTYPES)
        if use_numeric_z:
            if config.aggregation == AggregationType.COUNT:
                agg_expr = pl.count().alias("value")
            elif config.aggregation == AggregationType.MEAN:
                agg_expr = pl.mean(z).alias("value")
            elif config.aggregation == AggregationType.NUNIQUE:
                agg_expr = pl.n_unique(z).alias("value")
            elif config.aggregation == AggregationType.FIRST:
                agg_expr = pl.first(z).alias("value")
            else:
                agg_expr = pl.sum(z).alias("value")
        else:
            # Common AI output: heatmap with only x/y categories (no numeric z).
            agg_expr = pl.count().alias("value")

        grouped = base.group_by([y, x]).agg(agg_expr)
        if grouped.is_empty():
            return []

        pivot = grouped.pivot(
            index=y, columns=x, values="value", aggregate_function="first"
        ).fill_null(0)
        x_vals = [str(c) for c in pivot.columns if c != y]
        y_vals = [str(v) for v in pivot[y].to_list()]
        z_vals = pivot.select(pl.exclude(y)).to_numpy().tolist()
        if not x_vals or not y_vals or not z_vals:
            return []

        return [
            {
                "type": "heatmap",
                "x": x_vals,
                "y": y_vals,
                "z": z_vals,
                "colorscale": "Viridis",
            }
        ]
    except Exception as e:
        logger.warning(f"Heatmap matrix generation failed; trying correlation fallback: {e}")
        return _hydrate_correlation_heatmap(df)


def _hydrate_correlation_heatmap(df):
    num_cols = [c for c in df.columns if df[c].dtype in NUMERIC_DTYPES]
    if len(num_cols) < 2:
        return []
    corr = df.select(num_cols).to_pandas().corr().round(2)
    return [
        {
            "type": "heatmap",
            "z": corr.values.tolist(),
            "x": corr.columns.tolist(),
            "y": corr.index.tolist(),
            "colorscale": "RdBu",
        }
    ]


def _hydrate_treemap(df, config):
    group_by = getattr(config, "group_by", None)
    if isinstance(group_by, list):
        # Deduplicate: prevent "duplicate output name" when group_by contains
        # a column already in config.columns[0] — seen with treemap where
        # both config.columns[0] and group_by[0] are the same column.
        path = [config.columns[0]] + [g for g in group_by if g != config.columns[0]]
    elif isinstance(group_by, str):
        path = [config.columns[0], group_by] if group_by != config.columns[0] else [config.columns[0]]
    else:
        path = config.columns[:-1] if len(config.columns) > 1 else [config.columns[0]]

    val_col = config.columns[-1] if config.columns[-1] not in path else config.columns[0]
    # Ensure val_col is numeric if possible, else use count
    if val_col in path:
        val_col = [c for c in df.columns if c not in path and df[c].dtype in NUMERIC_DTYPES]
        val_col = val_col[0] if val_col else "__count__"

    if val_col not in df.columns or df[val_col].dtype not in NUMERIC_DTYPES:
        agg_df = df.group_by(path).agg(pl.count().alias("value"))
    else:
        agg_df = df.group_by(path).agg(pl.sum(val_col).alias("value"))

    rows = agg_df.to_dicts()
    ids, parents, labels, values = [], [], [], []

    for r in rows:
        full_path = "/".join(str(r[p]) for p in path)
        parent = "/".join(full_path.split("/")[:-1]) or "root"
        ids.append(full_path)
        parents.append(parent)
        labels.append(full_path.split("/")[-1])
        values.append(r["value"])

    return [
        {
            "type": "treemap",
            "ids": ids,
            "parents": parents,
            "labels": labels,
            "values": values,
        }
    ]


def _auto_detect_group_column(df, x_col, y_col):
    """Auto-detect a suitable categorical column for grouped/stacked charts when group_by is empty."""
    categorical_cols = []
    for col in df.columns:
        if col in (x_col, y_col):
            continue
        dtype = df[col].dtype
        if dtype in (pl.Utf8, pl.Categorical, pl.Enum):
            cardinality = df[col].n_unique()
            if 2 <= cardinality <= 15:
                categorical_cols.append((col, cardinality))

    if not categorical_cols:
        return None

    # Prefer column with moderate cardinality (5-10 unique values)
    for col, card in categorical_cols:
        if 5 <= card <= 10:
            return col

    # Fallback to lowest cardinality
    categorical_cols.sort(key=lambda x: x[1])
    return categorical_cols[0][0]


def _hydrate_grouped_bar(df, config):
    if len(config.columns) < 2:
        return _hydrate_bar(df, config)
    x_col = config.columns[0]
    y_col = config.columns[1]
    group_col = _resolve_group_by(config)

    # Multi-metric mode: columns = [x, metric1, metric2, metric3, ...]
    # Used when LLM wants to compare multiple y-metrics side-by-side (e.g. Math+Reading+Writing)
    y_cols = [c for c in config.columns[1:] if c in df.columns and df[c].dtype in NUMERIC_DTYPES]
    if len(y_cols) >= 2 and (not group_col or group_col not in df.columns):
        traces = []
        for i, yc in enumerate(y_cols[:MAX_GROUP_SERIES]):
            try:
                agg_df = _safe_aggregate(df, x_col, yc, config.aggregation)
            except HydrationError:
                continue
            if agg_df.is_empty():
                continue
            color = MULTI_SERIES_COLORS[i % len(MULTI_SERIES_COLORS)]
            traces.append(
                {
                    "type": "bar",
                    "x": agg_df["x"].to_list(),
                    "y": agg_df["y"].to_list(),
                    "name": yc.replace("_", " ").title(),
                    "marker": {"color": color},
                    "_axis_metadata": {
                        "x": {"format": "categorical"},
                        "y": {"format": _get_col_format(yc)},
                    },
                }
            )
        if traces:
            logger.info(f"Multi-y grouped_bar: {len(traces)} metrics on x={x_col}")
            return traces

    # Auto-detect a suitable group_by column if not provided
    if not group_col or group_col not in df.columns:
        group_col = _auto_detect_group_column(df, x_col, y_col)
        if not group_col:
            logger.warning(
                f"grouped_bar: no valid group_by (config.group_by={config.group_by}), "
                "falling back to plain bar"
            )
            return _hydrate_bar(df, config)
        logger.info(f"grouped_bar: auto-detected group_by='{group_col}' (was empty in config)")

    return _build_grouped_bar_traces(df, x_col, y_col, group_col, config)


def _hydrate_stacked_bar(df, config):
    """Stacked bar chart — same multi-trace structure as grouped_bar but rendered stacked."""
    if len(config.columns) < 2:
        return _hydrate_bar(df, config)
    x_col = config.columns[0]
    y_col = config.columns[1]
    group_col = _resolve_group_by(config)
    if not group_col or group_col not in df.columns:
        logger.warning(
            f"stacked_bar: no valid group_by (config.group_by={config.group_by}), "
            "falling back to plain bar"
        )
        return _hydrate_bar(df, config)
    traces = _build_grouped_bar_traces(df, x_col, y_col, group_col, config)
    # Tag traces so render.py can set barmode="stack" in the layout
    for tr in traces:
        tr["_stacked"] = True
    return traces


def _hydrate_area(df, config):
    traces = _hydrate_line(df, config)
    if not traces:
        return traces

    group_col = _resolve_group_by(config)
    if group_col and group_col in df.columns:
        for i, trace in enumerate(traces):
            opacity = 0.15 if i > 0 else 0.25
            fill_color = trace.get("line", {}).get("color", MULTI_SERIES_COLORS[0])
            if fill_color.startswith("#"):
                r = int(fill_color[1:3], 16)
                g = int(fill_color[3:5], 16)
                b = int(fill_color[5:7], 16)
                fill_color = f"rgba({r},{g},{b},{opacity})"
            trace["fill"] = "tozeroy"
            trace["fillcolor"] = fill_color
    else:
        traces[0]["fill"] = "tozeroy"
    return traces


def _hydrate_multi_line(df, config):
    """Multi-line chart - multiple y columns plotted against one x column."""
    MAX_LINE_POINTS = 1000

    if len(config.columns) < 3:
        return _hydrate_line(df, config)

    x_col = config.columns[0]
    y_cols = config.columns[1:]

    if x_col not in df.columns:
        return []

    x_is_year = False
    if df[x_col].dtype in NUMERIC_DTYPES:
        x_min, x_max = df[x_col].min(), df[x_col].max()
        if x_min is not None and x_max is not None:
            if 1900 <= x_min <= 2030 and 1900 <= x_max <= 2030:
                x_is_year = True

    traces = []
    for idx, y_col in enumerate(y_cols[:5]):
        if y_col not in df.columns:
            continue

        agg_df = _safe_aggregate(df, x_col, y_col, config.aggregation, sort_mode="x_asc")
        if agg_df.is_empty():
            continue

        total_points = len(agg_df)
        sampled_meta = None
        if total_points > MAX_LINE_POINTS:
            agg_df, _ = _lttb_downsample_df(agg_df, MAX_LINE_POINTS)
            sampled_meta = {
                "original_count": total_points,
                "shown": len(agg_df),
                "method": "lttb",
            }

        x_data = agg_df["x"].to_list()
        if x_is_year:
            x_data = [f"{int(v)}-01-01" for v in x_data]

        color = MULTI_SERIES_COLORS[idx % len(MULTI_SERIES_COLORS)]

        trace = {
            "type": "scatter",
            "mode": "lines",
            "name": y_col,
            "x": x_data,
            "y": agg_df["y"].to_list(),
            "line": {"color": color, "width": 2},
            "_axis_metadata": {
                "x": {
                    "format": "date"
                    if (x_is_year or df[x_col].dtype in TEMPORAL_DTYPES)
                    else "number"
                },
                "y": {"format": _get_col_format(y_col)},
            },
        }
        if sampled_meta:
            trace["_sampled"] = sampled_meta
        traces.append(trace)

    logger.info(f"multi_line: {len(traces)} series")
    return traces


def _hydrate_stacked_area(df, config):
    """Stacked area chart - multiple y columns stacked on top of each other."""
    MAX_LINE_POINTS = 1000

    if len(config.columns) < 3:
        return _hydrate_area(df, config)

    x_col = config.columns[0]
    y_cols = config.columns[1:]

    if x_col not in df.columns:
        return []

    x_is_year = False
    if df[x_col].dtype in NUMERIC_DTYPES:
        x_min, x_max = df[x_col].min(), df[x_col].max()
        if x_min is not None and x_max is not None:
            if 1900 <= x_min <= 2030 and 1900 <= x_max <= 2030:
                x_is_year = True

    traces = []
    cumulative_y = None

    for idx, y_col in enumerate(y_cols[:5]):
        if y_col not in df.columns:
            continue

        agg_df = _safe_aggregate(df, x_col, y_col, config.aggregation, sort_mode="x_asc")
        if agg_df.is_empty():
            continue

        total_points = len(agg_df)
        sampled_meta = None
        if total_points > MAX_LINE_POINTS:
            agg_df, _ = _lttb_downsample_df(agg_df, MAX_LINE_POINTS)
            sampled_meta = {
                "original_count": total_points,
                "shown": len(agg_df),
                "method": "lttb",
            }

        y_data = agg_df["y"].to_list()

        if cumulative_y is not None:
            y_data = [cumulative_y[i] + y_data[i] for i in range(len(y_data))]
        cumulative_y = y_data.copy()

        x_data = agg_df["x"].to_list()
        if x_is_year:
            x_data = [f"{int(v)}-01-01" for v in x_data]

        color = MULTI_SERIES_COLORS[idx % len(MULTI_SERIES_COLORS)]
        opacity = 0.6

        if color.startswith("#"):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            fill_color = f"rgba({r},{g},{b},{opacity})"
        else:
            fill_color = f"rgba(0,122,204,{opacity})"

        trace = {
            "type": "scatter",
            "mode": "lines",
            "name": y_col,
            "x": x_data,
            "y": y_data,
            "line": {"color": color, "width": 1},
            "fill": "tonexty" if idx > 0 else "tozeroy",
            "fillcolor": fill_color,
            "_axis_metadata": {
                "x": {
                    "format": "date"
                    if (x_is_year or df[x_col].dtype in TEMPORAL_DTYPES)
                    else "number"
                },
                "y": {"format": _get_col_format(y_col)},
            },
            "_stacked": True,
        }
        if sampled_meta:
            trace["_sampled"] = sampled_meta
        traces.append(trace)

    logger.info(f"stacked_area: {len(traces)} series")
    return traces


# =====================================================
# NEW CHART TYPE HANDLERS (Phase 1)
# =====================================================


def _hydrate_radar(df, config):
    """Radar/Spider chart - multi-dimensional comparison."""
    if len(config.columns) < 2:
        return []

    cat_col = config.columns[0]
    val_col = config.columns[1]

    if df[val_col].dtype in NUMERIC_DTYPES:
        agg_df = _safe_aggregate(df, cat_col, val_col, config.aggregation)
        if agg_df.is_empty():
            return []
        categories = agg_df["x"].to_list()
        values = agg_df["y"].to_list()
        if not categories:
            return []
        categories.append(categories[0])  # close the loop
        values.append(values[0])
        return [
            {
                "type": "scatterpolar",
                "r": values,
                "theta": categories,
                "fill": "toself",
                "name": val_col,
            }
        ]

    else:
        value_cols = config.columns[1:]
        traces = []
        for _, row in df.head(10).to_pandas().iterrows():
            vals = [row[c] for c in value_cols if c in df.columns]
            if not vals:
                continue
            vals.append(vals[0])  # close the loop
            axes = value_cols + [value_cols[0]]
            traces.append(
                {
                    "type": "scatterpolar",
                    "r": vals,
                    "theta": axes,
                    "fill": "toself",
                    "name": str(row[cat_col]) if cat_col in df.columns else f"Series {len(traces)}",
                }
            )
        return traces[:5]  # cap at 5 overlapping webs for readability


def _hydrate_bubble(df, config):
    """Bubble chart - scatter with size dimension."""
    if len(config.columns) < 3:
        # Need x, y, and size columns
        return _hydrate_scatter(df, config)

    x, y, size = config.columns[0], config.columns[1], config.columns[2]
    color = config.columns[3] if len(config.columns) > 3 else None

    # Filter valid rows
    valid_cols = [x, y, size] + ([color] if color else [])
    valid_rows = df.select(valid_cols).drop_nulls()

    if valid_rows.is_empty():
        return []

    # Normalize size for bubble display
    size_vals = valid_rows[size].to_numpy()
    size_min, size_max = size_vals.min(), size_vals.max()
    if size_max > size_min:
        normalized_size = 10 + 40 * (size_vals - size_min) / (size_max - size_min)
    else:
        normalized_size = [25] * len(size_vals)

    trace = {
        "type": "scatter",
        "mode": "markers",
        "x": valid_rows[x].to_list(),
        "y": valid_rows[y].to_list(),
        "marker": {"size": normalized_size.tolist(), "sizemode": "diameter"},
        "text": [f"{size}: {s:.2f}" for s in size_vals],
    }

    if color and color in valid_rows.columns:
        trace["marker"]["color"] = valid_rows[color].to_list()
        trace["marker"]["colorscale"] = "Viridis"

    return [trace]


def _hydrate_waterfall(df, config):
    """Waterfall chart - cumulative effect visualization."""
    if len(config.columns) < 2:
        return []

    x, y = config.columns[0], config.columns[1]
    agg_df = _safe_aggregate(df, x, y, config.aggregation)

    x_vals = agg_df["x"].to_list()
    y_vals = agg_df["y"].to_list()

    # Determine measure types (relative for all, total for last)
    measures = ["relative"] * len(y_vals)
    if measures:
        measures[-1] = "total"

    return [
        {
            "type": "waterfall",
            "x": x_vals,
            "y": y_vals,
            "measure": measures,
            "connector": {"line": {"color": "rgb(63, 63, 63)"}},
        }
    ]


def _hydrate_funnel(df, config):
    """Funnel chart - stage-based conversion visualization."""
    if len(config.columns) < 2:
        return []

    stage, value = config.columns[0], config.columns[1]
    agg_df = _safe_aggregate(df, stage, value, config.aggregation)

    # Sort by value descending for proper funnel shape
    agg_df = agg_df.sort("y", descending=True)

    return [
        {
            "type": "funnel",
            "y": agg_df["x"].to_list(),
            "x": agg_df["y"].to_list(),
            "textinfo": "value+percent initial",
        }
    ]


def _hydrate_candlestick(df, config):
    """Candlestick chart - OHLC financial data."""
    # Requires: date, open, high, low, close columns
    if len(config.columns) < 5:
        logger.warning("Candlestick requires 5 columns: date, open, high, low, close")
        return _hydrate_line(df, config)

    date_col, open_col, high_col, low_col, close_col = config.columns[:5]

    # Validate columns exist
    for col in [date_col, open_col, high_col, low_col, close_col]:
        if col not in df.columns:
            logger.warning(f"Missing column {col} for candlestick")
            return _hydrate_line(df, config)

    # Sort by date
    df_sorted = df.sort(date_col)

    return [
        {
            "type": "candlestick",
            "x": df_sorted[date_col].to_list(),
            "open": df_sorted[open_col].to_list(),
            "high": df_sorted[high_col].to_list(),
            "low": df_sorted[low_col].to_list(),
            "close": df_sorted[close_col].to_list(),
        }
    ]


def _hydrate_violin(df, config):
    """Violin plot - distribution shape visualization."""
    if len(config.columns) < 2:
        return []

    cat, num = config.columns[0], config.columns[1]
    traces = []

    for c in df[cat].unique().to_list()[:20]:
        group = df.filter(pl.col(cat) == c)[num].drop_nulls().to_list()
        if group:
            traces.append(
                {
                    "type": "violin",
                    "name": str(c),
                    "y": group,
                    "box": {"visible": True},
                    "meanline": {"visible": True},
                    "points": "all",
                    "jitter": 0.3,
                    "pointpos": -1.5,
                    "scalemode": "width",
                    "spanmode": "soft",
                }
            )

    return traces


def _hydrate_sunburst(df, config):
    """Sunburst chart - hierarchical radial visualization."""
    group_by = getattr(config, "group_by", None)
    if isinstance(group_by, list):
        # Deduplicate: prevent "duplicate output name" when group_by contains
        # a column already in config.columns[0]
        path = [config.columns[0]] + [g for g in group_by if g != config.columns[0]]
    elif isinstance(group_by, str):
        path = [config.columns[0], group_by] if group_by != config.columns[0] else [config.columns[0]]
    else:
        path = config.columns[:-1] if len(config.columns) > 1 else [config.columns[0]]

    val_col = config.columns[-1] if config.columns[-1] not in path else config.columns[0]
    if val_col in path:
        val_col = [c for c in df.columns if c not in path and df[c].dtype in NUMERIC_DTYPES]
        val_col = val_col[0] if val_col else "__count__"

    if val_col not in df.columns or df[val_col].dtype not in NUMERIC_DTYPES:
        agg_df = df.group_by(path).agg(pl.count().alias("value"))
    else:
        agg_df = df.group_by(path).agg(pl.sum(val_col).alias("value"))

    rows = agg_df.to_dicts()
    ids, parents, labels, values = [], [], [], []

    # ── Step 1: emit intermediate parent nodes first ──
    # Plotly requires every entry in parents[] to also exist in ids[].
    # The old code only added leaf nodes, so "Furniture" was referenced
    # as a parent but never existed as an id → blank/broken chart.
    seen_parents = set()
    for r in rows:
        parts = [str(r[p]) for p in path]
        for depth in range(1, len(parts)):
            node_id = "/".join(parts[:depth])
            if node_id not in seen_parents:
                seen_parents.add(node_id)
                ids.append(node_id)
                parents.append("/".join(parts[: depth - 1]) if depth > 1 else "")
                labels.append(parts[depth - 1])
                values.append(0)  # Plotly sums from children when branchvalues="total"

    # ── Step 2: emit leaf nodes (same as before) ──
    for r in rows:
        full_path = "/".join(str(r[p]) for p in path)
        parent = "/".join(full_path.split("/")[:-1]) or ""
        ids.append(full_path)
        parents.append(parent)
        labels.append(full_path.split("/")[-1])
        values.append(r["value"])

    return [
        {
            "type": "sunburst",
            "ids": ids,
            "parents": parents,
            "labels": labels,
            "values": values,
            "branchvalues": "total",
        }
    ]


# =====================================================
# NEW CHART TYPE HANDLERS (Phase 2) — ECharts-native Plotly fallbacks
# =====================================================


def _hydrate_donut(df, config):
    """
    Donut chart — same semantics as pie, with a center hole.
    The render.py `_patch_traces` sets `hole: 0.65` for the donut visual.
    """
    return _hydrate_pie(df, config)


def _hydrate_map(df, config):
    """
    Map chart — geographic data visualization.
    Supports:
    1) Lat/Lon columns → scattergeo points
    2) Location name + value → scattergeo location-mode
    3) Fallback → choropleth or bar
    """
    if not config.columns:
        return []

    cols = config.columns
    col_lower = [c.lower() for c in cols]

    # Detect lat/lon pairs by name heuristic
    lat_idx = next((i for i, c in enumerate(col_lower) if c in ("lat", "latitude", "lat_")), None)
    lon_idx = next((i for i, c in enumerate(col_lower) if c in ("lon", "long", "longitude", "lng", "lon_")), None)

    if lat_idx is not None and lon_idx is not None:
        lat_col, lon_col = cols[lat_idx], cols[lon_idx]
        if lat_col in df.columns and lon_col in df.columns:
            valid = df.select([lat_col, lon_col]).drop_nulls()
            if not valid.is_empty():
                trace = {
                    "type": "scattergeo",
                    "mode": "markers",
                    "lat": valid[lat_col].to_list(),
                    "lon": valid[lon_col].to_list(),
                    "marker": {"color": "#0ED2D2", "size": 8},
                    "name": config.title or "Map",
                }
                # Add color dimension if a 3rd numeric column exists
                if len(cols) > 2:
                    val_col = cols[2]
                    if val_col in df.columns and df[val_col].dtype in NUMERIC_DTYPES:
                        # Select all three cols together to keep row alignment
                        valid_with_val = df.select([lat_col, lon_col, val_col]).drop_nulls()
                        trace["marker"]["color"] = valid_with_val[val_col].to_list()
                        trace["marker"]["colorscale"] = "Viridis"
                        trace["marker"]["showscale"] = True
                        trace["lat"] = valid_with_val[lat_col].to_list()
                        trace["lon"] = valid_with_val[lon_col].to_list()
                        trace["text"] = [f"{val_col}: {v}" for v in valid_with_val[val_col].to_list()]
                return [trace]

    # Location name + value → scattergeo location-mode
    if len(cols) >= 2:
        loc_col, val_col = cols[0], cols[1]
        if loc_col in df.columns and val_col in df.columns:
            agg_df = _safe_aggregate(df, loc_col, val_col, config.aggregation)
            if not agg_df.is_empty():
                first_loc = str(agg_df["x"][0])
                location_mode = "ISO-3" if len(first_loc) == 3 else "country names"
                return [{
                    "type": "scattergeo",
                    "mode": "markers",
                    "locations": agg_df["x"].to_list(),
                    "locationmode": location_mode,
                    "text": agg_df["x"].to_list(),
                    "marker": {
                        "color": agg_df["y"].to_list(),
                        "colorscale": "Viridis",
                        "showscale": True,
                        "size": 12,
                        "colorbar": {"title": val_col},
                    },
                    "name": config.title or loc_col,
                }]

    return _hydrate_bar(df, config)


def _hydrate_pictorial_bar(df, config):
    """
    Pictorial bar — ECharts native (uses SVG images for bars).
    Plotly fallback: standard bar chart tagged for frontend awareness.
    """
    traces = _hydrate_bar(df, config)
    for tr in traces:
        tr["_is_pictorial"] = True
        # Use distinctive marker to hint at pictorial intent
        if "marker" not in tr:
            tr["marker"] = {}
        tr["marker"]["opacity"] = 0.85
        tr["marker"]["line"] = {"width": 1, "color": "rgba(0,0,0,0.2)"}
    return traces


def _hydrate_effect_scatter(df, config):
    """
    Effect scatter — ECharts native (animated ripple scatter).
    Plotly fallback: standard scatter with larger markers and tagging.
    """
    traces = _hydrate_scatter(df, config)
    for tr in traces:
        tr["_is_effect_scatter"] = True
        if "marker" not in tr:
            tr["marker"] = {}
        # Slightly larger markers with glow-like border
        tr["marker"].setdefault("size", 10)
        tr["marker"]["line"] = {"width": 2, "color": "rgba(14,210,210,0.6)"}
        tr["marker"]["opacity"] = 0.8
    return traces


def _hydrate_graph(df, config):
    """
    Network/graph visualization — force-directed node-link diagram.
    Plotly fallback: scatter for nodes + line segments for edges.

    Config:
      columns[0] = source node column
      columns[1] = target node column
      columns[2] (optional) = edge weight/value column
    """
    if len(config.columns) < 2:
        return _hydrate_scatter(df, config)

    src_col, tgt_col = config.columns[0], config.columns[1]
    val_col = config.columns[2] if len(config.columns) > 2 else None

    if src_col not in df.columns or tgt_col not in df.columns:
        return _hydrate_scatter(df, config)

    # Collect edges
    edge_rows = df.select([c for c in [src_col, tgt_col, val_col] if c in df.columns]).drop_nulls()
    if edge_rows.is_empty():
        return []

    # Build node set
    sources = edge_rows[src_col].to_list()
    targets = edge_rows[tgt_col].to_list()
    all_nodes = list(dict.fromkeys([str(s) for s in sources] + [str(t) for t in targets]))
    node_indices = {name: i for i, name in enumerate(all_nodes)}

    # Circular layout for nodes (spread evenly around a circle)
    n = len(all_nodes)
    radius = max(n * 0.5, 3)
    angle_step = 2 * math.pi / max(n, 1)
    node_positions = {}
    for i, name in enumerate(all_nodes):
        angle = i * angle_step - math.pi / 2  # start at top
        node_positions[name] = (
            math.cos(angle) * radius,
            math.sin(angle) * radius,
        )

    # Edge traces as lines
    edge_x, edge_y = [], []
    for i in range(len(sources)):
        sx, sy = node_positions[str(sources[i])]
        tx, ty = node_positions[str(targets[i])]
        edge_x.extend([sx, tx, None])
        edge_y.extend([sy, ty, None])

    traces = []

    # Edge trace
    edge_trace = {
        "type": "scatter",
        "mode": "lines",
        "x": edge_x,
        "y": edge_y,
        "line": {"color": "rgba(100,100,100,0.3)", "width": 1},
        "hoverinfo": "none",
        "showlegend": False,
        "name": "edges",
    }
    traces.append(edge_trace)

    # Node trace
    node_x = [node_positions[name][0] for name in all_nodes]
    node_y = [node_positions[name][1] for name in all_nodes]
    node_labels = list(all_nodes)

    # Compute node sizes based on degree (count of connections)
    degree = {n: 0 for n in all_nodes}
    for s, t in zip(sources, targets):
        degree[str(s)] += 1
        degree[str(t)] += 1
    node_sizes = [10 + min(degree[n] * 3, 30) for n in all_nodes]

    node_trace = {
        "type": "scatter",
        "mode": "markers+text",
        "x": node_x,
        "y": node_y,
        "text": node_labels,
        "textposition": "top center",
        "hovertext": [f"{n} (degree: {degree[n]})" for n in all_nodes],
        "hoverinfo": "text",
        "marker": {
            "size": node_sizes,
            "color": "#0ED2D2",
            "line": {"width": 1, "color": "#ffffff"},
        },
        "showlegend": False,
        "name": "nodes",
    }
    traces.append(node_trace)

    for tr in traces:
        tr["_is_graph"] = True

    return traces


def _hydrate_sankey(df, config):
    """
    Sankey diagram — flow visualization between categories.
    Uses native Plotly `sankey` trace type.

    Config:
      columns[0] = source category column
      columns[1] = target category column
      columns[2] (optional) = flow value column
    """
    if len(config.columns) < 2:
        return _hydrate_bar(df, config)

    src_col, tgt_col = config.columns[0], config.columns[1]
    val_col = config.columns[2] if len(config.columns) > 2 else None

    if src_col not in df.columns or tgt_col not in df.columns:
        return _hydrate_bar(df, config)

    # Aggregate flows
    group_cols = [src_col, tgt_col]
    if val_col and val_col in df.columns and df[val_col].dtype in NUMERIC_DTYPES:
        if config.aggregation == AggregationType.COUNT:
            agg_expr = pl.count().alias("flow_value")
        elif config.aggregation == AggregationType.MEAN:
            agg_expr = pl.mean(val_col).alias("flow_value")
        else:
            agg_expr = pl.sum(val_col).alias("flow_value")
    else:
        agg_expr = pl.count().alias("flow_value")

    flow_df = (
        df.group_by(group_cols)
        .agg(agg_expr)
        .sort("flow_value", descending=True)
        .head(100)  # Keep sankey readable
    )

    if flow_df.is_empty():
        return []

    # Build node list (deduplicated, in order of appearance)
    all_nodes = []
    seen = set()
    for row in flow_df.iter_rows(named=True):
        for col in [src_col, tgt_col]:
            name = str(row[col])
            if name not in seen:
                seen.add(name)
                all_nodes.append(name)

    node_map = {name: i for i, name in enumerate(all_nodes)}

    # Build links
    source_indices, target_indices, values = [], [], []
    for row in flow_df.iter_rows(named=True):
        source_indices.append(node_map[str(row[src_col])])
        target_indices.append(node_map[str(row[tgt_col])])
        values.append(float(row["flow_value"]))

    return [{
        "type": "sankey",
        "orientation": "h",
        "node": {
            "pad": 15,
            "thickness": 20,
            "line": {"color": "rgba(0,0,0,0.2)", "width": 0.5},
            "label": all_nodes,
            "color": "rgba(14,210,210,0.8)",
        },
        "link": {
            "source": source_indices,
            "target": target_indices,
            "value": values,
        },
    }]


def _hydrate_parallel(df, config):
    """
    Parallel coordinates chart — multi-dimensional data analysis.
    Uses native Plotly `parcoords` trace type.

    All columns become parallel axes with dimensions.
    """
    if len(config.columns) < 2:
        return _hydrate_bar(df, config)

    valid_cols = [c for c in config.columns if c in df.columns]
    if len(valid_cols) < 2:
        return _hydrate_bar(df, config)

    # Parcoords requires numeric dimensions — filter and encode categoricals
    dimensions = []
    color_col = None
    color_values = None
    for col in valid_cols:
        if df[col].dtype in NUMERIC_DTYPES:
            dim = {
                "label": col,
                "values": df[col].to_list(),
                "range": [float(df[col].min()), float(df[col].max())],
            }
            dimensions.append(dim)
            # Use first numeric column encountered as color
            if color_col is None:
                color_col = col
                color_values = df[col].to_list()
        elif df[col].dtype in (pl.Utf8, pl.Categorical):
            # Encode categoricals as integer codes with tickvals/ticktext
            unique_vals = df[col].unique().to_list()
            code_map = {v: i for i, v in enumerate(unique_vals)}
            codes = [code_map.get(v, -1) for v in df[col].to_list()]
            dim = {
                "label": col,
                "values": codes,
                "tickvals": list(range(len(unique_vals))),
                "ticktext": [str(v) for v in unique_vals],
            }
            dimensions.append(dim)

    if len(dimensions) < 2:
        # Not enough numeric or categorical dimensions for parallel coords
        return _hydrate_bar(df, config)

    trace = {
        "type": "parcoords",
        "dimensions": dimensions,
        "name": config.title or "Parallel Coordinates",
    }
    if color_values is not None:
        trace["line"] = {
            "color": color_values,
            "colorscale": "Viridis",
            "showscale": True,
        }

    return [trace]


def _hydrate_lines(df, config):
    """
    Lines chart — polyline trail visualization (ECharts native).
    Plotly fallback: multi_line chart with enhanced markers.
    """
    # lines behaves like multi_line with markers
    traces = _hydrate_multi_line(df, config)
    for tr in traces:
        tr["_is_lines"] = True
        if tr.get("mode") == "lines":
            tr["mode"] = "lines+markers"
        if "marker" not in tr:
            tr["marker"] = {}
        tr["marker"].setdefault("size", 5)
        tr["marker"]["opacity"] = 0.9
        tr["marker"]["line"] = {"width": 1, "color": "rgba(255,255,255,0.5)"}
    return traces


def _hydrate_tree(df, config):
    """
    Tree chart — hierarchical tree visualization (ECharts native).
    Plotly fallback: treemap with the same hierarchical structure.
    """
    return _hydrate_treemap(df, config)


def _hydrate_theme_river(df, config):
    """
    Theme river — stacked area chart over temporal axis (ECharts native).
    Plotly fallback: stacked area chart with auto-group detection when < 3 cols.
    """
    if len(config.columns) >= 3:
        return _hydrate_stacked_area(df, config)

    # With only 2 columns (time + value), auto-detect a group column
    # so we still produce a multi-stream stacked area
    if len(config.columns) == 2:
        x_col, y_col = config.columns[0], config.columns[1]
        group_col = _auto_detect_group_column(df, x_col, y_col)
        if group_col:
            # Build a stack by grouping detected column
            return _build_multi_line_traces(df, x_col, y_col, group_col, config)

    return _hydrate_area(df, config)


def _hydrate_gauge(df, config):
    """Gauge chart - single KPI meter visualization."""
    if not config.columns:
        return []

    col = config.columns[0]
    if col not in df.columns:
        return []

    # Calculate the value based on aggregation
    if config.aggregation == AggregationType.COUNT:
        value = len(df)
    elif config.aggregation == AggregationType.SUM:
        value = df[col].sum()
    elif config.aggregation == AggregationType.MEAN:
        value = df[col].mean()
    else:
        value = df[col].sum()

    # Determine range based on data
    if df[col].dtype in NUMERIC_DTYPES:
        max_val = float(df[col].max()) * 1.2  # 20% headroom
    else:
        max_val = value * 2

    return [
        {
            "type": "indicator",
            "mode": "gauge+number",
            "value": float(value) if value is not None else 0,
            "gauge": {
                "axis": {"range": [0, max_val]},
                "bar": {"color": "#3b82f6"},
                "steps": [
                    {"range": [0, max_val * 0.5], "color": "#dcfce7"},
                    {"range": [max_val * 0.5, max_val * 0.8], "color": "#fef9c3"},
                    {"range": [max_val * 0.8, max_val], "color": "#fee2e2"},
                ],
            },
            "title": {"text": config.title},
        }
    ]


def _hydrate_bullet(df, config):
    """Bullet chart - indicator performance visualization."""
    if not config.columns:
        return []

    val_col = config.columns[0]
    target_col = config.columns[1] if len(config.columns) > 1 else None

    if val_col not in df.columns:
        return []

    # Calculate current value
    if config.aggregation == AggregationType.COUNT:
        value = len(df)
    elif config.aggregation == AggregationType.SUM:
        value = df[val_col].sum()
    elif config.aggregation == AggregationType.MEAN:
        value = df[val_col].mean()
    else:
        value = df[val_col].sum()

    # Calculate target value
    if target_col and target_col in df.columns:
        target = df[target_col].mean()  # Use mean of target column
    else:
        # Heuristic target: if no target column, use 110% of mean or a safe multiplier
        avg = df[val_col].mean() if df[val_col].dtype in NUMERIC_DTYPES else value
        target = (avg * 1.1) if avg else (float(value) * 1.1)

    max_val = max(float(value or 0), float(target or 0)) * 1.2

    return [
        {
            "type": "indicator",
            "mode": "number+gauge+delta",
            "value": float(value) if value is not None else 0,
            "delta": {"reference": float(target)},
            "gauge": {
                "shape": "bullet",
                "axis": {"range": [None, max_val]},
                "threshold": {
                    "line": {"color": "red", "width": 2},
                    "thickness": 0.75,
                    "value": float(target),
                },
                "steps": [
                    {"range": [0, max_val * 0.5], "color": "lightgray"},
                    {"range": [max_val * 0.5, max_val * 0.8], "color": "gray"},
                ],
                "bar": {"color": "#6366f1"},
            },
            "title": {"text": config.title},
        }
    ]


def _hydrate_choropleth(df, config):
    """Choropleth map - geographic data visualization."""
    if len(config.columns) < 2:
        return []

    loc_col, val_col = config.columns[0], config.columns[1]

    if loc_col not in df.columns or val_col not in df.columns:
        return []

    agg_df = _safe_aggregate(df, loc_col, val_col, config.aggregation)
    if agg_df.is_empty():
        return []

    # Detect location format (very basic)
    first_val = str(agg_df["x"][0])
    location_mode = "ISO-3" if len(first_val) == 3 else "country names"

    return [
        {
            "type": "choropleth",
            "locations": agg_df["x"].to_list(),
            "z": agg_df["y"].to_list(),
            "locationmode": location_mode,
            "colorscale": "Viridis",
            "autocolorscale": False,
            "marker": {"line": {"color": "rgb(255,255,255)", "width": 1}},
            "colorbar": {"title": val_col, "thickness": 10},
        }
    ]


def hydrate_pivot_table(df, config):
    """Pivot Table - multi-dimensional aggregated matrix."""
    # config.columns[0] = row
    # config.columns[1] = col
    # config.columns[2] = value
    cols = getattr(config, "columns", [])
    if len(cols) < 3:
        return {"error": "Pivot table requires row, column, and value fields."}

    row, col, val = cols[0], cols[1], cols[2]

    try:
        # Convert to pandas for pivot_table (polars pivot is a bit different)
        pdf = df.to_pandas()
        agg_func = (
            config.aggregation.value if hasattr(config.aggregation, "value") else config.aggregation
        )
        if agg_func == "nunique":
            agg_func = "nunique"
        elif agg_func == "count":
            agg_func = "count"

        pivot = pdf.pivot_table(index=row, columns=col, values=val, aggfunc=agg_func).fillna(0)

        return {
            "rows": pivot.index.tolist(),
            "columns": pivot.columns.tolist(),
            "data": pivot.values.tolist(),
            "row_label": row,
            "col_label": col,
            "value_label": f"{agg_func} of {val}",
        }
    except Exception as e:
        logger.error(f"Pivot table hydration failed: {e}")
        return {"error": str(e)}


def hydrate_anomaly_feed(df, config):
    """Anomaly Feed - automatic outlier detection and reporting."""
    anomalies = []

    # Use specified columns if available, otherwise scan numeric columns
    scan_cols = getattr(config, "columns", None)
    if not scan_cols:
        scan_cols = [c for c in df.columns if df[c].dtype in NUMERIC_DTYPES]

    for col in scan_cols[:5]:  # Scan up to 5 cols
        if col not in df.columns:
            continue

        series = df[col].drop_nulls()
        if len(series) < 10:
            continue

        try:
            mean = series.mean()
            std = series.std()
            if std == 0 or std is None:
                continue

            # Simple Z-score detection
            outliers = (
                df.filter((pl.col(col) - mean).abs() > (3 * std))
                .sort((pl.col(col) - mean).abs(), descending=True)
                .head(3)
            )

            for row in outliers.to_dicts():
                val = row[col]
                anomalies.append(
                    {
                        "column": col,
                        "value": val,
                        "description": f"Abnormally {'high' if val > mean else 'low'} value in {col}",
                        "severity": "high" if abs(val - mean) > 4 * std else "medium",
                        "timestamp": str(row.get("date", row.get("timestamp", row.get("id", "")))),
                    }
                )
        except Exception as e:
            logger.warning(f"Anomaly detection failed for column {col}: {e}")

    return sorted(anomalies, key=lambda x: 1 if x["severity"] == "high" else 0, reverse=True)[:10]


def _hydrate_fallback(df, config):
    temp = ChartConfig(
        type=config.type,
        title=config.title,
        chart_type=ChartType.BAR,
        columns=config.columns[:2],
        aggregation=config.aggregation,
        span=config.span,
    )
    return _hydrate_bar(df, temp)


def hydrate_chart_extras(
    df,
    chart_config: dict,
) -> dict:
    """
    Compute enterprise annotation data for charts based on ChartItemV2 specs.

    Returns dict with:
    - reference_line_value: computed value for reference line (if show_reference_line=true)
    - outlier_indices: indices of outlier points (if highlight_outliers=true)
    - computed_key_numbers: enriched key_numbers with actual values from data

    Args:
        df: Polars DataFrame
        chart_config: ChartItemV2 dict with all 7 layers
    """
    extras = {
        "reference_line_value": None,
        "reference_line_label": None,
        "outlier_indices": [],
        "computed_key_numbers": [],
    }

    y_col = chart_config.get("y")
    if not y_col or y_col not in df.columns:
        return extras

    # Compute reference line value
    if chart_config.get("show_reference_line", False):
        ref_type = chart_config.get("reference_type", "none")
        if ref_type != "none" and df[y_col].dtype in NUMERIC_DTYPES:
            col_data = df[y_col].drop_nulls().cast(pl.Float64)
            if len(col_data) > 0:
                if ref_type == "mean":
                    extras["reference_line_value"] = float(col_data.mean())
                    extras["reference_line_label"] = "Mean"
                elif ref_type == "median":
                    extras["reference_line_value"] = float(col_data.median())
                    extras["reference_line_label"] = "Median"
                elif ref_type == "p75":
                    extras["reference_line_value"] = float(col_data.quantile(0.75))
                    extras["reference_line_label"] = "75th Percentile"
                elif ref_type == "p90":
                    extras["reference_line_value"] = float(col_data.quantile(0.90))
                    extras["reference_line_label"] = "90th Percentile"

    # Compute outlier indices
    if chart_config.get("highlight_outliers", False) and df[y_col].dtype in NUMERIC_DTYPES:
        col_data = df[y_col].drop_nulls().cast(pl.Float64)
        if len(col_data) > 10:
            mean_val = float(col_data.mean())
            std_val = float(col_data.std())
            if std_val > 0:
                threshold_upper = mean_val + 2 * std_val
                threshold_lower = mean_val - 2 * std_val
                outlier_indices = [
                    i
                    for i, v in enumerate(col_data.to_list())
                    if v < threshold_lower or v > threshold_upper
                ]
                extras["outlier_indices"] = outlier_indices[:50]  # Cap at 50 outliers

    # Enrich key_numbers with actual computed values from data
    key_numbers = chart_config.get("key_numbers", [])
    if key_numbers and y_col:
        aggregation = chart_config.get("aggregation", "mean")

        # Compute base aggregations
        col_data = df[y_col].drop_nulls()
        if df[y_col].dtype in NUMERIC_DTYPES:
            col_data = col_data.cast(pl.Float64)
            agg_value = _compute_agg_polars(col_data, aggregation)

            for kn in key_numbers:
                if kn.get("value") and (
                    "avg" in kn.get("value", "").lower() or "mean" in kn.get("value", "").lower()
                ):
                    # This is a placeholder that needs actual value
                    kn["_computed"] = agg_value

        # Try to compute values for group-specific key numbers
        group_by = chart_config.get("group_by")
        if group_by and group_by in df.columns:
            for kn in key_numbers:
                label_lower = kn.get("label", "").lower()
                # Find matching group
                unique_groups = df[group_by].unique().to_list()
                for grp in unique_groups:
                    grp_lower = str(grp).lower()
                    if grp_lower in label_lower:
                        grp_data = df.filter(pl.col(group_by) == grp)[y_col].drop_nulls()
                        if len(grp_data) > 0 and grp_data.dtype in NUMERIC_DTYPES:
                            grp_data = grp_data.cast(pl.Float64)
                            grp_agg = _compute_agg_polars(grp_data, aggregation)
                            kn["_computed"] = grp_agg
                        break

    return extras


def _compute_agg_polars(col_data, aggregation: str) -> float:
    """Compute aggregation on Polars column data."""
    try:
        if aggregation == "sum":
            return float(col_data.sum())
        elif aggregation in ("mean", "avg"):
            return float(col_data.mean())
        elif aggregation == "median":
            return float(col_data.median())
        elif aggregation == "std":
            return float(col_data.std())
        elif aggregation == "percentile_25":
            return float(col_data.quantile(0.25))
        elif aggregation == "percentile_75":
            return float(col_data.quantile(0.75))
        elif aggregation == "count":
            return float(col_data.count())
        elif aggregation == "min":
            return float(col_data.min())
        elif aggregation == "max":
            return float(col_data.max())
        elif aggregation == "count_unique":
            return float(col_data.n_unique())
        else:
            return float(col_data.mean())
    except Exception:
        return 0.0

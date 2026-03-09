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

from db.schemas_dashboard import (
    ChartConfig, AggregationType, ChartType,
    KpiConfig, TableConfig
)
from services.charts.chart_definitions import CHART_DEFINITIONS_BY_ID

logger = logging.getLogger(__name__)

NUMERIC_DTYPES = pl.NUMERIC_DTYPES
CATEGORICAL_DTYPES = {pl.Utf8, pl.Categorical, pl.Boolean}
TEMPORAL_DTYPES = {pl.Datetime, pl.Date}


class HydrationError(Exception):
    pass


def validate_config(df: pl.DataFrame, config: ChartConfig) -> None:
    # Guard: default to "bar" if chart_type is None
    if config.chart_type is None:
        logger.warning("chart_type is None — defaulting to 'bar'")
        config.chart_type = "bar"

    # Handle both string and enum types
    chart_type_str = config.chart_type.value if hasattr(config.chart_type, 'value') else config.chart_type
    chart_def = CHART_DEFINITIONS_BY_ID.get(chart_type_str, {})
    rules = chart_def.get("rules", {})

    safe_cols = [c for c in config.columns if c in df.columns]
    if len(safe_cols) < len(config.columns):
        config.columns = safe_cols

    # Chart types whose handlers have built-in fallback logic for fewer columns:
    #   pie       → 1 col: value_counts distribution
    #   heatmap   → <3 cols: correlation heatmap fallback
    #   histogram → 1 col: standard histogram
    #   treemap   → 1 col: group-by count
    HANDLER_MIN_COLUMNS = {
        "pie": 1,
        "pie_chart": 1,
        "donut": 1,
        "heatmap": 0,
        "histogram": 1,
        "treemap": 1,
    }
    effective_min = HANDLER_MIN_COLUMNS.get(chart_type_str, rules.get("min_columns", 1))

    if not config.columns and effective_min > 0:
        raise HydrationError("No valid columns after safety check.")

    if len(config.columns) < effective_min:
        raise HydrationError("Insufficient columns for chart type.")

    num_needed = sum(1 for req in rules.get("data_types", []) if req["type"] == "numeric")
    actual_num = sum(1 for c in config.columns if df[c].dtype in NUMERIC_DTYPES)
    if actual_num < num_needed:
        logger.warning("Not enough numeric columns for chart type.")


def _safe_aggregate(df: pl.DataFrame, group_col: str, value_col: str, agg: AggregationType) -> pl.DataFrame:
    if group_col not in df.columns or value_col not in df.columns:
        raise HydrationError(f"Missing agg cols: {group_col}, {value_col}")

    data = df.filter(pl.col(group_col).is_not_null() & pl.col(value_col).is_not_null())
    if data.is_empty():
        return pl.DataFrame()

    if agg == AggregationType.COUNT:
        expr = pl.count()
    elif agg == AggregationType.SUM:
        if data[value_col].dtype not in NUMERIC_DTYPES:
            raise HydrationError("SUM requires numeric column.")
        expr = pl.sum(value_col)
    elif agg == AggregationType.MEAN:
        if data[value_col].dtype not in NUMERIC_DTYPES:
            raise HydrationError("MEAN requires numeric column.")
        expr = pl.mean(value_col)
    elif agg == AggregationType.NUNIQUE:
        expr = pl.n_unique(value_col)
    else:
        expr = pl.first(value_col)

    agg_df = data.group_by(group_col).agg(expr)
    agg_df = agg_df.rename({group_col: "x", agg_df.columns[-1]: "y"})
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
            agg_str = agg.value if hasattr(agg, 'value') else agg
            value = df.select(getattr(pl, agg_str)(col)).item()

        result: Dict[str, Any] = {"value": value, "label": config.title}

        # --- Only enrich if we have a real numeric column ---
        if col != "__all__" and col in df.columns and df[col].dtype in NUMERIC_DTYPES:
            series = df[col].drop_nulls()
            n = len(series)

            # Format detection from column name
            col_lower = col.lower()
            if any(kw in col_lower for kw in ("price", "cost", "revenue", "amount", "salary",
                                                "income", "profit", "tax", "fee", "payment")):
                result["format"] = "currency"
            elif any(kw in col_lower for kw in ("percent", "ratio", "rate", "efficiency")):
                result["format"] = "percentage"
            elif agg == AggregationType.COUNT:
                result["format"] = "integer"
            else:
                result["format"] = "number"

            # Min / Max / Record count
            result["min_value"] = float(series.min()) if n > 0 else 0
            result["max_value"] = float(series.max()) if n > 0 else 0
            result["record_count"] = n

            # Sparkline — bucket into 16 points (rolling trend)
            if n >= 8:
                vals = series.to_list()
                bucket_count = min(16, n)
                bucket_size = n // bucket_count
                sparkline = []
                for i in range(bucket_count):
                    chunk = vals[i * bucket_size:(i + 1) * bucket_size]
                    if chunk:
                        sparkline.append(round(sum(chunk) / len(chunk), 2))
                result["sparkline_data"] = sparkline

            # Comparison — first half vs second half (with proper label)
            if n >= 10:
                mid = n // 2
                first_vals = series.slice(0, mid)
                second_vals = series.slice(mid)

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
                result["comparison_label"] = "vs first half"

                if prev != 0:
                    delta = ((curr - prev) / abs(prev)) * 100
                    result["delta_percent"] = round(delta, 1)

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
    validate_config(df, config)

    original_rows = len(df)
    sample_size = min(10000, len(df))
    if len(df) > sample_size:
        df = df.sample(n=sample_size, shuffle=True)
    
    rows_used = len(df)

    # Guard: default to "bar" if chart_type is None
    if config.chart_type is None:
        logger.warning("chart_type is None in hydrate_chart — defaulting to 'bar'")
        config.chart_type = "bar"

    # Handle both string and enum types
    chart_type = config.chart_type.value if hasattr(config.chart_type, 'value') else config.chart_type
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
        "area": _hydrate_area,
        # New chart types
        "radar": _hydrate_radar,
        "bubble": _hydrate_bubble,
        "waterfall": _hydrate_waterfall,
        "funnel": _hydrate_funnel,
        "candlestick": _hydrate_candlestick,
        "violin": _hydrate_violin,
        "sunburst": _hydrate_sunburst,
        "gauge": _hydrate_gauge,
    }
    if chart_type not in handlers:
        logger.warning(f"Unknown chart type: {chart_type}, using fallback")
    return handlers.get(chart_type, _hydrate_fallback)


def _hydrate_bar(df, config):
    MAX_BAR_CATEGORIES = 25
    if len(config.columns) < 2:
        return []
    x, y = config.columns[0], config.columns[1]
    agg_df = _safe_aggregate(df, x, y, config.aggregation)
    
    # Cap categories: keep top-N by value, aggregate remainder as "Other"
    total_categories = len(agg_df)
    if total_categories > MAX_BAR_CATEGORIES:
        top_df = agg_df.sort("y", descending=True).head(MAX_BAR_CATEGORIES - 1)
        other_sum = agg_df.sort("y", descending=True).tail(total_categories - (MAX_BAR_CATEGORIES - 1))["y"].sum()
        other_row = pl.DataFrame({"x": [f"Other ({total_categories - MAX_BAR_CATEGORIES + 1} more)"], "y": [other_sum]})
        agg_df = pl.concat([top_df, other_row])
        logger.info(f"Bar chart capped: {total_categories} → {MAX_BAR_CATEGORIES} categories")
    
    x_data = agg_df["x"].to_list()
    y_data = agg_df["y"].to_list()
    logger.info(f"Bar chart data - X: {x_data[:5]}... (total: {len(x_data)})")
    logger.info(f"Bar chart data - Y: {y_data[:5]}... (total: {len(y_data)})")
    trace = {"type": "bar", "x": x_data, "y": y_data, "name": config.title or y}
    if total_categories > MAX_BAR_CATEGORIES:
        trace["_sampled"] = {"original_count": total_categories, "shown": MAX_BAR_CATEGORIES}
    return [trace]


def _hydrate_line(df, config):
    MAX_LINE_POINTS = 1000
    if len(config.columns) < 2:
        return []
    x, y = config.columns[0], config.columns[1]
    if df[x].dtype in TEMPORAL_DTYPES:
        df = df.sort(x)
    agg_df = _safe_aggregate(df, x, y, config.aggregation)
    
    # Downsample line charts: take evenly spaced points to preserve shape
    total_points = len(agg_df)
    if total_points > MAX_LINE_POINTS:
        step = max(1, total_points // MAX_LINE_POINTS)
        agg_df = agg_df.gather_every(step)
        logger.info(f"Line chart downsampled: {total_points} → {len(agg_df)} points")
    
    trace = {"type": "scatter", "mode": "lines", "x": agg_df["x"].to_list(), "y": agg_df["y"].to_list(), "name": config.title or y}
    if total_points > MAX_LINE_POINTS:
        trace["_sampled"] = {"original_count": total_points, "shown": len(agg_df)}
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
        return [{"type": "pie", "labels": labels, "values": values, "name": config.title or col}]
    elif len(config.columns) >= 2:
        labels, values = config.columns[0], config.columns[1]
        agg_df = _safe_aggregate(df, labels, values, config.aggregation)
        if agg_df.is_empty():
            return []
        return [{"type": "pie", "labels": agg_df["x"].to_list(), "values": agg_df["y"].to_list(), "name": config.title or labels}]
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
        return [{
            "type": "bar",
            "x": [str(v) for v in counts[col].to_list()],
            "y": counts["cnt"].to_list(),
            "name": config.title or col,
        }]
    vals = df[col].drop_nulls().to_numpy()
    if len(vals) == 0:
        return []
    hist, bins = np.histogram(vals, bins=min(20, max(5, len(vals) // 10)))
    # Format bin labels for readability
    bin_labels = [f"{bins[i]:.1f}" for i in range(len(hist))]
    return [{
        "type": "bar",
        "x": bin_labels,
        "y": hist.tolist(),
        "name": config.title or col,
    }]


def _hydrate_box(df, config):
    if len(config.columns) < 2:
        return []
    cat, num = config.columns[0], config.columns[1]
    traces = []
    for c in df[cat].unique().to_list()[:20]:
        group = df.filter(pl.col(cat) == c)[num].drop_nulls().to_list()
        if group:
            traces.append({
                "type": "box",
                "name": str(c),
                "y": group,
                "boxpoints": "outliers",
                "whiskerwidth": 0.5,
            })
    return traces


def _hydrate_scatter(df, config):
    MAX_SCATTER_POINTS = 2000
    x, y = config.columns[0], config.columns[1]
    color = config.columns[2] if len(config.columns) > 2 else None
    
    # Sample large datasets to prevent frontend crash and overplotting
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
        trace = {"type": "scatter", "mode": "markers", "x": list(xs), "y": list(ys), "marker": {"color": list(cs)}, "name": config.title or f"{y} vs {x}"}
    else:
        pairs = [
            (xv, yv)
            for xv, yv in zip(df[x], df[y])
            if pd.notna(xv) and pd.notna(yv)
        ]
        if not pairs:
            return []
        xs, ys = zip(*pairs)
        trace = {"type": "scatter", "mode": "markers", "x": list(xs), "y": list(ys), "name": config.title or f"{y} vs {x}"}
    
    if total_rows > MAX_SCATTER_POINTS:
        trace["_sampled"] = {"original_count": total_rows, "shown": MAX_SCATTER_POINTS}
    return [trace]


def _hydrate_heatmap(df, config):
    if len(config.columns) < 3:
        return _hydrate_correlation_heatmap(df)
    x, y, z = config.columns
    pivot = df.pivot(index=y, columns=x, values=z, aggregate_function="mean").fill_null(0)
    x_vals = [c for c in pivot.columns if c != y]
    y_vals = pivot[y].to_list()
    z_vals = pivot.select(pl.exclude(y)).to_numpy().tolist()
    return [{"type": "heatmap", "x": x_vals, "y": y_vals, "z": z_vals, "colorscale": "Viridis"}]


def _hydrate_correlation_heatmap(df):
    num_cols = [c for c in df.columns if df[c].dtype in NUMERIC_DTYPES]
    if len(num_cols) < 2:
        return []
    corr = df.select(num_cols).to_pandas().corr().round(2)
    return [{
        "type": "heatmap",
        "z": corr.values.tolist(),
        "x": corr.columns.tolist(),
        "y": corr.index.tolist(),
        "colorscale": "RdBu"
    }]


def _hydrate_treemap(df, config):
    if not config.columns:
        return []
    path = config.columns[:-1] if len(config.columns) > 1 else [config.columns[0]]
    val_col = config.columns[-1]

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

    return [{"type": "treemap", "ids": ids, "parents": parents, "labels": labels, "values": values}]


def _hydrate_grouped_bar(df, config):
    if not config.group_by or len(config.columns) < 1:
        return _hydrate_bar(df, config)
    idx, col_group = config.group_by[:2]
    val = config.columns[0]
    pivot = df.pivot(index=idx, columns=col_group, values=val, aggregate_function="sum").fill_null(0)
    categories = pivot[idx].to_list()
    traces = [
        {"type": "bar", "name": series, "x": categories, "y": pivot[series].to_list()}
        for series in pivot.columns[1:]
    ]
    return traces


def _hydrate_area(df, config):
    traces = _hydrate_line(df, config)
    if traces:
        traces[0]["fill"] = "tozeroy"
    return traces


# =====================================================
# NEW CHART TYPE HANDLERS
# =====================================================

def _hydrate_radar(df, config):
    """Radar/Spider chart - multi-dimensional comparison."""
    if len(config.columns) < 2:
        return []
    
    category_col = config.columns[0]
    value_cols = config.columns[1:] if len(config.columns) > 1 else []
    
    if not value_cols:
        # Single value column - aggregate by category
        cat, val = config.columns[0], config.columns[1] if len(config.columns) > 1 else config.columns[0]
        agg_df = _safe_aggregate(df, cat, val, config.aggregation)
        categories = agg_df["x"].to_list()
        values = agg_df["y"].to_list()
        # Close the radar loop
        categories.append(categories[0])
        values.append(values[0])
        return [{
            "type": "scatterpolar",
            "r": values,
            "theta": categories,
            "fill": "toself",
            "name": val
        }]
    else:
        # Multiple value columns for each category
        traces = []
        for _, row in df.head(10).to_pandas().iterrows():
            values = [row[col] for col in value_cols if col in df.columns]
            values.append(values[0])  # Close loop
            cols = value_cols + [value_cols[0]]
            traces.append({
                "type": "scatterpolar",
                "r": values,
                "theta": cols,
                "fill": "toself",
                "name": str(row[category_col]) if category_col in df.columns else f"Series {len(traces)}"
            })
        return traces[:5]  # Limit to 5 series


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
        "marker": {
            "size": normalized_size.tolist(),
            "sizemode": "diameter"
        },
        "text": [f"{size}: {s:.2f}" for s in size_vals]
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
    
    return [{
        "type": "waterfall",
        "x": x_vals,
        "y": y_vals,
        "measure": measures,
        "connector": {"line": {"color": "rgb(63, 63, 63)"}}
    }]


def _hydrate_funnel(df, config):
    """Funnel chart - stage-based conversion visualization."""
    if len(config.columns) < 2:
        return []
    
    stage, value = config.columns[0], config.columns[1]
    agg_df = _safe_aggregate(df, stage, value, config.aggregation)
    
    # Sort by value descending for proper funnel shape
    agg_df = agg_df.sort("y", descending=True)
    
    return [{
        "type": "funnel",
        "y": agg_df["x"].to_list(),
        "x": agg_df["y"].to_list(),
        "textinfo": "value+percent initial"
    }]


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
    
    return [{
        "type": "candlestick",
        "x": df_sorted[date_col].to_list(),
        "open": df_sorted[open_col].to_list(),
        "high": df_sorted[high_col].to_list(),
        "low": df_sorted[low_col].to_list(),
        "close": df_sorted[close_col].to_list()
    }]


def _hydrate_violin(df, config):
    """Violin plot - distribution shape visualization."""
    if len(config.columns) < 2:
        return []

    cat, num = config.columns[0], config.columns[1]
    traces = []

    for c in df[cat].unique().to_list()[:20]:
        group = df.filter(pl.col(cat) == c)[num].drop_nulls().to_list()
        if group:
            traces.append({
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
            })

    return traces


def _hydrate_sunburst(df, config):
    """Sunburst chart - hierarchical radial visualization."""
    if not config.columns:
        return []
    
    path = config.columns[:-1] if len(config.columns) > 1 else [config.columns[0]]
    val_col = config.columns[-1]
    
    if val_col not in df.columns or df[val_col].dtype not in NUMERIC_DTYPES:
        agg_df = df.group_by(path).agg(pl.count().alias("value"))
    else:
        agg_df = df.group_by(path).agg(pl.sum(val_col).alias("value"))
    
    rows = agg_df.to_dicts()
    ids, parents, labels, values = [], [], [], []
    
    for r in rows:
        full_path = "/".join(str(r[p]) for p in path)
        parent = "/".join(full_path.split("/")[:-1]) or ""
        ids.append(full_path)
        parents.append(parent)
        labels.append(full_path.split("/")[-1])
        values.append(r["value"])
    
    return [{
        "type": "sunburst",
        "ids": ids,
        "parents": parents,
        "labels": labels,
        "values": values,
        "branchvalues": "total"
    }]


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
    
    return [{
        "type": "indicator",
        "mode": "gauge+number",
        "value": float(value) if value is not None else 0,
        "gauge": {
            "axis": {"range": [0, max_val]},
            "bar": {"color": "#3b82f6"},
            "steps": [
                {"range": [0, max_val * 0.5], "color": "#dcfce7"},
                {"range": [max_val * 0.5, max_val * 0.8], "color": "#fef9c3"},
                {"range": [max_val * 0.8, max_val], "color": "#fee2e2"}
            ]
        },
        "title": {"text": config.title}
    }]


def _hydrate_fallback(df, config):
    temp = ChartConfig(
        type=config.type,
        title=config.title,
        chart_type=ChartType.BAR,
        columns=config.columns[:2],
        aggregation=config.aggregation,
        span=config.span
    )
    return _hydrate_bar(df, temp)
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
    # Handle both string and enum types
    chart_type_str = config.chart_type.value if hasattr(config.chart_type, 'value') else config.chart_type
    chart_def = CHART_DEFINITIONS_BY_ID.get(chart_type_str, {})
    rules = chart_def.get("rules", {})

    safe_cols = [c for c in config.columns if c in df.columns]
    if len(safe_cols) < len(config.columns):
        config.columns = safe_cols

    if not config.columns:
        raise HydrationError("No valid columns after safety check.")

    if len(config.columns) < rules.get("min_columns", 1):
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
    start = time.time()
    try:
        validate_config(df, config)
        if config.aggregation == AggregationType.COUNT:
            value = len(df)
        else:
            if config.column not in df.columns:
                raise HydrationError("KPI column missing.")
            value = df.select(
                getattr(pl, config.aggregation.value)(config.column)
            ).item()
        return {"value": value, "label": config.title}
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
    }
    if chart_type not in handlers:
        logger.error(f"Unknown chart type: {chart_type}")
    return handlers.get(chart_type, _hydrate_fallback)


def _hydrate_bar(df, config):
    if len(config.columns) < 2:
        return []
    x, y = config.columns[0], config.columns[1]
    agg_df = _safe_aggregate(df, x, y, config.aggregation)
    x_data = agg_df["x"].to_list()
    y_data = agg_df["y"].to_list()
    logger.info(f"Bar chart data - X: {x_data[:5]}... (total: {len(x_data)})")
    logger.info(f"Bar chart data - Y: {y_data[:5]}... (total: {len(y_data)})")
    trace = {"type": "bar", "x": x_data, "y": y_data}
    logger.info(f"Created trace with keys: {trace.keys()}")
    return [trace]


def _hydrate_line(df, config):
    if len(config.columns) < 2:
        return []
    x, y = config.columns[0], config.columns[1]
    if df[x].dtype in TEMPORAL_DTYPES:
        df = df.sort(x)
    agg_df = _safe_aggregate(df, x, y, config.aggregation)
    return [{"type": "scatter", "mode": "lines", "x": agg_df["x"].to_list(), "y": agg_df["y"].to_list()}]


def _hydrate_pie(df, config):
    if len(config.columns) != 2:
        return []
    labels, values = config.columns
    agg_df = _safe_aggregate(df, labels, values, AggregationType.SUM)
    return [{"type": "pie", "labels": agg_df["x"].to_list(), "values": agg_df["y"].to_list()}]


def _hydrate_histogram(df, config):
    col = config.columns[0]
    if df[col].dtype not in NUMERIC_DTYPES:
        return []
    vals = df[col].drop_nulls().to_numpy()
    hist, bins = np.histogram(vals, bins=20)
    return [{"type": "bar", "x": bins[:-1].tolist(), "y": hist.tolist()}]


def _hydrate_box(df, config):
    cat, num = config.columns[0], config.columns[1]
    traces = []
    for c in df[cat].unique():
        group = df.filter(pl.col(cat) == c)[num].drop_nulls().to_list()
        if group:
            traces.append({"type": "box", "name": str(c), "y": group})
    return traces


def _hydrate_scatter(df, config):
    x, y = config.columns[0], config.columns[1]
    color = config.columns[2] if len(config.columns) > 2 else None
    if color:
        triples = [
            (xv, yv, cv)
            for xv, yv, cv in zip(df[x], df[y], df[color])
            if pd.notna(xv) and pd.notna(yv) and pd.notna(cv)
        ]
        if not triples:
            return []
        xs, ys, cs = zip(*triples)
        trace = {"type": "scatter", "mode": "markers", "x": list(xs), "y": list(ys), "marker": {"color": list(cs)}}
    else:
        pairs = [
            (xv, yv)
            for xv, yv in zip(df[x], df[y])
            if pd.notna(xv) and pd.notna(yv)
        ]
        if not pairs:
            return []
        xs, ys = zip(*pairs)
        trace = {"type": "scatter", "mode": "markers", "x": list(xs), "y": list(ys)}
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
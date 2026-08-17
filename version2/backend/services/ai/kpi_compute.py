"""
KPI Computation
===============
Value computation, comparisons, sparklines, anomaly detection, driver
detection, trend forecasting, and time-period detection.
Extracted from intelligent_kpi_generator.py.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import polars as pl

from .kpi_types import (
    _INTEGER_DTYPES,
    _NUMERIC_DTYPES,
    _TIME_RE,
    ColumnProfile,
    ColumnRole,
)

logger = logging.getLogger(__name__)


def _compute_kpi_value(df: pl.DataFrame, profile: ColumnProfile) -> Any:
    try:
        col = df[profile.name].drop_nulls()
        if len(col) == 0:
            return 0
        agg = profile.aggregation
        if agg == "sum":
            return round(float(col.sum()), 2)
        if agg == "mean":
            return round(float(col.mean()), 2)
        if agg == "median":
            return round(float(col.median()), 2)
        if agg == "max":
            return round(float(col.max()), 2)
        if agg == "min":
            return round(float(col.min()), 2)
        return round(float(col.sum()), 2)
    except Exception:
        return profile.primary_value or 0


def _find_time_column(df: pl.DataFrame) -> Optional[str]:
    for col in df.columns:
        if df[col].dtype in (pl.Date, pl.Datetime):
            return col
    for col in df.columns:
        if _TIME_RE.search(col) and df[col].dtype in _NUMERIC_DTYPES:
            return col
    return None


def _period_agg_expr(col: str, agg: str) -> pl.Expr:
    """Aggregation expression for period binning (sum/mean/median/count)."""
    if agg == "mean":
        return pl.col(col).mean().alias("_v")
    if agg == "median":
        return pl.col(col).median().alias("_v")
    if agg == "count":
        return pl.col(col).count().alias("_v")
    return pl.col(col).sum().alias("_v")


def _compute_period_comparison(
    sorted_df: pl.DataFrame,
    profile: ColumnProfile,
    time_col: str,
    comparison: str,
) -> Optional[Dict[str, Any]]:
    """
    Period-over-period comparison at month grain.

    - prior_period    → latest month vs the previous month
    - prior_year      → latest month vs the same month a year ago
    - rolling_baseline→ latest month vs the trailing 3-month average

    Returns the same dict shape as ``_compute_comparison``.
    """
    try:
        col = profile.name
        binned = (
            sorted_df.with_columns(pl.col(time_col).cast(pl.Date).alias("_d"))
            .group_by_dynamic("_d", every="1mo")
            .agg(_period_agg_expr(col, profile.aggregation or "sum"))
            .sort("_d")
            .filter(pl.col("_v").is_not_null())
        )
        values = binned["_v"].to_list()
        dates = binned["_d"].to_list()
        if len(values) < 2:
            return None

        current = float(values[-1])
        if comparison == "prior_period":
            baseline, label = float(values[-2]), "vs previous period"
        elif comparison == "prior_year":
            target = dates[-1].replace(year=dates[-1].year - 1)
            baseline = None
            for d, v in zip(dates, values):
                if d.year == target.year and d.month == target.month:
                    baseline = float(v)
                    break
            if baseline is None:
                return None
            label = "vs same period last year"
        else:  # rolling_baseline
            prior = [float(v) for v in values[-4:-1]]
            if len(prior) < 2:
                return None
            baseline = sum(prior) / len(prior)
            label = f"vs {len(prior)}-period average"

        if abs(baseline) < 1e-9:
            return None

        delta_pct = round(((current - baseline) / abs(baseline)) * 100, 1)
        direction = "up" if delta_pct > 0 else ("down" if delta_pct < 0 else "neutral")
        is_positive = profile.polarity == "higher_is_better"
        is_good = (direction == "up" and is_positive) or (direction == "down" and not is_positive)

        return {
            "comparison_value": round(baseline, 2),
            "comparison_label": label,
            "delta_percent": delta_pct,
            "delta_direction": direction,
            "is_delta_positive": is_positive,
            "is_good": is_good,
            "is_temporal": True,
        }
    except Exception as e:
        logger.debug(f"[KPI] Period comparison failed for '{profile.name}': {e}")
        return None


def _compute_comparison(
    df: pl.DataFrame,
    profile: ColumnProfile,
    time_col: Optional[str],
    comparison: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Compute the delta vs a baseline for a KPI card.

    When ``comparison`` is one of ``prior_year`` / ``prior_period`` /
    ``rolling_baseline`` (resolved from the user's question by
    ``comparison_resolver``), a real period-over-period comparison runs at
    month grain. Otherwise the default first-half-vs-second-half split is
    kept (backward compatible).
    """
    try:
        col = profile.name
        if col not in df.columns:
            return None
        clean = df.drop_nulls(subset=[col])
        if len(clean) == 0:
            return None

        if time_col and time_col in df.columns:
            try:
                sorted_df = clean.sort(time_col)
            except Exception:
                return None
        else:
            return None

        if comparison in ("prior_year", "prior_period", "rolling_baseline"):
            return _compute_period_comparison(sorted_df, profile, time_col, comparison)

        # Default: first half vs second half (backward compatible) — needs
        # enough rows to be meaningful.
        if len(sorted_df) < 10:
            return None
        mid = len(sorted_df) // 2
        first_half = sorted_df[:mid]
        second_half = sorted_df[mid:]

        def agg_half(half: pl.DataFrame) -> Optional[float]:
            c = half[col].drop_nulls()
            if len(c) == 0:
                return None
            agg = profile.aggregation
            if agg == "mean":
                return float(c.mean())
            if agg == "median":
                return float(c.median())
            return float(c.sum())

        v1 = agg_half(first_half)
        v2 = agg_half(second_half)

        if v1 is None or v2 is None or abs(v1) < 1e-9:
            return None

        delta_pct = round(((v2 - v1) / abs(v1)) * 100, 1)
        direction = "up" if delta_pct > 0 else ("down" if delta_pct < 0 else "neutral")
        is_positive = profile.polarity == "higher_is_better"
        is_good = (direction == "up" and is_positive) or (direction == "down" and not is_positive)

        return {
            "comparison_value": round(v1, 2),
            "comparison_label": "vs first half (time-sorted)",
            "delta_percent": delta_pct,
            "delta_direction": direction,
            "is_delta_positive": is_positive,
            "is_good": is_good,
            "is_temporal": True,
        }
    except Exception as e:
        logger.debug(f"[KPI] Comparison failed for '{profile.name}': {e}")
        return None


def _compute_sparkline(
    df: pl.DataFrame,
    profile: ColumnProfile,
    time_col: Optional[str],
    max_points: int = 12,
) -> Dict[str, Any]:
    col = profile.name
    try:
        if time_col and time_col in df.columns and df[time_col].dtype in (pl.Date, pl.Datetime):
            try:
                binned = (
                    df.sort(time_col)
                    .with_columns(pl.col(time_col).cast(pl.Date).alias("_d"))
                    .group_by_dynamic("_d", every="1mo")
                    .agg(pl.col(col).mean().alias("_v"))
                    .sort("_d")
                    .tail(max_points)
                )
                vals = binned["_v"].drop_nulls().to_list()
                if len(vals) >= 3:
                    return {"data": [round(v, 2) for v in vals], "type": "time_series"}
            except Exception:
                pass
        return {"data": [], "type": "distribution"}
    except Exception:
        return {"data": [], "type": "distribution"}


def _compute_accent_color(importance: str, delta_direction: Optional[str], polarity: str) -> str:
    if importance == "hero":
        return "teal"
    if not delta_direction or delta_direction == "neutral":
        return "neutral"
    is_positive = polarity == "higher_is_better"
    if is_positive:
        return "green" if delta_direction == "up" else "red"
    else:
        return "green" if delta_direction == "down" else "red"


def _detect_time_period(
    df: pl.DataFrame, profile: ColumnProfile, time_col: Optional[str]
) -> Dict[str, Any]:
    try:
        col = profile.name
        if col not in df.columns:
            return {}

        clean = df.drop_nulls(subset=[col])
        if len(clean) < 10:
            return {}

        if time_col and time_col in df.columns and df[time_col].dtype in (pl.Date, pl.Datetime):
            try:
                sorted_df = clean.sort(time_col)
                binned = (
                    sorted_df.with_columns(pl.col(time_col).cast(pl.Date).alias("_d"))
                    .group_by_dynamic("_d", every="1mo")
                    .agg(pl.col(col).mean().alias("_v"))
                    .sort("_d")
                )
                periods = binned.filter(pl.col("_v").is_not_null())
                if len(periods) < 2:
                    return {}

                last_periods = periods.tail(4)
                current = last_periods[-1]
                previous = last_periods[-2] if len(last_periods) >= 2 else None
                current_date = current["_d"].to_list()[0]
                period_label = _format_period_label(current_date, "month")
                prev_date = previous["_d"].to_list()[0] if previous else None
                prev_period_label = _format_period_label(prev_date, "month") if prev_date else "previous period"
                period_values = last_periods["_v"].drop_nulls().to_list()

                return {
                    "period_label": period_label,
                    "previous_period_label": prev_period_label,
                    "period_type": "month",
                    "current_period_value": float(current["_v"].to_list()[0]),
                    "previous_period_value": float(previous["_v"].to_list()[0]) if previous else None,
                    "period_values": [round(v, 2) for v in period_values],
                }
            except Exception:
                return {}

        return {}
    except Exception as e:
        logger.debug(f"[KPI] Time period detection failed for '{profile.name}': {e}")
        return {}


def _format_period_label(date_val, period_type: str) -> str:
    try:
        if hasattr(date_val, "strftime"):
            if period_type == "month":
                return date_val.strftime("%B %Y")
            if period_type == "quarter":
                quarter = (date_val.month - 1) // 3 + 1
                return f"Q{quarter} {date_val.year}"
            if period_type == "year":
                return str(date_val.year)
            if period_type == "week":
                return date_val.strftime("Week %W, %Y")
        return str(date_val)
    except Exception:
        return str(date_val)


def _compute_rolling_baseline(period_values: List[float], window: int = 3) -> Dict[str, Any]:
    try:
        if not period_values or len(period_values) < 2:
            return {}
        baseline_periods = period_values[-min(window, len(period_values)):]
        if len(baseline_periods) < 2:
            return {}

        mean_val = sum(baseline_periods) / len(baseline_periods)
        variance = sum((x - mean_val) ** 2 for x in baseline_periods) / len(baseline_periods)
        std_val = math.sqrt(variance)

        if std_val < 1e-9:
            std_val = abs(mean_val) * 0.01 if mean_val != 0 else 1.0

        return {
            "baseline_value": round(mean_val, 2),
            "baseline_std": round(std_val, 2),
            "normal_range_low": round(mean_val - std_val, 2),
            "normal_range_high": round(mean_val + std_val, 2),
            "period_count": len(baseline_periods),
        }
    except Exception as e:
        logger.debug(f"[KPI] Baseline computation failed: {e}")
        return {}


def _detect_anomaly(current_value: float, baseline_mean: float, baseline_std: float) -> Dict[str, Any]:
    try:
        if baseline_std < 1e-9:
            return {"is_anomaly": False, "anomaly_direction": "normal", "z_score": 0.0, "anomaly_severity": "normal"}

        z_score = (current_value - baseline_mean) / baseline_std

        if abs(z_score) > 3:
            direction = "above_normal" if z_score > 0 else "below_normal"
            return {"is_anomaly": True, "anomaly_direction": direction, "z_score": round(z_score, 2), "anomaly_severity": "critical"}
        elif abs(z_score) > 2:
            direction = "above_normal" if z_score > 0 else "below_normal"
            return {"is_anomaly": True, "anomaly_direction": direction, "z_score": round(z_score, 2), "anomaly_severity": "warning"}
        else:
            return {"is_anomaly": False, "anomaly_direction": "normal", "z_score": round(z_score, 2), "anomaly_severity": "normal"}
    except Exception:
        return {"is_anomaly": False, "anomaly_direction": "normal", "z_score": 0.0, "anomaly_severity": "normal"}


def _compute_top_driver(df: pl.DataFrame, metric_col: str, max_dimensions: int = 3) -> Optional[Dict[str, Any]]:
    try:
        if metric_col not in df.columns:
            return None

        dimension_cols = []
        _ALL_DTYPES = _NUMERIC_DTYPES + (pl.Boolean,)
        for col in df.columns:
            if col == metric_col or col.startswith("_"):
                continue
            dtype = df[col].dtype
            unique_count = df[col].n_unique()

            if dtype in (pl.Utf8, pl.Categorical):
                if 2 <= unique_count <= 50:
                    dimension_cols.append(col)
            elif dtype in _INTEGER_DTYPES:
                if 2 <= unique_count <= 30:
                    dimension_cols.append(col)
            elif dtype in (pl.Float32, pl.Float64):
                if 2 <= unique_count <= 20 and unique_count <= len(df) * 0.05:
                    dimension_cols.append(col)
            elif dtype == pl.Boolean:
                if unique_count == 2:
                    dimension_cols.append(col)

        if not dimension_cols:
            return None

        dimension_cols.sort(key=lambda c: df[c].n_unique())
        dimension_cols = dimension_cols[:max_dimensions]

        best_driver = None
        best_pct = 0.0

        for dim_col in dimension_cols:
            try:
                grouped = (
                    df.drop_nulls(subset=[metric_col, dim_col])
                    .group_by(dim_col)
                    .agg(pl.col(metric_col).mean().alias("_agg"))
                    .sort("_agg", descending=True)
                )
                if len(grouped) < 2:
                    continue
                total = grouped["_agg"].sum()
                if total == 0:
                    continue
                top_row = grouped.head(1)
                segment_val = float(top_row["_agg"].to_list()[0])
                segment_name = str(top_row[dim_col].to_list()[0])
                pct_of_total = (segment_val / abs(total)) * 100

                if pct_of_total > best_pct:
                    best_pct = pct_of_total
                    best_driver = {
                        "dimension": dim_col,
                        "segment": segment_name,
                        "segment_value": round(segment_val, 2),
                        "pctOfTotal": round(pct_of_total, 1),
                        "pct_of_total": round(pct_of_total, 1),
                    }
            except Exception:
                continue

        if best_driver:
            logger.info(f"[KPI] Top driver for '{metric_col}': {best_driver['segment']} ({best_driver['dimension']}) = {best_driver['pctOfTotal']:.0f}%")

        return best_driver
    except Exception as e:
        logger.debug(f"[KPI] Top driver detection failed for '{metric_col}': {e}")
        return None


def _compute_trend_forecast(period_values: List[float]) -> Dict[str, Any]:
    try:
        if not period_values or len(period_values) < 2:
            return {}

        n = len(period_values)
        x_mean = (n - 1) / 2.0
        y_mean = sum(period_values) / n

        numerator = sum((i - x_mean) * (period_values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator < 1e-9:
            return {"expected_value": round(y_mean, 2), "trend_direction": "flat", "trend_slope": 0.0}

        slope = numerator / denominator
        intercept = y_mean - slope * x_mean
        expected = intercept + slope * (n - 1)

        if abs(slope) < abs(y_mean) * 0.01:
            direction = "flat"
        elif slope > 0:
            direction = "up"
        else:
            direction = "down"

        return {"expected_value": round(expected, 2), "trend_direction": direction, "trend_slope": round(slope, 2)}
    except Exception as e:
        logger.debug(f"[KPI] Trend forecast failed: {e}")
        return {}


def _compute_segment_comparison(
    df: pl.DataFrame,
    metric_col: str,
    polarity: str = "higher_is_better",
) -> Optional[Dict[str, Any]]:
    try:
        if metric_col not in df.columns:
            return None
        clean = df.drop_nulls(subset=[metric_col])
        if len(clean) < 20:
            return None
        dims = []
        for col in df.columns:
            if col == metric_col:
                continue
            dtype = df[col].dtype
            if dtype in (pl.Utf8, pl.Categorical):
                n = df[col].n_unique()
                if 2 <= n <= 10:
                    dims.append(col)
            elif dtype in _INTEGER_DTYPES:
                n = df[col].n_unique()
                if 2 <= n <= 10:
                    dims.append(col)
        if not dims:
            return None
        dim = dims[0]
        segments = (
            clean.group_by(dim)
            .agg(pl.col(metric_col).mean().alias("_avg"))
            .sort("_avg", descending=True)
        )
        if len(segments) < 2:
            return None
        top = segments.row(0)
        bottom = segments.row(-1)
        top_seg, top_val = str(top[0]), float(top[1])
        bottom_seg, bottom_val = str(bottom[0]), float(bottom[1])
        if abs(top_val) < 1e-9 or abs(bottom_val) < 1e-9:
            return None
        delta_pct = round(((top_val - bottom_val) / abs(bottom_val)) * 100, 1)
        if abs(delta_pct) < 5:
            return None
        return {
            "comparison_value": round(bottom_val, 2),
            "comparison_label": f"{top_seg} vs {bottom_seg} ({dim})",
            "delta_percent": delta_pct,
            "delta_direction": "up" if delta_pct > 0 else "down",
            "is_delta_positive": delta_pct > 0,
            "is_good": delta_pct > 0 if polarity == "higher_is_better" else delta_pct < 0,
            "is_temporal": False,
            "segment_dimension": dim,
            "top_segment": top_seg,
            "bottom_segment": bottom_seg,
        }
    except Exception as e:
        logger.debug(f"[KPI] Segment comparison failed for '{metric_col}': {e}")
        return None

"""
Chart Render Service
====================
Production-grade chart rendering service that wraps the render.py module.

Features:
- Async/await support for FastAPI integration
- Error handling and logging
- Chart hydration → rendering pipeline
- Theme support (light/dark)
- Caching support
- Performance monitoring
- Per-point statistical intelligence

Author: Signal Team
Version: 2.1 (Production + Intelligence)
"""

import logging
import asyncio
import math
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import polars as pl

from services.charts.render import ChartRenderer
from services.charts.hydrate import (
    hydrate_chart,
    HydrationError,
    aggregate_sampling_metadata,
)
from services.charts.semantic_types import (
    infer_semantic_types,
    apply_auto_layout,
)
from db.schemas_dashboard import ChartConfig, ChartType, ComponentType
from services.datasets.enhanced_dataset_service import enhanced_dataset_service

logger = logging.getLogger(__name__)


class ChartRenderService:
    """
    Production-grade chart rendering service.
    Orchestrates hydration → rendering → output.
    """

    def __init__(self):
        self.renderer = ChartRenderer()
        self._cache = {}  # Simple in-memory cache
        self._render_count = 0
        self._error_count = 0

    def _compute_point_intelligence(
        self,
        traces: List[Dict[str, Any]],
        df: pl.DataFrame,
        chart_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compute per-data-point statistical intelligence from the actual
        DataFrame and rendered traces. Pure math — no LLM, no latency.

        Returns a dict that the frontend can look up by category/x-value
        to show meaningful insights in the tooltip.

        Structure:
        {
            "y_label": "price",
            "x_label": "packaging_type",
            "total_records": 13000,
            "stats": {
                "mean": 120.5,
                "median": 115.0,
                "std": 34.2,
                "min": 10.0,
                "max": 450.0,
                "q1": 95.0,
                "q3": 145.0,
                "iqr": 50.0,
            },
            "points": {
                "Bottle": {
                    "value": 449400,
                    "rank": 1,
                    "percentile": 100,
                    "z_score": 1.82,
                    "vs_avg_pct": 23.5,
                    "is_outlier": false,
                    "record_count": 2100,
                    "insight": "Highest value — 23.5% above average"
                },
                ...
            }
        }
        """
        try:
            columns = chart_config.get("columns", [])
            if len(columns) < 2:
                return {}

            x_col, y_col = columns[0], columns[1]

            # Get trace data (the aggregated values actually shown in the chart)
            trace = traces[0] if traces else {}
            trace_type = trace.get("type", "bar")

            # For pie charts, labels/values instead of x/y
            if trace_type == "pie":
                x_values = trace.get("labels", [])
                y_values = trace.get("values", [])
            else:
                x_values = trace.get("x", [])
                y_values = trace.get("y", [])

            if not x_values or not y_values or len(x_values) != len(y_values):
                return {}

            # Convert to float safely
            numeric_values = []
            for v in y_values:
                try:
                    numeric_values.append(float(v))
                except (TypeError, ValueError):
                    numeric_values.append(0.0)

            n = len(numeric_values)
            if n == 0:
                return {}

            # ── Core statistics ──
            sorted_vals = sorted(numeric_values)
            total = sum(numeric_values)
            mean = total / n
            median = (
                sorted_vals[n // 2]
                if n % 2
                else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
            )
            variance = sum((v - mean) ** 2 for v in numeric_values) / max(n - 1, 1)
            std = math.sqrt(variance) if variance > 0 else 0.0
            min_val = sorted_vals[0]
            max_val = sorted_vals[-1]
            q1 = sorted_vals[max(n // 4 - 1, 0)]
            q3 = sorted_vals[min(3 * n // 4, n - 1)]
            iqr = q3 - q1
            lower_fence = q1 - 1.5 * iqr
            upper_fence = q3 + 1.5 * iqr

            # ── Per-category record counts (from raw DataFrame) ──
            record_counts = {}
            try:
                if x_col in df.columns:
                    counts = df.group_by(x_col).len()
                    for row in counts.iter_rows():
                        record_counts[str(row[0])] = row[1]
            except Exception:
                pass

            total_records = len(df)

            # ── Rank: sorted descending (1 = highest) ──
            rank_sorted = sorted(range(n), key=lambda i: numeric_values[i], reverse=True)
            rank_map = {}
            for rank_pos, idx in enumerate(rank_sorted):
                rank_map[idx] = rank_pos + 1

            # ── Build per-point intelligence ──
            points = {}
            for i, x_val in enumerate(x_values):
                val = numeric_values[i]
                x_key = str(x_val)
                rank = rank_map.get(i, i + 1)
                z_score = (val - mean) / std if std > 0 else 0.0
                vs_avg_pct = ((val - mean) / mean * 100) if mean != 0 else 0.0
                is_outlier = val < lower_fence or val > upper_fence
                percentile = round((1 - (rank - 1) / max(n - 1, 1)) * 100)
                rec_count = record_counts.get(x_key, None)

                # ── Generate a meaningful insight sentence ──
                insight = self._generate_point_insight(
                    val,
                    mean,
                    std,
                    rank,
                    n,
                    vs_avg_pct,
                    is_outlier,
                    percentile,
                    x_key,
                    y_col,
                )

                points[x_key] = {
                    "value": val,
                    "rank": rank,
                    "percentile": percentile,
                    "z_score": round(z_score, 2),
                    "vs_avg_pct": round(vs_avg_pct, 1),
                    "is_outlier": is_outlier,
                    "record_count": rec_count,
                    "insight": insight,
                }

            return {
                "y_label": y_col,
                "x_label": x_col,
                "total_records": total_records,
                "stats": {
                    "mean": round(mean, 2),
                    "median": round(median, 2),
                    "std": round(std, 2),
                    "min": round(min_val, 2),
                    "max": round(max_val, 2),
                    "q1": round(q1, 2),
                    "q3": round(q3, 2),
                    "iqr": round(iqr, 2),
                },
                "points": points,
            }

        except Exception as e:
            logger.warning(f"Point intelligence computation failed (non-fatal): {e}")
            return {}

    def _compute_and_attach_overlays(
        self,
        chart_payload: Dict[str, Any],
        chart_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compute statistical overlays (trend lines, reference lines, confidence
        bands, outlier markers) and attach them directly to the chart payload.

        Injects:
        - layout.shapes: reference/trend lines and confidence bands
        - layout.annotations: labels for overlays + outlier markers
        - traces (appended): trend line as an overlay trace

        Returns the modified payload.
        """
        try:
            traces = chart_payload.get("traces", [])
            layout = chart_payload.get("layout", {})
            point_intel = chart_payload.get("point_intelligence", {})

            if not traces:
                return chart_payload

            # ── Identify the primary data trace (skip overlay/aux traces) ──
            primary = None
            for t in traces:
                ttype = (t.get("type") or "").lower()
                # Skip pie/donut, heatmap, and overlay fill traces
                if ttype in ("pie", "heatmap", "choropleth"):
                    continue
                if t.get("fill") == "tozeroy" and t.get("showlegend") is False:
                    continue  # Skip the fill-underlay trace added by PlotlyRenderer
                if t.get("x") and t.get("y") and len(t["x"]) >= 2:
                    primary = t
                    break

            if not primary or not primary.get("x") or not primary.get("y"):
                # Fallback: use any trace with x/y data
                for t in traces:
                    if t.get("x") and t.get("y"):
                        primary = t
                        break

            if not primary:
                return chart_payload

            x_arr = primary.get("x", [])
            y_arr = [v for v in primary.get("y", []) if isinstance(v, (int, float))]

            if len(x_arr) < 2 or len(y_arr) < 2:
                return chart_payload

            # Ensure same length
            n = min(len(x_arr), len(y_arr))
            x_arr = x_arr[:n]
            y_arr = y_arr[:n]

            shapes = list(layout.get("shapes", []))
            annotations = list(layout.get("annotations", []))
            overlay_traces = []

            chart_type = chart_config.get("chart_type", "").lower()

            stats = point_intel.get("stats", {})
            points_data = point_intel.get("points", {})

            # ────────────────────────────────────────────────────────────────
            # 1. MEAN & MEDIAN REFERENCE LINES
            # ────────────────────────────────────────────────────────────────
            y_values = y_arr
            if len(y_values) >= 3:
                y_sorted = sorted(y_values)
                mean_val = sum(y_values) / len(y_values)
                median_val = (
                    y_sorted[len(y_sorted) // 2]
                    if len(y_sorted) % 2
                    else (y_sorted[len(y_sorted) // 2 - 1] + y_sorted[len(y_sorted) // 2]) / 2
                )

                # Use stats from point_intelligence if available (more precise)
                if stats:
                    mean_val = stats.get("mean", mean_val)
                    median_val = stats.get("median", median_val)

                def _fmt_label(v):
                    if abs(v) >= 1e9:
                        return f"{v/1e9:.1f}B"
                    if abs(v) >= 1e6:
                        return f"{v/1e6:.1f}M"
                    if abs(v) >= 1e3:
                        return f"{v/1e3:.1f}K"
                    return f"{v:.1f}"

                # Mean line (solid, lower opacity)
                shapes.append({
                    "type": "line",
                    "xref": "paper",
                    "x0": 0,
                    "x1": 1,
                    "y0": mean_val,
                    "y1": mean_val,
                    "line": {
                        "color": "rgba(59, 130, 246, 0.5)",
                        "width": 1.5,
                        "dash": "dash",
                    },
                })
                annotations.append({
                    "xref": "paper",
                    "x": 1.02,
                    "yref": "y",
                    "y": mean_val,
                    "text": f"Mean: {_fmt_label(mean_val)}",
                    "showarrow": False,
                    "font": {"size": 10, "color": "rgba(59, 130, 246, 0.7)"},
                    "xanchor": "left",
                    "bgcolor": "rgba(59, 130, 246, 0.08)",
                    "borderpad": 2,
                })

                # Median line only if significantly different from mean (>5%)
                if abs(mean_val - median_val) / (abs(mean_val) or 1) > 0.05:
                    shapes.append({
                        "type": "line",
                        "xref": "paper",
                        "x0": 0,
                        "x1": 1,
                        "y0": median_val,
                        "y1": median_val,
                        "line": {
                            "color": "rgba(251, 146, 60, 0.5)",
                            "width": 1,
                            "dash": "dot",
                        },
                    })
                    annotations.append({
                        "xref": "paper",
                        "x": 1.02,
                        "yref": "y",
                        "y": median_val,
                        "text": f"Median: {_fmt_label(median_val)}",
                        "showarrow": False,
                        "font": {"size": 10, "color": "rgba(251, 146, 60, 0.7)"},
                        "xanchor": "left",
                        "bgcolor": "rgba(251, 146, 60, 0.08)",
                        "borderpad": 2,
                    })

                # ── IQR band (Q1-Q3 range) for context ──
                q1 = stats.get("q1", y_sorted[len(y_sorted) // 4] if y_sorted else 0)
                q3 = stats.get("q3", y_sorted[3 * len(y_sorted) // 4] if y_sorted else 0)
                if q1 < q3:
                    shapes.append({
                        "type": "rect",
                        "xref": "paper",
                        "x0": 0,
                        "x1": 1,
                        "y0": q1,
                        "y1": q3,
                        "fillcolor": "rgba(16, 185, 129, 0.04)",
                        "line": {"width": 0},
                        "layer": "below",
                    })

            # ────────────────────────────────────────────────────────────────
            # 2. TREND LINE (Linear Regression)
            # ────────────────────────────────────────────────────────────────
            # Only for line, bar, scatter, area charts with enough points
            if chart_type in ("line", "bar", "scatter", "area", "multi_line") and len(y_values) >= 4:
                try:
                    import numpy as np

                    # Use numeric indices for x if x is categorical
                    numeric_indices = list(range(len(y_values)))
                    x_numeric = [
                        float(v) if isinstance(v, (int, float)) else i
                        for i, v in enumerate(x_arr)
                    ]
                    if all(v == 0 for v in x_numeric):
                        x_numeric = numeric_indices

                    x_arr_np = np.array(x_numeric, dtype=float)
                    y_arr_np = np.array(y_values, dtype=float)

                    # Linear regression: y = slope * x + intercept
                    A = np.vstack([x_arr_np, np.ones_like(x_arr_np)]).T
                    slope, intercept = np.linalg.lstsq(A, y_arr_np, rcond=None)[0]

                    # R-squared
                    y_pred = slope * x_arr_np + intercept
                    ss_res = np.sum((y_arr_np - y_pred) ** 2)
                    ss_tot = np.sum((y_arr_np - np.mean(y_arr_np)) ** 2)
                    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

                    # Only show trend if reasonably predictive (R² > 0.15 or slope is notable)
                    if r_squared > 0.15 or abs(slope / (np.mean(y_arr_np) or 1)) > 0.05:
                        trend_y = slope * x_arr_np + intercept

                        # Build categorical x labels for trend trace
                        trend_trace = {
                            "type": "scatter",
                            "mode": "lines",
                            "x": list(x_arr),
                            "y": list(trend_y),
                            "line": {
                                "color": "rgba(139, 92, 246, 0.6)",
                                "width": 2,
                                "dash": "dot",
                            },
                            "name": f"Trend",
                            "showlegend": True,
                            "hoverinfo": "skip",
                            "legendgroup": "trend",
                        }
                        overlay_traces.append(trend_trace)

                        # Confidence band (±1.96 * SE around prediction)
                        if len(y_values) >= 6 and r_squared > 0.3:
                            n_points = len(y_arr_np)
                            se = np.sqrt(ss_res / max(n_points - 2, 1))
                            x_mean = np.mean(x_arr_np)
                            x_var = np.sum((x_arr_np - x_mean) ** 2)

                            ci = []
                            for xi in x_arr_np:
                                se_fit = se * np.sqrt(
                                    1 / n_points + (xi - x_mean) ** 2 / max(x_var, 1e-10)
                                )
                                ci.append(1.96 * se_fit)

                            y_upper = [y_pred[i] + ci[i] for i in range(n_points)]
                            y_lower = [y_pred[i] - ci[i] for i in range(n_points)]

                            # Build confidence band as filled polygon
                            band_x = list(x_arr) + list(reversed(list(x_arr)))
                            band_y = y_upper + list(reversed(y_lower))

                            overlay_traces.append({
                                "type": "scatter",
                                "mode": "lines",
                                "x": band_x,
                                "y": band_y,
                                "fill": "toself",
                                "fillcolor": "rgba(139, 92, 246, 0.08)",
                                "line": {"color": "rgba(139, 92, 246, 0)", "width": 0},
                                "name": f"95% CI (R²={r_squared:.2f})",
                                "showlegend": True,
                                "hoverinfo": "skip",
                                "legendgroup": "trend",
                            })
                except ImportError:
                    pass  # numpy not available — skip trend line
                except Exception:
                    pass  # Non-fatal — trend line is best-effort

            # ────────────────────────────────────────────────────────────────
            # 3. OUTLIER MARKERS (from point_intelligence)
            # ────────────────────────────────────────────────────────────────
            if points_data:
                outlier_points = []
                for x_key, pt in points_data.items():
                    if pt.get("is_outlier"):
                        # Find the matching x value from the trace
                        matching_idx = None
                        for i, xv in enumerate(x_arr):
                            if str(xv) == x_key:
                                matching_idx = i
                                break
                        if matching_idx is not None and matching_idx < len(y_arr):
                            outlier_points.append({
                                "x": x_arr[matching_idx],
                                "y": y_arr[matching_idx],
                                "insight": pt.get("insight", "Outlier"),
                                "z_score": pt.get("z_score", 0),
                            })

                if len(outlier_points) >= 1 and len(outlier_points) <= len(x_arr) * 0.3:
                    for op in outlier_points:
                        is_high = op["z_score"] > 0
                        color = "#ef4444" if is_high else "#f59e0b"
                        arrow_dir = -30 if is_high else 28

                        annotations.append({
                            "x": op["x"],
                            "y": op["y"],
                            "xref": "x",
                            "yref": "y",
                            "text": f"{'⬆' if is_high else '⬇'} {op['insight'][:50]}",
                            "showarrow": True,
                            "arrowhead": 0,
                            "arrowcolor": color,
                            "ax": 0,
                            "ay": arrow_dir,
                            "font": {"size": 9, "color": color},
                            "bgcolor": f"{color}15",
                            "bordercolor": f"{color}40",
                            "borderwidth": 1,
                            "borderpad": 3,
                        })

            # ── Apply to payload ──
            layout["shapes"] = shapes
            layout["annotations"] = annotations
            if overlay_traces:
                chart_payload["traces"] = traces + overlay_traces

            # Add overlay metadata so frontend knows what's available
            chart_payload["statistical_overlays"] = {
                "has_trend_line": any(
                    t.get("name", "") == "Trend" for t in overlay_traces
                ),
                "has_reference_lines": any(
                    s.get("type") == "line" and s.get("xref") == "paper"
                    for s in shapes
                ),
                "has_outlier_markers": len(
                    [a for a in annotations if a.get("showarrow")]
                )
                > 0,
            }

        except Exception as e:
            logger.warning(f"Statistical overlay computation failed (non-fatal): {e}")

        return chart_payload

    def _apply_semantic_autolayout(
        self,
        chart_payload: Dict[str, Any],
        chart_config: Dict[str, Any],
        df: pl.DataFrame,
    ) -> Dict[str, Any]:
        """
        Apply Flint-inspired semantic auto-layout to the rendered payload.

        - Infers semantic types (currency, percentage, date, ...) for the
          columns used by the chart from column names, dtypes, and values.
        - Declares them on chart_config (so consumers can see them) and
          attaches them to the payload + trace `_axis_metadata`.
        - Runs the auto-layout pass: axis titles, tick formatting,
          zero baselines for bars, label rotation for dense categories.

        Best-effort: never raises.
        """
        try:
            # Work on a copy so we never mutate the caller's chart_config
            # (avoids stale inferred types leaking into cached/reused configs).
            config = dict(chart_config or {})
            semantic_types = infer_semantic_types(df, config)

            # Expose declared semantic types on the payload so the
            # frontend + consumers can reference them without re-inferring.
            declared = {col: st.value for col, st in semantic_types.items()}
            if declared:
                chart_payload["semantic_types"] = declared

            layout = chart_payload.get("layout", {})
            # Single-series payloads use "traces"; multi-series use "data".
            traces = chart_payload.get("traces") or chart_payload.get("data") or []

            apply_auto_layout(
                layout=layout,
                semantic_types=semantic_types,
                chart_config=config,
                traces=traces,
            )
            chart_payload["layout"] = layout
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Semantic auto-layout failed (non-fatal): {e}")

        return chart_payload

    def _generate_point_insight(
        self,
        val,
        mean,
        std,
        rank,
        total,
        vs_avg_pct,
        is_outlier,
        percentile,
        x_key,
        y_col,
    ) -> str:
        """Generate a concise, meaningful insight sentence for a single data point."""

        parts = []

        # Outlier flag — highest signal
        if is_outlier and val > mean:
            parts.append(f"Statistical outlier — unusually high {y_col}")
        elif is_outlier and val < mean:
            parts.append(f"Statistical outlier — unusually low {y_col}")

        # Rank-based insight
        if rank == 1:
            parts.append(f"Highest {y_col} across all {total} categories")
        elif rank == 2 and total > 3:
            parts.append(f"2nd highest — in the top tier")
        elif rank == total:
            parts.append(f"Lowest {y_col} across all {total} categories")
        elif rank == total - 1 and total > 3:
            parts.append(f"2nd lowest — near the bottom")

        # Deviation-based insight (only if not already covered by outlier/rank)
        if not parts:
            if vs_avg_pct > 40:
                parts.append(f"{vs_avg_pct:+.1f}% above average — a significant leader")
            elif vs_avg_pct > 15:
                parts.append(f"{vs_avg_pct:+.1f}% above average — a solid performer")
            elif vs_avg_pct > 0:
                parts.append(f"Slightly above average ({vs_avg_pct:+.1f}%)")
            elif vs_avg_pct > -15:
                parts.append(f"Slightly below average ({vs_avg_pct:+.1f}%)")
            elif vs_avg_pct > -40:
                parts.append(f"{vs_avg_pct:+.1f}% below average — underperforming")
            else:
                parts.append(f"{vs_avg_pct:+.1f}% below average — significantly trailing")

        # Add std context for outliers
        if is_outlier and std > 0:
            z = abs(val - mean) / std
            parts.append(f"{z:.1f}σ from the mean")

        return " · ".join(parts)

    async def render_chart(
        self, df: pl.DataFrame, chart_config: Dict[str, Any], theme: str = "light"
    ) -> Dict[str, Any]:
        """
        Main rendering method: DataFrame + config → Plotly chart.

        Args:
            df: Polars DataFrame with data
            chart_config: Chart configuration dict
            theme: Visual theme ("light" or "dark")

        Returns:
            Dict with Plotly chart data, layout, and metadata
        """
        start_time = datetime.now(timezone.utc).replace(tzinfo=None)

        try:
            # Validate inputs
            if df is None or df.is_empty():
                raise ValueError("DataFrame is empty")

            if not chart_config:
                raise ValueError("Chart config is required")

            # Parse chart config
            config = self._parse_config(chart_config)

            # Validate config against DataFrame (now permissive - no longer raises)
            # Validation is now handled inside hydrate_chart with graceful degradation

            # Handle both string and enum types for chart_type
            chart_type_str = (
                config.chart_type.value
                if hasattr(config.chart_type, "value")
                else config.chart_type
            )

            # Hydrate: DataFrame → Plotly traces
            logger.info(f"Hydrating {chart_type_str} chart...")
            traces, rows_used = hydrate_chart(df, config)

            if not traces:
                raise HydrationError("No traces generated")

            # Render: Traces → Final Plotly payload
            logger.info(f"Rendering chart with {len(traces)} trace(s)...")
            chart_payload = self.renderer.render(
                chart_type=chart_type_str,
                title=chart_config.get("title", "Chart"),
                traces=traces,
                rows_used=rows_used,
                theme=theme,
                colorscale=chart_config.get("colorscale"),
            )

            # Add metadata
            chart_payload["metadata"] = {
                "rows_used": rows_used,
                "total_rows": len(df),
                "columns": config.columns,
                "chart_type": chart_type_str,
                "render_time_ms": (datetime.now(timezone.utc).replace(tzinfo=None) - start_time).total_seconds() * 1000,
            }

            # ── Honest sampling metadata ──
            # Tells the frontend how many points are actually shown vs the
            # original count when LTTB/category-caps downsampled the traces,
            # so it can display a "shown of total" badge instead of silently
            # truncating. Best-effort: never raises.
            try:
                sampling = aggregate_sampling_metadata(
                    chart_payload.get("traces", traces)
                )
                if sampling:
                    chart_payload["metadata"]["sampling"] = sampling
            except Exception as e:
                logger.debug(f"Sampling metadata aggregation skipped: {e}")

            # ── Compute per-point statistical intelligence ──
            try:
                point_intel = self._compute_point_intelligence(
                    traces=chart_payload.get("traces", traces),
                    df=df,
                    chart_config=chart_config,
                )
                if point_intel:
                    chart_payload["point_intelligence"] = point_intel
            except Exception as e:
                logger.warning(f"Point intelligence skipped: {e}")

            # ── Compute and attach statistical overlays ──
            try:
                chart_payload = self._compute_and_attach_overlays(
                    chart_payload=chart_payload,
                    chart_config=chart_config,
                )
            except Exception as e:
                logger.warning(f"Statistical overlays skipped: {e}")

            # ── Semantic auto-layout (Flint-inspired) ──
            # Method is fully self-guarded (documented never to raise).
            chart_payload = self._apply_semantic_autolayout(
                chart_payload=chart_payload,
                chart_config=chart_config,
                df=df,
            )

            self._render_count += 1
            logger.info(
                f"✓ Chart rendered successfully ({chart_payload['metadata']['render_time_ms']:.0f}ms)"
            )

            return chart_payload

        except HydrationError as e:
            self._error_count += 1
            logger.error(f"✗ Hydration error: {e}")
            raise

        except Exception as e:
            self._error_count += 1
            logger.error(f"✗ Chart rendering failed: {e}", exc_info=True)
            raise

    async def render_chart_from_config(
        self, chart_config: Dict[str, Any], dataset_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Render chart from config with automatic dataset loading.

        Args:
            chart_config: Chart configuration
            dataset_id: Optional dataset ID (if not in config)

        Returns:
            Rendered chart payload
        """
        try:
            # Extract dataset_id
            ds_id = chart_config.get("dataset_id") or dataset_id
            if not ds_id:
                raise ValueError("dataset_id is required")

            # Load dataset using enhanced_dataset_service
            logger.info(f"Loading dataset {ds_id}...")

            # Get user_id from config if provided, otherwise use None
            user_id = chart_config.get("user_id")  # ← was: config.get("user_id")
            if not user_id:
                raise ValueError("user_id is required in config for dataset loading")

            # Load the dataset data
            df = await enhanced_dataset_service.load_dataset_data(ds_id, user_id)

            # Now render the chart with the loaded dataframe
            return await self.render_chart(df, chart_config)  # ← was: render_chart(df, config)

        except Exception as e:
            logger.error(f"✗ Failed to render chart from config: {e}")
            raise

    async def render_multiple_charts(
        self,
        df: pl.DataFrame,
        chart_configs: List[Dict[str, Any]],
        theme: str = "light",
    ) -> List[Dict[str, Any]]:
        """
        Render multiple charts in parallel.

        Args:
            df: Polars DataFrame
            chart_configs: List of chart configurations
            theme: Visual theme

        Returns:
            List of rendered charts
        """
        logger.info(f"Rendering {len(chart_configs)} charts in parallel...")

        tasks = [self.render_chart(df, config, theme) for config in chart_configs]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out errors
        charts = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Chart {i} failed: {result}")
            else:
                charts.append(result)

        logger.info(f"✓ Rendered {len(charts)}/{len(chart_configs)} charts successfully")
        return charts

    def _normalize_chart_type(self, chart_type_str: str) -> str:
        """
        Normalize chart type names from various formats to valid ChartType values.

        Examples:
        - 'bar_chart' -> 'bar'
        - 'scatter_plot' -> 'scatter'
        - 'line_chart' -> 'line'
        - 'pie_chart' -> 'pie'
        - 'box_plot' -> 'box_plot' (already valid)
        - 'box' -> 'box_plot'
        - 'donut' -> 'pie'
        """
        # Mapping from alternative names to canonical ChartType values
        type_mapping = {
            # Basic aliases
            "bar_chart": "bar",
            "line_chart": "line",
            "pie_chart": "pie",
            "histogram_chart": "histogram",
            "scatter_plot": "scatter",
            "heatmap_chart": "heatmap",
            "treemap_chart": "treemap",
            "area_chart": "area",
            "radar_chart": "radar",
            "bubble_chart": "bubble",
            "waterfall_chart": "waterfall",
            "funnel_chart": "funnel",
            "gauge_chart": "gauge",
            # Short aliases
            "donut": "pie",
            "donut_chart": "pie",
            "box": "box_plot",
            # Multi-series aliases
            "multi_line_chart": "multi_line",
            "stacked_area_chart": "stacked_area",
            "grouped_bar_chart": "grouped_bar",
            "stacked_bar_chart": "stacked_bar",
        }

        normalized = chart_type_str.lower().strip()
        return type_mapping.get(normalized, normalized)

    def _parse_config(self, chart_config: Dict[str, Any]) -> ChartConfig:
        """
        Parse chart config dict to ChartConfig object.

        Args:
            chart_config: Raw config dict

        Returns:
            ChartConfig object
        """
        try:
            # Handle chart_type
            chart_type_str = chart_config.get("chart_type", "bar")
            if isinstance(chart_type_str, str):
                # Normalize the chart type name first
                normalized_type = self._normalize_chart_type(chart_type_str)
                chart_type = ChartType(normalized_type)
            else:
                chart_type = chart_type_str

            chart_types_requiring_two_cols = {
                ChartType.BAR,
                ChartType.LINE,
                ChartType.GROUPED_BAR,
                ChartType.STACKED_BAR,
                ChartType.MULTI_LINE,
                ChartType.STACKED_AREA,
                ChartType.SCATTER,
                ChartType.AREA,
            }

            # Extract columns
            columns = chart_config.get("columns", [])
            if not columns:
                # Try x_axis, y_axis fallback (with underscore)
                x_axis = chart_config.get("x_axis")
                y_axis = chart_config.get("y_axis")
                if x_axis:
                    columns.append(x_axis)
                if y_axis:
                    columns.append(y_axis)
            # Also check for x, y (no underscore) - common in AI-generated configs
            if not columns:
                x_col = chart_config.get("x")
                y_col = chart_config.get("y")
                if x_col:
                    columns.append(x_col)
                if y_col:
                    columns.append(y_col)

            # Handle group_by as either string or list
            raw_group_by = chart_config.get("group_by")
            if isinstance(raw_group_by, str):
                group_by = [raw_group_by]
            elif isinstance(raw_group_by, list):
                group_by = [g for g in raw_group_by if isinstance(g, str) and g.strip()]
            else:
                group_by = []

            # Auto-repair AI configs that provide only one column for 2-axis charts.
            # Prefer using group_by as X when present; otherwise duplicate the column and use COUNT.
            aggregation = chart_config.get("aggregation", "none")
            if len(columns) == 1 and chart_type in chart_types_requiring_two_cols:
                if group_by and group_by[0] != columns[0]:
                    columns = [group_by[0], columns[0]]
                    logger.info(
                        "Auto-repaired single-column chart config using group_by: "
                        f"chart_type={chart_type}, columns={columns}"
                    )
                else:
                    columns = [columns[0], columns[0]]
                    if str(aggregation).lower() in {"none", "", "null"}:
                        aggregation = "count"
                    logger.info(
                        "Auto-repaired single-column chart config with COUNT fallback: "
                        f"chart_type={chart_type}, columns={columns}, aggregation={aggregation}"
                    )

            # Create ChartConfig
            config = ChartConfig(
                type=ComponentType.CHART,
                title=chart_config.get("title", "Chart"),
                chart_type=chart_type,
                columns=columns,
                aggregation=aggregation,
                group_by=group_by,
                span=chart_config.get("span", 1),
            )

            return config

        except Exception as e:
            logger.error(f"Failed to parse chart config: {e}")
            raise ValueError(f"Invalid chart config: {e}")

    # ── Multi-series smart rendering ─────────────────────────────────────────

    MULTI_SERIES_TYPES = {"dual_axis", "facet", "combo", "multi_series", "small_multiples"}

    async def render_multi_series(
        self,
        df: pl.DataFrame,
        metric_columns: List[str],
        x_column: str,
        title: str = "Chart",
        analysis_intent: Optional[str] = None,
        time_indexed: bool = False,
        theme: str = "light",
    ) -> Dict[str, Any]:
        """
        Smart multi-series rendering via MultiSeriesChartService.

        Runs pattern detection → selects the best strategy → renders with the
        correct renderer (overlay / dual_axis / facet / combo / grouped / stacked).

        Use this instead of render_chart() when:
        - You have 2+ metric columns and want the system to choose the right layout
        - The chart type might be dual_axis or faceted (hydrate.py can't do these)
        - You want pattern insights attached to the result
        """
        from services.charts.multi_series_chart_service import (
            multi_series_chart_service,
        )

        result = await multi_series_chart_service.generate_chart(
            df=df,
            metric_columns=metric_columns,
            x_column=x_column,
            title=title,
            analysis_intent=analysis_intent,
            time_indexed=time_indexed,
            auto_strategy=True,
        )

        # ── Semantic auto-layout for multi-series charts ──
        # The multi-series path bypasses render_chart(), so apply the same
        # Flint-inspired semantic pass here. _apply_semantic_autolayout is
        # fully self-guarded (never raises), so no extra try/except needed.
        # Note: with multiple metrics, axis format/tooltip hints reflect the
        # FIRST metric's semantic type (best-effort for mixed-unit charts).
        chart = result.get("chart")
        if isinstance(chart, dict) and "layout" in chart:
            # Map the auto-selected strategy to a chart_type so the
            # auto-layout rules (e.g. zero baseline for bars) apply
            # correctly instead of assuming multi_line.
            strategy = result.get("strategy_used", "overlay")
            chart_type = {
                "grouped": "grouped_bar",
                "stacked": "stacked_bar",
                "facet": "multi_line",
                "small_multiples": "multi_line",
                "combo": "combo",
                "dual_axis": "dual_axis",
            }.get(strategy, "multi_line")
            chart_config = {
                "columns": [x_column] + list(metric_columns),
                "chart_type": chart_type,
                "title": title,
            }
            chart = self._apply_semantic_autolayout(
                chart_payload=chart,
                chart_config=chart_config,
                df=df,
            )
            result["chart"] = chart

        return result

    async def render_chart_smart(
        self,
        df: pl.DataFrame,
        chart_config: Dict[str, Any],
        theme: str = "light",
    ) -> Dict[str, Any]:
        """
        Drop-in upgrade to render_chart() that routes multi-series types through
        MultiSeriesChartService while keeping single-series on the existing path.

        Routing rules:
        - chart_type in {dual_axis, facet, combo, multi_series} → multi-series path
        - 3+ columns with multi_line/grouped_bar/stacked_bar → multi-series path
        - everything else → existing render_chart()
        """
        chart_type = chart_config.get("chart_type", "").lower()
        columns = chart_config.get("columns", [])

        use_multi = chart_type in self.MULTI_SERIES_TYPES or (
            chart_type in {"multi_line", "grouped_bar", "stacked_bar", "stacked_area"}
            and len(columns) >= 3
        )

        if use_multi and len(columns) >= 2:
            x_col = columns[0]
            metric_cols = columns[1:]
            intent_map = {
                "stacked_bar": "composition",
                "stacked_area": "composition",
                "grouped_bar": "comparison",
                "multi_line": "trend",
                "dual_axis": "comparison",
                "combo": "diagnosis",
                "facet": "comparison",
                "small_multiples": "comparison",
            }
            intent = intent_map.get(chart_type, chart_config.get("analysis_intent"))
            time_indexed = chart_type in {"multi_line", "stacked_area", "dual_axis", "combo"}

            return await self.render_multi_series(
                df=df,
                metric_columns=metric_cols,
                x_column=x_col,
                title=chart_config.get("title", "Chart"),
                analysis_intent=intent,
                time_indexed=time_indexed,
                theme=theme,
            )

        return await self.render_chart(df, chart_config, theme)

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            "total_renders": self._render_count,
            "total_errors": self._error_count,
            "success_rate": (
                (self._render_count / (self._render_count + self._error_count))
                if (self._render_count + self._error_count) > 0
                else 1.0
            ),
            "cache_size": len(self._cache),
        }


# Singleton instance
chart_render_service = ChartRenderService()

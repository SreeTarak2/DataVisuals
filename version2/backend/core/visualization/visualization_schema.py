"""
Visualization Intent Schema (VIS) — Core Models
================================================
Renderer-agnostic visualization contract for DataSage.

Backend produces VIS. Frontend adapters translate VIS into
Plotly, ECharts, or any visualization library.

Key design decisions:
- `VISDataSeries` stores rendered/aggregated data arrays (no Plotly keys)
- Series metadata hints at chart family but adapter owns all styling
- Multi-series layouts expressed via `series_strategy` + `facet_config`
- Analytics, interaction, narrative are first-class, renderer-independent
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal, Union
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════

class VISDataSeriesType(str, Enum):
    """
    All visualization families supported by VIS.

    Covers Plotly, ECharts, and library-agnostic intents.
    ECharts-only types (graph, sankey, parallel, lines, tree,
    theme_river, pictorial_bar, effect_scatter, map) have full
    first-class status — each adapter handles or degrades them.

    Variant configs (step, smooth, rose_type, etc.) live in
    VISVariantConfig, NOT as separate enum entries.
    """
    # ── Core shared types (Plotly + ECharts) ──
    BAR = "bar"
    LINE = "line"
    SCATTER = "scatter"
    PIE = "pie"
    DONUT = "donut"
    HISTOGRAM = "histogram"
    BOX_PLOT = "box_plot"
    HEATMAP = "heatmap"
    TREEMAP = "treemap"
    SUNBURST = "sunburst"
    RADAR = "radar"
    CANDLESTICK = "candlestick"
    FUNNEL = "funnel"

    # ── Shared with config differences ──
    AREA = "area"                            # Plotly: scatter+fill; ECharts: line+areaStyle
    BUBBLE = "bubble"                        # Plotly: scatter+size; ECharts: scatter+symbolSize
    WATERFALL = "waterfall"                  # Plotly: native; ECharts: custom/bar
    VIOLIN = "violin"                        # Plotly: native; ECharts: custom
    GAUGE = "gauge"                          # Plotly: indicator; ECharts: gauge
    BULLET = "bullet"                        # Plotly: indicator; ECharts: gauge+progress
    CORRELATION_MATRIX = "correlation_matrix" # Both via heatmap

    # ── Multi-series primitives (adapter maps to config) ──
    MULTI_LINE = "multi_line"
    GROUPED_BAR = "grouped_bar"
    STACKED_BAR = "stacked_bar"
    STACKED_AREA = "stacked_area"

    # ── ECharts-native types (Plotly degrades gracefully) ──
    GRAPH = "graph"                          # Force-directed graph (nodes + links)
    SANKEY = "sankey"                        # Flow diagram (source + target + value)
    PARALLEL = "parallel"                    # Parallel coordinates (multi-dim array)
    LINES = "lines"                          # Flow/migration lines (coordinate pairs)
    TREE = "tree"                            # Hierarchical tree (nested children)
    THEME_RIVER = "theme_river"              # Time-based flow (date, value, category)
    PICTORIAL_BAR = "pictorial_bar"          # Bar with custom symbol/image
    EFFECT_SCATTER = "effect_scatter"        # Scatter with ripple animation
    MAP = "map"                              # Geographical map (requires map data)

    # ── Strategic compositions ──
    DUAL_AXIS = "dual_axis"
    COMBO = "combo"
    FACET = "facet"
    SMALL_MULTIPLES = "small_multiples"


class SeriesStrategyType(str, Enum):
    """How multiple series are composed in a single visualization."""
    OVERLAY = "overlay"           # Multiple series on shared axes
    DUAL_AXIS = "dual_axis"       # Left/right y-axes
    COMBO = "combo"               # Bars + line combination
    FACET = "facet"               # Faceted subplots (shared x or y)
    SMALL_MULTIPLES = "small_multiples"  # Independent subplots in grid
    GROUPED = "grouped"           # Grouped bars side by side
    STACKED = "stacked"           # Stacked bars or areas
    NONE = "none"                 # Single series


class AnalysisIntentType(str, Enum):
    """What analytical question this visualization answers."""
    TREND = "trend"
    COMPARISON = "comparison"
    COMPOSITION = "composition"
    DISTRIBUTION = "distribution"
    CORRELATION = "correlation"
    RANKING = "ranking"
    ANOMALY = "anomaly"
    FORECAST = "forecast"
    DIAGNOSIS = "diagnosis"
    PROFILE = "profile"
    HIERARCHY = "hierarchy"
    FLOW = "flow"
    UNKNOWN = "unknown"


class VISAxisType(str, Enum):
    """Axis type — renderer-agnostic."""
    LINEAR = "linear"
    LOG = "log"
    CATEGORY = "category"
    DATE = "date"
    MULTICATEGORY = "multicategory"
    TIME = "time"


class VISAxisFormat(str, Enum):
    """Format hint for axis values — adapter uses for tick labels."""
    NUMBER = "number"
    INTEGER = "integer"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    DURATION = "duration"
    SCIENTIFIC = "scientific"
    AUTO = "auto"


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ═══════════════════════════════════════════════════════════════════
# DATA SERIES — The core data container
# ═══════════════════════════════════════════════════════════════════

# _sampled and _axis_metadata are internal-use dicts with no fixed shape
SampledInfo = Optional[Dict[str, Any]]
AxisMetadata = Optional[Dict[str, Any]]


# ═══════════════════════════════════════════════════════════════════
# GRAPH/SANKEY/TREE DATA MODELS
# ═══════════════════════════════════════════════════════════════════

class VISNode(BaseModel):
    """
    A node in a graph, sankey, or tree structure.

    ECharts-native: graph, sankey, tree all use node-like structures.
    Adapts to:
    - Plotly: not natively supported (degrades to table or non-interactive)
    - ECharts: nodes[] for graph and sankey; nested tree for tree type
    """
    model_config = {"extra": "forbid"}

    name: str = Field(..., description="Node identifier / display name")
    value: Optional[Union[float, int]] = Field(default=None, description="Numeric value for node sizing")
    category: Optional[int] = Field(default=None, description="Category index for coloring")
    x: Optional[float] = Field(default=None, description="Fixed x position (graph layout)")
    y: Optional[float] = Field(default=None, description="Fixed y position (graph layout)")
    symbol: Optional[str] = Field(default=None, description="ECharts symbol type: 'circle', 'rect', 'diamond', SVG path")
    symbol_size: Optional[Union[float, int]] = Field(default=None)
    label_style: Optional[Dict[str, Any]] = Field(default=None, description="Node label styling")
    item_style: Optional[Dict[str, Any]] = Field(default=None, description="Node styling overrides")
    children: Optional[List[VISNode]] = Field(default=None, description="Child nodes (for tree type)")
    extra: Optional[Dict[str, Any]] = Field(default=None, description="Free-form extra attributes")


class VISLink(BaseModel):
    """
    A directed link/edge between two nodes.

    Used by:
    - graph: source → target relationship
    - sankey: source → target flow with value
    """
    model_config = {"extra": "forbid"}

    source: Union[str, int] = Field(..., description="Source node name or index")
    target: Union[str, int] = Field(..., description="Target node name or index")
    value: Optional[Union[float, int]] = Field(default=None, description="Link weight / flow magnitude")
    label: Optional[str] = Field(default=None, description="Link label")
    line_style: Optional[Dict[str, Any]] = Field(default=None, description="Line styling overrides")
    extra: Optional[Dict[str, Any]] = Field(default=None, description="Free-form extra attributes")


# ═══════════════════════════════════════════════════════════════════
# VARIANT CONFIG — Renderer-agnostic variant hints
# ═══════════════════════════════════════════════════════════════════

class VISVariantConfig(BaseModel):
    """
    Renderer-agnostic variant configuration.

    These are NOT adapter escape hatches — they describe visual intent
    that is meaningful across rendering libraries.

    Example: a "step line" is a line chart with step interpolation,
    not an ECharts-specific concept.

    Each adapter uses what it supports and ignores the rest.
    """
    model_config = {"extra": "forbid"}

    # ── Line variants ──
    step: Optional[Literal["start", "middle", "end"]] = Field(
        default=None,
        description="Step line interpolation (Plotly: line.shape; ECharts: line.step)"
    )
    smooth: Optional[bool] = Field(
        default=None,
        description="Smooth bezier curves (Plotly: line.shape='spline'; ECharts: line.smooth)"
    )
    show_area: Optional[bool] = Field(
        default=None,
        description="Fill area under the line (Plotly: fill='tozeroy'; ECharts: areaStyle)"
    )

    # ── Pie variants ──
    donut_hole: Optional[float] = Field(
        default=None, ge=0, le=0.95,
        description="Hole ratio for donut (Plotly: hole; ECharts: radius inner/outer)"
    )
    rose_type: Optional[Literal["radius", "area"]] = Field(
        default=None,
        description="Rose diagram style (ECharts: pie.roseType)"
    )

    # ── Bar variants ──
    realtime_sort: Optional[bool] = Field(
        default=None,
        description="Bar race sorting (ECharts: realtimeSort)"
    )
    orientation: Optional[Literal["vertical", "horizontal"]] = Field(
        default=None,
        description="Bar orientation (Plotly: orientation; ECharts: axis config)"
    )
    show_background: Optional[bool] = Field(
        default=None,
        description="Bar background fill (ECharts: showBackground)"
    )

    # ── Scatter variants ──
    effect_ripple: Optional[bool] = Field(
        default=None,
        description="Ripple animation effect (ECharts: effectScatter)"
    )

    # ── PictorialBar variants ──
    symbol_path: Optional[str] = Field(
        default=None,
        description="SVG path or image URL for pictorial bars (ECharts: pictorialBar.symbol)"
    )
    symbol_repeat: Optional[Literal["fixed", "repeat"]] = Field(
        default=None,
        description="Symbol repetition for pictorial bars"
    )

    # ── Graph variants ──
    graph_layout: Optional[Literal["force", "circular", "none"]] = Field(
        default=None,
        description="Graph layout algorithm (ECharts: graph.layout)"
    )
    graph_force_repulsion: Optional[float] = Field(
        default=None,
        description="Force-directed repulsion strength"
    )
    graph_roam: Optional[bool] = Field(
        default=None,
        description="Enable graph dragging/zooming (ECharts: graph.roam)"
    )

    # ── Gauge variants ──
    gauge_progress: Optional[bool] = Field(
        default=None,
        description="Show progress arc (ECharts: gauge.progress)"
    )
    gauge_pointer: Optional[bool] = Field(
        default=None,
        description="Show gauge pointer needle"
    )

    # ── Map variants ──
    map_name: Optional[str] = Field(
        default=None,
        description="Geographic map name (ECharts: map.map='world'|'USA')"
    )
    map_roam: Optional[bool] = Field(
        default=None,
        description="Enable map zoom/pan (ECharts: map.roam)"
    )

    # ── Parallel variants ──
    parallel_axis_order: Optional[List[str]] = Field(
        default=None,
        description="Order of parallel axes (ECharts: parallelAxis)"
    )


class VISDataSeries(BaseModel):
    """
    A single data series — renderer-agnostic, no Plotly keys.

    Adapters use `series_type` to decide trace type, styling, etc.
    Fields are designed to cover all supported chart families:

    - Bar/Line/Area/Scatter: x + y
    - Pie: labels + values
    - Heatmap: z (2D matrix) + optional x/y tick labels
    - Treemap/Sunburst: ids + parents + labels + values
    - Box/Violin: y_raw (all values per group)
    - Waterfall: x + y + measure type
    - Candlestick: x + open + high + low + close
    - Radar: r + theta
    """
    model_config = {"extra": "forbid"}

    # Identity
    name: str = Field(default="", description="Series name / legend label")
    series_type: VISDataSeriesType = Field(
        default=VISDataSeriesType.BAR,
        description="Hints which chart family this series belongs to"
    )

    # Standard x/y data (bar, line, area, scatter, histogram)
    x: Optional[List[Any]] = Field(default=None, description="X-axis values")
    y: Optional[List[Union[float, int, None]]] = Field(default=None, description="Y-axis values")

    # Pie: labels + values
    labels: Optional[List[str]] = Field(default=None, description="Pie slice labels")
    values: Optional[List[Union[float, int]]] = Field(default=None, description="Pie slice values")

    # Heatmap: 2D matrix
    z: Optional[List[List[Union[float, int, None]]]] = Field(
        default=None, description="2D matrix for heatmap"
    )
    x_labels: Optional[List[str]] = Field(default=None, description="Heatmap x tick labels")
    y_labels: Optional[List[str]] = Field(default=None, description="Heatmap y tick labels")

    # Treemap / Sunburst: hierarchical
    ids: Optional[List[str]] = Field(default=None, description="Hierarchical node IDs")
    parents: Optional[List[str]] = Field(default=None, description="Parent IDs for hierarchy")
    labels_hier: Optional[List[str]] = Field(
        default=None, description="Hierarchy display labels"
    )

    # Box / Violin: raw values per group
    y_raw: Optional[List[Union[float, int]]] = Field(
        default=None, description="Raw Y values for box/violin (single series)"
    )

    # Waterfall: cumulative breakdown
    measure: Optional[List[Literal["relative", "total"]]] = Field(
        default=None, description="Waterfall measure type per step"
    )

    # Candlestick: OHLC
    open: Optional[List[Union[float, int]]] = Field(default=None)
    high: Optional[List[Union[float, int]]] = Field(default=None)
    low: Optional[List[Union[float, int]]] = Field(default=None)
    close: Optional[List[Union[float, int]]] = Field(default=None)

    # Radar: polar coordinates
    r: Optional[List[Union[float, int]]] = Field(default=None, description="Radial values")
    theta: Optional[List[str]] = Field(default=None, description="Angular categories")

    # Gauge / Bullet / Indicator: single value
    value: Optional[Union[float, int]] = Field(default=None, description="Single value for gauge/bullet")
    target: Optional[Union[float, int]] = Field(default=None, description="Target value for bullet")
    gauge_max: Optional[Union[float, int]] = Field(default=None, description="Gauge axis max")

    # Choropleth: geographic
    locations: Optional[List[str]] = Field(default=None, description="Geo location codes")
    z_geo: Optional[List[Union[float, int]]] = Field(default=None, description="Geo values")

    # Grouping context (for multi-series)
    group: Optional[str] = Field(
        default=None,
        description="Group value this series belongs to (e.g. 'Electronics' for grouped_bar)"
    )
    group_key: Optional[str] = Field(
        default=None,
        description="Column name used for grouping (e.g. 'category')"
    )

    # Sampling / downsampling metadata
    sampled: Optional[SampledInfo] = Field(
        default=None,
        description="Downsampling metadata: original_count, displayed_count, method"
    )

    # ── Graph / Sankey / Tree: nodes and links ──
    nodes: Optional[List[VISNode]] = Field(
        default=None,
        description="Node list for graph, sankey, tree types"
    )
    links: Optional[List[VISLink]] = Field(
        default=None,
        description="Link/edge list for graph, sankey types"
    )
    children: Optional[List[VISNode]] = Field(
        default=None,
        description="Root-level children for tree type (nested hierarchy)"
    )

    # ── Parallel coordinates ──
    dimensions: Optional[List['VISAxis']] = Field(
        default=None,
        description="Parallel coordinate axes (ECharts: parallelAxis)"
    )
    data_rows: Optional[List[List[Any]]] = Field(
        default=None,
        description="Multi-dimensional data array for parallel coordinates"
    )

    # ── Lines (flow/migration) ──
    coords: Optional[List[List[List[float]]]] = Field(
        default=None,
        description="Coordinate paths for lines type: [[[x1,y1],[x2,y2]], ...]"
    )

    # ── ThemeRiver ──
    theme_data: Optional[List[List[Any]]] = Field(
        default=None,
        description="ThemeRiver data: [[date, value, category], ...]"
    )

    # ── Pictorial bar ──
    pictorial_symbol: Optional[str] = Field(
        default=None,
        description="SVG path or image URL for pictorialBar symbols"
    )

    # Axis format hints (renderer-agnostic)
    axis_hints: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Format hints: {'x_format': 'date', 'y_format': 'currency'}"
    )



    @field_validator("x", "y", "labels", "values", mode="before")
    @classmethod
    def ensure_list_or_none(cls, v):
        if v is None:
            return v
        if isinstance(v, list):
            return v
        return [v]

    @field_validator("series_type", mode="before")
    @classmethod
    def normalize_series_type(cls, v):
        if isinstance(v, str):
            return v.lower().replace("_chart", "").replace("_plot", "")
        return v


class VISSeriesCollection(BaseModel):
    """
    Group of related series — used for multi-series visualizations.

    E.g., a grouped_bar has multiple series, one per group value.
    """
    model_config = {"extra": "forbid"}

    series: List[VISDataSeries] = Field(default_factory=list)
    strategy: SeriesStrategyType = SeriesStrategyType.OVERLAY


# ═══════════════════════════════════════════════════════════════════
# AXIS SPECIFICATION
# ═══════════════════════════════════════════════════════════════════

class VISAxis(BaseModel):
    """Axis metadata — adapter uses this for tick formatting, titles, etc."""
    model_config = {"extra": "forbid"}

    field: Optional[str] = Field(default=None, description="Source column name")
    title: Optional[str] = Field(default=None, description="Display title (auto-generated if None)")
    axis_type: VISAxisType = VISAxisType.CATEGORY
    format: VISAxisFormat = VISAxisFormat.AUTO
    unit_prefix: str = Field(default="", description="E.g. $, £, €")
    unit_suffix: str = Field(default="", description="E.g. %, MPG, km")
    is_temporal: bool = Field(default=False, description="True if this axis is time-based")


# ═══════════════════════════════════════════════════════════════════
# INTERACTION CONFIG
# ═══════════════════════════════════════════════════════════════════

class VISInteraction(BaseModel):
    """Interaction settings — renderer must implement if set."""
    model_config = {"extra": "forbid"}

    cross_filterable: bool = Field(
        default=False,
        description="True if clicking this chart filters other charts"
    )
    drilldown_enabled: bool = Field(
        default=False,
        description="True if chart supports drill-down navigation"
    )
    drill_path: List[str] = Field(
        default_factory=list,
        description="Hierarchical column path: ['region', 'country', 'state', 'city']"
    )
    point_analysis: bool = Field(
        default=False,
        description="True if clicking a point triggers AI deep analysis"
    )


# ═══════════════════════════════════════════════════════════════════
# ANALYTICS OVERLAYS
# ═══════════════════════════════════════════════════════════════════

class ReferenceLine(BaseModel):
    """A reference line (mean, median, threshold, etc.) to overlay on a chart."""
    model_config = {"extra": "forbid"}

    label: str = Field(default="", description="Display label")
    value: Union[float, int] = Field(default=0, description="Y-axis value")
    line_type: Literal["mean", "median", "p75", "p90", "threshold", "target"] = "mean"
    color: Optional[str] = Field(default=None, description="Optional color hint")
    dash: Literal["solid", "dash", "dot", "dashdot"] = "dash"


class VISAnalytics(BaseModel):
    """Statistical overlays — adapter handles rendering them."""
    model_config = {"extra": "forbid"}

    show_average: bool = Field(default=False, description="Show mean reference line")
    show_median: bool = Field(default=False, description="Show median reference line")
    show_trendline: bool = Field(default=False, description="Show linear/LOESS trend line")
    show_anomalies: bool = Field(default=False, description="Highlight outlier points")
    show_forecast: bool = Field(default=False, description="Show forecast extension")
    reference_lines: List[ReferenceLine] = Field(default_factory=list)
    outlier_indices: List[int] = Field(default_factory=list, description="Indices of outlier points")


# ═══════════════════════════════════════════════════════════════════
# NARRATIVE
# ═══════════════════════════════════════════════════════════════════

class VISKeyNumber(BaseModel):
    """A key statistic displayed alongside the chart."""
    label: str
    value: Union[str, float, int]
    format: str = "number"


class VISNarrative(BaseModel):
    """Natural language explanation of the chart."""
    model_config = {"extra": "forbid"}

    headline: str = Field(default="", description="Insight-first headline (≤15 words)")
    description: str = Field(default="", description="Detailed explanation")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    badge_type: Optional[str] = Field(
        default=None,
        description="KEY FINDING | ANOMALY DETECTED | STRONG TREND | etc."
    )
    insight_annotation: str = Field(
        default="",
        description="One-sentence annotation with ≥1 specific number"
    )
    key_numbers: List[VISKeyNumber] = Field(default_factory=list, max_length=6)
    reading_guide: str = Field(default="", description="Action instruction for the user")
    drill_down_suggestion: Optional[str] = Field(
        default=None, description="Suggested next drill level"
    )


# ═══════════════════════════════════════════════════════════════════
# POINT INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════

class VISPointIntelligencePoint(BaseModel):
    """Per-category statistical intelligence."""
    value: float
    rank: int
    percentile: float
    z_score: float
    vs_avg_pct: float
    is_outlier: bool
    record_count: Optional[int] = None
    insight: str = ""


class VISPointIntelligenceStats(BaseModel):
    """Global statistics for the visualization."""
    mean: float = 0.0
    median: float = 0.0
    std: float = 0.0
    min: float = 0.0
    max: float = 0.0
    q1: float = 0.0
    q3: float = 0.0
    iqr: float = 0.0


class VISPointIntelligence(BaseModel):
    """Statistical intelligence for every data point in the chart."""
    y_label: str = ""
    x_label: str = ""
    total_records: int = 0
    stats: VISPointIntelligenceStats = VISPointIntelligenceStats()
    points: Dict[str, VISPointIntelligencePoint] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# FACET CONFIG
# ═══════════════════════════════════════════════════════════════════

class VIFacetConfig(BaseModel):
    """Configuration for faceted / small-multiples layouts."""
    model_config = {"extra": "forbid"}

    facet_column: str = Field(default="", description="Column to split facets by")
    facet_count: int = Field(default=1, ge=1, le=16)
    shared_x: bool = Field(default=True, description="Share x-axis across facets")
    shared_y: bool = Field(default=True, description="Share y-axis across facets")
    max_facets: int = Field(default=9, ge=1, le=16)


# ═══════════════════════════════════════════════════════════════════
# THE ROOT VIS MODEL
# ═══════════════════════════════════════════════════════════════════

class VIS(BaseModel):
    """
    Visualization Intent Schema — the root contract.

    Every visualization in DataSage is represented as a VIS object.
    Backend produces VIS. Frontend adapters render it.
    """
    model_config = {"extra": "forbid"}

    # Identity
    id: str = Field(default="", description="Unique chart identifier")
    version: str = Field(default="1.0", description="VIS schema version")

    # Classification
    visualization_type: VISDataSeriesType = Field(
        default=VISDataSeriesType.BAR,
        description="Primary visualization type for this VIS"
    )
    analysis_intent: AnalysisIntentType = Field(
        default=AnalysisIntentType.UNKNOWN,
        description="What analytical question does this answer?"
    )
    title: str = Field(default="Visualization", max_length=200)
    description: str = Field(default="", max_length=500)

    # Data — the rendered/aggregated arrays
    data_mapping: Dict[str, Any] = Field(
        default_factory=dict,
        description="Column mapping: {'x': 'col_name', 'y': ['col1', 'col2'], 'group_by': 'col'}"
    )
    aggregation: str = Field(default="sum", description="Aggregation function applied")

    # Series — one or more data series
    series: List[VISDataSeries] = Field(default_factory=list)

    # Multi-series configuration
    series_strategy: SeriesStrategyType = SeriesStrategyType.NONE
    series_collection: Optional[VISSeriesCollection] = Field(
        default=None,
        description="Alternative grouped series representation for multi-series"
    )
    facet_config: Optional[VIFacetConfig] = Field(
        default=None,
        description="Configuration for faceted/small-multiples layouts"
    )

    # Axes
    axes: Dict[str, VISAxis] = Field(
        default_factory=dict,
        description="Axis specs keyed by role: 'x', 'y', 'y2', 'color', 'size', 'facet'"
    )

    # Interaction
    interaction: VISInteraction = Field(default_factory=VISInteraction)

    # Analytics overlays
    analytics: VISAnalytics = Field(default_factory=VISAnalytics)

    # Narrative
    narrative: VISNarrative = Field(default_factory=VISNarrative)

    # Per-point intelligence
    point_intelligence: Optional[VISPointIntelligence] = None

    # Variant configuration (renderer-agnostic)
    variant_config: Optional[VISVariantConfig] = Field(
        default=None,
        description="Variant configuration for step lines, rose diagrams, bar races, etc."
    )

    # Rendering hints (adapter MAY use these)
    color_hint: Optional[str] = Field(
        default=None,
        description="Optional color strategy hint: 'brand_sequential', 'categorical', etc."
    )
    theme: str = Field(default="dark", description="Theme hint for adapter")

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form metadata: rows_used, render_time_ms, etc."
    )

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    source: str = Field(default="unknown", description="VIS producer: chart_render, chat, dashboard, etc.")

    @field_validator("visualization_type", mode="before")
    @classmethod
    def normalize_viz_type(cls, v):
        if isinstance(v, str):
            return v.lower().replace("_chart", "").replace("_plot", "")
        return v

    def get_primary_series(self) -> Optional[VISDataSeries]:
        """Get the primary (first non-empty) series."""
        if self.series:
            return self.series[0]
        if self.series_collection and self.series_collection.series:
            return self.series_collection.series[0]
        return None

    def is_multi_series(self) -> bool:
        """True if this VIS has multiple data series."""
        count = len(self.series)
        if self.series_collection:
            count += len(self.series_collection.series)
        return count > 1

    def series_count(self) -> int:
        """Total number of data series."""
        count = len(self.series)
        if self.series_collection:
            count += len(self.series_collection.series)
        return count or 0


# ═══════════════════════════════════════════════════════════════════
# MODULE EXPORTS
# ═══════════════════════════════════════════════════════════════════

__all__ = [
    "VIS",
    "VISDataSeries",
    "VISDataSeriesType",
    "VISSeriesCollection",
    "VISAxis",
    "VISAxisType",
    "VISAxisFormat",
    "VISInteraction",
    "VISAnalytics",
    "VISNarrative",
    "VISKeyNumber",
    "ReferenceLine",
    "SeriesStrategyType",
    "AnalysisIntentType",
    "VIFacetConfig",
    "VISPointIntelligence",
    "VISPointIntelligenceStats",
    "VISPointIntelligencePoint",
    "ValidationSeverity",
    # ECharts-native models
    "VISNode",
    "VISLink",
    "VISVariantConfig",
]

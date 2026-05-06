"""
Chart Schemas (Core)
--------------------
These schemas define:
- Requests for generating charts
- Responses returned by chart engines
- Chart recommendations produced by AI
- Explanations & confidence scoring

They are used by:
- Chart Hydration Service
- Chart Renderer
- Chart Insights Service
- Chart API Routes
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


# ---------------------------------------------------
# Base Config
# ---------------------------------------------------
class _Config:
    from_attributes = True  # Pydantic v2: renamed from orm_mode
    extra = "forbid"
    use_enum_values = True


# ---------------------------------------------------
# CHART REQUEST (New Enhanced Version)
# ---------------------------------------------------
class ChartRenderRequest(BaseModel):
    """
    Enhanced chart generation request with full configuration.

    This replaces the ad-hoc {x_axis, y_axis, ...} payload.
    """
    dataset_id: str = Field(..., description="Dataset ID to render chart from")
    chart_type: str = Field(..., min_length=2, description="Chart type (bar, line, pie, etc.)")
    fields: List[str] = Field(..., min_items=1, max_items=10, description="Column names for the chart")
    aggregation: Optional[str] = Field(default="sum", description="Aggregation type (sum, count, mean, etc.)")
    group_by: Optional[List[str]] = Field(default=None, description="Optional grouping columns")
    filters: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional data filters")
    title: Optional[str] = Field(default=None, description="Chart title")
    include_insights: bool = Field(default=True, description="Whether to generate AI insights")
    # Date range filtering
    from_date: Optional[str] = Field(default=None, alias="from", description="Start date (ISO 8601, e.g. 2024-01-01)")
    to_date: Optional[str] = Field(default=None, alias="to", description="End date (ISO 8601, e.g. 2024-12-31)")
    granularity: Optional[str] = Field(default="day", description="Time granularity: hour | day | week | month")
    limit: Optional[int] = Field(default=10000, ge=1, le=100000, description="Max rows returned")

    class Config(_Config):
        populate_by_name = True  # allow both alias and field name


# ---------------------------------------------------
# CHART REQUEST (Legacy - for backward compatibility)
# ---------------------------------------------------
class ChartRequest(BaseModel):
    """
    Legacy chart generation request.

    chart_type: The type of chart (bar/line/pie/etc.)
    fields: List of column names to visualize
    title: Optional chart title
    explanation: Optional narrative provided by AI
    """
    chart_type: str = Field(..., min_length=2)
    fields: List[str] = Field(..., min_items=1)
    title: Optional[str] = None
    explanation: Optional[str] = None

    class Config(_Config):
        pass


# ---------------------------------------------------
# CHART RESPONSE (Enhanced with Plotly Support)
# ---------------------------------------------------
class ChartResponse(BaseModel):
    """
    Enhanced return from chart engine, includes Plotly traces + layout.

    id: Unique chart ID
    type: Chart type
    title: Title displayed in the UI
    traces: Plotly trace objects (with x, y, labels, values, etc.)
    layout: Plotly layout configuration (axis titles, theme, etc.)
    data: DEPRECATED - Legacy hydrated data rows (kept for backward compatibility)
    fields: Columns used
    explanation: Natural language explanation of what the chart shows
    confidence: Confidence score (0–1) for AI-generated recommendations
    metadata: Additional rendering metadata (rows used, render time, etc.)
    """
    id: str
    type: str
    title: str
    traces: List[Dict[str, Any]] = Field(..., description="Plotly trace objects")
    layout: Dict[str, Any] = Field(default_factory=dict, description="Plotly layout configuration")
    data: Optional[List[Dict[str, Any]]] = Field(default=None, description="DEPRECATED: Legacy data rows")
    fields: List[str]
    explanation: Optional[str] = Field(default="", description="Natural language explanation")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence score for recommendations")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    point_intelligence: Optional[Dict[str, Any]] = Field(default=None, description="Per-data-point statistical intelligence for tooltip enrichment")

    class Config(_Config):
        pass


# ---------------------------------------------------
# CHART RECOMMENDATION (AI)
# ---------------------------------------------------
class ChartRecommendation(BaseModel):
    """
    AI-driven chart recommendations.

    chart_type: Suggested chart type
    title: Recommended title
    description: Why this chart works
    suitable_columns: List of eligible columns
    confidence: Qualitative confidence ("High", "Medium", "Low")
    """
    chart_type: str
    title: str
    description: str
    suitable_columns: List[str]
    confidence: str = Field(..., pattern="^(High|Medium|Low)$")  # Pydantic v2: regex → pattern

    class Config(_Config):
        pass


# ===================================================
# PHASE 2: MULTI-SERIES CHART SUPPORT
# ===================================================

# ---------------------------------------------------
# ENUMS & CONSTANTS
# ---------------------------------------------------
from enum import Enum


class SeriesStrategy(str, Enum):
    """Valid multi-series rendering strategies"""
    OVERLAY = "overlay"  # Multiple lines/bars on shared axes
    FACET = "facet"      # Faceted charts (small multiples)
    DUAL_AXIS = "dual_axis"  # Left/right y-axes
    COMBO = "combo"      # Bars + line combination
    GROUPED = "grouped"  # Grouped bars
    STACKED = "stacked"  # Stacked bars/areas


class AnalysisIntent(str, Enum):
    """User intent behind the chart request"""
    TREND = "trend"        # Show how values change over time
    COMPARISON = "comparison"  # Compare values across dimensions
    COMPOSITION = "composition"  # Show parts of a whole
    RELATIONSHIP = "relationship"  # Show correlation/causation
    DISTRIBUTION = "distribution"  # Show how values are distributed
    RANKING = "ranking"    # Show ordered rankings
    DIAGNOSIS = "diagnosis"  # Identify problems/anomalies


# ---------------------------------------------------
# PANEL POLICY (Multi-panel configuration)
# ---------------------------------------------------
class PanelPolicy(BaseModel):
    """Configuration for faceted/multi-panel charts"""
    facet_count: int = Field(default=1, ge=1, description="Number of facets/panels")
    max_facets: int = Field(default=9, ge=4, le=16, description="Max facets before collapse to 'other'")
    shared_axes: bool = Field(default=True, description="Share axes across facets for comparison")
    axis_type: str = Field(
        default="shared",
        description="'shared' (same scale all facets) | 'shared_time' (shared x-axis only) | 'independent'"
    )
    collapse_to_other: bool = Field(default=True, description="Collapse excess segments to 'Other'")
    other_label: str = Field(default="Other", description="Label for collapsed segments")

    class Config(_Config):
        pass


# ---------------------------------------------------
# PATTERN DETECTION (Cross-series patterns)
# ---------------------------------------------------
class CrossSeriesPattern(BaseModel):
    """Pattern detected across multiple series"""
    pattern_type: str = Field(
        ...,
        description="divergence | correlation | dominance | concentration | unit_scale_mismatch"
    )
    series_involved: List[str] = Field(..., description="Series that exhibit this pattern")
    description: str = Field(..., description="Human-friendly description")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence 0-1")
    metrics: Dict[str, float] = Field(default_factory=dict, description="Supporting metrics (correlation, ratio, etc)")

    class Config(_Config):
        pass


# ---------------------------------------------------
# MULTI-SERIES VIEW SPECIFICATION
# ---------------------------------------------------
class MultiSeriesViewSpec(BaseModel):
    """
    Complete specification for rendering a multi-series chart.

    Replaces ad-hoc parameters with structured spec.
    """
    # Chart identity
    title: str = Field(..., description="Chart title")
    chart_type_primary: str = Field(
        ...,
        description="Primary chart type (bar, line, area, scatter, etc)"
    )
    chart_type_secondary: Optional[str] = Field(
        default=None,
        description="Secondary chart type (for combo charts)"
    )

    # Series strategy
    series_strategy: SeriesStrategy = Field(
        default=SeriesStrategy.OVERLAY,
        description="How to render multiple series"
    )

    # Data mapping
    encoding: Dict[str, Any] = Field(
        ...,
        description="Visual encoding: {'x_axis': {'column': 'date', 'type': 'category'}, ...}"
    )
    y_roles: List[str] = Field(
        ...,
        min_items=1,
        description="Primary metric(s) for y-axis"
    )
    secondary_metric: Optional[str] = Field(
        default=None,
        description="Secondary metric (for dual-axis charts)"
    )

    # Faceting/segmentation
    split_dimension: Optional[str] = Field(
        default=None,
        description="Column to split/facet by (for faceted charts)"
    )
    panel_policy: PanelPolicy = Field(
        default_factory=PanelPolicy,
        description="Configuration for multi-panel layout"
    )

    # Analysis context
    analysis_intent: AnalysisIntent = Field(
        default=AnalysisIntent.TREND,
        description="What question does this chart answer?"
    )

    # Unit handling
    unit_handling: Optional[str] = Field(
        default="auto",
        description="'auto' (detect) | 'dual_axis' | 'normalize' | 'scale'"
    )

    # Quality metrics
    readability_score: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Estimated readability (0=confusing, 1=crystal clear)"
    )

    # Patterns (populated by pattern detector)
    patterns: List[CrossSeriesPattern] = Field(
        default_factory=list,
        description="Detected patterns in the data"
    )

    # Narrative
    narrative_summary: Optional[str] = Field(
        default=None,
        description="Initial narrative summary of what chart shows"
    )
    why_this_strategy: Optional[str] = Field(
        default=None,
        description="Explanation of why this strategy was chosen"
    )

    class Config(_Config):
        pass


# ---------------------------------------------------
# Export
# ---------------------------------------------------
__all__ = [
    "ChartRequest",
    "ChartResponse",
    "ChartRecommendation",
    "SeriesStrategy",
    "AnalysisIntent",
    "PanelPolicy",
    "CrossSeriesPattern",
    "MultiSeriesViewSpec",
]

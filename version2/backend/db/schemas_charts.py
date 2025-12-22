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
    include_insights: bool = Field(default=False, description="Whether to generate AI insights")
    
    class Config(_Config):
        pass


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


# ---------------------------------------------------
# Export
# ---------------------------------------------------
__all__ = [
    "ChartRequest",
    "ChartResponse",
    "ChartRecommendation",
]

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
    orm_mode = True
    extra = "forbid"
    use_enum_values = True


# ---------------------------------------------------
# CHART REQUEST
# ---------------------------------------------------
class ChartRequest(BaseModel):
    """
    Incoming chart generation request.

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
# CHART RESPONSE
# ---------------------------------------------------
class ChartResponse(BaseModel):
    """
    Return from chart engine, sent to frontend.

    id: Unique chart ID
    type: Chart type
    title: Title displayed in the UI
    data: Hydrated data rows for the plot
    fields: Columns used
    explanation: Natural language explanation
    confidence: Confidence score (0–1)
    """
    id: str
    type: str
    title: str
    data: List[Dict[str, Any]]
    fields: List[str]
    explanation: str
    confidence: float = Field(0.0, ge=0.0, le=1.0)

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
    confidence: str = Field(..., regex="^(High|Medium|Low)$")

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

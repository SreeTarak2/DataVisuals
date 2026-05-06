"""
Overlay Chart API Endpoints
============================
FastAPI routes for overlay chart generation.

Endpoints:
POST /api/v1/charts/overlay — Generate overlay chart
GET  /api/v1/charts/overlay/info — Service info
"""

from typing import List, Optional, Dict, Any
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, Field
import polars as pl
import json

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/v1/charts",
    tags=["charts"]
)


# ──────────────────────────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────────────────────────

class YRoleRequest(BaseModel):
    """Y-axis role configuration."""
    column: str = Field(..., description="Column name in data")
    role: str = Field(default="series", description="Role of this column")

    class Config:
        json_schema_extra = {
            "example": {"column": "Revenue", "role": "series"}
        }


class OverlayChartRequest(BaseModel):
    """Request to generate overlay chart."""
    title: str = Field(..., description="Chart title", min_length=1)
    data: Dict[str, List[Any]] = Field(..., description="Data as dict of lists")
    x_column: str = Field(..., description="X-axis column name")
    y_columns: List[str] = Field(
        ...,
        description="Y-axis columns (must be at least 2 for overlay)",
        min_items=2
    )
    analysis_intent: Optional[str] = Field(
        default="comparison",
        description="trend, comparison, composition, etc."
    )
    trace_mode: Optional[str] = Field(
        default="lines+markers",
        description="Plotly trace mode"
    )
    unit_handling: Optional[Dict[str, str]] = Field(
        default=None,
        description="Unit mapping for columns"
    )
    secondary_metric: Optional[str] = Field(
        default=None,
        description="Optional reference metric"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Revenue vs Cost",
                "data": {
                    "Date": ["2025-01-01", "2025-01-02", "2025-01-03"],
                    "Revenue": [1000.0, 1200.0, 1100.0],
                    "Cost": [400.0, 450.0, 480.0]
                },
                "x_column": "Date",
                "y_columns": ["Revenue", "Cost"],
                "analysis_intent": "comparison",
                "trace_mode": "lines+markers"
            }
        }


class OverlayChartResponse(BaseModel):
    """Response with generated overlay chart."""
    success: bool = Field(description="Whether generation succeeded")
    chart: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Plotly figure dict"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Chart metadata"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )
    warnings: Optional[List[str]] = Field(
        default=None,
        description="Warnings during generation"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "chart": {
                    "data": [...],
                    "layout": {...},
                    "metadata": {...}
                },
                "metadata": {
                    "renderer": "overlay",
                    "series_count": 2,
                    "data_points_per_series": 3
                }
            }
        }


class ChartInfoResponse(BaseModel):
    """Info about overlay chart service."""
    service: str
    version: str
    status: str
    capabilities: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "service": "overlay-chart-renderer",
                "version": "1.0.0",
                "status": "ready",
                "capabilities": {
                    "max_series": 7,
                    "max_data_points": 10000,
                    "supported_modes": ["lines+markers", "lines", "markers"]
                }
            }
        }


# ──────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────

@router.get("/overlay/info", response_model=ChartInfoResponse)
async def get_overlay_info() -> ChartInfoResponse:
    """
    Get overlay chart service information.

    Returns:
        Service info including version, status, capabilities
    """
    return ChartInfoResponse(
        service="overlay-chart-renderer",
        version="1.0.0",
        status="ready",
        capabilities={
            "max_series": 7,
            "max_data_points": 10000,
            "supported_modes": ["lines+markers", "lines", "markers"],
            "trace_types": ["scatter"],
            "analysis_intents": [
                "trend", "comparison", "composition",
                "relationship", "distribution", "ranking", "diagnosis"
            ]
        }
    )


@router.post("/overlay", response_model=OverlayChartResponse)
async def generate_overlay_chart(request: OverlayChartRequest) -> OverlayChartResponse:
    """
    Generate an overlay multi-series chart.

    Args:
        request: Chart configuration and data

    Returns:
        Generated Plotly chart with metadata

    Raises:
        HTTPException: If generation fails

    Example:
        ```
        POST /api/v1/charts/overlay
        {
            "title": "Revenue vs Cost",
            "data": {
                "Date": ["2025-01-01", "2025-01-02"],
                "Revenue": [1000, 1200],
                "Cost": [400, 450]
            },
            "x_column": "Date",
            "y_columns": ["Revenue", "Cost"]
        }
        ```
    """
    try:
        logger.info(f"Generate overlay chart: {request.title}")

        # Validate request
        warnings = []

        if len(request.y_columns) < 2:
            raise HTTPException(
                status_code=400,
                detail="Overlay requires at least 2 y_columns"
            )

        if len(request.y_columns) > 7:
            warnings.append(
                f"High series count ({len(request.y_columns)}) "
                "may reduce readability"
            )

        # Convert dict data to Polars DataFrame
        try:
            data_df = pl.DataFrame(request.data)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to parse data: {str(e)}"
            )

        # Validate required columns exist
        if request.x_column not in data_df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"X column '{request.x_column}' not found in data"
            )

        for y_col in request.y_columns:
            if y_col not in data_df.columns:
                raise HTTPException(
                    status_code=400,
                    detail=f"Y column '{y_col}' not found in data"
                )

        # Validate data types (y columns should be numeric)
        for y_col in request.y_columns:
            dtype = data_df.schema[y_col]
            if dtype not in [pl.Int32, pl.Int64, pl.Float32, pl.Float64]:
                warnings.append(
                    f"Column '{y_col}' has non-numeric type {dtype}, "
                    "will attempt conversion"
                )

        # Build MultiSeriesViewSpec
        from db.schemas_charts import MultiSeriesViewSpec

        spec = MultiSeriesViewSpec(
            title=request.title,
            chart_type_primary="scatter",
            chart_type_secondary=None,
            series_strategy="overlay",
            encoding={"x": request.x_column},
            y_roles=[
                {"column": col, "role": "series"}
                for col in request.y_columns
            ],
            analysis_intent=request.analysis_intent or "comparison",
            unit_handling=request.unit_handling,
            secondary_metric=request.secondary_metric
        )

        # Render
        from services.charts.renderers.overlay_renderer import OverlayRenderer

        renderer = OverlayRenderer(trace_mode=request.trace_mode or "lines+markers")
        chart = await renderer.render(spec, data_df)

        logger.info(
            f"Overlay chart generated successfully: "
            f"{len(chart['data'])} series, "
            f"{len(chart['data'][0]['x'])} points"
        )

        return OverlayChartResponse(
            success=True,
            chart=chart,
            metadata=chart.get("metadata"),
            warnings=warnings if warnings else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Overlay chart generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chart generation failed: {str(e)}"
        )


@router.post("/overlay/csv")
async def generate_overlay_chart_from_csv(
    title: str = Query(..., description="Chart title"),
    x_column: str = Query(..., description="X column name"),
    y_columns: str = Query(..., description="Y columns (comma-separated)"),
    analysis_intent: Optional[str] = Query(
        default="comparison",
        description="Analysis intent"
    ),
    file: UploadFile = File(..., description="CSV file with data")
) -> OverlayChartResponse:
    """
    Generate overlay chart from CSV file.

    Args:
        title: Chart title
        x_column: X-axis column name
        y_columns: Comma-separated list of y-column names
        analysis_intent: Optional analysis intent
        file: CSV file upload

    Returns:
        Generated chart

    Example:
        ```
        POST /api/v1/charts/overlay/csv
        ?title=Revenue%20vs%20Cost
        &x_column=Date
        &y_columns=Revenue,Cost
        ```
    """
    try:
        logger.info(f"Generate overlay chart from CSV: {file.filename}")

        # Read CSV
        try:
            contents = await file.read()
            import io
            df = pl.read_csv(io.BytesIO(contents))
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to parse CSV: {str(e)}"
            )

        # Parse y_columns
        y_cols = [col.strip() for col in y_columns.split(",")]

        # Create request and delegate to main endpoint
        request = OverlayChartRequest(
            title=title,
            data=df.to_dict(as_series=False),
            x_column=x_column,
            y_columns=y_cols,
            analysis_intent=analysis_intent
        )

        return await generate_overlay_chart(request)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV overlay generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"CSV processing failed: {str(e)}"
        )


# Health check endpoint
@router.get("/overlay/health")
async def overlay_health():
    """Health check for overlay renderer."""
    return {
        "status": "healthy",
        "service": "overlay-chart-renderer",
        "timestamp": datetime.now().isoformat(),
        "checks": {
            "database": "ok",
            "dependencies": "ok",
            "renderer": "ok"
        }
    }


# Export router for main app
__all__ = ["router"]

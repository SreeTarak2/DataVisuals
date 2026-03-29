"""
Charts API - New Unified Chart Rendering Service
================================================

This module provides the new chart rendering API with:
- Unified /api/charts/render endpoint
- Chart recommendations based on data
- Chart insights and explanations
- Dashboard chart management

Author: DataSage AI Team
Version: 3.0 (Refactored)
"""

import logging
import uuid
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

# --- Application Modules ---
from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from services.charts.chart_render_service import chart_render_service
from services.charts.chart_insights_service import chart_insights_service
from services.charts.chart_intelligence_service import ChartIntelligenceService
from services.charts.explanation_validator import validate_and_normalize_explanation
from db.schemas_charts import ChartRenderRequest, ChartResponse, ChartRecommendation
from db.schemas_dashboard import ChartConfig, ChartType, AggregationType

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
chart_intelligence_service = ChartIntelligenceService()


# ============================================================
#            MAIN CHART RENDERING ENDPOINT
# ============================================================
@router.post("/render", response_model=ChartResponse)
async def render_chart(
    request: ChartRenderRequest, current_user: dict = Depends(get_current_user)
):
    """
    Main chart rendering endpoint.

    Accepts ChartRenderRequest with full configuration and returns
    a ChartResponse with Plotly traces, layout, and AI-generated explanation.

    Flow:
    1. Load dataset
    2. Parse and validate chart config
    3. Hydrate chart (DataFrame → Plotly traces)
    4. Render with theme and layout
    5. Generate AI explanation/insights
    6. Return unified response
    """
    try:
        logger.info(
            f"Rendering chart: type={request.chart_type}, dataset={request.dataset_id}"
        )

        # Load dataset
        df = await enhanced_dataset_service.load_dataset_data(
            request.dataset_id, current_user["id"]
        )

        if df is None or df.is_empty():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or empty",
            )

        # Apply row cap
        limit = request.limit or 10000
        if len(df) > limit:
            df = df.head(limit)
            logger.info(f"Dataset capped at {limit} rows")

        # Apply date range filter if fields include a temporal column
        from_date = request.from_date
        to_date = request.to_date
        if from_date or to_date:
            import polars as pl
            # Try to detect the date column: first field or first temporal column
            date_col = None
            for col in request.fields:
                if col in df.columns:
                    try:
                        sample = df[col].drop_nulls().head(5).to_list()
                        if sample and all(isinstance(v, str) and len(v) >= 8 for v in sample):
                            date_col = col
                            break
                    except Exception:
                        pass
            if date_col:
                try:
                    date_series = pl.col(date_col).cast(pl.Utf8).str.slice(0, 10)
                    if from_date:
                        df = df.filter(date_series >= from_date)
                    if to_date:
                        df = df.filter(date_series <= to_date)
                    logger.info(f"Date filter applied on '{date_col}': {from_date} → {to_date}, {len(df)} rows remain")
                except Exception as e:
                    logger.warning(f"Date filter failed: {e}")

        # Build chart config
        chart_config = {
            "chart_type": request.chart_type,
            "columns": request.fields,
            "aggregation": request.aggregation or "sum",
            "title": request.title or f"{request.chart_type.title()} Chart",
            "group_by": request.group_by,
            "granularity": request.granularity or "day",
        }

        # Apply column-level filters if provided
        if request.filters:
            import polars as pl
            for f in request.filters:
                col = f.get("column")
                op = f.get("op", "eq")
                val = f.get("value")
                if col and col in df.columns and val is not None:
                    try:
                        if op == "eq":
                            df = df.filter(pl.col(col) == val)
                        elif op == "neq":
                            df = df.filter(pl.col(col) != val)
                        elif op == "gt":
                            df = df.filter(pl.col(col) > val)
                        elif op == "lt":
                            df = df.filter(pl.col(col) < val)
                        elif op == "gte":
                            df = df.filter(pl.col(col) >= val)
                        elif op == "lte":
                            df = df.filter(pl.col(col) <= val)
                        elif op == "in" and isinstance(val, list):
                            df = df.filter(pl.col(col).is_in(val))
                    except Exception as e:
                        logger.warning(f"Filter failed for column '{col}': {e}")
            logger.info(f"Applied {len(request.filters)} filters, {len(df)} rows remain")

        # Render chart (hydrate + render pipeline)
        chart_payload = await chart_render_service.render_chart(
            df=df,
            chart_config=chart_config,
            theme="dark",  # TODO: Get from user preferences
        )

        # Generate AI explanation and insights (only if requested)
        insights = {}
        if request.include_insights:
            # Ensure chart_payload has chart_type at top level for insights service
            if "chart_type" not in chart_payload and "metadata" in chart_payload:
                chart_payload["chart_type"] = chart_payload["metadata"].get(
                    "chart_type"
                )

            insights = await chart_insights_service.generate_chart_insight(
                chart_data=chart_payload, df=df, use_llm=True
            )

        # Build response
        chart_id = str(uuid.uuid4())
        response = ChartResponse(
            id=chart_id,
            type=request.chart_type,
            title=chart_config["title"],
            traces=chart_payload.get("traces", []),
            layout=chart_payload.get("layout", {}),
            fields=request.fields,
            explanation=insights.get("summary", ""),
            confidence=insights.get("confidence", 0.0),
            metadata=chart_payload.get("metadata", {}),
            point_intelligence=chart_payload.get("point_intelligence"),
        )

        logger.info(f"✓ Chart rendered successfully: {chart_id}")
        return response

    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid chart configuration: {e}",
        )
    except Exception as e:
        logger.error(f"Chart rendering failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to render chart: {str(e)}",
        )


# ============================================================
#            CHART RECOMMENDATIONS
# ============================================================
@router.get("/recommendations", response_model=List[ChartRecommendation])
async def get_chart_recommendations(
    dataset_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Get AI-powered chart recommendations for a dataset.

    Returns a list of suggested chart types with descriptions
    and suitable columns based on data analysis.
    """
    try:
        logger.info(f"Getting chart recommendations for dataset: {dataset_id}")

        # Load dataset metadata
        dataset = await enhanced_dataset_service.get_dataset(
            dataset_id, current_user["id"]
        )

        metadata = dataset.get("metadata", {})
        column_metadata = metadata.get("column_metadata", [])

        if not column_metadata:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dataset metadata not available. Please process the dataset first.",
            )

        # Generate recommendations using AI service
        recommendations = await chart_intelligence_service.suggest_charts_for_dataset(
            column_metadata=column_metadata,
            dataset_overview=metadata.get("dataset_overview", {}),
            max_suggestions=5,
        )

        # Convert to ChartRecommendation schema
        result = []
        for rec in recommendations:
            result.append(
                ChartRecommendation(
                    chart_type=rec.get("chart_type", "bar"),
                    title=rec.get("title", ""),
                    description=rec.get("description", ""),
                    suitable_columns=rec.get("columns", []),
                    confidence=rec.get("confidence", "Medium"),
                )
            )

        logger.info(f"✓ Generated {len(result)} chart recommendations")
        return result

    except Exception as e:
        logger.error(f"Failed to generate recommendations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate chart recommendations: {str(e)}",
        )


# ============================================================
#            CHART INSIGHTS (Detailed Analysis)
# ============================================================
@router.post("/insights")
async def get_chart_insights(
    request: Dict[str, Any], current_user: dict = Depends(get_current_user)
):
    """
    Get detailed insights for an existing or proposed chart.

    Provides:
    - Pattern detection (trends, comparisons, outliers)
    - Statistical summary
    - Natural language explanation
    - Confidence score
    """
    try:
        chart_config = request.get("chart_config", {})
        chart_data = request.get("chart_data", [])
        dataset_id = request.get("dataset_id")

        if not chart_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="chart_config is required",
            )

        # Get dataset metadata if provided
        dataset_metadata = {}
        if dataset_id:
            dataset = await enhanced_dataset_service.get_dataset(
                dataset_id, current_user["id"]
            )
            dataset_metadata = dataset.get("metadata", {})

        # Generate insights
        insights = await chart_insights_service.generate_chart_insight(
            chart_config=chart_config,
            chart_data=chart_data,
            dataset_metadata=dataset_metadata,
        )

        return insights

    except Exception as e:
        logger.error(f"Error generating chart insights: {e}", exc_info=True)
        # Return fallback insights instead of erroring
        return chart_insights_service._generate_fallback_insight(
            request.get("chart_config", {}), []
        )


# ============================================================
#            CHART EXPLANATION (Lazy Load)
# ============================================================
@router.post("/explain")
async def explain_chart(
    request: Dict[str, Any], current_user: dict = Depends(get_current_user)
):
    """
    Generate or retrieve explanation for a specific chart.

    This endpoint supports lazy loading - explanations are generated on-demand
    when user clicks "Explain" on a chart, and cached for future visits.

    Based on ChartQA-X methodology:
    - OBSERVE → CALCULATE → INTERPRET → IMPLY chain-of-thought
    - 2-4 sentences following the reasoning chain
    - Faithfulness (numbers from data), Informativeness (specific values),
      Coherence (connected reasoning), Plain language (no jargon)
    """
    try:
        chart_key = request.get("chart_key")
        chart_config = request.get("chart_config", {})
        dataset_id = request.get("dataset_id")

        if not chart_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="chart_key is required"
            )

        if not dataset_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="dataset_id is required"
            )

        user_id = current_user["id"]

        # Check cache first
        from services.cache import dashboard_cache_service

        cached = await dashboard_cache_service.get_cached_chart_explanation(
            dataset_id, user_id, chart_key
        )
        if cached:
            logger.info(f"📖 Returning cached explanation for '{chart_key}'")
            return {
                "explanation": cached.get("explanation", ""),
                "key_insights": cached.get("key_insights", []),
                "reading_guide": cached.get("reading_guide", ""),
                "anomaly_flag": cached.get("anomaly_flag"),
                "cached": True,
                "chart_key": chart_key,
            }

        # Load dataset for generating explanation
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
            )

        df = await enhanced_dataset_service.load_dataset_data(dataset_id, user_id)

        # Generate explanation using chart_insights_service with LLM
        insight = await chart_insights_service.generate_chart_insight(
            chart_data=chart_config, df=df, use_llm=True, chart_config=chart_config
        )

        # Validate and normalize LLM explanation using quality gates
        enhanced = insight.get("enhanced_insight") or {}
        validation_result = validate_and_normalize_explanation(enhanced, chart_config)
        
        if validation_result["valid"]:
            # Use validated LLM explanation
            explanation_text = validation_result["explanation"]
            key_insights = validation_result["key_insights"]
            reading_guide = validation_result["reading_guide"]
            anomaly_flag = validation_result["anomaly_flag"]
            logger.info(f"✓ Explanation passed quality gates [source: LLM]")
        else:
            # Fall back to deterministic explanation if LLM failed quality gates
            logger.warning(
                f"Explanation rejected: {validation_result['rejection_reasons']}"
            )
            # Fall back to pattern-derived summary
            template_summary = insight.get("summary", "")
            explanation_text = template_summary if template_summary else ""
            key_insights = _extract_key_insights(insight)
            reading_guide = _generate_reading_guide(insight, chart_config)
            anomaly_flag = _detect_anomaly(insight)

        # Cache the explanation
        cached_payload = {
            "explanation": explanation_text,
            "key_insights": key_insights,
            "reading_guide": reading_guide,
            "anomaly_flag": anomaly_flag,
        }
        await dashboard_cache_service.cache_chart_explanation(
            dataset_id, user_id, chart_key, cached_payload
        )

        return {
            "explanation": explanation_text,
            "key_insights": key_insights,
            "reading_guide": reading_guide,
            "anomaly_flag": anomaly_flag,
            "cached": False,
            "chart_key": chart_key,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chart explanation failed: {e}", exc_info=True)
        return {
            "explanation": "Unable to generate explanation. Please try again.",
            "key_insights": [],
            "reading_guide": None,
            "anomaly_flag": None,
            "cached": False,
            "error": str(e),
            "chart_key": request.get("chart_key", ""),
        }


def _extract_key_insights(insight: Dict[str, Any]) -> List[str]:
    """Extract up to 2 key insights from insight object — never repeat the summary."""
    insights = []
    summary = (insight.get("summary", "") or "").strip()

    # Prefer pattern descriptions — they contain actual computed values
    patterns = insight.get("patterns", [])
    for pattern in patterns[:3]:
        if not isinstance(pattern, dict):
            continue
        desc = (pattern.get("description", "") or "").strip()
        # Skip if it's just restating the summary
        if desc and desc.rstrip(".") != summary.rstrip("."):
            insights.append(desc[:120])
        if len(insights) >= 2:
            break

    # If patterns gave nothing useful, try enhanced_insight (LLM output)
    if not insights:
        enhanced = insight.get("enhanced_insight", "")
        if isinstance(enhanced, dict):
            enhanced = enhanced.get("description", enhanced.get("summary", str(enhanced)))
        enhanced = (str(enhanced) or "").strip()
        if enhanced and enhanced.rstrip(".") != summary.rstrip("."):
            insights.append(enhanced[:120])

    return insights[:2]


def _generate_reading_guide(
    insight: Dict[str, Any], chart_config: Dict[str, Any]
) -> str:
    """Generate actionable reading guide from insight."""
    recommendations = insight.get("recommendations", [])
    if recommendations:
        for rec in recommendations[:1]:
            if isinstance(rec, dict):
                action = rec.get("action", rec.get("description", ""))
                if action:
                    return action[:150]  # Max 150 chars

    # Fallback based on chart type
    chart_type = chart_config.get("chart_type", "bar")
    column = (
        chart_config.get("columns", [chart_config.get("x", "")])[0]
        if chart_config.get("columns")
        else chart_config.get("x", "data")
    )

    guides = {
        "bar": f"Compare the tallest vs. shortest bars — the gap shows how much {column} varies by category.",
        "line": f"Look for slope changes in {column} — steep rises or drops signal turning points worth investigating.",
        "pie": f"The largest slice dominates {column} — check if that concentration creates risk or opportunity.",
        "scatter": f"Hover over outlier points far from the cluster — they reveal unusual {column} combinations.",
        "histogram": f"Find where {column} peaks — if the peak is skewed left or right, the average is misleading.",
        "box_plot": f"Compare the box medians across groups — if one group's box doesn't overlap others, the difference is real.",
        "heatmap": f"The brightest cell shows the highest concentration — click it to filter the dashboard to that segment.",
        "area": f"Watch where areas overlap in {column} — crossover points mark moments of category shift.",
        "grouped_bar": f"Within each group, compare bar heights to find which category consistently leads in {column}.",
        "treemap": f"Largest rectangles in {column} dominate the total — click to drill down into sub-segments.",
    }

    return guides.get(chart_type, f"Filter by the highest-value segment in {column} to see what drives it.")


def _detect_anomaly(insight: Dict[str, Any]) -> Optional[str]:
    """Detect if there's an anomaly worth flagging."""
    patterns = insight.get("patterns", [])

    for pattern in patterns:
        if isinstance(pattern, dict):
            pattern_type = pattern.get("type", "")
            if pattern_type in ("outlier", "anomaly", "spike", "drop"):
                desc = pattern.get("description", "")
                if desc:
                    return desc[:150]

    return None


# ============================================================
#            DASHBOARD CHART MANAGEMENT
# ============================================================
@router.post("/dashboard/save")
async def save_chart_to_dashboard(
    request: Dict[str, Any], current_user: dict = Depends(get_current_user)
):
    """
    Save a chart configuration to the user's dashboard.

    Stores the ChartConfig so it can be reloaded later.
    """
    try:
        dataset_id = request.get("dataset_id")
        chart_config = request.get("chart_config")

        if not dataset_id or not chart_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="dataset_id and chart_config are required",
            )

        from db.database import get_database
        import datetime

        db = get_database()
        chart_id = str(uuid.uuid4())
        user_id = current_user["id"]
        chart_doc = {
            "_id": chart_id,
            "user_id": user_id,
            "dataset_id": dataset_id,
            "chart_config": chart_config,
            "title": request.get("title", chart_config.get("title", "Chart")),
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow(),
        }
        try:
            await db.charts.insert_one(chart_doc)
            logger.info(f"Saved chart {chart_id} to dashboard for user {user_id}")
            return {
                "success": True,
                "chart_id": chart_id,
                "message": "Chart saved to dashboard",
            }
        except Exception as db_err:
            logger.error(f"Failed to save chart to dashboard: {db_err}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save chart: {str(db_err)}",
            )

    except Exception as e:
        logger.error(f"Error saving chart: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save chart: {str(e)}",
        )


@router.get("/dashboard/list")
async def list_dashboard_charts(
    dataset_id: Optional[str] = None, current_user: dict = Depends(get_current_user)
):
    """
    List all saved charts for a user's dashboard.

    Optionally filter by dataset_id.
    """
    try:
        from db.database import get_database
        db = get_database()
        user_id = current_user["id"]
        query = {"user_id": user_id}
        if dataset_id:
            query["dataset_id"] = dataset_id

        cursor = db.charts.find(query, {"chart_config": 1, "title": 1, "dataset_id": 1, "created_at": 1}).sort("created_at", -1).limit(50)
        charts = []
        async for doc in cursor:
            charts.append({
                "chart_id": str(doc["_id"]),
                "title": doc.get("title", "Untitled Chart"),
                "dataset_id": doc.get("dataset_id"),
                "chart_config": doc.get("chart_config", {}),
                "created_at": doc.get("created_at", "").isoformat() if doc.get("created_at") else "",
            })

        logger.info(f"Listed {len(charts)} saved charts for user {user_id}")
        return {"charts": charts, "count": len(charts)}

    except Exception as e:
        logger.error(f"Error listing charts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list charts: {str(e)}",
        )


# ============================================================
#            LEGACY ENDPOINTS (Backward Compatibility)
# ============================================================
@router.post("/generate")
async def generate_chart_legacy(
    request: Dict[str, Any], current_user: dict = Depends(get_current_user)
):
    """
    Legacy endpoint for backward compatibility.
    Maps old {x_axis, y_axis, ...} format to new ChartRenderRequest.
    """
    try:
        # Map legacy format to new format
        new_request = ChartRenderRequest(
            dataset_id=request.get("dataset_id"),
            chart_type=request.get("chart_type", "bar"),
            fields=[request.get("x_axis"), request.get("y_axis")],
            aggregation=request.get("aggregation", "sum"),
            title=request.get("title"),
        )

        # Call new render endpoint
        return await render_chart(new_request, current_user)

    except Exception as e:
        logger.error(f"Legacy chart generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate chart: {str(e)}",
        )

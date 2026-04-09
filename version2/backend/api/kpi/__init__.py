"""
KPI API Routes
==============
Endpoints for KPI management and calculation:
- GET /templates - List available KPI templates
- GET /templates/{id} - Get specific template
- GET /definitions - List all KPI definitions
- POST /suggest - Auto-suggest KPIs for a dataset
- POST /calculate - Calculate KPIs with column mappings
- GET /config/{dataset_id} - Get saved KPI config
- POST /config - Save KPI config for a dataset
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from db.database import get_database
from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from services.kpi import kpi_service, ALL_KPIS, ALL_TEMPLATES
from db.schemas_kpi import (
    KPITemplate,
    KPIDefinition,
    KPIColumnMapping,
    KPICalculateRequest,
    KPICalculateResponse,
    KPISuggestResponse,
    SavedKPIConfig,
    ComparisonPeriod,
)
from core.rate_limiter import limiter, RateLimits

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------
# Request/Response Models
# ---------------------------------------------------
class KPICalculateRequestBody(BaseModel):
    """Request body for KPI calculation."""
    kpi_ids: List[str] = Field(..., min_length=1, max_length=20)
    column_mappings: List[KPIColumnMapping]
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    comparison_period: Optional[ComparisonPeriod] = None
    date_column: Optional[str] = None


class KPISaveConfigRequest(BaseModel):
    """Request to save KPI configuration."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    kpi_ids: List[str] = Field(..., min_length=1)
    column_mappings: List[KPIColumnMapping]
    template_id: Optional[str] = None
    auto_refresh: bool = False
    refresh_interval: Optional[ComparisonPeriod] = None


class TemplateListResponse(BaseModel):
    """Response for template list."""
    templates: List[KPITemplate]
    total: int


class KPIDefinitionListResponse(BaseModel):
    """Response for KPI definitions list."""
    kpis: List[KPIDefinition]
    total: int
    categories: List[str]


# ---------------------------------------------------
# Template Endpoints
# ---------------------------------------------------
@router.get("/templates", response_model=TemplateListResponse)
@limiter.limit(RateLimits.DATASET_LIST)
async def list_templates(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: dict = Depends(get_current_user),
):
    """
    List all available KPI templates.
    
    Templates provide pre-configured KPI dashboards for different use cases:
    - saas-metrics: SaaS business metrics (MRR, ARR, Churn, etc.)
    - ecommerce-metrics: E-commerce metrics (Revenue, AOV, etc.)
    - finance-metrics: Financial overview (Profit, Expenses, Cash Flow)
    """
    templates = list(ALL_TEMPLATES.values())
    
    if category:
        templates = [t for t in templates if t.category.value == category]
    
    return TemplateListResponse(
        templates=templates,
        total=len(templates)
    )


@router.get("/templates/{template_id}", response_model=KPITemplate)
@limiter.limit(RateLimits.DATASET_GET)
async def get_template(
    request: Request,
    template_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a specific KPI template by ID."""
    template = ALL_TEMPLATES.get(template_id)
    if not template:
        raise HTTPException(
            status_code=404, 
            detail=f"Template '{template_id}' not found. Available: {list(ALL_TEMPLATES.keys())}"
        )
    return template


# ---------------------------------------------------
# KPI Definition Endpoints
# ---------------------------------------------------
@router.get("/definitions", response_model=KPIDefinitionListResponse)
@limiter.limit(RateLimits.DATASET_LIST)
async def list_kpi_definitions(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category (saas, ecommerce, finance)"),
    current_user: dict = Depends(get_current_user),
):
    """
    List all available KPI definitions.
    
    Each KPI includes:
    - Formula type (simple, ratio, custom)
    - Display format (currency, percentage, number)
    - Health thresholds for alerts
    - Trend direction (up/down is good)
    """
    kpis = list(ALL_KPIS.values())
    
    if category:
        kpis = [k for k in kpis if k.category.value == category]
    
    # Get unique categories
    categories = list(set(k.category.value for k in ALL_KPIS.values()))
    
    return KPIDefinitionListResponse(
        kpis=kpis,
        total=len(kpis),
        categories=categories
    )


@router.get("/definitions/{kpi_id}", response_model=KPIDefinition)
@limiter.limit(RateLimits.DATASET_GET)
async def get_kpi_definition(
    request: Request,
    kpi_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a specific KPI definition by ID."""
    kpi = ALL_KPIS.get(kpi_id)
    if not kpi:
        raise HTTPException(
            status_code=404,
            detail=f"KPI '{kpi_id}' not found. Available: {list(ALL_KPIS.keys())}"
        )
    return kpi


# ---------------------------------------------------
# KPI Suggestion Endpoint
# ---------------------------------------------------
@router.post("/suggest/{dataset_id}", response_model=KPISuggestResponse)
@limiter.limit(RateLimits.ANALYSIS_CREATE)
async def suggest_kpis(
    request: Request,
    dataset_id: str,
    columns: Optional[List[str]] = Query(None, description="Columns to analyze (defaults to all)"),
    current_user: dict = Depends(get_current_user),
):
    """
    Auto-suggest KPIs based on dataset columns.
    
    This endpoint:
    1. Analyzes column names and data types
    2. Detects financial column types (revenue, cost, customer, date, etc.)
    3. Suggests appropriate KPIs with confidence scores
    4. Recommends the best matching template
    
    Use this to quickly set up KPI tracking for a new dataset.
    """
    # Get dataset
    dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Load dataset data
    try:
        df = await enhanced_dataset_service.load_dataset_as_polars(dataset_id, current_user["id"])
        if df is None:
            raise HTTPException(status_code=404, detail="Dataset data not found")
    except Exception as e:
        logger.error(f"Error loading dataset {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {str(e)}")
    
    # Suggest KPIs
    suggestions = kpi_service.suggest_kpis(
        df=df,
        dataset_id=dataset_id,
        columns=columns
    )
    
    return suggestions


# ---------------------------------------------------
# KPI Calculation Endpoint
# ---------------------------------------------------
@router.post("/calculate/{dataset_id}", response_model=KPICalculateResponse)
@limiter.limit(RateLimits.ANALYSIS_CREATE)
async def calculate_kpis(
    request: Request,
    dataset_id: str,
    body: KPICalculateRequestBody,
    current_user: dict = Depends(get_current_user),
):
    """
    Calculate KPIs for a dataset.
    
    Provide:
    - kpi_ids: List of KPI IDs to calculate
    - column_mappings: Map KPI formula variables to dataset columns
    - from_date/to_date: Optional date range filter
    - comparison_period: Period for trend comparison (day, week, month, etc.)
    - date_column: Column to use for date filtering
    
    Returns calculated values with:
    - Current value and formatted display
    - Previous period comparison
    - Change percentage and trend direction
    - Health status (healthy, warning, critical)
    """
    # Get dataset
    dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Load dataset data
    try:
        df = await enhanced_dataset_service.load_dataset_as_polars(dataset_id, current_user["id"])
        if df is None:
            raise HTTPException(status_code=404, detail="Dataset data not found")
    except Exception as e:
        logger.error(f"Error loading dataset {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {str(e)}")
    
    # Validate KPI IDs
    invalid_kpis = [k for k in body.kpi_ids if k not in ALL_KPIS]
    if invalid_kpis:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid KPI IDs: {invalid_kpis}. Available: {list(ALL_KPIS.keys())}"
        )
    
    # Calculate KPIs
    result = kpi_service.calculate_kpis(
        df=df,
        dataset_id=dataset_id,
        kpi_ids=body.kpi_ids,
        column_mappings=body.column_mappings,
        from_date=body.from_date,
        to_date=body.to_date,
        comparison_period=body.comparison_period,
        date_column=body.date_column
    )
    
    return result


# ---------------------------------------------------
# KPI Config Management
# ---------------------------------------------------
@router.get("/config/{dataset_id}")
@limiter.limit(RateLimits.DATASET_GET)
async def get_kpi_config(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """
    Get saved KPI configuration for a dataset.
    
    Returns the user's saved KPI setup including:
    - Selected KPIs
    - Column mappings
    - Auto-refresh settings
    """
    # Initialize service with database
    kpi_service.db = db
    
    config = await kpi_service.get_config(
        user_id=current_user["id"],
        dataset_id=dataset_id
    )
    
    if not config:
        return {"message": "No saved configuration", "config": None}
    
    return {"config": config}


@router.post("/config/{dataset_id}")
@limiter.limit(RateLimits.DASHBOARD_CREATE)
async def save_kpi_config(
    request: Request,
    dataset_id: str,
    body: KPISaveConfigRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """
    Save KPI configuration for a dataset.
    
    This saves:
    - Selected KPIs
    - Column mappings
    - Auto-refresh settings
    - Template reference (if used)
    
    Saved configs can be loaded later to restore KPI dashboard setup.
    """
    # Validate dataset exists
    dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Validate KPI IDs
    invalid_kpis = [k for k in body.kpi_ids if k not in ALL_KPIS]
    if invalid_kpis:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid KPI IDs: {invalid_kpis}"
        )
    
    # Build saved config
    kpi_definitions = [ALL_KPIS[k] for k in body.kpi_ids]
    
    config = SavedKPIConfig(
        user_id=current_user["id"],
        dataset_id=dataset_id,
        name=body.name,
        description=body.description,
        kpis=kpi_definitions,
        column_mappings=body.column_mappings,
        template_id=body.template_id,
        auto_refresh=body.auto_refresh,
        refresh_interval=body.refresh_interval
    )
    
    # Initialize service with database
    kpi_service.db = db
    
    config_id = await kpi_service.save_config(
        user_id=current_user["id"],
        dataset_id=dataset_id,
        config=config
    )
    
    return {
        "message": "KPI configuration saved",
        "config_id": config_id
    }


# ---------------------------------------------------
# Quick Calculate (with auto-detection)
# ---------------------------------------------------
@router.post("/quick-calculate/{dataset_id}")
@limiter.limit(RateLimits.ANALYSIS_CREATE)
async def quick_calculate_kpis(
    request: Request,
    dataset_id: str,
    template_id: Optional[str] = Query(None, description="Template to use (auto-detects if not provided)"),
    current_user: dict = Depends(get_current_user),
):
    """
    Quick KPI calculation with auto-detection.
    
    This is a convenience endpoint that:
    1. Auto-detects column types
    2. Suggests appropriate KPIs (or uses specified template)
    3. Maps columns automatically
    4. Calculates all suggested KPIs
    
    Perfect for getting instant insights from a new dataset.
    """
    # Get dataset
    dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Load dataset
    try:
        df = await enhanced_dataset_service.load_dataset_as_polars(dataset_id, current_user["id"])
        if df is None:
            raise HTTPException(status_code=404, detail="Dataset data not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {str(e)}")
    
    # Get suggestions
    suggestions = kpi_service.suggest_kpis(df=df, dataset_id=dataset_id)
    
    if not suggestions.suggested_kpis:
        return {
            "message": "No KPIs could be suggested for this dataset",
            "detected_columns": suggestions.detected_columns,
            "hint": "Ensure your dataset has columns with recognizable names like 'revenue', 'cost', 'customer_id', etc."
        }
    
    # Use template if specified, otherwise use suggested KPIs
    if template_id:
        template = ALL_TEMPLATES.get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
        kpi_ids = [c.kpi_id for c in template.kpis]
    else:
        # Use top 5 suggested KPIs
        kpi_ids = [s.kpi.id for s in suggestions.suggested_kpis[:5] if s.kpi.id]
    
    # Build column mappings from suggestions
    column_mappings = []
    for suggestion in suggestions.suggested_kpis:
        if suggestion.kpi.id in kpi_ids:
            column_mappings.append(KPIColumnMapping(
                kpi_id=suggestion.kpi.id,
                column_mappings=suggestion.suggested_mappings
            ))
    
    # Calculate KPIs
    result = kpi_service.calculate_kpis(
        df=df,
        dataset_id=dataset_id,
        kpi_ids=kpi_ids,
        column_mappings=column_mappings
    )
    
    return {
        "suggestions": suggestions,
        "calculations": result
    }

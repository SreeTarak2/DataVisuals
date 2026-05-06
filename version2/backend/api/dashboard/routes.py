from datetime import datetime
from fastapi import APIRouter, Depends, Query, Request

from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from core.rate_limiter import limiter, RateLimits

router = APIRouter()


def _build_kpis(dataset: dict) -> list[dict]:
	row_count = dataset.get("row_count") or 0
	column_count = dataset.get("column_count") or 0
	quality = dataset.get("metadata", {}).get("data_quality", {})
	completeness = quality.get("completeness")

	kpis = [
		{
			"id": "rows",
			"title": "Rows",
			"value": row_count,
			"format": "number",
		},
		{
			"id": "columns",
			"title": "Columns",
			"value": column_count,
			"format": "number",
		},
	]

	if completeness is not None:
		kpis.append(
			{
				"id": "completeness",
				"title": "Data Completeness",
				"value": completeness,
				"format": "percent",
			}
		)

	return kpis


@router.get("/{dataset_id}/overview")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dashboard_overview(
	request: Request,
	dataset_id: str,
	period: str = Query("all"),
	current_user: dict = Depends(get_current_user),
):
	from db.database import get_database
	from services.cache.dashboard_cache_service import dashboard_cache_service

	db = get_database()
	user_id = current_user["id"]
	dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)

	# ── Intelligent KPIs from cache (pre-computed during upload) ──────────────
	intelligent_kpis = []
	try:
		cached = await dashboard_cache_service.get_cached_kpis(dataset_id, user_id)
		if cached:
			intelligent_kpis = cached if isinstance(cached, list) else cached.get("kpis", [])
	except Exception:
		pass

	# ── Fallback: basic structural KPIs if no intelligent KPIs ───────────────
	basic_kpis = _build_kpis(dataset) if not intelligent_kpis else []

	kpis = intelligent_kpis or basic_kpis

	return {
		"dataset": {
			"id": dataset.get("id") or dataset_id,
			"name": dataset.get("name"),
			"row_count": dataset.get("row_count", 0),
			"column_count": dataset.get("column_count", 0),
			"processing_status": dataset.get("processing_status"),
		},
		"kpis": kpis,
		"kpi_source": "intelligent" if intelligent_kpis else "basic",
		"period": period,
		"available_periods": ["all"],
	}


@router.get("/{dataset_id}/charts")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dashboard_charts(
	request: Request,
	dataset_id: str,
	current_user: dict = Depends(get_current_user),
):
	from db.database import get_database
	
	db = get_database()
	
	# First, try to get the dashboard blueprint from the dashboards collection
	dashboard = await db.dashboards.find_one({
		"dataset_id": dataset_id,
		"user_id": current_user["id"],
		"is_default": True
	})
	
	charts = []
	if dashboard and dashboard.get("blueprint"):
		blueprint = dashboard["blueprint"]
		components = blueprint.get("components", [])
		# Extract all chart components from the blueprint
		charts = [comp for comp in components if comp.get("type") == "chart"]
	
	# Fallback to analytics if no dashboard found
	if not charts:
		combined = await enhanced_dataset_service.get_full_dataset_with_analytics(
			dataset_id,
			current_user["id"],
		)
		analytics = combined.get("analytics") or {}
		metadata = combined.get("metadata") or {}
		charts = analytics.get("chart_recommendations") or metadata.get("chart_recommendations") or []

	return {
		"charts": charts,
		"generated_at": datetime.utcnow().isoformat(),
	}


@router.get("/{dataset_id}/insights")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dashboard_insights(
	request: Request,
	dataset_id: str,
	current_user: dict = Depends(get_current_user),
):
	combined = await enhanced_dataset_service.get_full_dataset_with_analytics(
		dataset_id,
		current_user["id"],
	)

	analytics = combined.get("analytics") or {}
	metadata = combined.get("metadata") or {}

	deep_analysis = analytics.get("deep_analysis") or metadata.get("deep_analysis") or {}
	summary = deep_analysis.get("executive_summary") or ""

	insights_raw = (
		deep_analysis.get("quis_insights", {}).get("top_insights")
		or deep_analysis.get("quis_insights", {}).get("insights")
		or []
	)

	insights = []
	for idx, item in enumerate(insights_raw):
		insights.append(
			{
				"id": item.get("id") or f"insight_{idx}",
				"title": item.get("title") or item.get("question") or "Insight",
				"description": item.get("description") or item.get("insight") or item.get("finding") or "",
				"type": item.get("type") or "insight",
				"confidence": item.get("confidence"),
				"effect_size": item.get("effect_size"),
				"p_value": item.get("p_value"),
				"columns": item.get("columns") or [],
			}
		)

	return {
		"summary": summary,
		"insights": insights,
		"generated_at": datetime.utcnow().isoformat(),
	}


@router.get("/{dataset_id}/config")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dashboard_config(
	request: Request,
	dataset_id: str,
	current_user: dict = Depends(get_current_user),
):
	"""
	Get the complete AI-generated dashboard configuration (blueprint with all components).
	This is used by the frontend to render the full dashboard with charts, KPIs, and layout.
	"""
	from db.database import get_database
	
	db = get_database()
	
	# Fetch the dashboard blueprint from the dashboards collection
	dashboard = await db.dashboards.find_one({
		"dataset_id": dataset_id,
		"user_id": current_user["id"],
		"is_default": True
	})
	
	if not dashboard:
		return {
			"dashboard_blueprint": None,
			"design_pattern": None,
			"components": [],
			"reasoning": "No dashboard found",
			"cached": False,
		}
	
	blueprint = dashboard.get("blueprint", {})
	
	return {
		"dashboard_blueprint": blueprint,
		"design_pattern": dashboard.get("design_pattern"),
		"pattern_name": dashboard.get("pattern_name"),
		"components": blueprint.get("components", []),
		"summary": blueprint.get("summary"),
		"reasoning": dashboard.get("reasoning"),
		"cached": True,
		"created_at": dashboard.get("created_at"),
	}

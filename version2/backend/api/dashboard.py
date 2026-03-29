# backend/api/dashboard.py

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query

import polars as pl

# --- Application Modules ---
from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from services.charts.chart_render_service import chart_render_service
from services.charts.chart_insights_service import chart_insights_service
from services.charts.chart_intelligence_service import chart_intelligence_service
from services.ai.ai_service import ai_service
from services.ai.intelligent_kpi_generator import intelligent_kpi_generator
from services.analysis.analysis_service import analysis_service
from services.cache import dashboard_cache_service

# --- Config ---
logger = logging.getLogger(__name__)
router = APIRouter()


def _serialize_timestamp(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _recommendation_for_insight(insight_type: str, columns: list[str]) -> str:
    column_label = ", ".join(columns[:2]) if columns else "this signal"
    recommendations = {
        "correlation": f"Validate the operational driver behind {column_label} before treating it as causal.",
        "comparison": f"Break down {column_label} by segment and identify which groups need a targeted response.",
        "group_comparison": f"Break down {column_label} by segment and identify which groups need a targeted response.",
        "subspace": "Open the detailed insights report to inspect the filtered segment and confirm whether the pattern holds over time.",
        "trend": f"Track {column_label} weekly and add an alert so the team reacts before the trend compounds.",
        "anomaly": f"Audit recent records around {column_label} to separate true business exceptions from data quality issues.",
        "simpson_paradox": "Avoid using only rolled-up averages here; compare the same metric inside each major segment first.",
        "distribution": f"Use robust statistics such as median and percentile bands when reporting on {column_label}.",
    }
    return recommendations.get(
        insight_type,
        "Review the full analysis and decide whether this signal should drive a dashboard alert or follow-up investigation.",
    )


def _evidence_label(
    p_value: Any = None, effect_size: Any = None, confidence: Any = None
) -> str:
    if p_value is not None and p_value <= 0.01:
        return "Strong statistical evidence"
    if (
        effect_size is not None
        and isinstance(effect_size, (int, float))
        and abs(effect_size) >= 0.7
    ):
        return "Strong effect size"
    if confidence is not None and confidence >= 90:
        return "High-confidence pattern"
    if p_value is not None and p_value <= 0.05:
        return "Statistically significant"
    return "Directional signal"


def _severity_for_insight(
    insight_type: str, confidence: int, effect_size: Any = None, skewness: Any = None
) -> str:
    if insight_type in {"simpson_paradox", "anomaly"}:
        return "high"
    if (
        insight_type in {"warning", "distribution"}
        and isinstance(skewness, (int, float))
        and abs(skewness) >= 2
    ):
        return "high"
    if confidence >= 90 or (
        isinstance(effect_size, (int, float)) and abs(effect_size) >= 0.7
    ):
        return "high"
    if confidence >= 70 or (
        isinstance(effect_size, (int, float)) and abs(effect_size) >= 0.4
    ):
        return "medium"
    return "low"


def _business_impact_for_insight(
    insight_type: str, columns: list[str], severity: str
) -> str:
    column_label = ", ".join(columns[:2]) if columns else "this metric"
    prefix = {
        "high": "High impact",
        "medium": "Meaningful impact",
        "low": "Monitor",
    }.get(severity, "Monitor")
    impact_map = {
        "correlation": f"{prefix}: changes in {column_label} can move together and affect forecasting or target setting.",
        "comparison": f"{prefix}: performance is uneven across groups, which can hide winners and lagging segments.",
        "group_comparison": f"{prefix}: performance is uneven across groups, which can hide winners and lagging segments.",
        "subspace": f"{prefix}: the portfolio average may be masking a concentrated opportunity or risk pocket.",
        "trend": f"{prefix}: the direction of {column_label} may require intervention if it continues.",
        "anomaly": f"{prefix}: unusual observations around {column_label} may point to leakage, abuse, or operational exceptions.",
        "simpson_paradox": f"{prefix}: aggregate reporting on {column_label} could push the business toward the wrong decision.",
        "distribution": f"{prefix}: averages for {column_label} may be misleading for executive reporting.",
    }
    return impact_map.get(
        insight_type,
        f"{prefix}: this signal is worth validating before it influences decisions.",
    )


def _build_insights_summary(insights: list[dict]) -> dict:
    if not insights:
        return {
            "total_findings": 0,
            "high_priority_findings": 0,
            "top_categories": [],
        }

    counts: dict[str, int] = {}
    high_priority = 0
    for insight in insights:
        insight_type = insight.get("type", "info")
        counts[insight_type] = counts.get(insight_type, 0) + 1
        if insight.get("severity") == "high":
            high_priority += 1

    top_categories = [
        {"type": insight_type, "count": count}
        for insight_type, count in sorted(
            counts.items(), key=lambda item: item[1], reverse=True
        )[:3]
    ]

    return {
        "total_findings": len(
            [item for item in insights if item.get("id") != "executive_summary"]
        ),
        "high_priority_findings": high_priority,
        "top_categories": top_categories,
    }


# ============================================================
#                 DASHBOARD OVERVIEW
# ============================================================
@router.get("/{dataset_id}/overview")
async def get_dashboard_overview(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
    force_refresh: bool = Query(
        False, description="Force regeneration, ignoring cache"
    ),
):
    try:
        user_id = current_user["id"]

        # Check cache first (unless force_refresh=True)
        if not force_refresh:
            cached_data = await dashboard_cache_service.get_cached_kpis(
                dataset_id, user_id
            )
            if cached_data:
                logger.info(f"📊 Returning cached KPIs for dataset {dataset_id}")
                # Handle both dict (with dataset info) and list (KPIs only) formats
                if isinstance(cached_data, dict):
                    return {
                        "dataset": cached_data.get("dataset"),
                        "kpis": cached_data.get("kpis"),
                        "cached": True,
                    }
                else:
                    # cached_data is a list of KPIs
                    return {
                        "dataset": None,
                        "kpis": cached_data,
                        "cached": True,
                    }

        logger.info(f"🔄 Generating fresh KPIs for dataset {dataset_id}")

        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        metadata = dataset.get("metadata", {})

        overview = metadata.get("dataset_overview", {})
        quality = metadata.get("data_quality", {})

        if not overview:
            raise HTTPException(
                status_code=409,
                detail="Dataset metadata is not available. Please reprocess the dataset.",
            )

        # Load actual dataframe for intelligent KPI generation
        df = await enhanced_dataset_service.load_dataset_data(dataset_id, user_id)

        # Detect domain from metadata
        domain = metadata.get("domain_intelligence", {}).get("domain") or dataset.get(
            "domain"
        )

        # Generate intelligent, context-aware KPIs with full metadata
        intelligent_kpis = await intelligent_kpi_generator.generate_intelligent_kpis(
            df=df,
            domain=domain,
            max_kpis=4,  # hard ceiling — prompt enforces 3-4 by selection gate
            dataset_metadata=metadata,
        )

        # Format KPIs for frontend with enterprise data
        kpis = []
        for kpi in intelligent_kpis:
            value = kpi["value"]
            # Format large numbers for display
            if isinstance(value, dict):
                # Structured values (e.g. range: {"min": x, "max": y})
                if "min" in value and "max" in value:
                    formatted_value = f"{value['min']:,.2f} – {value['max']:,.2f}"
                else:
                    formatted_value = str(value)
            elif isinstance(value, (int, float)):
                if value >= 1_000_000:
                    formatted_value = f"{value / 1_000_000:.2f}M"
                elif value >= 1_000:
                    formatted_value = f"{value / 1_000:.2f}K"
                else:
                    formatted_value = (
                        f"{value:,.2f}" if isinstance(value, float) else f"{value:,}"
                    )
            elif value is None:
                formatted_value = "N/A"
            else:
                formatted_value = str(value)

            # Normalize sparkline: backend may return dict or list
            raw_sparkline = kpi.get("sparkline_data", [])
            if isinstance(raw_sparkline, dict):
                sparkline_data = raw_sparkline.get("data", [])
            else:
                sparkline_data = raw_sparkline

            kpis.append(
                {
                    "title": kpi["title"],
                    "value": formatted_value,
                    "subtitle": kpi.get("subtitle", ""),
                    "raw_value": value,
                    # Enterprise KPI fields
                    "format": kpi.get("format", "number"),
                    "comparison_value": kpi.get("comparison_value"),
                    "comparison_label": kpi.get("comparison_label", "vs last period"),
                    "delta_percent": kpi.get("delta_percent"),
                    "delta_direction": kpi.get("delta_direction"),
                    "target_value": kpi.get("target_value"),
                    "target_label": kpi.get("target_label"),
                    "sparkline_data": sparkline_data,
                    "context": kpi.get("context", ""),
                    "column": kpi.get("column", ""),
                    "aggregation": kpi.get("aggregation", ""),
                }
            )

        # Cache the result
        dataset_info = {
            "id": dataset.get("id"),
            "name": dataset.get("name"),
            "row_count": overview.get("total_rows", 0),
            "column_count": overview.get("total_columns", 0),
        }
        await dashboard_cache_service.cache_kpis(
            dataset_id, user_id, kpis, dataset_info
        )

        return {
            "dataset": dataset_info,
            "kpis": kpis,
            "cached": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting dashboard overview for {dataset_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to get dashboard overview.")


# ============================================================
#                 DASHBOARD INSIGHTS
# ============================================================
@router.get("/{dataset_id}/insights")
async def get_dashboard_insights(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
    force_refresh: bool = Query(
        False, description="Force regeneration, ignoring cache"
    ),
):
    try:
        user_id = current_user["id"]

        # Check cache first (unless force_refresh=True)
        if not force_refresh:
            cached_data = await dashboard_cache_service.get_cached_insights(
                dataset_id, user_id
            )
            if cached_data:
                logger.info(f"💡 Returning cached insights for dataset {dataset_id}")
                return {
                    "insights": cached_data,
                    "cached": True,
                    "generated_at": None,
                    "summary": _build_insights_summary(cached_data),
                }

        logger.info(f"🔄 Generating fresh insights for dataset {dataset_id}")

        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        metadata = dataset.get("metadata", {})
        deep_analysis = metadata.get("deep_analysis", {})

        insights = []

        # ── Helper: generate human-readable titles & descriptions ──
        def _humanize_correlation(
            col1: str, col2: str, r: float, effect_interp: str = ""
        ) -> tuple[str, str]:
            """Return (title, description) in plain English for a correlation insight."""
            direction = "increases with" if r > 0 else "decreases as"
            strength = effect_interp or (
                "strongly"
                if abs(r) >= 0.7
                else "moderately"
                if abs(r) >= 0.4
                else "weakly"
            )
            # Make column names readable
            c1 = col1.replace("_", " ").title()
            c2 = col2.replace("_", " ").title()
            title = (
                f"{c1} {direction} {c2}"
                if abs(r) < 0.7
                else f"Strong link: {c1} ↔ {c2}"
            )
            desc = f"{c1} and {c2} are {strength} correlated — when one changes, the other tends to follow {'in the same' if r > 0 else 'the opposite'} direction."
            return title, desc

        def _humanize_comparison(desc: str, finding: dict) -> tuple[str, str]:
            """Return (title, description) for a group comparison insight."""
            columns = finding.get("columns", [])
            col_names = (
                [c.replace("_", " ").title() for c in columns] if columns else []
            )
            if len(col_names) >= 2:
                title = f"{col_names[0]} varies across {col_names[1]} groups"
            else:
                title = f"Significant difference found across groups"
            effect_interp = finding.get("effect_interpretation", "notable")
            human_desc = f"There's a {effect_interp} difference in {col_names[0] if col_names else 'values'} when comparing different groups — this pattern is statistically significant and worth investigating."
            return title, human_desc

        def _humanize_subspace(desc: str, finding: dict) -> tuple[str, str]:
            """Return (title, description) for a subspace/hidden pattern insight."""
            subspace = finding.get("subspace", {})
            columns = finding.get("columns", [])
            if subspace:
                filters = [f"{k}={v}" for k, v in subspace.items()]
                title = f"Hidden pattern in {', '.join(filters[:2])}"
                human_desc = f"When filtering to {' and '.join(filters[:2])}, an unexpected pattern emerges that isn't visible in the overall data."
            elif columns:
                col_names = [c.replace("_", " ").title() for c in columns[:2]]
                title = f"Hidden pattern in {' & '.join(col_names)}"
                human_desc = f"A surprising pattern was found in {' and '.join(col_names)} that only appears in a specific subset of the data."
            else:
                title = "Hidden pattern discovered"
                human_desc = (
                    desc
                    or "A non-obvious pattern was detected in a data subset — this could reveal insights not visible in summary statistics."
                )
            return title, human_desc

        def _is_trivial_correlation(col1: str, col2: str, r: float) -> bool:
            """Detect obviously redundant column pairs (Close↔Adj Close, etc.)."""
            if abs(r) > 0.98:
                return True
            # Common trivially correlated pairs (case-insensitive substrings)
            c1, c2 = col1.lower(), col2.lower()
            trivial_pairs = [
                ("close", "adj_close"),
                ("close", "adj close"),
                ("close", "adjusted_close"),
                ("open", "high"),
                ("low", "close"),
                ("price", "adj_price"),
                ("amount", "total_amount"),
            ]
            for a, b in trivial_pairs:
                if (a in c1 and b in c2) or (a in c2 and b in c1):
                    return True
            return False

        # ── If deep_analysis was pre-computed at upload (pipeline v3.0+) ──
        if deep_analysis and deep_analysis.get("analysis_version"):
            enhanced = deep_analysis.get("enhanced_analysis", {})
            quis = deep_analysis.get("quis_insights", {})
            executive_summary = deep_analysis.get("executive_summary", "")

            type_map = {
                "correlation": "info",
                "comparison": "warning",
                "subspace": "success",
                "trend": "trend",
                "anomaly": "warning",
                "simpson_paradox": "success",
            }

            # Track seen column pairs to avoid duplicates
            seen_pairs = set()

            # Top QUIS insights — stored as basic_insights + deep_insights, not top_insights
            raw_quis = (
                quis.get("top_insights")   # future schema (not yet used)
                or (
                    quis.get("basic_insights", [])   # correlations, outliers
                    + quis.get("deep_insights", [])  # subspace findings
                )
            )
            for i, finding in enumerate(raw_quis[:12]):
                # Normalise field names: stored as "type"/"value", endpoint expects "insight_type"/"effect_size"
                insight_type = finding.get("insight_type") or finding.get("type", "insight")
                desc = finding.get("description", "")
                p_val = finding.get("p_value")
                effect = finding.get("effect_size") or finding.get("value")
                effect_interp = finding.get("effect_interpretation", "")
                # Normalize subspace types
                if insight_type in ("subspace_correlation", "two_level_subspace_correlation"):
                    insight_type = "subspace"
                # Derive columns from base_insight for subspace findings
                if not finding.get("columns") and finding.get("base_insight"):
                    finding = {**finding, "columns": finding["base_insight"].get("columns", [])}
                columns = finding.get("columns", [])

                # Skip statistically insignificant insights
                if p_val is not None and p_val > 0.05:
                    continue

                # Skip trivial correlations
                if insight_type == "correlation" and len(columns) >= 2:
                    pair = tuple(sorted([columns[0].lower(), columns[1].lower()]))
                    if pair in seen_pairs or _is_trivial_correlation(
                        columns[0], columns[1], effect or 0
                    ):
                        continue
                    seen_pairs.add(pair)

                # Generate human-readable title & description
                if insight_type == "correlation" and len(columns) >= 2:
                    title, human_desc = _humanize_correlation(
                        columns[0], columns[1], effect or 0, effect_interp
                    )
                elif insight_type in ("comparison", "group_comparison"):
                    title, human_desc = _humanize_comparison(desc, finding)
                elif insight_type == "subspace":
                    title, human_desc = _humanize_subspace(desc, finding)
                elif insight_type == "simpson_paradox":
                    title = "⚠️ Simpson's Paradox detected"
                    human_desc = (
                        desc
                        or "A trend that appears in the overall data reverses when the data is split into groups — be cautious drawing conclusions from aggregated numbers."
                    )
                else:
                    # trend, anomaly, or unknown — keep original desc but clean up title
                    title = insight_type.replace("_", " ").title()
                    human_desc = desc

                confidence = max(10, int((1 - (p_val or 0.5)) * 100))
                severity = _severity_for_insight(insight_type, confidence, effect, None)

                insights.append(
                    {
                        "id": f"quis_{i}",
                        "type": type_map.get(insight_type, "info"),
                        "title": title,
                        "description": human_desc,
                        "confidence": min(confidence, 99),
                        "p_value": p_val,
                        "effect_size": effect,
                        "is_simpson_paradox": finding.get("is_simpson_paradox", False),
                        "columns": columns,
                        "severity": severity,
                        "evidence_label": _evidence_label(p_val, effect, confidence),
                        "recommended_action": _recommendation_for_insight(
                            insight_type, columns
                        ),
                        "business_impact": _business_impact_for_insight(
                            insight_type, columns, severity
                        ),
                    }
                )

            # Strong correlations from enhanced analysis (only if not already covered by QUIS)
            for i, corr in enumerate(enhanced.get("correlations", [])[:4]):
                r = corr.get("correlation", 0)
                if abs(r) < 0.5 or len(insights) >= 8:
                    continue

                col1 = corr.get("column1", "?")
                col2 = corr.get("column2", "?")
                p = corr.get("p_value")

                # Skip insignificant, trivial, or already-seen pairs
                if p is not None and p > 0.05:
                    continue
                pair = tuple(sorted([col1.lower(), col2.lower()]))
                if pair in seen_pairs or _is_trivial_correlation(col1, col2, r):
                    continue
                seen_pairs.add(pair)

                strength = corr.get("strength", "notable")
                title, human_desc = _humanize_correlation(col1, col2, r, strength)
                confidence = max(10, int((1 - (p or 0.5)) * 100))
                severity = _severity_for_insight("correlation", confidence, r, None)

                insights.append(
                    {
                        "id": f"corr_{i}",
                        "type": "info",
                        "title": title,
                        "description": human_desc,
                        "confidence": confidence,
                        "p_value": p,
                        "effect_size": abs(r),
                        "columns": [col1, col2],
                        "severity": severity,
                        "evidence_label": _evidence_label(p, r, confidence),
                        "recommended_action": _recommendation_for_insight(
                            "correlation", [col1, col2]
                        ),
                        "business_impact": _business_impact_for_insight(
                            "correlation", [col1, col2], severity
                        ),
                    }
                )

            # Distribution anomalies (only genuinely skewed ones)
            for i, dist in enumerate(enhanced.get("distributions", [])[:3]):
                skew = dist.get("skewness", 0)
                if abs(skew) > 1.5 and len(insights) < 8:
                    col = dist.get("column", "?")
                    col_name = col.replace("_", " ").title()
                    dist_type = dist.get("distribution_type", "skewed")
                    direction = "right" if skew > 0 else "left"
                    confidence = 90
                    severity = _severity_for_insight(
                        "distribution", confidence, None, skew
                    )

                    title = f"{col_name} is heavily {direction}-skewed"
                    human_desc = (
                        f"The distribution of {col_name} is not bell-shaped — it's skewed to the {direction}, "
                        f"meaning {'most values cluster low with a few extreme highs' if skew > 0 else 'most values cluster high with a few extreme lows'}. "
                        f"Consider using median instead of mean for this column."
                    )

                    insights.append(
                        {
                            "id": f"dist_{i}",
                            "type": "warning" if abs(skew) > 2 else "info",
                            "title": title,
                            "description": human_desc,
                            "confidence": confidence,
                            "columns": [col],
                            "severity": severity,
                            "evidence_label": _evidence_label(
                                None, abs(skew), confidence
                            ),
                            "recommended_action": _recommendation_for_insight(
                                "distribution", [col]
                            ),
                            "business_impact": _business_impact_for_insight(
                                "distribution", [col], severity
                            ),
                        }
                    )

            # Executive summary as first insight if available
            if executive_summary:
                # Build meaningful action + impact from actual computed data
                high_sev = [ins for ins in insights if ins.get("severity") == "high"]
                anomaly_ins = [ins for ins in insights if ins.get("type") == "warning"]
                corr_ins = [ins for ins in insights if ins.get("id", "").startswith(("quis_", "corr_"))]
                total_findings = len(insights)

                if high_sev:
                    top_cols = high_sev[0].get("columns", [])
                    top_col_label = top_cols[0].replace("_", " ").title() if top_cols else "the top signal"
                    exec_action = (
                        f"Prioritize {top_col_label} — it has the strongest effect in this dataset. "
                        f"Review the {len(high_sev)} high-priority finding{'s' if len(high_sev) != 1 else ''} below and decide which need an alert or workflow change."
                    )
                elif anomaly_ins:
                    exec_action = (
                        f"Investigate the {len(anomaly_ins)} anomaly or warning signal{'s' if len(anomaly_ins) != 1 else ''} below before acting on any summary statistics — they may be distorting your averages."
                    )
                else:
                    exec_action = (
                        f"Review the {total_findings} findings below and confirm which patterns are persistent vs. one-time — persistent signals should drive alerts or model inputs."
                    )

                if anomaly_ins and high_sev:
                    exec_impact = (
                        f"This dataset contains {len(high_sev)} high-impact signal{'s' if len(high_sev) != 1 else ''} and {len(anomaly_ins)} anomaly flag{'s' if len(anomaly_ins) != 1 else ''} — acting on these selectively could reduce reporting error and surface hidden performance gaps."
                    )
                elif corr_ins:
                    exec_impact = (
                        f"{len(corr_ins)} correlated column pair{'s' if len(corr_ins) != 1 else ''} {'were' if len(corr_ins) != 1 else 'was'} detected. If these relationships hold causally, they can improve forecast accuracy or flag leading indicators for the business."
                    )
                else:
                    exec_impact = (
                        f"{total_findings} pattern{'s' if total_findings != 1 else ''} found. Use these signals to prioritize which metrics need monitoring, alerting, or deeper drill-down."
                    )

                insights.insert(
                    0,
                    {
                        "id": "executive_summary",
                        "type": "success",
                        "title": "Executive Summary",
                        "description": executive_summary,
                        "confidence": 100,
                        "severity": "medium",
                        "evidence_label": "Portfolio summary",
                        "recommended_action": exec_action,
                        "business_impact": exec_impact,
                    },
                )

        else:
            # ── Fallback for datasets processed before v3.0 ──
            df = await enhanced_dataset_service.load_dataset_data(
                dataset_id, current_user["id"]
            )
            quis_results = analysis_service.run_quis_analysis(df, dataset_id=dataset_id)

            for finding in quis_results.get("deep_insights", [])[:4]:
                insights.append(
                    {
                        "id": f"deep_{len(insights)}",
                        "type": "success",
                        "title": finding.get("type", "Deep Insight")
                        .replace("_", " ")
                        .title(),
                        "description": f"A strong pattern was found in the subspace: {finding.get('subspace', 'N/A')}",
                        "confidence": 95,
                        "severity": "high",
                        "evidence_label": "High-confidence pattern",
                        "recommended_action": _recommendation_for_insight(
                            "subspace", []
                        ),
                        "business_impact": _business_impact_for_insight(
                            "subspace", [], "high"
                        ),
                    }
                )

            for finding in quis_results.get("basic_insights", [])[: 4 - len(insights)]:
                if finding.get("type") in ["correlation", "outlier"]:
                    insights.append(
                        {
                            "id": f"basic_{len(insights)}",
                            "type": "warning"
                            if finding.get("type") == "outlier"
                            else "info",
                            "title": finding.get("type", "Insight").title(),
                            "description": f"Column '{finding.get('column', finding.get('columns'))}' shows notable {finding.get('type')}.",
                            "confidence": 85,
                            "severity": "medium",
                            "evidence_label": "Directional signal",
                            "recommended_action": "Review the underlying records and confirm whether this should trigger an alert or a data quality rule.",
                            "business_impact": "This signal may affect reporting quality or point to a segment worth further review.",
                        }
                    )

        if not insights:
            insights.append(
                {
                    "id": "default",
                    "type": "info",
                    "title": "Analysis Complete",
                    "description": "The dataset has been analyzed. No high-significance automated insights were found.",
                    "confidence": 100,
                    "severity": "low",
                    "evidence_label": "No critical findings",
                    "recommended_action": "Use the full insights report or chat to explore a specific business question instead of relying on automated highlights alone.",
                    "business_impact": "The absence of strong automated findings suggests the dataset may require a narrower hypothesis or segment-level exploration.",
                }
            )

        # Cache insights
        await dashboard_cache_service.cache_insights(dataset_id, user_id, insights)

        return {
            "insights": insights,
            "cached": False,
            "generated_at": None,
            "summary": _build_insights_summary(insights),
        }

    except Exception as e:
        logger.error(
            f"Error getting dashboard insights for {dataset_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to get dashboard insights.")


# ============================================================
#                 DEFAULT DASHBOARD CHARTS
# ============================================================
@router.get("/{dataset_id}/charts")
async def get_dashboard_charts(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
    force_refresh: bool = Query(
        False, description="Force regeneration, ignoring cache"
    ),
):
    try:
        user_id = current_user["id"]

        # Check cache first (unless force_refresh=True)
        if not force_refresh:
            cached_charts = await dashboard_cache_service.get_cached_charts(
                dataset_id, user_id
            )
            if cached_charts:
                logger.info(f"📈 Returning cached charts for dataset {dataset_id}")
                return {"charts": cached_charts, "cached": True}

        logger.info(f"🔄 Generating fresh charts for dataset {dataset_id}")

        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        df = await enhanced_dataset_service.load_dataset_data(dataset_id, user_id)

        metadata = dataset.get("metadata", {})
        column_metadata = metadata.get("column_metadata", [])
        data_profile = metadata.get("data_profile", {})
        domain_info = metadata.get("domain_intelligence", {})
        deep_analysis = metadata.get("deep_analysis", {})

        charts = {}

        numeric_cols = df.select(pl.col(pl.NUMERIC_DTYPES)).columns
        categorical_cols = df.select(pl.col(pl.Utf8, pl.Categorical)).columns

        if numeric_cols and categorical_cols:
            chart_selection = chart_intelligence_service.select_dashboard_charts(
                df=df,
                column_metadata=column_metadata,
                domain=domain_info.get("domain", "general"),
                domain_confidence=domain_info.get("confidence", 0.5),
                statistical_findings=deep_analysis.get("enhanced_analysis", {}),
                data_profile=data_profile,
                context="executive",
            )

            selected_charts = chart_selection.get("charts", [])[:5]

            for i, chart_spec in enumerate(selected_charts):
                chart_key = f"chart_{i}"
                config = chart_spec.get("config", {})

                # Resolve columns: support both "columns" list and "x_axis"/"y_axis" keys
                columns = config.get("columns") or (
                    [config["x_axis"], config["y_axis"]]
                    if config.get("x_axis") and config.get("y_axis")
                    else [categorical_cols[0], numeric_cols[0]]
                )

                chart_data = await chart_render_service.render_chart(
                    df,
                    {
                        "chart_type": chart_spec.get("chart_type", "bar"),
                        "columns": columns,
                        "aggregation": config.get("aggregation", "sum"),
                        "title": chart_spec.get("title", f"Chart {i + 1}"),
                    },
                )
                charts[chart_key] = chart_data

            logger.info(
                f"Generated {len(charts)} AI-selected charts for dataset {dataset_id}"
            )

        if not charts:
            if numeric_cols and categorical_cols:
                charts["sales_by_category"] = await chart_render_service.render_chart(
                    df,
                    {
                        "chart_type": "bar",
                        "columns": [categorical_cols[0], numeric_cols[0]],
                        "aggregation": "sum",
                    },
                )

                charts["traffic_source"] = await chart_render_service.render_chart(
                    df,
                    {
                        "chart_type": "pie",
                        "columns": [categorical_cols[0], numeric_cols[0]],
                        "aggregation": "count",
                    },
                )
                logger.info("Using fallback charts (bar + pie)")

        # Cache charts
        await dashboard_cache_service.cache_charts(dataset_id, user_id, charts)

        return {"charts": charts, "cached": False}

    except Exception as e:
        logger.error(
            f"Error getting dashboard charts for {dataset_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to get dashboard charts.")


# ============================================================
#            AI-GENERATED DASHBOARD LAYOUT
# ============================================================
@router.get("/{dataset_id}/ai-layout")
async def get_ai_dashboard_layout(
    dataset_id: str, current_user: dict = Depends(get_current_user)
):
    try:
        layout = await ai_service.generate_ai_dashboard(dataset_id, current_user["id"])
        return {"success": True, "layout": layout}

    except Exception as e:
        logger.error(f"Error generating AI dashboard layout: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to generate AI dashboard layout."
        )


# ============================================================
#            ANALYTICS STUDIO (CUSTOM CHARTS)
# ============================================================
@router.post("/analytics/generate-chart")
async def generate_analytics_chart(
    request: Dict[str, Any], current_user: dict = Depends(get_current_user)
):
    try:
        dataset_id = request.get("dataset_id")
        chart_config = {
            "chart_type": request.get("chart_type", "bar"),
            "columns": [request.get("x_axis"), request.get("y_axis")],
            "aggregation": request.get("aggregation", "sum"),
        }

        if not dataset_id or not chart_config["columns"][0]:
            raise HTTPException(
                status_code=400, detail="dataset_id and x_axis are required."
            )

        return await chart_render_service.render_chart(
            chart_config, dataset_id, current_user["id"]
        )

    except Exception as e:
        logger.error(f"Error generating analytics chart: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to generate chart data: {e}"
        )


# ============================================================
#                 PREVIEW RENDERING
# ============================================================
@router.post("/charts/render-preview")
async def render_chart_preview(
    request: Dict[str, Any], current_user: dict = Depends(get_current_user)
):
    try:
        chart_config = request.get("chart_config")
        dataset_id = request.get("dataset_id")

        if not chart_config or not dataset_id:
            raise HTTPException(
                status_code=400, detail="chart_config and dataset_id are required."
            )

        return await chart_render_service.render_chart(
            chart_config, dataset_id, current_user["id"]
        )

    except Exception as e:
        logger.error(f"Chart rendering error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to render chart.")


# ============================================================
#                 AI CHART INSIGHTS
# ============================================================
@router.post("/charts/insights")
async def generate_chart_insights(
    request: Dict[str, Any], current_user: dict = Depends(get_current_user)
):
    try:
        chart_config = request.get("chart_config", {})
        chart_data = request.get("chart_data", [])
        dataset_id = request.get("dataset_id")

        dataset = await enhanced_dataset_service.get_dataset(
            dataset_id, current_user["id"]
        )

        return await chart_insights_service.generate_chart_insight(
            chart_config, chart_data, dataset.get("metadata", {})
        )

    except Exception as e:
        logger.error(f"Error generating chart insights: {e}", exc_info=True)
        return chart_insights_service._generate_fallback_insight(chart_config, [])


# ============================================================
#                CACHED CHARTS
# ============================================================
@router.get("/{dataset_id}/cached-charts")
async def get_cached_charts(
    dataset_id: str, current_user: dict = Depends(get_current_user)
):
    return await chart_insights_service.get_dataset_cached_charts(
        dataset_id, current_user["id"]
    )


# ============================================================
#                CACHE STATUS & MANAGEMENT
# ============================================================


@router.get("/{dataset_id}/cache-status")
async def get_cache_status(
    dataset_id: str, current_user: dict = Depends(get_current_user)
):
    """Get dashboard cache status for a dataset."""
    try:
        user_id = current_user["id"]
        await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        status = await dashboard_cache_service.get_cache_status(dataset_id, user_id)
        return {
            "success": True,
            "cache_status": status,
        }
    except Exception as e:
        logger.error(f"Error getting cache status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get cache status.")


@router.delete("/{dataset_id}/cache")
async def invalidate_dashboard_cache(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
    cache_keys: str = Query(
        None,
        description="Specific keys to invalidate: kpis,charts,insights (comma-separated)",
    ),
):
    """Invalidate dashboard cache for a dataset."""
    try:
        user_id = current_user["id"]
        await enhanced_dataset_service.get_dataset(dataset_id, user_id)

        # Parse cache keys if provided
        keys_to_invalidate = None
        if cache_keys:
            keys_to_invalidate = [k.strip() for k in cache_keys.split(",")]

        await dashboard_cache_service.invalidate_cache(
            dataset_id, user_id, keys_to_invalidate
        )
        return {
            "success": True,
            "invalidated_keys": keys_to_invalidate or ["all"],
            "message": "Cache invalidated successfully",
        }
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to invalidate cache.")

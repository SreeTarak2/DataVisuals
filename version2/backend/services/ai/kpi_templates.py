"""
KPI Template Generation
=======================
Domain-template-based KPI generation using column pattern matching
and LLM-provided column mapping.
Extracted from intelligent_kpi_generator.py.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import polars as pl

from .kpi_compute import (
    _compute_comparison,
    _compute_kpi_value,
    _compute_rolling_baseline,
    _compute_sparkline,
    _compute_accent_color,
    _detect_anomaly,
    _detect_time_period,
    _compute_trend_forecast,
    _compute_top_driver,
)
from .kpi_insights import _generate_deterministic_insight, build_provenance
from .kpi_types import ColumnProfile, ColumnRole

logger = logging.getLogger(__name__)


def _generate_template_kpis(
    df: pl.DataFrame,
    template_id: str,
    profiles: List[ColumnProfile],
    time_col: Optional[str],
    llm_column_mapping: Optional[dict[str, str]] = None,
    is_estimated: bool = False,
    estimate_ratio: Optional[float] = None,
    entity_profile_by_col: Optional[Dict[str, 'EntityAwareProfile']] = None,
    comparison: Optional[str] = None,
) -> List[Dict[str, Any]]:
    from services.kpi.patterns import COLUMN_PATTERNS
    from services.kpi.templates import ALL_TEMPLATES
    from services.kpi.definitions import (
        SAAS_KPIS, ECOMMERCE_KPIS, FINANCE_KPIS,
        HEALTHCARE_KPIS, REAL_ESTATE_KPIS, HR_KPIS,
        MARKETING_KPIS, EDUCATION_KPIS, MANUFACTURING_KPIS, LOGISTICS_KPIS,
        AUTOMOTIVE_KPIS,
    )

    CATEGORY_KPIS_MAP: dict[str, dict] = {
        "saas-metrics": SAAS_KPIS,
        "ecommerce-metrics": ECOMMERCE_KPIS,
        "finance-metrics": FINANCE_KPIS,
        "healthcare-metrics": HEALTHCARE_KPIS,
        "real-estate-metrics": REAL_ESTATE_KPIS,
        "hr-metrics": HR_KPIS,
        "marketing-metrics": MARKETING_KPIS,
        "education-metrics": EDUCATION_KPIS,
        "manufacturing-metrics": MANUFACTURING_KPIS,
        "logistics-metrics": LOGISTICS_KPIS,
        "automotive-metrics": AUTOMOTIVE_KPIS,
    }

    template = ALL_TEMPLATES.get(template_id)
    kpi_defs = CATEGORY_KPIS_MAP.get(template_id, {})
    if not template or not kpi_defs:
        return []

    # Detect column types via pattern matching
    detected_types: dict[str, str] = {}
    for p in profiles:
        col_lower = p.name.lower().replace("_", " ").replace("-", " ")
        for col_type, patterns in COLUMN_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, col_lower, re.IGNORECASE):
                    detected_types[p.name] = col_type
                    break

    type_to_col: dict[str, str] = {}
    for col_name, col_type in detected_types.items():
        if col_type not in type_to_col:
            type_to_col[col_type] = col_name

    if llm_column_mapping:
        for col_type, col_name in llm_column_mapping.items():
            if col_name in df.columns:
                type_to_col[col_type] = col_name

    # Map common synonyms
    for p in profiles:
        nl = p.name.lower().replace("_", " ").replace("-", " ")
        if "revenue" in nl and "revenue" not in type_to_col:
            type_to_col["revenue"] = p.name
        if "date" in nl or "time" in nl:
            if "date" not in type_to_col:
                type_to_col["date"] = p.name
        if "customer" in nl or "user" in nl or "client" in nl:
            if "customer_id" not in type_to_col and "customer_count" not in type_to_col:
                if "count" in nl or "number" in nl or "total" in nl:
                    type_to_col["customer_count"] = p.name
        if "cost" in nl or "expense" in nl or "spend" in nl:
            if "cost" not in type_to_col:
                type_to_col["cost"] = p.name
        if "order" in nl or "transaction" in nl or "invoice" in nl:
            if "transaction_id" not in type_to_col:
                type_to_col["transaction_id"] = p.name

    kpis: list[Dict[str, Any]] = []

    for component in template.kpis:
        kpi_id = component.kpi_id
        kpi_def = kpi_defs.get(kpi_id)
        if not kpi_def or not kpi_def.formula:
            continue

        try:
            value: Optional[float] = None
            used_column: Optional[str] = None
            used_profile: Optional[ColumnProfile] = None
            formula = kpi_def.formula

            if formula.formula_type == "simple":
                fc = formula.column or "revenue"
                mapped = type_to_col.get(fc)
                if mapped and mapped in df.columns:
                    used_column = mapped
                    used_profile = next((p for p in profiles if p.name == mapped), None)
                    if used_profile:
                        value = _compute_kpi_value(df, used_profile)

            elif formula.formula_type == "ratio":
                num_type = formula.numerator_column or ""
                den_type = formula.denominator_column or ""
                num_col = type_to_col.get(num_type)
                den_col = type_to_col.get(den_type)

                if num_col and den_col and num_col in df.columns and den_col in df.columns:
                    num_prof = next((p for p in profiles if p.name == num_col), None)
                    den_prof = next((p for p in profiles if p.name == den_col), None)
                    if num_prof and den_prof:
                        numerator = _compute_kpi_value(df, num_prof)
                        denominator = _compute_kpi_value(df, den_prof)
                        if denominator and denominator != 0:
                            value = numerator / denominator
                            if kpi_def.format == "percentage":
                                value *= 100
                            used_column = num_col
                            used_profile = num_prof

            elif formula.formula_type == "custom" and formula.custom_expression:
                value = _evaluate_template_formula(formula.custom_expression, type_to_col, df)
                first_col = next(iter(type_to_col.values()), None)
                if first_col and first_col in df.columns:
                    used_column = first_col
                    used_profile = next((p for p in profiles if p.name == first_col), None)

            if value is not None:
                card = _build_template_kpi_card(
                    kpi_def=kpi_def,
                    value=value,
                    used_column=used_column,
                    used_profile=used_profile,
                    profiles=profiles,
                    df=df,
                    time_col=time_col,
                    component_position=component.position,
                    is_estimated=is_estimated,
                    estimate_ratio=estimate_ratio,
                    entity_profile_by_col=entity_profile_by_col,
                )
                if card:
                    kpis.append(card)

        except Exception as e:
            logger.debug(f"[KPI] Template KPI '{kpi_id}' failed: {e}")
            continue

    return kpis


def _evaluate_template_formula(
    expr: str, column_mappings: dict[str, str], df: pl.DataFrame
) -> Optional[float]:
    context: dict[str, float] = {}
    for var_name, col_name in column_mappings.items():
        if col_name in df.columns:
            try:
                context[var_name] = float(df[col_name].drop_nulls().sum())
            except Exception:
                context[var_name] = 0.0

    try:
        eval_expr = expr
        for var, val in context.items():
            eval_expr = re.sub(rf"\b{re.escape(var)}\b", str(val), eval_expr)

        from services.kpi.evaluator import safe_eval as safe_arithmetic_eval

        if re.match(r"^[\d\s\+\-\*\/\(\)\.]+$", eval_expr):
            return safe_arithmetic_eval(eval_expr)
    except Exception:
        pass
    return None


def _build_template_kpi_card(
    kpi_def,
    value: float,
    used_column: Optional[str],
    used_profile: Optional[ColumnProfile],
    profiles: List[ColumnProfile],
    df: pl.DataFrame,
    time_col: Optional[str],
    component_position: int = 0,
    is_estimated: bool = False,
    estimate_ratio: Optional[float] = None,
    entity_profile_by_col: Optional[Dict[str, 'EntityAwareProfile']] = None,
) -> Optional[Dict[str, Any]]:
    if value is None:
        return None

    fmt_map = {"currency": "currency", "percentage": "percentage", "number": "decimal"}
    fmt = fmt_map.get(kpi_def.format, "decimal")

    from db.schemas_kpi import TrendDirection

    polarity = "higher_is_better"
    if kpi_def.trend_direction == TrendDirection.DOWN_IS_GOOD:
        polarity = "lower_is_better"

    profile = used_profile or next((p for p in profiles if p.name == used_column), None)

    if profile:
        comparison = _compute_comparison(df, profile, time_col, comparison)
        sparkline = _compute_sparkline(df, profile, time_col)
        time_period = _detect_time_period(df, profile, time_col)
        period_values = time_period.get("period_values", [])
        baseline = _compute_rolling_baseline(period_values, window=3)
        baseline_value = baseline.get("baseline_value")
        baseline_std = baseline.get("baseline_std")
        anomaly = _detect_anomaly(value, baseline_value or 0, baseline_std or 0)
        trend = _compute_trend_forecast(period_values)
        top_driver = _compute_top_driver(df, profile.name)
    else:
        comparison = None
        sparkline = {"data": [], "type": "distribution"}
        time_period = {}
        baseline = {}
        anomaly = {"is_anomaly": False, "anomaly_direction": "normal", "z_score": 0.0, "anomaly_severity": "normal"}
        trend = {}
        top_driver = None
        baseline_value = None

    delta_dir = comparison["delta_direction"] if comparison else None
    accent = _compute_accent_color("hero" if component_position < 3 else "high", delta_dir, polarity)

    dummy_profile = profile or ColumnProfile(
        name=used_column or kpi_def.id or kpi_def.name,
        role=ColumnRole.MEASURE,
        n_rows=len(df),
        n_nulls=0,
        n_unique=0,
    )

    entity_info_for_insight = None
    entity_type_val = "Unknown"
    entity_conc = None
    top_entity_val = None
    entity_card = None
    if entity_profile_by_col and used_column:
        ep = entity_profile_by_col.get(used_column)
        if ep:
            entity_type_val = ep.entity_type
            entity_conc = ep.entity_concentration_pct
            top_entity_val = ep.top_entity_value
            entity_card = ep.entity_cardinality
            entity_info_for_insight = {
                "entity_type": entity_type_val,
                "entity_concentration_pct": entity_conc,
                "top_entity_value": top_entity_val,
                "entity_cardinality": entity_card,
            }

    insight, action = _generate_deterministic_insight(
        dummy_profile, value, comparison, anomaly, trend, top_driver, fmt,
        entity_info=entity_info_for_insight,
    )

    bench_val = dummy_profile.col_p75 if dummy_profile else None
    bench_label = "Top 25%" if bench_val else None

    cat_str = "general"
    if hasattr(kpi_def, "category"):
        c = kpi_def.category
        if hasattr(c, "value"):
            cat_str = c.value
        elif isinstance(c, str):
            cat_str = c

    provenance = build_provenance(
        profile=dummy_profile,
        df=df,
        column=used_column or kpi_def.id or kpi_def.name.lower().replace(" ", "_"),
        aggregation=kpi_def.formula.formula_type if kpi_def.formula else "sum",
        is_estimated=is_estimated,
        estimate_ratio=estimate_ratio,
        source_table="upload",
        formula_override=kpi_def.name,
    )

    # Import _fmt_val lazily to avoid circular
    from .kpi_merge import _fmt_val

    return {
        "type": "kpi",
        "column": used_column or kpi_def.id or kpi_def.name.lower().replace(" ", "_"),
        "provenance": provenance.to_dict(),
        "entity_type": entity_type_val,
        "entity_concentration_pct": entity_conc,
        "top_entity_value": top_entity_val,
        "entity_cardinality": entity_card,
        "aggregation": kpi_def.formula.formula_type if kpi_def.formula else "sum",
        "importance": "hero" if component_position < 2 else "high",
        "business_category": cat_str,
        "template_kpi": True,
        "template_id": kpi_def.id,
        "is_estimated": is_estimated,
        "estimate_ratio": estimate_ratio,
        "title": kpi_def.name,
        "subtitle": kpi_def.description[:80] if kpi_def.description else "",
        "value": round(value, 4),
        "format": fmt,
        "icon": _template_icon_name(kpi_def.icon),
        "record_count": len(df),
        "comparison_value": comparison["comparison_value"] if comparison else None,
        "comparison_label": comparison["comparison_label"] if comparison else None,
        "delta_percent": comparison["delta_percent"] if comparison else None,
        "delta_direction": comparison["delta_direction"] if comparison else None,
        "is_delta_positive": comparison["is_delta_positive"] if comparison else (polarity == "higher_is_better"),
        "accent_color": accent,
        "sparkline_data": sparkline,
        "benchmark_value": round(bench_val, 2) if bench_val else None,
        "benchmark_label": bench_label,
        "benchmark_text": f"{bench_label}: {_fmt_val(bench_val, fmt)}" if bench_val and bench_label else None,
        "ai_suggestion": insight,
        "action_prompt": action,
        "dashboard_story": "",
        "archetype": cat_str,
        "col_p75": dummy_profile.col_p75 if dummy_profile else None,
        "col_median": dummy_profile.col_median if dummy_profile else None,
        "polarity": polarity,
        "period_label": time_period.get("period_label", ""),
        "previous_period_label": time_period.get("previous_period_label", ""),
        "period_type": time_period.get("period_type", ""),
        "baseline_value": baseline_value,
        "baseline_label": "3-month avg" if time_period.get("period_type") == "month" else "baseline",
        "vs_baseline_pct": (
            round(((value - (baseline_value or 0)) / abs(baseline_value or 1)) * 100, 1)
            if baseline_value and baseline_value != 0 else None
        ),
        "baseline_std": baseline.get("baseline_std"),
        "normal_range_low": baseline.get("normal_range_low"),
        "normal_range_high": baseline.get("normal_range_high"),
        "is_anomaly": anomaly.get("is_anomaly", False),
        "anomaly_direction": anomaly.get("anomaly_direction", "normal"),
        "z_score": anomaly.get("z_score", 0.0),
        "anomaly_severity": anomaly.get("anomaly_severity", "normal"),
        "expected_value": trend.get("expected_value"),
        "trend_direction": trend.get("trend_direction", "flat"),
        "top_driver": top_driver,
        "vs_previous_pct": (
            round(((value - (time_period.get("previous_period_value") or 0)) / abs(time_period.get("previous_period_value") or 1)) * 100, 1)
            if time_period.get("previous_period_value") else None
        ),
    }


def _template_icon_name(icon: Optional[str]) -> str:
    mapping = {
        "dollar-sign": "DollarSign", "trending-up": "TrendingUp",
        "user-minus": "UserMinus", "users": "Users", "target": "Target",
        "scale": "Scale", "refresh-cw": "RefreshCw", "flame": "Flame",
        "clock": "Clock", "user": "User", "shopping-cart": "ShoppingCart",
        "receipt": "Receipt", "package": "Package", "credit-card": "CreditCard",
        "activity": "Activity", "calendar": "Calendar", "line-chart": "LineChart",
        "shopping-bag": "ShoppingBag", "bar-chart-2": "BarChart3",
        "user-check": "UserCheck", "mouse-pointer": "MousePointer",
        "book-open": "BookOpen", "truck": "Truck", "home": "Home",
        "alert-triangle": "AlertTriangle", "percent": "Percent",
    }
    return mapping.get(icon or "", "BarChart3")

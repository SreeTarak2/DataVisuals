# backend/api/insights.py

"""
Dedicated Insights API
======================
Comprehensive endpoint for the Insights page — goes far beyond the simple
dashboard InsightsBar. Returns structured, human-readable insights with:

1. Executive Summary — plain-English overview
2. Key Findings — statistically validated, ranked by impact
3. Anomalies & Outliers — with contextual explanations
4. Correlation Map — relationships between variables
5. Trend Analysis — temporal patterns
6. Data Quality Health — completeness, consistency, uniqueness
7. Actionable Recommendations — what the user should do next
8. Segment Analysis — how patterns differ across groups
"""

import logging
import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import polars as pl
import numpy as np

from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from services.analysis.analysis_service import analysis_service
from services.analysis.insight_interpreter import insight_interpreter
from services.analysis.advanced_stats import feature_analyzer
from services.llm_router import llm_router
from services.dashboard_cache_service import dashboard_cache_service
from core.prompt_templates import get_narrative_insights_prompt
from db.database import get_database
from bson import ObjectId
import json as json_mod

logger = logging.getLogger(__name__)
router = APIRouter()


# ────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────

def _severity(p_value: Optional[float], effect: Optional[float] = None) -> str:
    """Classify finding severity for user-facing display."""
    if p_value is None:
        return "info"
    if p_value < 0.001 and (effect or 0) > 0.5:
        return "critical"
    if p_value < 0.01:
        return "high"
    if p_value < 0.05:
        return "medium"
    return "low"


def _impact_label(severity: str) -> str:
    return {
        "critical": "High Impact",
        "high": "Significant",
        "medium": "Moderate",
        "low": "Minor",
        "info": "Informational",
    }.get(severity, "Informational")


def _plain_english_correlation(r: float, col1: str, col2: str) -> str:
    """Turn a correlation coefficient into a sentence anyone can understand."""
    direction = "increases" if r > 0 else "decreases"
    abs_r = abs(r)
    if abs_r >= 0.8:
        strength = "very strongly"
    elif abs_r >= 0.6:
        strength = "strongly"
    elif abs_r >= 0.4:
        strength = "moderately"
    else:
        strength = "slightly"
    return f"When **{col1}** goes up, **{col2}** {strength} {direction}."


def _plain_english_outlier(col: str, count: int, pct: float, method: str) -> str:
    if pct > 5:
        concern = "This is unusually high and may indicate data quality issues or important edge cases worth investigating."
    elif pct > 2:
        concern = "Some of these may represent genuine unusual events or data entry errors."
    else:
        concern = "This is within normal range — your data looks clean here."
    return f"Found **{count} unusual values** ({pct:.1f}%) in **{col}**. {concern}"


def _build_data_quality(df: pl.DataFrame) -> Dict[str, Any]:
    """Build comprehensive data quality metrics."""
    total_rows = len(df)
    total_cols = len(df.columns)
    total_cells = total_rows * total_cols

    # Missing values
    missing_by_col = []
    total_missing = 0
    for col in df.columns:
        missing = df[col].null_count()
        total_missing += missing
        if missing > 0:
            missing_by_col.append({
                "column": col,
                "missing_count": int(missing),
                "missing_pct": round(missing / total_rows * 100, 1),
            })
    missing_by_col.sort(key=lambda x: x["missing_pct"], reverse=True)

    # Duplicates
    dup_count = int(df.is_duplicated().sum())

    # Completeness score
    completeness = round((1 - total_missing / total_cells) * 100, 1) if total_cells > 0 else 100

    # Uniqueness (ratio of unique rows)
    uniqueness = round((1 - dup_count / total_rows) * 100, 1) if total_rows > 0 else 100

    # Overall health score
    health_score = round((completeness * 0.5 + uniqueness * 0.3 + min(100, (total_rows / 100) * 100) * 0.2), 1)
    health_score = min(health_score, 100)

    if health_score >= 90:
        health_label = "Excellent"
        health_color = "emerald"
    elif health_score >= 75:
        health_label = "Good"
        health_color = "blue"
    elif health_score >= 60:
        health_label = "Fair"
        health_color = "amber"
    else:
        health_label = "Needs Attention"
        health_color = "red"

    return {
        "health_score": health_score,
        "health_label": health_label,
        "health_color": health_color,
        "completeness": completeness,
        "uniqueness": uniqueness,
        "total_rows": total_rows,
        "total_columns": total_cols,
        "total_missing_cells": total_missing,
        "duplicate_rows": dup_count,
        "missing_columns": missing_by_col[:10],
        "tips": _quality_tips(completeness, uniqueness, dup_count, missing_by_col),
    }


def _quality_tips(completeness: float, uniqueness: float, dups: int, missing: list) -> List[str]:
    tips = []
    if completeness < 95 and missing:
        worst = missing[0]
        tips.append(f"Column **{worst['column']}** is missing {worst['missing_pct']}% of values — consider imputation or removal.")
    if dups > 0:
        tips.append(f"Found **{dups}** duplicate rows — review if these are valid or should be deduplicated.")
    if completeness >= 98 and uniqueness >= 99:
        tips.append("Your data quality is excellent! No major issues detected.")
    return tips


def _evidence_tier(p_value: Optional[float], effect: Optional[float] = None) -> str:
    """
    Traffic-light evidence tier combining p-value strength with effect magnitude.
    Returns 'strong' (green), 'moderate' (yellow), or 'weak' (red).
    """
    if p_value is None:
        return "weak"
    abs_effect = abs(effect) if effect is not None else 0
    # Strong: highly significant AND meaningful effect
    if p_value < 0.01 and abs_effect >= 0.3:
        return "strong"
    # Moderate: significant OR decent effect
    if p_value < 0.05 or abs_effect >= 0.5:
        return "moderate"
    return "weak"


def _compute_segments_fallback(df: pl.DataFrame, max_segments: int = 10) -> List[Dict[str, Any]]:
    """
    On-the-fly segment analysis when pre-computed deep_insights
    don't contain category_specific patterns. For each cat×num combo,
    compute group means and flag groups with |deviation| > 1.5σ.
    """
    segments = []
    categorical_cols = [c for c in df.columns if df[c].dtype in (pl.Utf8, pl.Categorical)]
    numeric_cols = df.select(pl.col(pl.NUMERIC_DTYPES)).columns

    for cat_col in categorical_cols[:4]:
        unique_vals = df[cat_col].drop_nulls().unique().to_list()
        if len(unique_vals) < 2 or len(unique_vals) > 20:
            continue
        for num_col in numeric_cols[:4]:
            try:
                overall_mean = float(df[num_col].mean())
                overall_std = float(df[num_col].std())
                if overall_std == 0 or overall_std is None:
                    continue

                for val in unique_vals[:8]:
                    sub = df.filter(pl.col(cat_col) == val)
                    if len(sub) < 5:
                        continue
                    sub_mean = float(sub[num_col].mean())
                    deviation = abs(sub_mean - overall_mean) / overall_std

                    if deviation >= 1.5:
                        direction = "higher" if sub_mean > overall_mean else "lower"
                        segments.append({
                            "column": num_col,
                            "segment_value": str(val),
                            "segment": f"{cat_col} = {val}",
                            "metric": num_col,
                            "mean_value": round(sub_mean, 2),
                            "overall_mean": round(overall_mean, 2),
                            "deviation": round(deviation, 2),
                            "direction": direction,
                            "count": len(sub),
                            "percentage": round(len(sub) / len(df) * 100, 1),
                            "plain_english": f"When **{cat_col}** is **{val}**, the average **{num_col}** is {direction} than usual ({sub_mean:.2f} vs {overall_mean:.2f} overall, {deviation:.1f}σ deviation).",
                            "severity": "high" if deviation > 2 else "medium",
                        })
            except Exception:
                continue

    segments.sort(key=lambda x: x["deviation"], reverse=True)
    return segments[:max_segments]


def _compute_drivers(df: pl.DataFrame, max_drivers: int = 8) -> List[Dict[str, Any]]:
    """
    Compute feature importance (driver analysis) using Mutual Information
    from FeatureAnalyzer. For each numeric target, find which other columns
    drive it the most.
    """
    drivers = []
    numeric_cols = df.select(pl.col(pl.NUMERIC_DTYPES)).columns
    if len(numeric_cols) < 2:
        return drivers

    # Pick the top-variance columns as targets (max 3)
    variances = []
    for col in numeric_cols:
        try:
            v = float(df[col].var())
            if v and not math.isnan(v):
                variances.append((col, v))
        except Exception:
            continue
    variances.sort(key=lambda x: x[1], reverse=True)
    target_cols = [v[0] for v in variances[:3]]

    for target_col in target_cols:
        feature_cols = [c for c in numeric_cols if c != target_col]
        if len(feature_cols) < 1:
            continue
        try:
            X = df.select(feature_cols).to_numpy()
            y = df[target_col].to_numpy()
            # Clean NaNs
            mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
            if mask.sum() < 20:
                continue

            mi_scores = feature_analyzer.calculate_mutual_information(
                X[mask], y[mask], feature_cols, is_classification=False
            )

            # Sort and pick top drivers
            sorted_mi = sorted(mi_scores.items(), key=lambda x: x[1], reverse=True)
            top = [d for d in sorted_mi if d[1] > 0.01][:5]
            if not top:
                continue

            # Plain English
            top_name = top[0][0]
            second = f" followed by **{top[1][0]}**" if len(top) > 1 else ""
            plain = f"**{top_name}** is the strongest driver of **{target_col}** (MI={top[0][1]:.3f}){second}."

            drivers.append({
                "target": target_col,
                "drivers": [{"column": name, "importance": round(score, 4)} for name, score in top],
                "method": "mutual_information",
                "plain_english": plain,
            })
        except Exception as e:
            logger.debug(f"Driver analysis failed for {target_col}: {e}")
            continue

    return drivers[:max_drivers]


# ────────────────────────────────────────────────────────────
#  NARRATIVE INTELLIGENCE (LLM layer)
# ────────────────────────────────────────────────────────────

def _build_fact_sheet(
    data_quality: dict,
    correlations: list,
    anomalies: list,
    distributions: list,
    key_findings: list,
    trends: list,
    segments: list,
    driver_analysis: list,
    recommendations: list,
) -> str:
    """
    Condense all statistical outputs into a compact text Fact Sheet
    that fits within an LLM context window. No raw data — just metadata.
    """
    lines = []

    # Data Quality
    lines.append(f"DATA QUALITY: {data_quality['total_rows']:,} rows × {data_quality['total_columns']} columns | "
                 f"Health: {data_quality['health_score']}/100 ({data_quality['health_label']}) | "
                 f"Completeness: {data_quality['completeness']}% | Uniqueness: {data_quality['uniqueness']}% | "
                 f"Missing cells: {data_quality['total_missing_cells']:,} | Duplicate rows: {data_quality['duplicate_rows']}")
    if data_quality.get('missing_columns'):
        worst = data_quality['missing_columns'][:3]
        lines.append("Worst missing columns: " + ", ".join(
            f"{m['column']} ({m['missing_pct']}% missing)" for m in worst
        ))

    # Correlations
    lines.append(f"\nCORRELATIONS ({len(correlations)} found):")
    if correlations:
        for c in correlations[:8]:
            lines.append(f"  - {c['column1']} ↔ {c['column2']}: r={c['value']}, {c['strength']} {c['direction']} "
                         f"(explains {c['variance_explained']} of variance)")
    else:
        lines.append("  No notable linear relationships found (threshold r≥0.25).")

    # Anomalies
    lines.append(f"\nANOMALIES ({len(anomalies)} columns with outliers):")
    if anomalies:
        for a in anomalies[:6]:
            lines.append(f"  - {a['column']}: {a['count']} outliers ({a['percentage']}%), severity={a['severity']}")
    else:
        lines.append("  No significant outliers detected.")

    # Key Findings
    lines.append(f"\nKEY FINDINGS ({len(key_findings)} total):")
    if key_findings:
        for f in key_findings[:8]:
            ev = f.get('evidence', {})
            p_str = f"p={ev.get('p_value', 'N/A')}" if ev.get('p_value') is not None else ""
            eff_str = f"effect={ev.get('effect_size', '')} ({ev.get('effect_interpretation', '')})" if ev.get('effect_size') is not None else ""
            lines.append(f"  [{f['id']}] ({f['severity']}) {f['description']} {p_str} {eff_str}".strip())
    else:
        lines.append("  No statistically significant findings surfaced.")

    # Trends
    lines.append(f"\nTRENDS ({len(trends)} detected):")
    if trends:
        for t in trends[:5]:
            sig = "significant" if t['is_significant'] else "not significant"
            lines.append(f"  - {t['column']}: {t['direction']} (strength={t['strength']}, {sig})")
    else:
        lines.append("  No temporal trends detected (data may lack time dimension).")

    # Segments
    lines.append(f"\nSEGMENTS ({len(segments)} notable):")
    if segments:
        for s in segments[:5]:
            lines.append(f"  - {s['segment']}: {s['metric']} is {s['direction']} "
                         f"({s['mean_value']} vs {s['overall_mean']} overall, {s['deviation']}σ)")
    else:
        lines.append("  No notable segment differences found.")

    # Drivers
    lines.append(f"\nDRIVERS ({len(driver_analysis)} targets analyzed):")
    if driver_analysis:
        for d in driver_analysis[:4]:
            top_drivers = ", ".join(f"{dr['column']}(MI={dr['importance']})" for dr in d['drivers'][:3])
            lines.append(f"  - What drives {d['target']}? → {top_drivers}")
    else:
        lines.append("  Insufficient numeric columns for driver analysis.")

    # Recommendations
    lines.append(f"\nRECOMMENDATIONS ({len(recommendations)} actions):")
    for r in recommendations[:6]:
        lines.append(f"  [{r.get('id', '')}] (urgency={r.get('urgency_score', 0)}) {r['title']}: {r['description']}")

    return "\n".join(lines)


async def _generate_narrative_intelligence(
    fact_sheet: str,
    dataset_name: str,
    domain: str,
    key_findings: list,
    recommendations: list,
) -> dict:
    """
    Call the LLM with the statistical Fact Sheet to generate:
    - AI narrative executive summary
    - Per-finding plain-English rewrites
    - Per-recommendation action plan narratives
    - Story headline + data personality

    Returns a dict with the AI-generated narratives, or empty dict on failure.
    """
    try:
        prompt = get_narrative_insights_prompt(fact_sheet, dataset_name, domain)

        result = await llm_router.call(
            prompt=prompt,
            model_role="narrative_insights",
            expect_json=True,
            temperature=0.5,
            max_tokens=3000,
        )

        if isinstance(result, dict):
            logger.info(f"✓ Narrative intelligence generated: "
                        f"summary={len(result.get('executive_summary', ''))} chars, "
                        f"findings={len(result.get('finding_narratives', []))}, "
                        f"actions={len(result.get('action_plan_narratives', []))}")
            return result

        # If result is a string, try to parse it
        if isinstance(result, str):
            parsed = json_mod.loads(result)
            return parsed

        return {}

    except Exception as e:
        logger.warning(f"Narrative intelligence generation failed (falling back to templates): {e}")
        return {}


def _apply_narratives(
    narrative: dict,
    exec_summary: str,
    key_findings: list,
    recommendations: list,
) -> tuple:
    """
    Overlay AI-generated narratives onto the statistical results.
    Falls back gracefully to template text for any missing pieces.

    Returns (updated_exec_summary, updated_findings, updated_recommendations, headline, personality)
    """
    # Executive Summary
    ai_summary = narrative.get("executive_summary", "").strip()
    if ai_summary and len(ai_summary) > 50:
        exec_summary = ai_summary

    # Story headline & data personality
    headline = narrative.get("story_headline", "")
    personality = narrative.get("data_personality", "")

    # Per-finding narratives
    finding_map = {}
    for fn in narrative.get("finding_narratives", []):
        fid = fn.get("id", "")
        if fid and fn.get("narrative"):
            finding_map[fid] = fn["narrative"]

    for f in key_findings:
        fid = f.get("id", "")
        if fid in finding_map:
            f["plain_english"] = finding_map[fid]
            f["ai_narrated"] = True

    # Per-recommendation narratives
    rec_map = {}
    for rn in narrative.get("action_plan_narratives", []):
        rid = rn.get("id", "")
        if rid and rn.get("narrative"):
            rec_map[rid] = rn["narrative"]

    for r in recommendations:
        rid = r.get("id", "")
        if rid in rec_map:
            r["description"] = rec_map[rid]
            r["ai_narrated"] = True

    return exec_summary, key_findings, recommendations, headline, personality


# ────────────────────────────────────────────────────────────
#  MAIN ENDPOINT
# ────────────────────────────────────────────────────────────

@router.get("/{dataset_id}")
async def get_comprehensive_insights(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
    force_refresh: bool = Query(False),
    filters: Optional[str] = Query(None, description="Filter subsets, e.g. 'column1:value1,column2:value2'"),
):
    """
    Returns the full insights payload for the dedicated Insights page.
    Combines pre-computed deep_analysis (from upload pipeline) with
    on-the-fly calculations for data quality and actionable recommendations.

    Optional ?filters= param lets users re-run analysis on filtered subsets.
    Format: column:value,column2:value2
    """
    try:
        user_id = current_user["id"]
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        metadata = dataset.get("metadata", {})
        df = await enhanced_dataset_service.load_dataset_data(dataset_id, user_id)

        # ── Apply subset filters if provided ──
        applied_filters = {}
        is_filtered = False
        if filters:
            try:
                for pair in filters.split(","):
                    pair = pair.strip()
                    if ":" in pair:
                        col, val = pair.split(":", 1)
                        col, val = col.strip(), val.strip()
                        if col in df.columns:
                            df = df.filter(pl.col(col).cast(pl.Utf8) == val)
                            applied_filters[col] = val
                if applied_filters:
                    is_filtered = True
                    logger.info(f"Insights filtered: {applied_filters}, {len(df)} rows remain")
            except Exception as e:
                logger.warning(f"Filter parsing failed: {e}")

        deep_analysis = metadata.get("deep_analysis", {})
        domain_intel = metadata.get("domain_intelligence", {})
        data_profile = metadata.get("data_profile", {})
        overview = metadata.get("dataset_overview", {})

        # When filtered, skip pre-computed results — everything runs fresh
        if is_filtered:
            deep_analysis = {}

        # ── 1. Data Quality ──
        data_quality = _build_data_quality(df)

        # ── 2. Correlations (human-readable) ──
        correlations = []
        enhanced = deep_analysis.get("enhanced_analysis", {})
        raw_corrs = enhanced.get("correlations", [])

        if not raw_corrs:
            # Fallback: compute correlations on the fly
            raw_corrs = analysis_service.find_correlations_comprehensive(df, threshold=0.3)

        for corr in raw_corrs:
            r = corr.get("correlation", 0)
            col1 = corr.get("column1", "?")
            col2 = corr.get("column2", "?")
            p = corr.get("p_value")
            ci = corr.get("confidence_interval")
            method = corr.get("method", "pearson")

            abs_r = abs(r)
            if abs_r < 0.25:
                continue  # Skip weak correlations

            if abs_r >= 0.7:
                strength = "Strong"
            elif abs_r >= 0.4:
                strength = "Moderate"
            else:
                strength = "Weak"

            correlations.append({
                "column1": col1,
                "column2": col2,
                "value": round(r, 3),
                "abs_value": round(abs_r, 3),
                "strength": strength,
                "direction": "positive" if r > 0 else "negative",
                "method": method,
                "p_value": round(p, 5) if p is not None else None,
                "confidence_interval": [round(x, 3) for x in ci] if ci else None,
                "severity": _severity(p, abs_r),
                "plain_english": _plain_english_correlation(r, col1, col2),
                "variance_explained": f"{abs_r**2 * 100:.1f}%",
            })

        correlations.sort(key=lambda x: x["abs_value"], reverse=True)

        # ── 3. Anomalies & Outliers ──
        anomalies = []
        raw_outliers = enhanced.get("outliers_iqr", []) or analysis_service.detect_outliers_iqr(df)

        for out in raw_outliers:
            col = out.get("column", "?")
            count = out.get("count", out.get("outlier_count", 0))
            pct = out.get("percentage", out.get("outlier_percentage", 0))
            method = out.get("method", "IQR")
            anomalies.append({
                "column": col,
                "count": count,
                "percentage": round(pct, 1),
                "method": method,
                "severity": "high" if pct > 5 else "medium" if pct > 2 else "low",
                "plain_english": _plain_english_outlier(col, count, pct, method),
            })

        anomalies.sort(key=lambda x: x["percentage"], reverse=True)

        # ── 4. Distribution Insights ──
        distributions = []
        raw_dists = enhanced.get("distributions", [])
        if not raw_dists:
            raw_dists = analysis_service.analyze_distribution(df)

        for dist in raw_dists:
            col = dist.get("column", "?")
            skew = dist.get("skewness", 0)
            kurt = dist.get("kurtosis", dist.get("excess_kurtosis", 0))
            dist_type = dist.get("distribution_type", "unknown")
            is_normal = dist.get("is_normal", True)
            norm_p = dist.get("normality_p_value")

            if abs(skew) < 0.3 and abs(kurt) < 1:
                continue  # Skip boring distributions

            # Plain English
            if abs(skew) > 1.5:
                skew_desc = f"**{col}** is heavily {'right' if skew > 0 else 'left'}-skewed — most values are {'low' if skew > 0 else 'high'} with a long tail of {'high' if skew > 0 else 'low'} values."
            elif abs(skew) > 0.5:
                skew_desc = f"**{col}** leans {'right' if skew > 0 else 'left'} — slightly more {'low' if skew > 0 else 'high'} values than expected."
            else:
                skew_desc = f"**{col}** has an unusual shape (kurtosis={kurt:.1f})."

            distributions.append({
                "column": col,
                "distribution_type": dist_type,
                "skewness": round(skew, 2),
                "kurtosis": round(kurt, 2),
                "is_normal": is_normal,
                "normality_p_value": round(norm_p, 4) if norm_p is not None else None,
                "plain_english": skew_desc,
                "severity": "high" if abs(skew) > 2 else "medium" if abs(skew) > 1 else "low",
            })

        # ── 5. QUIS Deep Insights (key findings) ──
        key_findings = []
        quis = deep_analysis.get("quis_insights", {})
        top_insights = quis.get("top_insights", [])

        if not top_insights:
            # Fallback: run basic QUIS
            try:
                quis_result = analysis_service.run_quis_analysis(df, dataset_id=dataset_id)
                for finding in quis_result.get("deep_insights", [])[:8]:
                    f_type = finding.get("type", "pattern")
                    subspace = finding.get("subspace", {})
                    sub_corr = finding.get("subspace_correlation", 0)
                    improvement = finding.get("improvement", 0)

                    subspace_desc = " AND ".join([f"{k}={v}" for k, v in subspace.items()])
                    desc = f"When filtering to **{subspace_desc}**, the pattern becomes {improvement:.0%} stronger (correlation: {sub_corr:.2f})."

                    key_findings.append({
                        "id": f"quis_{len(key_findings)}",
                        "type": f_type.replace("_", " ").title(),
                        "title": f"Hidden Pattern in {subspace_desc}",
                        "description": desc,
                        "severity": "high" if improvement > 0.3 else "medium",
                        "impact": _impact_label("high" if improvement > 0.3 else "medium"),
                        "plain_english": desc,
                        "evidence": {
                            "subspace": subspace,
                            "correlation": sub_corr,
                            "improvement": improvement,
                        },
                        "category": "hidden_pattern",
                    })
            except Exception as e:
                logger.warning(f"QUIS fallback failed: {e}")

        for i, finding in enumerate(top_insights[:10]):
            f_type = finding.get("insight_type", "pattern")
            desc = finding.get("description", "")
            p_val = finding.get("p_value")
            effect = finding.get("effect_size")
            effect_interp = finding.get("effect_interpretation", "")
            ci = finding.get("confidence_interval")
            is_simpson = finding.get("is_simpson_paradox", False)

            sev = _severity(p_val, effect)

            # Build plain English explanation
            if is_simpson:
                plain = f"⚠️ **Simpson's Paradox detected**: {desc}. The overall trend reverses when you look at subgroups — this is a critical finding that could lead to wrong decisions."
            elif f_type == "correlation":
                plain = desc
            elif f_type == "comparison":
                plain = f"A significant difference was found: {desc}"
            else:
                plain = desc

            # Evidence block
            evidence = {}
            if p_val is not None:
                evidence["p_value"] = round(p_val, 5)
            if effect is not None:
                evidence["effect_size"] = round(effect, 3)
                evidence["effect_interpretation"] = effect_interp
            if ci:
                evidence["confidence_interval"] = [round(x, 3) for x in ci]

            key_findings.append({
                "id": f"finding_{i}",
                "type": f_type.replace("_", " ").title(),
                "title": f_type.replace("_", " ").title(),
                "description": desc,
                "severity": sev,
                "impact": _impact_label(sev),
                "plain_english": plain,
                "evidence": evidence,
                "evidence_tier": _evidence_tier(p_val, effect),
                "category": "simpson_paradox" if is_simpson else f_type,
                "is_simpson_paradox": is_simpson,
            })

        # ── 6. Trend Analysis ──
        trends = []
        ts_data = enhanced.get("time_series", {}) or deep_analysis.get("time_series", {})
        if isinstance(ts_data, dict):
            for col_name, ts_result in ts_data.items():
                if not isinstance(ts_result, dict):
                    continue
                trend_info = ts_result.get("trend_analysis", {})
                trend_dir = trend_info.get("trend", "no_trend")
                tau = trend_info.get("tau", 0)
                p_val = trend_info.get("p_value", 1)
                is_sig = trend_info.get("is_significant", False)

                acf = ts_result.get("autocorrelation", {})
                sig_lags = acf.get("significant_lags", [])

                if trend_dir == "no_trend" and not sig_lags:
                    continue

                if trend_dir != "no_trend":
                    direction = "upward 📈" if trend_dir == "increasing" else "downward 📉"
                    plain = f"**{col_name}** shows a {direction} trend over time"
                    if is_sig:
                        plain += f" (statistically significant, p={p_val:.4f})."
                    else:
                        plain += " (though not yet statistically significant)."
                else:
                    plain = f"**{col_name}** has no clear trend, but shows periodic patterns at lags {sig_lags[:3]}."

                seasonality = None
                if 12 in sig_lags or 24 in sig_lags:
                    seasonality = "monthly"
                elif 7 in sig_lags or 14 in sig_lags:
                    seasonality = "weekly"
                elif 4 in sig_lags or 13 in sig_lags:
                    seasonality = "quarterly"

                trends.append({
                    "column": col_name,
                    "direction": trend_dir,
                    "strength": round(abs(tau), 3),
                    "p_value": round(p_val, 5),
                    "is_significant": is_sig,
                    "seasonality": seasonality,
                    "significant_lags": sig_lags[:5],
                    "plain_english": plain,
                })

        # ── 7. Segment Analysis (with fallback) ──
        segments = []
        deep_insights_list = deep_analysis.get("deep_insights", []) or []
        for finding in deep_insights_list:
            f_type = finding.get("type", "")
            if "category_specific" in f_type:
                cat_col = finding.get("category_column", "?")
                cat_val = finding.get("category_value", "?")
                num_col = finding.get("numeric_column", "?")
                overall_mean = finding.get("overall_mean", 0)
                sub_mean = finding.get("subspace_mean", 0)
                deviation = finding.get("deviation", 0)

                if deviation > 0:
                    direction = "higher" if sub_mean > overall_mean else "lower"
                    segments.append({
                        "column": num_col,
                        "segment_value": str(cat_val),
                        "segment": f"{cat_col} = {cat_val}",
                        "metric": num_col,
                        "mean_value": round(sub_mean, 2),
                        "overall_mean": round(overall_mean, 2),
                        "deviation": round(deviation, 2),
                        "direction": direction,
                        "count": finding.get("subspace_size", 0),
                        "percentage": 0,
                        "plain_english": f"When **{cat_col}** is **{cat_val}**, the average **{num_col}** is {direction} than usual ({sub_mean:.2f} vs {overall_mean:.2f} overall, {deviation:.1f}σ deviation).",
                        "severity": "high" if deviation > 2 else "medium",
                    })

        # Fallback: if no pre-computed segments, compute on-the-fly
        if not segments:
            segments = _compute_segments_fallback(df)

        segments.sort(key=lambda x: x["deviation"], reverse=True)

        # ── 7b. Driver Analysis (feature importance) ──
        driver_analysis = []
        try:
            driver_analysis = _compute_drivers(df)
        except Exception as e:
            logger.debug(f"Driver analysis skipped: {e}")

        # ── 8. Executive Summary ──
        exec_summary = deep_analysis.get("executive_summary", "")
        if not exec_summary:
            # Build one from what we have
            parts = []
            parts.append(f"Your dataset has **{data_quality['total_rows']:,} rows** and **{data_quality['total_columns']} columns**.")

            if data_quality["health_score"] >= 90:
                parts.append("Data quality is **excellent**.")
            elif data_quality["health_score"] >= 75:
                parts.append("Data quality is **good** with minor issues.")
            else:
                parts.append(f"Data quality needs attention — completeness is **{data_quality['completeness']}%**.")

            if correlations:
                strong = [c for c in correlations if c["abs_value"] >= 0.6]
                if strong:
                    parts.append(f"Found **{len(strong)} strong relationship{'s' if len(strong) != 1 else ''}** between variables.")

            if anomalies:
                parts.append(f"Detected unusual values in **{len(anomalies)} column{'s' if len(anomalies) != 1 else ''}**.")

            if key_findings:
                critical = [f for f in key_findings if f["severity"] in ("critical", "high")]
                if critical:
                    parts.append(f"⚡ **{len(critical)} high-impact finding{'s' if len(critical) != 1 else ''}** require attention.")

            if trends:
                sig_trends = [t for t in trends if t["is_significant"]]
                if sig_trends:
                    parts.append(f"Detected significant trends in **{len(sig_trends)} variable{'s' if len(sig_trends) != 1 else ''}**.")

            exec_summary = " ".join(parts)

        # ── 9. Actionable Recommendations (adaptive scoring) ──
        recommendations = _generate_recommendations(
            correlations, anomalies, distributions, key_findings, data_quality, trends, segments
        )

        # ── 10. Persist QUIS cache to metadata (survives restarts) ──
        if not is_filtered and not deep_analysis.get("quis_insights") and key_findings:
            try:
                db = get_database()
                if db:
                    try:
                        query = {"_id": ObjectId(dataset_id)}
                    except Exception:
                        query = {"_id": dataset_id}
                    await db.datasets.update_one(
                        query,
                        {"$set": {"metadata.deep_analysis.quis_insights.top_insights": [
                            {"insight_type": f.get("type", ""), "description": f.get("description", ""),
                             "p_value": f.get("evidence", {}).get("p_value"),
                             "effect_size": f.get("evidence", {}).get("effect_size"),
                             "effect_interpretation": f.get("evidence", {}).get("effect_interpretation", ""),
                             "confidence_interval": f.get("evidence", {}).get("confidence_interval"),
                             "is_simpson_paradox": f.get("is_simpson_paradox", False)}
                            for f in key_findings
                        ]}}
                    )
                    logger.info(f"Persisted {len(key_findings)} QUIS insights to metadata for {dataset_id}")
            except Exception as e:
                logger.warning(f"Failed to persist QUIS cache: {e}")

        # ── 11. NARRATIVE INTELLIGENCE (LLM) ──
        domain = domain_intel.get("domain", overview.get("domain", "general"))
        story_headline = ""
        data_personality = ""

        try:
            fact_sheet = _build_fact_sheet(
                data_quality, correlations, anomalies, distributions,
                key_findings, trends, segments, driver_analysis, recommendations
            )
            narrative = await _generate_narrative_intelligence(
                fact_sheet=fact_sheet,
                dataset_name=dataset.get("name", "Unknown"),
                domain=domain,
                key_findings=key_findings,
                recommendations=recommendations,
            )
            if narrative:
                exec_summary, key_findings, recommendations, story_headline, data_personality = \
                    _apply_narratives(narrative, exec_summary, key_findings, recommendations)
                logger.info(f"✓ Narrative intelligence applied to insights for {dataset_id}")
        except Exception as e:
            logger.warning(f"Narrative intelligence failed, using template fallback: {e}")

        # ── Build Response ──

        response = {
            "dataset_id": dataset_id,
            "dataset_name": dataset.get("name", "Unknown"),
            "domain": domain,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "executive_summary": exec_summary,
            "story_headline": story_headline,
            "data_personality": data_personality,
            "ai_narrated": bool(story_headline),
            "data_quality": data_quality,
            "key_findings": key_findings[:12],
            "correlations": correlations[:15],
            "anomalies": anomalies[:10],
            "distributions": distributions[:10],
            "trends": trends[:8],
            "segments": segments[:10],
            "recommendations": recommendations,
            "driver_analysis": driver_analysis[:8],
            "counts": {
                "key_findings": len(key_findings),
                "correlations": len(correlations),
                "anomalies": len(anomalies),
                "distributions": len(distributions),
                "trends": len(trends),
                "segments": len(segments),
                "drivers": len(driver_analysis),
            },
        }

        # Include filter info if subset was applied
        if is_filtered:
            response["applied_filters"] = applied_filters
            response["filtered_row_count"] = len(df)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating comprehensive insights for {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate insights.")


def _generate_recommendations(
    correlations: list,
    anomalies: list,
    distributions: list,
    key_findings: list,
    data_quality: dict,
    trends: list,
    segments: list,
) -> List[Dict[str, Any]]:
    """
    Generate actionable recommendations scored by MAGNITUDE, not fixed order.
    Each candidate rec gets a urgency_score (0-100), then sorted descending.
    """
    candidates = []  # list of (urgency_score, rec_dict)

    # ── Simpson's Paradox — always top-tier ──
    simpsons = [f for f in key_findings if f.get("is_simpson_paradox")]
    if simpsons:
        candidates.append((99, {
            "category": "critical",
            "icon": "alert-triangle",
            "title": "⚠️ Simpson's Paradox Detected",
            "description": "A trend reversal was found when data is segmented. **Do not make decisions based on the overall trend alone** — the subgroup behavior tells a different story.",
            "action_type": "critical",
        }))

    # ── Missing data — scored by how bad the worst column is ──
    if data_quality["completeness"] < 95:
        worst_missing = data_quality["missing_columns"][0] if data_quality["missing_columns"] else None
        if worst_missing:
            missing_pct = worst_missing["missing_pct"]
            # 50% missing = score 90, 10% missing = score 50, 2% missing = score 30
            score = min(95, 30 + missing_pct * 1.3)
            candidates.append((score, {
                "category": "data_quality",
                "icon": "shield",
                "title": "Fix Missing Data",
                "description": f"Column **{worst_missing['column']}** is missing {missing_pct}% of values. Consider imputation (fill with median/mode) or investigate why data is missing.",
                "action_type": "investigate",
            }))

    # ── Duplicates — scored by count ──
    if data_quality["duplicate_rows"] > 0:
        dup_pct = data_quality["duplicate_rows"] / max(data_quality["total_rows"], 1) * 100
        score = min(85, 25 + dup_pct * 2)
        candidates.append((score, {
            "category": "data_quality",
            "icon": "copy",
            "title": "Review Duplicate Rows",
            "description": f"Found **{data_quality['duplicate_rows']}** duplicate rows ({dup_pct:.1f}%). Verify if these are valid entries or data collection errors.",
            "action_type": "investigate",
        }))

    # ── High anomalies — scored by percentage ──
    high_anomalies = [a for a in anomalies if a["severity"] == "high"]
    if high_anomalies:
        worst = high_anomalies[0]
        score = min(90, 40 + worst["percentage"] * 3)
        candidates.append((score, {
            "category": "anomaly",
            "icon": "alert-circle",
            "title": "Investigate Outliers",
            "description": f"**{worst['column']}** has {worst['percentage']}% unusual values. These could be data errors, fraud, or genuinely interesting edge cases.",
            "action_type": "investigate",
        }))

    # ── Strong correlations — scored by r-value ──
    strong_corrs = [c for c in correlations if c["abs_value"] >= 0.7]
    if strong_corrs:
        top = strong_corrs[0]
        score = 30 + top["abs_value"] * 50  # r=0.7 → 65, r=0.95 → 77.5
        candidates.append((score, {
            "category": "relationship",
            "icon": "git-branch",
            "title": "Explore Strong Relationships",
            "description": f"**{top['column1']}** and **{top['column2']}** are strongly correlated (r={top['value']:.2f}). Investigate if one drives the other, or if a hidden factor causes both.",
            "action_type": "explore",
        }))

    # ── Skewed distributions — scored by |skewness| ──
    skewed = [d for d in distributions if abs(d["skewness"]) > 1.5]
    if skewed:
        worst_skew = max(skewed, key=lambda d: abs(d["skewness"]))
        score = min(70, 20 + abs(worst_skew["skewness"]) * 12)
        candidates.append((score, {
            "category": "distribution",
            "icon": "bar-chart",
            "title": "Consider Data Transformation",
            "description": f"**{worst_skew['column']}** is heavily skewed (skewness={worst_skew['skewness']:.1f}). A log or square root transformation may improve analysis accuracy.",
            "action_type": "transform",
        }))

    # ── Trends — scored by strength × significance ──
    sig_trends = [t for t in trends if t["is_significant"]]
    if sig_trends:
        t = sig_trends[0]
        score = 35 + t["strength"] * 60  # tau=0.5 → 65, tau=0.8 → 83
        candidates.append((score, {
            "category": "trend",
            "icon": "trending-up",
            "title": f"Monitor {t['column']} Trend",
            "description": f"**{t['column']}** shows a statistically significant {t['direction']} trend. {'Set up alerts if this continues.' if t['direction'] == 'decreasing' else 'Identify what is driving this growth.'}",
            "action_type": "monitor",
        }))

    # ── Segments — scored by deviation magnitude ──
    if segments:
        top_seg = segments[0]
        dev = top_seg.get("deviation", 0)
        score = min(80, 30 + dev * 15)  # 2σ → 60, 3σ → 75
        candidates.append((score, {
            "category": "segment",
            "icon": "layers",
            "title": "Segment-Specific Strategy",
            "description": f"The segment **{top_seg['segment']}** behaves very differently from average ({dev:.1f}σ deviation). Consider segment-specific strategies or deeper investigation.",
            "action_type": "segment",
        }))

    # ── General positive rec if data quality is good ──
    if not candidates or (data_quality["health_score"] >= 90 and len(candidates) <= 2):
        candidates.append((10, {
            "category": "positive",
            "icon": "check-circle",
            "title": "Data Looks Great!",
            "description": "Your dataset is clean and well-structured. Use the AI Chat to ask specific questions or explore deeper patterns.",
            "action_type": "explore",
        }))

    # Sort by urgency score descending, assign final priorities
    candidates.sort(key=lambda x: x[0], reverse=True)
    recs = []
    for i, (score, rec) in enumerate(candidates):
        rec["id"] = f"rec_{i + 1}"
        rec["priority"] = i
        rec["urgency_score"] = round(score, 1)
        recs.append(rec)

    return recs

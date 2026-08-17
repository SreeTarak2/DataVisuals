"""
KPI Merge & Utilities
=====================
Merge helpers (template + auto KPI merging), story attachment,
entity synthetic profile injection, and utility functions.
Extracted from intelligent_kpi_generator.py.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import polars as pl

from .kpi_types import ColumnProfile, ColumnRole

logger = logging.getLogger(__name__)


# ── Merge helpers ─────────────────────────────────────────────────────────────


def _merge_template_and_auto_kpis(
    template_kpis: List[Dict[str, Any]],
    auto_kpis: List[Dict[str, Any]],
    max_kpis: int,
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen_columns: set = set()

    for k in template_kpis:
        col = k.get("column", "")
        if col and col not in seen_columns:
            result.append(k)
            seen_columns.add(col)

    for k in auto_kpis:
        if len(result) >= max_kpis:
            break
        col = k.get("column", "")
        if col and col not in seen_columns:
            result.append(k)
            seen_columns.add(col)

    hero_idx = next((i for i, k in enumerate(result) if k.get("importance") == "hero"), None)
    if hero_idx and hero_idx > 0:
        result.insert(0, result.pop(hero_idx))

    return result


def _attach_story(kpis: List[Dict[str, Any]], story: str, domain: str) -> List[Dict[str, Any]]:
    for k in kpis:
        if k.get("importance") == "hero":
            k["dashboard_story"] = story
            break
    return kpis


# ── Entity synthetic profiles ─────────────────────────────────────────────────


def _inject_entity_synthetic_profiles(
    df: pl.DataFrame,
    profiles: List[ColumnProfile],
    entity_aware_profiles: List['EntityAwareProfile'],
    log: logging.Logger,
) -> int:
    added = 0
    if not entity_aware_profiles:
        return 0
    entity_id_cols = [p for p in entity_aware_profiles if p.is_entity_id]
    if not entity_id_cols:
        return 0
    primary = entity_id_cols[0]
    entity_col = primary.name
    entity_type = primary.entity_type
    if entity_col not in df.columns:
        return 0
    unique_count = float(df[entity_col].n_unique())

    # 1. Entity count
    existing = [p for p in profiles if p.role == ColumnRole.COUNT and entity_type.lower() in p.name.lower()]
    if not existing:
        profiles.append(ColumnProfile(
            name=f"_{entity_type.lower()}_count_synthetic",
            role=ColumnRole.COUNT,
            n_rows=len(df), n_nulls=0, n_unique=int(unique_count),
            col_sum=unique_count, col_mean=unique_count,
            col_median=unique_count, col_min=unique_count, col_max=unique_count,
            cv=0.0, aggregation="sum", polarity="higher_is_better",
            business_category="users",
        ))
        added += 1
        log.info(f"[KPI] Injected synthetic: {entity_type} Count = {int(unique_count)}")

    # 2. Per-entity averages for numeric columns
    attrs = [p for p in entity_aware_profiles if p.is_entity_attribute
             and p.semantic_role in ("measure", "rate") and p.name in df.columns
             and p.entity_column == entity_col][:2]
    for ep in attrs:
        try:
            avg = df.group_by(entity_col).agg(pl.col(ep.name).mean().alias("_v")).get_column("_v").mean()
            if avg is not None:
                col_display = ep.name.replace("_", " ").replace("-", " ").strip().title()
                col_display = re.sub(r'\s*\([^)]*\)', '', col_display).strip()
                profiles.append(ColumnProfile(
                    name=f"_{entity_type.lower()}_avg_{ep.name}_synthetic",
                    role=ColumnRole.MEASURE,
                    n_rows=len(df), n_nulls=0, n_unique=int(unique_count),
                    col_sum=float(avg) * unique_count, col_mean=float(avg),
                    col_median=float(avg), col_min=float(avg), col_max=float(avg),
                    cv=0.0, aggregation="mean", polarity="higher_is_better",
                    business_category="price",
                ))
                added += 1
                log.info(f"[KPI] Injected per-entity avg: Avg {col_display} per {entity_type} = {float(avg):.2f}")
        except Exception as e:
            log.debug(f"[KPI] Per-entity avg failed: {e}")

    if added:
        log.info(f"[KPI] Injected {added} synthetic entity-derived profiles")
    return added


# ── Utility functions ─────────────────────────────────────────────────────────


_AGG_PREFIX = {
    "sum": "Total",
    "mean": "Average",
    "median": "Median",
    "max": "Peak",
    "min": "Lowest",
    "count": "Count of",
}


def _humanize_title(profile: ColumnProfile) -> str:
    name = profile.name.replace("_", " ").replace("-", " ").strip()
    _ABBREV = {
        r"\bnum\b": "Number", r"\bnums\b": "Numbers", r"\bavg\b": "Average",
        r"\bqty\b": "Quantity", r"\bpct\b": "Percent", r"\bcnt\b": "Count",
        r"\bamt\b": "Amount", r"\bmin\b": "Minimum", r"\bmax\b": "Maximum",
        r"\bapprox\b": "Approximate", r"\bconfig\b": "Configuration",
        r"\bdiff\b": "Difference", r"\binfo\b": "Information", r"\breq\b": "Request",
        r"\borig\b": "Original", r"\bsrc\b": "Source", r"\bprod\b": "Product",
        r"\becom\b": "Ecommerce", r"\bdel\b": "Delivery", r"\bcust\b": "Customer",
        r"\bdept\b": "Department", r"\baddr\b": "Address", r"\borganization\b": "Organization",
    }
    for abbr_pattern, replacement in _ABBREV.items():
        name = re.sub(abbr_pattern, replacement, name, flags=re.IGNORECASE)
    name = name.title()
    name = re.sub(r'\s+Synthetic\s*$', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'\s*\([^)]*\)\s*$', '', name).strip()
    name = re.sub(r'\s*\([^)]*\)', '', name).strip()
    name = re.sub(r'\s+', ' ', name).strip()
    prefix = _AGG_PREFIX.get(profile.aggregation, "")
    if prefix:
        if name.lower().startswith(prefix.lower()):
            return name
        return f"{prefix} {name}"
    return name


def _agg_series(series: pl.Series, aggregation: str) -> float:
    clean = series.drop_nulls()
    if len(clean) == 0:
        return 0.0
    if aggregation == "sum":
        return float(clean.sum())
    elif aggregation == "mean":
        return float(clean.mean())
    elif aggregation == "median":
        return float(clean.median())
    elif aggregation == "count":
        return float(len(clean))
    elif aggregation == "max":
        return float(clean.max())
    elif aggregation == "min":
        return float(clean.min())
    else:
        return float(clean.sum())


def _fmt_val(val: Optional[float], fmt: str) -> str:
    if val is None:
        return "N/A"
    if fmt == "currency":
        if abs(val) >= 1e9:
            return f"${val / 1e9:.1f}B"
        if abs(val) >= 1e6:
            return f"${val / 1e6:.1f}M"
        if abs(val) >= 1e3:
            return f"${val / 1e3:.1f}K"
        return f"${val:,.0f}"
    if fmt == "percentage":
        display_val = val * 100 if 0 <= abs(val) < 1 else val
        return f"{display_val:.1f}%"
    if abs(val) >= 1e6:
        return f"{val / 1e6:.1f}M"
    if abs(val) >= 1e3:
        return f"{val / 1e3:.1f}K"
    return f"{val:,.1f}"

"""
KPI Metric Families
===================
Selects and balances KPI families for dashboard design.

Implements the 8 metric families from the ChatGPT Build Dashboard skill:
  Reach, Volume, Value, Quality, Depth, Mix, Movement, Risk

Ensures dashboard KPIs cover all decision-relevant families rather than
clustering on a single category (e.g., 3 revenue KPIs and nothing else).

Usage:
    from .kpi_families import assign_families, format_family_block_for_prompt

    report = assign_families(column_metadata, domain="saas-metrics")
    prompt_block = format_family_block_for_prompt(report)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── MetricFamily Enum ─────────────────────────────────────────────────────────


class MetricFamily(str, Enum):
    """The 8 metric families from the ChatGPT Build Dashboard skill."""

    REACH = "reach"          # Who/what is using it — users, customers, coverage
    VOLUME = "volume"        # How much activity — orders, sessions, transactions
    VALUE = "value"          # How valuable — revenue, margin, LTV, ARPU
    QUALITY = "quality"      # How good — NPS, satisfaction, success rate
    DEPTH = "depth"          # How deep — repeat usage, adoption, stickiness
    MIX = "mix"              # Distribution — segment, geography, channel breakdown
    MOVEMENT = "movement"    # How changing — trend, growth, momentum
    RISK = "risk"            # What could go wrong — churn, defects, outliers


# ── Category → Family Mapping ─────────────────────────────────────────────────

# Maps existing business_category from ColumnProfile to MetricFamily
CATEGORY_TO_FAMILY: Dict[str, MetricFamily] = {
    "revenue":     MetricFamily.VALUE,
    "cost":        MetricFamily.RISK,
    "volume":      MetricFamily.VOLUME,
    "users":       MetricFamily.REACH,
    "rate_metric": MetricFamily.QUALITY,
    "churn_risk":  MetricFamily.RISK,
    "price":       MetricFamily.VALUE,
    "performance": MetricFamily.QUALITY,
    "duration":    MetricFamily.QUALITY,
    "quantity":    MetricFamily.VOLUME,
    "neutral":     MetricFamily.VOLUME,
}

# Column-name patterns for detecting families when business_category is "unknown"
FAMILY_PATTERNS: Dict[MetricFamily, List[str]] = {
    MetricFamily.REACH: [
        r"\b(users|customers|subscribers|members|accounts|clients|visitors|leads|prospects|buyers|audience|coverage|penetration|adoption|signups|registrations|unique|new\s*users|active|total\s*users)\b",
    ],
    MetricFamily.VOLUME: [
        r"\b(orders|transactions|purchases|bookings|units|items|shipments|deliveries|installs|sessions|visits|clicks|impressions|requests|calls|tickets|volume|throughput|load|count|total\s*orders|total\s*sales)\b",
    ],
    MetricFamily.VALUE: [
        r"\b(revenue|sales|gmv|income|earnings|gross|mrr|arr|net_sales|turnover|proceeds|receipts|profit|margin|aov|arpu|arpc|ltv|cac|worth|value|amount|price|average\s*order|deal\s*size|contract\s*value)\b",
    ],
    MetricFamily.QUALITY: [
        r"\b(rate|ratio|percent|pct|margin|conversion|retention|satisfaction|nps|csat|engagement|utilization|score|rating|quality|accuracy|precision|recall|uptime|availability|latency|response_time|duration|efficiency|success|completion|fulfillment)\b",
    ],
    MetricFamily.DEPTH: [
        r"\b(repeat|returning|frequency|intensity|adoption|feature\s*usage|stickiness|dau|mau|wau|daily|weekly|monthly|active|session\s*depth|time\s*spent|engagement\s*depth|per\s*user|per\s*customer|sessions\s*per|actions\s*per)\b",
    ],
    MetricFamily.MIX: [
        r"\b(share|distribution|segment|concentration|split|breakdown|composition|diversity|penetration|by\s*region|by\s*category|by\s*plan|by\s*product|top\s*\d|percentage\s*of|mix|channel|cross\s*section)\b",
    ],
    MetricFamily.MOVEMENT: [
        r"\b(growth|trend|change|delta|increase|decrease|rise|decline|momentum|acceleration|deceleration|rate\s*of\s*change|forecast|projection|vs|comparison|period\s*over\s*period|wow|mom|yoy)\b",
    ],
    MetricFamily.RISK: [
        r"\b(churn|attrition|cancellation|dropout|refund|return|complaint|defect|error|failure|bug|issue|loss|burn|overhead|risk|volatility|uncertainty|outlier|anomaly|chargeback|dispute|penalty|waste)\b",
    ],
}


# ── Domain Priority Families ──────────────────────────────────────────────────

# Each domain lists families in priority order for that domain
DOMAIN_PRIORITIES: Dict[str, List[MetricFamily]] = {
    "saas-metrics": [
        MetricFamily.VALUE, MetricFamily.REACH, MetricFamily.MOVEMENT,
        MetricFamily.RISK, MetricFamily.QUALITY, MetricFamily.VOLUME,
        MetricFamily.MIX, MetricFamily.DEPTH,
    ],
    "ecommerce-metrics": [
        MetricFamily.VALUE, MetricFamily.VOLUME, MetricFamily.MIX,
        MetricFamily.MOVEMENT, MetricFamily.QUALITY, MetricFamily.REACH,
        MetricFamily.DEPTH, MetricFamily.RISK,
    ],
    "finance-metrics": [
        MetricFamily.VALUE, MetricFamily.RISK, MetricFamily.MOVEMENT,
        MetricFamily.QUALITY, MetricFamily.VOLUME, MetricFamily.MIX,
        MetricFamily.REACH, MetricFamily.DEPTH,
    ],
    "healthcare-metrics": [
        MetricFamily.QUALITY, MetricFamily.REACH, MetricFamily.DEPTH,
        MetricFamily.VOLUME, MetricFamily.VALUE, MetricFamily.MOVEMENT,
        MetricFamily.RISK, MetricFamily.MIX,
    ],
    "automotive-metrics": [
        MetricFamily.VALUE, MetricFamily.VOLUME, MetricFamily.QUALITY,
        MetricFamily.MIX, MetricFamily.MOVEMENT, MetricFamily.REACH,
        MetricFamily.DEPTH, MetricFamily.RISK,
    ],
    "real-estate-metrics": [
        MetricFamily.VALUE, MetricFamily.VOLUME, MetricFamily.MIX,
        MetricFamily.MOVEMENT, MetricFamily.QUALITY, MetricFamily.REACH,
        MetricFamily.DEPTH, MetricFamily.RISK,
    ],
    "hr-metrics": [
        MetricFamily.REACH, MetricFamily.VALUE, MetricFamily.DEPTH,
        MetricFamily.QUALITY, MetricFamily.MOVEMENT, MetricFamily.VOLUME,
        MetricFamily.MIX, MetricFamily.RISK,
    ],
    "marketing-metrics": [
        MetricFamily.REACH, MetricFamily.VALUE, MetricFamily.VOLUME,
        MetricFamily.MOVEMENT, MetricFamily.QUALITY, MetricFamily.MIX,
        MetricFamily.DEPTH, MetricFamily.RISK,
    ],
    "education-metrics": [
        MetricFamily.QUALITY, MetricFamily.REACH, MetricFamily.DEPTH,
        MetricFamily.MOVEMENT, MetricFamily.VOLUME, MetricFamily.VALUE,
        MetricFamily.MIX, MetricFamily.RISK,
    ],
    "manufacturing-metrics": [
        MetricFamily.QUALITY, MetricFamily.VOLUME, MetricFamily.RISK,
        MetricFamily.VALUE, MetricFamily.MOVEMENT, MetricFamily.DEPTH,
        MetricFamily.MIX, MetricFamily.REACH,
    ],
    "logistics-metrics": [
        MetricFamily.QUALITY, MetricFamily.VOLUME, MetricFamily.MOVEMENT,
        MetricFamily.VALUE, MetricFamily.RISK, MetricFamily.MIX,
        MetricFamily.DEPTH, MetricFamily.REACH,
    ],
}

# Default priority for unknown domains
_DEFAULT_PRIORITIES: List[MetricFamily] = [
    MetricFamily.VALUE, MetricFamily.VOLUME, MetricFamily.REACH,
    MetricFamily.QUALITY, MetricFamily.MOVEMENT, MetricFamily.MIX,
    MetricFamily.RISK, MetricFamily.DEPTH,
]


# ── Dataclasses ───────────────────────────────────────────────────────────────


@dataclass
class FamilyAssignment:
    """A column tagged with its metric family and representation quality."""
    column_name: str
    column_type: str  # e.g., numeric, categorical
    family: MetricFamily
    aggregation: str = "sum"           # Suggested aggregation for this metric
    is_primary: bool = False           # Best representative of this family
    family_score: float = 0.5          # 0.0-1.0 how well it represents the family
    suggested_title: str = ""          # Human-readable KPI title


@dataclass
class FamilyCoverageReport:
    """Complete family coverage analysis for a dataset."""
    covered_families: Dict[MetricFamily, List[FamilyAssignment]] = field(default_factory=dict)
    missing_families: List[MetricFamily] = field(default_factory=list)
    priority_families: List[MetricFamily] = field(default_factory=list)
    gap_suggestions: List[str] = field(default_factory=list)
    coverage_score: float = 0.0        # 0.0-1.0


# ── Family Detection Helpers ──────────────────────────────────────────────────


def detect_family_from_name(
    col_name: str,
    col_type: str,
    business_category: Optional[str] = None,
) -> Tuple[Optional[MetricFamily], float]:
    """
    Detect which metric family a column belongs to.

    Returns (family, confidence) where confidence is 0.0-1.0.
    """
    # 1. If business_category is known, use direct mapping
    if business_category and business_category in CATEGORY_TO_FAMILY:
        return CATEGORY_TO_FAMILY[business_category], 0.9

    # 2. Detect from column name patterns
    name = col_name.lower().replace("_", " ").replace("-", " ")

    # Special handling for temporal columns
    if col_type in ("datetime", "date", "time", "timestamp"):
        return MetricFamily.MOVEMENT, 0.3  # Time columns are weak MOVEMENT signals

    # Score each family by pattern matches
    scores: Dict[MetricFamily, float] = {}
    for family, patterns in FAMILY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, name, re.I):
                # Longer matches = higher confidence
                match = re.search(pattern, name, re.I)
                if match:
                    match_len = len(match.group())
                    confidence = min(0.5 + match_len * 0.02, 0.95)
                    scores[family] = max(scores.get(family, 0), confidence)

    if scores:
        best = max(scores, key=scores.get)
        return best, scores[best]

    # 3. Fallback based on column type
    if col_type in ("numeric", "integer", "float", "int"):
        return MetricFamily.VOLUME, 0.2
    if col_type in ("categorical", "str", "utf8"):
        return MetricFamily.MIX, 0.1

    return None, 0.0


def _compute_family_score(col_name: str, col_type: str, confidence: float) -> float:
    """
    Compute a family representation score (0.0-1.0) for a column.
    Higher = better KPI for this family.
    """
    score = confidence

    # Numeric columns make better KPIs
    if col_type in ("numeric", "integer", "float", "int"):
        score += 0.2

    # Columns with "total" or "sum" are strong signals
    name_lower = col_name.lower()
    if "total" in name_lower or "sum" in name_lower:
        score += 0.1
    if "average" in name_lower or "avg" in name_lower or "mean" in name_lower:
        score += 0.05

    return min(score, 1.0)


def _generate_title(col_name: str, aggregation: str) -> str:
    """Generate a human-readable KPI title from a column name."""
    title = col_name.replace("_", " ").replace("-", " ").strip().title()
    agg_prefix = {"sum": "Total ", "mean": "Average ", "median": "Median ", "count": "Count of "}
    prefix = agg_prefix.get(aggregation, "")
    if prefix and not title.lower().startswith(prefix.lower().strip()):
        return f"{prefix}{title}"
    if prefix and title.lower().startswith(prefix.lower().strip()):
        return title
    return title


# ── Domain Priority ───────────────────────────────────────────────────────────


def _get_domain_priority_families(domain: Optional[str]) -> List[MetricFamily]:
    """Get the priority-ordered list of metric families for a domain."""
    if domain and domain in DOMAIN_PRIORITIES:
        return DOMAIN_PRIORITIES[domain]
    return _DEFAULT_PRIORITIES


# ── Main Function ─────────────────────────────────────────────────────────────


def assign_families(
    column_metadata: List[Dict[str, Any]],
    domain: Optional[str] = None,
    existing_kpi_columns: Optional[List[str]] = None,
) -> FamilyCoverageReport:
    """
    Assign metric families to dataset columns and produce a coverage report.

    Args:
        column_metadata: List of column dicts with at least "name" and "type" keys.
            Optionally includes "business_category" from the KPI profiler.
        domain: Detected domain (e.g., "saas-metrics", "ecommerce-metrics").
            Used to prioritize families.
        existing_kpi_columns: If provided, only score these columns for family
            assignments (e.g., columns already selected by the KPI gate).

    Returns:
        FamilyCoverageReport with covered/missing families and gap suggestions.
    """
    priority_families = _get_domain_priority_families(domain)

    # Build assignments for each column
    all_assignments: Dict[MetricFamily, List[FamilyAssignment]] = {}

    for col in column_metadata:
        col_name = col.get("name", "")
        col_type = col.get("type", "")
        business_category = col.get("business_category")

        # If existing_kpi_columns is provided, only consider those columns
        # Note: empty list means "no existing KPIs" — all columns still scored
        if existing_kpi_columns is not None and len(existing_kpi_columns) > 0 and col_name not in existing_kpi_columns:
            continue

        # Skip ID columns
        col_lower = col_name.lower()
        if any(kw in col_lower for kw in ["id", "uuid", "guid", "hash", "token"]):
            if "name" not in col_lower and "label" not in col_lower:
                continue

        family, confidence = detect_family_from_name(col_name, col_type, business_category)
        if family is None:
            continue

        family_score = _compute_family_score(col_name, col_type, confidence)

        # Determine aggregation from type
        if col_type in ("numeric", "integer", "float", "int"):
            if "rate" in col_lower or "pct" in col_lower or "percent" in col_lower:
                agg = "mean"
            elif "count" in col_lower:
                agg = "sum"
            elif "price" in col_lower or "aov" in col_lower or "arpu" in col_lower:
                agg = "mean"
            else:
                agg = "sum"
        elif col_type in ("categorical", "str", "utf8"):
            agg = "count"
        else:
            agg = "sum"

        suggested_title = _generate_title(col_name, agg)

        assignment = FamilyAssignment(
            column_name=col_name,
            column_type=col_type,
            family=family,
            aggregation=agg,
            family_score=family_score,
            suggested_title=suggested_title,
        )

        if family not in all_assignments:
            all_assignments[family] = []
        all_assignments[family].append(assignment)

    # Sort assignments within each family by score (descending)
    for family in all_assignments:
        all_assignments[family].sort(key=lambda a: a.family_score, reverse=True)
        if all_assignments[family]:
            all_assignments[family][0].is_primary = True

    # Determine which families are covered and missing
    covered_families: Dict[MetricFamily, List[FamilyAssignment]] = {}
    missing_families: List[MetricFamily] = []

    for family in priority_families:
        assignments = all_assignments.get(family, [])
        if assignments:
            covered_families[family] = assignments
        else:
            # Check if there are assignments for non-priority families too
            pass

    # Any family (even non-priority) that has assignments should be included
    for family, assignments in all_assignments.items():
        if family not in covered_families:
            covered_families[family] = assignments

    # Find genuinely missing priority families
    for family in priority_families:
        if family not in covered_families:
            missing_families.append(family)

    # Generate gap suggestions
    gap_suggestions: List[str] = []
    family_examples: Dict[MetricFamily, str] = {
        MetricFamily.REACH: "active_users, customer_count",
        MetricFamily.VOLUME: "total_orders, session_count",
        MetricFamily.VALUE: "revenue, mrr, aov",
        MetricFamily.QUALITY: "nps_score, satisfaction_rate",
        MetricFamily.DEPTH: "repeat_rate, sessions_per_user",
        MetricFamily.MIX: "revenue_by_plan, category_share",
        MetricFamily.MOVEMENT: "revenue_growth, month_over_month",
        MetricFamily.RISK: "churn_rate, error_count",
    }
    for family in missing_families:
        examples = family_examples.get(family, "")
        suggestion = f"Consider adding a metric for '{family.value}' (e.g., {examples})"
        gap_suggestions.append(suggestion)

    # Compute coverage score
    total_priority = len(priority_families)
    covered_priority = sum(1 for f in priority_families if f in covered_families)
    coverage_score = covered_priority / max(total_priority, 1)

    return FamilyCoverageReport(
        covered_families=covered_families,
        missing_families=missing_families,
        priority_families=priority_families,
        gap_suggestions=gap_suggestions,
        coverage_score=coverage_score,
    )


# ── Prompt Formatting ─────────────────────────────────────────────────────────


def format_family_block_for_prompt(report: FamilyCoverageReport) -> str:
    """
    Format the family coverage report as a structured block for LLM prompts.

    The LLM uses this to understand which KPI families must be covered
    and which columns are available for each family.
    """
    lines: List[str] = []
    lines.append("=" * 60)
    lines.append("METRIC FAMILIES — COVERAGE REQUIREMENT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(
        "Your dashboard MUST include at least one KPI from each family listed below. "
        "Prioritize families in the order shown."
    )
    lines.append("")

    for i, family in enumerate(report.priority_families, 1):
        is_covered = family in report.covered_families
        if is_covered:
            assignments = report.covered_families[family]
            primary = next((a for a in assignments if a.is_primary), assignments[0])
            other_names = ", ".join(a.suggested_title for a in assignments[1:3])
            cols_str = primary.suggested_title
            if other_names:
                cols_str += f" (also: {other_names})"
            lines.append(f"  ✓ {i}. {family.value.upper():<10} → {cols_str}")
        else:
            lines.append(f"  ✗ {i}. {family.value.upper():<10} → NO COLUMN AVAILABLE — skip this family")

    if report.gap_suggestions:
        lines.append("")
        lines.append("GAP SUGGESTIONS:")
        for suggestion in report.gap_suggestions:
            lines.append(f"  • {suggestion}")

    lines.append("")
    lines.append(f"COVERAGE SCORE: {report.coverage_score:.0%} ({sum(len(v) for v in report.covered_families.values())} metrics across {len(report.covered_families)} families)")
    lines.append("=" * 60)
    lines.append("")

    return "\n".join(lines)


def get_primary_kpi_columns(report: FamilyCoverageReport) -> List[Dict[str, Any]]:
    """
    Get the primary KPI column for each covered family.

    Returns a list of dicts with column, aggregation, title, family suitable
    for programmatic dashboard generation (skipping the LLM for KPIs).
    """
    result = []
    for family in report.priority_families:
        if family in report.covered_families:
            assignments = report.covered_families[family]
            primary = next((a for a in assignments if a.is_primary), assignments[0])
            result.append({
                "column": primary.column_name,
                "aggregation": primary.aggregation,
                "title": primary.suggested_title,
                "family": family.value,
            })
    return result

"""
intelligence/decision_engine.py — Decision Engine (P0)

Takes a KPI card with:
  - Business category (revenue, cost, volume, users, churn, etc.)
  - Delta direction and magnitude
  - Root cause chain (segment contributors)
  - Entity concentration data

And produces:
  - Actionable recommendations (what to do)
  - Expected impact estimates (what to expect)
  - Priority and confidence levels

All deterministic. No LLM calls.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

_PRIMARY_DRIVER_THRESHOLD = 30.0   # % contribution to mark as primary driver
_CRITICAL_CHANGE_PCT = 20.0        # % delta to trigger critical priority
_SIGNIFICANT_CHANGE_PCT = 10.0     # % delta to trigger high priority

# ── Data Structures ───────────────────────────────────────────────────────────


@dataclass
class ActionItem:
    """A single recommended action for a KPI.

    Each action has a clear "what to do", "why", and "what to expect".
    Designed to be rendered as a bullet in a decision card.
    """
    action: str                                      # "Restore Region B marketing campaigns"
    rationale: str                                   # "Region B contributed -8pp to overall revenue decline"
    impact_estimate: Optional[str] = None            # "Expected recovery: +6-10%"
    priority: str = "medium"                         # "critical" | "high" | "medium" | "low"
    confidence: str = "medium"                       # "High" | "Medium" | "Low"
    category: str = "investigate"                    # "investigate" | "restore" | "optimize" | "scale" | "monitor"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "rationale": self.rationale,
            "impact_estimate": self.impact_estimate,
            "priority": self.priority,
            "confidence": self.confidence,
            "category": self.category,
        }


@dataclass
class Decision:
    """Complete decision output for one KPI metric.

    Contains ranked recommendations with business context.
    """
    kpi_title: str
    kpi_column: str
    value: Optional[float] = None
    delta_pct: Optional[float] = None
    has_recommendations: bool = False
    primary_action: Optional[str] = None              # The single most important action
    items: List[ActionItem] = field(default_factory=list)
    summary: str = ""                                  # One-line takeaway for the CEO
    decision_confidence: str = "medium"                # Overall confidence in the recommendations

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kpi_title": self.kpi_title,
            "kpi_column": self.kpi_column,
            "value": self.value,
            "delta_pct": self.delta_pct,
            "has_recommendations": self.has_recommendations,
            "primary_action": self.primary_action,
            "items": [i.to_dict() for i in self.items],
            "summary": self.summary,
            "decision_confidence": self.decision_confidence,
        }


# ── Action Templates (by business category + direction) ───────────────────

# Each template is: (action_template, category, rationale_template, impact_template_high, impact_template_low)
# Format uses {driver}, {driver_pct}, {expected_recovery_pct}, {dimension}, {entity_type}, {entity_value}

_ACTION_TEMPLATES: Dict[str, Dict[str, List[tuple]]] = {
    "revenue": {
        "decline": [
            ("Investigate {driver_segment} in {dimension}", "restore",
             "{driver_segment} ({dimension}) contributed {driver_pct:.0f}% of the revenue decline",
             "Recover +{expected:.0f}% by addressing {driver_segment}",
             "Stabilize decline by monitoring {driver_segment}"),
        ],
        "growth": [
            ("Scale {driver_segment} {dimension} strategy", "scale",
             "{driver_segment} ({dimension}) drove {driver_pct:.0f}% of revenue growth",
             "Potential +{expected:.0f}% additional growth by doubling down",
             "Sustain growth by maintaining {driver_segment} momentum"),
        ],
    },
    "cost": {
        "decline": [
            ("Standardize {driver_segment} cost savings", "optimize",
             "{driver_segment} ({dimension}) contributed {driver_pct:.0f}% to cost reduction",
             "Projected savings of {expected:.0f}% from standardizing",
             "Monitor {driver_segment} to ensure savings persist"),
        ],
        "growth": [
            ("Audit {driver_segment} in {dimension}", "investigate",
             "{driver_segment} ({dimension}) drove {driver_pct:.0f}% of cost increase",
             "Potential {expected:.0f}% savings by optimizing {driver_segment}",
             "Contain {driver_segment} cost growth"),
        ],
    },
    "volume": {
        "decline": [
            ("Boost {driver_segment} in {dimension}", "restore",
             "{driver_segment} ({dimension}) contributed {driver_pct:.0f}% to volume decline",
             "Recover +{expected:.0f}% volume by focusing on {driver_segment}",
             "Reverse decline in {driver_segment}"),
        ],
        "growth": [
            ("Scale {driver_segment} {dimension} operations", "scale",
             "{driver_segment} ({dimension}) drove {driver_pct:.0f}% of volume growth",
             "Capacity for +{expected:.0f}% more volume from {driver_segment}",
             "Prepare for continued {driver_segment} growth"),
        ],
    },
    "users": {
        "decline": [
            ("Re-engage {driver_segment} in {dimension}", "restore",
             "{driver_segment} ({dimension}) contributed {driver_pct:.0f}% to user decline",
             "Recover +{expected:.0f}% users by re-engaging {driver_segment}",
             "Stem user loss in {driver_segment}"),
        ],
        "growth": [
            ("Expand {driver_segment} acquisition in {dimension}", "scale",
             "{driver_segment} ({dimension}) drove {driver_pct:.0f}% of user growth",
             "Potential +{expected:.0f}% more users from {driver_segment} expansion",
             "Continue {driver_segment} acquisition momentum"),
        ],
    },
    "churn_risk": {
        "decline": [
            ("Reinforce {driver_segment} retention wins", "optimize",
             "{driver_segment} ({dimension}) contributed {driver_pct:.0f}% to churn reduction",
             "Sustain {expected:.0f}% retention improvement across segments",
             "Document {driver_segment} retention practices"),
        ],
        "growth": [
            ("Intervene with {driver_segment} in {dimension}", "restore",
             "{driver_segment} ({dimension}) drove {driver_pct:.0f}% of churn increase",
             "Potential {expected:.0f}% churn reduction by targeting {driver_segment}",
             "Contain {driver_segment} churn immediately"),
        ],
    },
    "rate_metric": {
        "decline": [
            ("Improve {driver_segment} in {dimension}", "optimize",
             "{driver_segment} ({dimension}) contributed {driver_pct:.0f}% to rate decline",
             "Recover +{expected:.0f}% by improving {driver_segment}",
             "Address {driver_segment} rate decline"),
        ],
        "growth": [
            ("Leverage {driver_segment} success in {dimension}", "scale",
             "{driver_segment} ({dimension}) drove {driver_pct:.0f}% of rate improvement",
             "Target +{expected:.0f}% further improvement via {driver_segment}",
             "Apply {driver_segment} best practices broadly"),
        ],
    },
    "performance": {
        "decline": [
            ("Review {driver_segment} in {dimension}", "investigate",
             "{driver_segment} ({dimension}) contributed {driver_pct:.0f}% to performance decline",
             "Restore +{expected:.0f}% by fixing {driver_segment}",
             "Diagnose {driver_segment} performance drop"),
        ],
        "growth": [
            ("Celebrate and analyze {driver_segment} gains", "optimize",
             "{driver_segment} ({dimension}) drove {driver_pct:.0f}% of performance improvement",
             "Sustain +{expected:.0f}% improvement trajectory",
             "Identify what changed in {driver_segment}"),
        ],
    },
    "duration": {
        "decline": [
            ("Optimize {driver_segment} further", "optimize",
             "{driver_segment} ({dimension}) contributed {driver_pct:.0f}% to duration reduction",
             "Potential {expected:.0f}% more improvement from {driver_segment}",
             "Lock in {driver_segment} gains"),
        ],
        "growth": [
            ("Investigate {driver_segment} slowdown", "investigate",
             "{driver_segment} ({dimension}) drove {driver_pct:.0f}% of duration increase",
             "Potential {expected:.0f}% reduction by fixing {driver_segment}",
             "Address {driver_segment} duration increase"),
        ],
    },
    "quantity": {
        "decline": [
            ("Restore {driver_segment} supply in {dimension}", "restore",
             "{driver_segment} ({dimension}) contributed {driver_pct:.0f}% to quantity decline",
             "Recover +{expected:.0f}% by restoring {driver_segment}",
             "Stabilize {driver_segment} quantity"),
        ],
        "growth": [
            ("Scale {driver_segment} capacity in {dimension}", "scale",
             "{driver_segment} ({dimension}) drove {driver_pct:.0f}% of quantity growth",
             "Prepare for +{expected:.0f}% more demand from {driver_segment}",
             "Increase {driver_segment} capacity"),
        ],
    },
}

# Generic templates for unknown categories or when no driver is available
_GENERIC_ACTION_TEMPLATES: Dict[str, List[tuple]] = {
    "decline": [
        ("Investigate what's driving the {delta:.0f}% decline", "investigate",
         "The metric declined {delta:.1f}% — identifying the root cause is the first step",
         "Recover +{expected:.0f}% by addressing identified causes",
         "Stabilize the decline trajectory"),
    ],
    "growth": [
        ("Analyze what's driving the {delta:.0f}% growth", "optimize",
         "The metric grew {delta:.1f}% — understanding why helps sustain it",
         "Sustain +{expected:.0f}% growth trajectory",
         "Document what worked"),
    ],
}


def _compute_expected_recovery(
    delta_pct: float,
    driver_contribution_pct: float,
    severity: str,
) -> float:
    """Estimate expected recovery/impact percentage.

    The core heuristic:
    - If a primary driver contributed X% of the change, addressing that driver
      could recover roughly X% × (a decay factor based on severity).
    - High-confidence drivers (>=50% contribution) get a higher factor.
    """
    abs_delta = abs(delta_pct)
    abs_driver = abs(driver_contribution_pct)

    if severity == "critical" and abs_driver >= 50:
        # Strong driver of a large change → high recovery potential
        factor = 0.75
    elif abs_driver >= 40:
        factor = 0.60
    elif abs_driver >= 30:
        factor = 0.50
    elif abs_driver >= 20:
        factor = 0.35
    else:
        factor = 0.20

    recovery = abs_delta * factor * (abs_driver / 100.0)
    recovery = min(recovery, abs_delta * 0.9)  # Cap at 90% recovery
    return max(recovery, 3.0)  # Floor: at least 3% impact


def _categorize_priority(
    delta_pct: float,
    confidence: str,
    is_anomaly: bool = False,
) -> str:
    """Map change magnitude + confidence to priority level."""
    abs_delta = abs(delta_pct)

    if is_anomaly or abs_delta >= _CRITICAL_CHANGE_PCT:
        return "critical"
    elif abs_delta >= _SIGNIFICANT_CHANGE_PCT:
        return "high"
    elif confidence == "High" and abs_delta >= 5:
        return "high"
    elif abs_delta >= 3:
        return "medium"
    else:
        return "low"


# ── Core Engine ───────────────────────────────────────────────────────────────


def compute_decision(
    kpi_title: str,
    kpi_column: str,
    business_category: str,
    delta_pct: Optional[float],
    value: Optional[float] = None,
    polarity: str = "higher_is_better",
    root_cause_chain: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
    anomaly: Optional[Dict[str, Any]] = None,
    entity_concentration: Optional[Dict[str, Any]] = None,
) -> Decision:
    """Compute a structured decision for one KPI.

    Ingests the KPI's computed signals (delta, root cause, anomaly, entity)
    and produces ranked recommendations with expected impact.

    Args:
        kpi_title: Human-readable KPI name
        kpi_column: Column name
        business_category: From KPI classification (revenue, cost, etc.)
        delta_pct: Percent change
        value: Current value
        polarity: higher_is_better or lower_is_better
        root_cause_chain: From RootCauseChain.to_dict()
        provenance: From ProvenanceInfo.to_dict()
        anomaly: Anomaly dict (is_anomaly, severity, z_score)
        entity_concentration: Entity info dict

    Returns:
        Decision with ranked ActionItems
    """
    if delta_pct is None or abs(delta_pct) < 1.0:
        # No significant change — no decision needed
        return Decision(
            kpi_title=kpi_title,
            kpi_column=kpi_column,
            value=value,
            delta_pct=delta_pct,
            has_recommendations=False,
            summary=f"{kpi_title} is stable — no action needed.",
        )

    direction = "growth" if delta_pct > 0 else "decline"
    is_good = (delta_pct > 0 and polarity == "higher_is_better") or (delta_pct < 0 and polarity == "lower_is_better")
    is_anomaly = anomaly.get("is_anomaly", False) if anomaly else False

    # Determine severity for recovery estimates
    abs_delta = abs(delta_pct)
    if is_anomaly or abs_delta >= _CRITICAL_CHANGE_PCT:
        severity = "critical"
    elif abs_delta >= _SIGNIFICANT_CHANGE_PCT:
        severity = "high"
    else:
        severity = "moderate"

    items: List[ActionItem] = []
    summary_parts: List[str] = []

    confidence = "High" if abs_delta >= 10 else "Medium"
    dir_word = "growth" if delta_pct > 0 else "decline"
    dir_label = "up" if delta_pct > 0 else "down"

    # ── Extract root cause info ──
    driver_segment = None
    driver_pct = None
    dimension = None
    if root_cause_chain and root_cause_chain.get("has_root_cause"):
        links = root_cause_chain.get("links", [])
        if links:
            top_link = links[0]
            contributors = top_link.get("contributors", [])
            if contributors:
                top = contributors[0]
                driver_segment = top.get("segment", "")
                driver_pct = abs(top.get("contribution_pct", 0))
                dimension = top.get("dimension", "")

    # ── Build Template-Based Actions ──
    category_template_map = _ACTION_TEMPLATES.get(business_category, _GENERIC_ACTION_TEMPLATES)
    direction_templates = category_template_map.get(direction, [])
    generic_templates = _GENERIC_ACTION_TEMPLATES.get(direction, [])

    effective_templates = direction_templates if direction_templates else generic_templates

    for template in effective_templates:
        action_str, cat, rationale_template, impact_high, impact_low = template

        # If templates expect driver data but none available, skip driver-specific ones
        if "{driver_segment}" in action_str and not driver_segment:
            continue

        # Compute expected recovery
        recovery_pct = _compute_expected_recovery(
            delta_pct,
            driver_pct or 30.0,
            severity,
        )

        # Format template
        formatted_action = action_str.format(
            driver_segment=driver_segment or "the primary driver",
            driver_pct=driver_pct or 30.0,
            delta=abs_delta,
            expected=recovery_pct,
            dimension=dimension or "the relevant dimension",
            entity_type="entity",
            entity_value="the largest entity",
        )

        formatted_rationale = rationale_template.format(
            driver_segment=driver_segment or "the primary driver",
            driver_pct=driver_pct or 30.0,
            delta=abs_delta,
            expected=recovery_pct,
            dimension=dimension or "the relevant dimension",
            entity_type="entity",
            entity_value="the largest entity",
        )

        impact_str = impact_high.format(expected=recovery_pct) if severity in ("critical", "high") else impact_low.format(expected=recovery_pct)

        priority = _categorize_priority(delta_pct, confidence, is_anomaly)
        item_confidence = "High" if (driver_pct and driver_pct >= 40) else "Medium"

        items.append(ActionItem(
            action=formatted_action,
            rationale=formatted_rationale,
            impact_estimate=impact_str,
            priority=priority,
            confidence=item_confidence,
            category=cat,
        ))

    # ── Add Anomaly Action (if applicable) ──
    if is_anomaly and anomaly:
        severity_label = anomaly.get("anomaly_severity", "notable")
        z = abs(anomaly.get("z_score", 0))
        items.append(ActionItem(
            action=f"Investigate {severity_label} anomaly ({z:.1f}σ deviation)",
            rationale=f"The {severity_label} anomaly ({z:.1f}σ) signals unusual behavior beyond normal variation",
            impact_estimate=f"Restoring to normal range could recover {abs_delta:.0f}%",
            priority="critical" if severity_label == "critical" else "high",
            confidence="High" if z >= 3 else "Medium",
            category="investigate",
        ))

    # ── Add Entity Concentration Action (if meaningful) ──
    if entity_concentration:
        conc_pct = entity_concentration.get("entity_concentration_pct")
        ent_val = entity_concentration.get("top_entity_value")
        ent_type = entity_concentration.get("entity_type", "entity")
        if conc_pct and conc_pct >= 20 and ent_val:
            risk = "risk" if direction == "decline" else "opportunity"
            items.append(ActionItem(
                action=f"Review top {ent_type}: {ent_val}",
                rationale=f"Top {ent_type} '{ent_val}' accounts for {conc_pct:.0f}% of total — {risk} concentration",
                impact_estimate=f"Managing {ent_val} could affect {conc_pct:.0f}% of the metric",
                priority="high" if conc_pct >= 40 else "medium",
                confidence="High" if conc_pct >= 50 else "Medium",
                category=risk,
            ))

    # ── Sort by priority ──
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    items.sort(key=lambda i: priority_order.get(i.priority, 99))

    # Deduplicate: keep highest priority version of similar actions
    seen_actions: set = set()
    deduped: List[ActionItem] = []
    for item in items:
        key = item.category + ":" + item.action[:40]
        if key not in seen_actions:
            seen_actions.add(key)
            deduped.append(item)
    items = deduped[:4]  # Max 4 recommendations

    # ── Build summary ──
    if items:
        primary = items[0]
        has_action = f"Recommended: {primary.action}"
        summary_parts.append(has_action)
        if primary.impact_estimate:
            summary_parts.append(primary.impact_estimate)
        summary = f"{kpi_title} {dir_label} {abs_delta:.0f}% — {'; '.join(summary_parts)}."
    else:
        if driver_segment:
            summary = f"{kpi_title} {dir_label} {abs_delta:.0f}% — no clear action beyond monitoring {driver_segment}."
        else:
            summary = f"{kpi_title} {dir_label} {abs_delta:.0f}% — no specific driver identified for targeted action."

    if is_good:
        summary = "✅ " + summary
    else:
        summary = "⚠️ " + summary

    return Decision(
        kpi_title=kpi_title,
        kpi_column=kpi_column,
        value=value,
        delta_pct=delta_pct,
        has_recommendations=len(items) > 0,
        primary_action=items[0].action if items else None,
        items=items,
        summary=summary,
        decision_confidence=confidence,
    )


# ── Batch API ────────────────────────────────────────────────────────────────


def compute_decisions_for_kpis(kpis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compute decisions for a list of KPI cards.

    Adds 'decision' field to each KPI dict that has a meaningful delta.

    Args:
        kpis: List of KPI card dicts (from IntelligentKPIGenerator)

    Returns:
        Updated KPI cards with decision field
    """
    for kpi in kpis:
        delta = kpi.get("delta_percent")
        if delta is None or abs(delta) < 1.0:
            continue

        try:
            decision = compute_decision(
                kpi_title=kpi.get("title", ""),
                kpi_column=kpi.get("column", ""),
                business_category=kpi.get("business_category", "unknown"),
                delta_pct=delta,
                value=kpi.get("value"),
                polarity=kpi.get("polarity", "higher_is_better"),
                root_cause_chain=kpi.get("root_cause_chain"),
                provenance=kpi.get("provenance"),
                anomaly={
                    "is_anomaly": kpi.get("is_anomaly", False),
                    "anomaly_severity": kpi.get("anomaly_severity", "normal"),
                    "z_score": kpi.get("z_score", 0),
                },
                entity_concentration={
                    "entity_type": kpi.get("entity_type"),
                    "entity_concentration_pct": kpi.get("entity_concentration_pct"),
                    "top_entity_value": kpi.get("top_entity_value"),
                } if kpi.get("entity_concentration_pct") else None,
            )
            if decision.has_recommendations:
                kpi["decision"] = decision.to_dict()
        except Exception as e:
            logger.debug(f"[Decision] Failed for '{kpi.get('column', '?')}': {e}")
            continue

    return kpis

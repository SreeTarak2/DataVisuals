"""
diagnostic_modes — 4 investigation modes for AnomalyInvestigatorAgent.

Each mode implements a different analytical approach to metric investigation:
  - metric_change:       Focal window vs baseline, segment contributions, mix shift
  - spike_regression:    Onset/peak/recovery timing, distribution shape, affected slices
  - largest_contributors: Rank entities, track movers, concentration change
  - reconciliation:      Align definitions across sources, quantify gap components
"""

from __future__ import annotations

import logging
from typing import Any, Optional



logger = logging.getLogger(__name__)


# ── Mode Selection ──────────────────────────────────────────────────────────

def detect_mode(
    anomalies: list[dict],
    has_time_column: bool = False,
    row_count: int = 0,
    has_comparison_data: bool = False,
    explicit_mode: str | None = None,
) -> str:
    """
    Auto-detect the best investigation mode based on available data.

    Priority:
      1. Explicit mode override
      2. reconciliation — only when user explicitly requests source comparison
      3. spike_regression — when anomalies have a dominant direction and
         many outliers in one column (suggests a spike, not a trend)
      4. largest_contributors — when multiple anomalies exist across columns,
         suggesting a concentration/concentration-change question
      5. metric_change — default: focal vs baseline comparison

    Args:
        anomalies: List of anomaly dicts from AnomalyDetector
        has_time_column: Whether the dataset has a usable time column
        row_count: Total row count for threshold tuning
        has_comparison_data: Whether comparison/baseline data exists
        explicit_mode: Override — skips auto-detection

    Returns:
        One of: "metric_change", "spike_regression", "largest_contributors", "reconciliation"
    """
    if explicit_mode and explicit_mode in MODE_REGISTRY:
        return explicit_mode

    if not anomalies:
        return "metric_change"

    # Count properties across all anomalies
    total_outliers = sum(a.get("outlier_count", 0) for a in anomalies)
    cols_with_critical_severity = sum(
        1 for a in anomalies if a.get("severity") in ("critical", "high")
    )
    directions_seen = set()
    for a in anomalies:
        d = a.get("direction", "mixed")
        if isinstance(d, str):
            directions_seen.add(d)

    has_mixed_direction = "mixed" in directions_seen or len(directions_seen) > 1

    # Spike/regression: one dominant column with critical severity and clear direction
    if cols_with_critical_severity >= 1 and not has_mixed_direction:
        # Check if one column dominates
        max_pct = max((a.get("outlier_percentage", 0) for a in anomalies), default=0)
        if max_pct > 5:  # >5% outliers in a single column = spike
            logger.info("[Mode] Auto-selected: spike_regression (dominant critical anomaly)")
            return "spike_regression"

    # Largest contributors: multiple anomalies, suggests concentration question
    if len(anomalies) >= 3 and total_outliers > 50:
        logger.info("[Mode] Auto-selected: largest_contributors (multiple anomalies across columns)")
        return "largest_contributors"

    # Default
    logger.info("[Mode] Auto-selected: metric_change (default)")
    return "metric_change"


# ── Mode-specific context builders ──────────────────────────────────────────

def build_metric_change_context(
    anomalies: list[dict],
    schema_context: str,
    sample_context: str,
) -> tuple[str, str, str]:
    """
    Build context for metric_change mode.

    Focuses on: focal window statistics, baseline comparison, dimension contributions.

    Returns:
        (anomalies_text, schema_context, sample_context) — enriched for comparison analysis
    """
    enriched_schema = schema_context + (
        "\n\nInvestigation focus: Compare focal window against baseline. "
        "For each anomalous column, identify:\n"
        "1. How the focal window's distribution differs from baseline\n"
        "2. Which dimension segments contributed most to the change\n"
        "3. Whether this is a mix shift (composition changed) or within-segment change\n"
        "4. Whether the change is broad-based or concentrated in few segments"
    )
    return _format_anomalies_detailed(anomalies), enriched_schema, sample_context


def build_spike_context(
    anomalies: list[dict],
    schema_context: str,
    sample_context: str,
) -> tuple[str, str, str]:
    """
    Build context for spike_regression mode.

    Focuses on: timing (onset, peak, recovery), distribution shape (not just mean),
    and affected slices.

    Returns:
        (anomalies_text, schema_context, sample_context) — enriched for spike investigation
    """
    enriched_schema = schema_context + (
        "\n\nInvestigation focus: Spike/regression analysis.\n"
        "For each anomalous column, identify:\n"
        "1. When the spike started (onset), peaked, and if recovery has begun\n"
        "2. The distribution shape during the spike — not just the average\n"
        "3. Which specific segments/slices are most affected\n"
        "4. Whether the spike is broad-based (all segments) or localized\n"
        "5. Possible external causes (seasonal, incident, campaign, data pipeline change)"
    )
    # Add timing-focused context line
    timing_note = (
        "\n\nTime-series context: If a time column is available, "
        "the anomaly is analyzed with temporal segmentation. "
        "Consider when the anomalous pattern emerges relative to known events."
    )
    enriched_schema += timing_note
    return _format_anomalies_detailed(anomalies), enriched_schema, sample_context


def build_contributor_context(
    anomalies: list[dict],
    schema_context: str,
    sample_context: str,
) -> tuple[str, str, str]:
    """
    Build context for largest_contributors mode.

    Focuses on: ranking entities by contribution, tracking movement,
    identifying entrants/exits, concentration changes.

    Returns:
        (anomalies_text, schema_context, sample_context) — enriched for contributor analysis
    """
    enriched_schema = schema_context + (
        "\n\nInvestigation focus: Largest contributors & concentration analysis.\n"
        "For each anomalous column, identify:\n"
        "1. Which dimension segments are the largest contributors to the anomaly\n"
        "2. Whether concentration has changed (is the metric more or less concentrated?)\n"
        "3. Which segments gained or lost share (movers)\n"
        "4. Whether new segments appeared (entrants) or disappeared (exits)\n"
        "5. Whether the top contributors are stable or shifting"
    )
    return _format_anomalies_detailed(anomalies), enriched_schema, sample_context


def build_reconciliation_context(
    anomalies: list[dict],
    schema_context: str,
    sample_context: str,
) -> tuple[str, str, str]:
    """
    Build context for reconciliation mode.

    Focuses on: comparing definitions, aligning grain/numerator/denominator,
    quantifying gap components.

    Returns:
        (anomalies_text, schema_context, sample_context) — enriched for reconciliation
    """
    enriched_schema = schema_context + (
        "\n\nInvestigation focus: Reconciliation / source comparison.\n"
        "For each anomalous column, identify:\n"
        "1. Whether different sources or definitions could explain the discrepancy\n"
        "2. Does the data grain match between compared sources?\n"
        "3. Are numerators and denominators defined consistently?\n"
        "4. Could filters, time windows, or exclusions differ between sources?\n"
        "5. Quantify the gap components — what % is explained by each factor\n"
        "6. What residual remains unexplained after aligning definitions"
    )
    return _format_anomalies_detailed(anomalies), enriched_schema, sample_context


# ── Mode-specific prompt templates ─────────────────────────────────────────

ROOT_CAUSE_CHANGE_PROMPT = """\
<role>You are a root-cause analyst investigating why a metric changed between two periods.</role>
<instructions>
Below is an anomaly detection result with baseline comparison context.

## Anomaly Detail
{anomalies_text}

## Dataset Schema
{schema_context}

## Sample Data
{sample_context}

## Investigation Task
This is a **metric change investigation** — compare the focal window against a baseline.

For each anomalous column:
1. Quantify the change magnitude (absolute and relative)
2. Identify which dimension segments explain the change (segment contribution analysis)
3. Determine if this is a mix shift (composition change) or within-segment performance change
4. Assess whether the change is broad-based or concentrated in specific segments
5. State whether measurement artifacts (logging changes, backfills, dedup changes) could explain the difference

Return a JSON array of root causes, each with:
- "affected_metric": Column or KPI affected
- "change_magnitude": Absolute and relative change
- "root_cause": Specific explanation
- "driver_segments": Which segments contributed most ({segment}: {contribution_pct})
- "change_type": "mix_shift" | "within_segment" | "both" | "measurement_artifact"
- "confidence": 0.0–1.0
- "supporting_evidence": What in the data supports this
- "verification_query": What query would confirm this
</instructions>"""

ROOT_CAUSE_SPIKE_PROMPT = """\
<role>You are a root-cause analyst investigating a data spike or sudden regression.</role>
<instructions>
Below is an anomaly detection result from a dataset, with focus on spike/regression patterns.

## Anomaly Detail
{anomalies_text}

## Dataset Schema
{schema_context}

## Sample Data
{sample_context}

## Investigation Task
This is a **spike / regression investigation** — identify the timing, affected populations,
and likely trigger.

For each anomalous column:
1. Characterize the spike pattern: sudden onset vs gradual ramp, peak timing, recovery state
2. Analyze the distribution during the spike (not just the average — look at percentiles and spread)
3. Identify which segments or slices are most affected vs unaffected
4. Assess breadth: is the spike broad-based or localized to a segment?
5. Consider possible causes: product launch, campaign, seasonality, pipeline change, incident, data quality issue
6. If a cause cannot be confirmed, state what additional data would confirm it

Return a JSON array of root causes, each with:
- "affected_metric": Column or KPI affected
- "spike_characteristics": Onset timing, peak magnitude, recovery state
- "root_cause": Specific explanation
- "affected_segments": Which segments drove the spike
- "breadth": "broad" | "localized" | "unknown"
- "confidence": 0.0–1.0
- "supporting_evidence": What in the data supports this
- "verification_query": What query would confirm this
</instructions>"""

ROOT_CAUSE_CONTRIBUTOR_PROMPT = """\
<role>You are a root-cause analyst identifying the largest contributors to a pattern.</role>
<instructions>
Below is an anomaly detection result with contributor analysis context.

## Anomaly Detail
{anomalies_text}

## Dataset Schema
{schema_context}

## Sample Data
{sample_context}

## Investigation Task
This is a **largest contributors investigation** — identify which entities or segments
are driving the anomaly pattern.

For each anomalous column:
1. Rank the top contributing segments by share of total
2. Identify which segments gained or lost share (movers)
3. Check for entrants (new segments) or exits (disappeared segments)
4. Assess whether concentration is increasing or decreasing
5. Determine if the top contributors are stable or shifting

Return a JSON array of root causes, each with:
- "affected_metric": Column or KPI affected
- "root_cause": Specific explanation
- "top_contributors": [{{"segment": "...", "share_pct": ..., "direction": "gaining|losing|stable"}}]
- "concentration_trend": "increasing" | "decreasing" | "stable"
- "confidence": 0.0–1.0
- "supporting_evidence": What in the data supports this
- "verification_query": What query would confirm this
</instructions>"""

ROOT_CAUSE_RECONCILIATION_PROMPT = """\
<role>You are a data reconciliation analyst identifying why sources disagree.</role>
<instructions>
Below is an anomaly detection result with reconciliation context.

## Anomaly Detail
{anomalies_text}

## Dataset Schema
{schema_context}

## Sample Data
{sample_context}

## Investigation Task
This is a **reconciliation investigation** — identify why different sources,
definitions, or time windows produce different numbers.

For each anomalous column:
1. Compare definitions across potential sources (grain, numerator, denominator, filters)
2. Quantify the gap: what % of the discrepancy is explained by each factor
3. Identify any residual gap that remains unexplained
4. Recommend which source or definition should be treated as authoritative
5. Suggest what would resolve the remaining discrepancy

Return a JSON array of root causes, each with:
- "affected_metric": Column or KPI affected
- "root_cause": Specific explanation for the discrepancy
- "gap_components": [{{"factor": "...", "explained_pct": ..., "details": "..."}}]
- "residual_gap_pct": Percentage still unexplained
- "recommended_source": Which source or definition to trust
- "confidence": 0.0–1.0
- "supporting_evidence": What in the data supports this
</instructions>"""


def get_mode_prompts(mode: str) -> tuple[str, str, str, str]:
    """
    Get the prompt templates for the given mode.

    Returns:
        (root_cause_prompt, impact_prompt, recommendation_prompt, narrative_prompt)
    """
    # Impact and recommendation prompts are mode-aware with extra context
    impact_templates = {
        "spike_regression": (
            "Assess the business impact of this spike/regression. "
            "Focus on: which populations are affected, whether this is an ongoing incident, "
            "and the revenue/cost/trust implications."
        ),
        "metric_change": (
            "Assess the business impact of this metric change. "
            "Focus on: whether the change is positive or negative, how large it is relative "
            "to normal variation, and what functions would need to respond."
        ),
        "largest_contributors": (
            "Assess the business impact of these contributor shifts. "
            "Focus on: whether concentration risk is increasing, which segments need attention, "
            "and whether the trend is accelerating."
        ),
        "reconciliation": (
            "Assess the business impact of this reconciliation gap. "
            "Focus on: which reporting surfaces are affected, whether decisions are being "
            "made on incorrect data, and what trust has been lost."
        ),
    }

    recommendation_templates = {
        "spike_regression": (
            "Recommend actions for a spike/regression incident. "
            "Focus on: immediate containment, investigation steps, monitoring, "
            "and communication to affected teams."
        ),
        "metric_change": (
            "Recommend actions for a metric change. "
            "Focus on: whether to alert stakeholders, what deeper analysis is needed, "
            "and what automated monitoring to set up."
        ),
        "largest_contributors": (
            "Recommend actions for concentration changes. "
            "Focus on: whether to investigate specific segments, diversify risk, "
            "or adjust forecasts."
        ),
        "reconciliation": (
            "Recommend actions for data reconciliation. "
            "Focus on: aligning definitions, fixing pipeline issues, "
            "and documenting source-of-truth decisions."
        ),
    }

    root_cause = MODE_PROMPTS.get(mode, ROOT_CAUSE_CHANGE_PROMPT)
    impact_prefix = impact_templates.get(mode, impact_templates["metric_change"])
    rec_prefix = recommendation_templates.get(mode, recommendation_templates["metric_change"])

    impact = (
        "<role>You are a business impact analyst.</role>\n<instructions>\n"
        + impact_prefix
        + "\n\n## Anomalies Detected\n{anomalies_text}\n\n"
        "## Root Causes Identified\n{root_causes_text}\n\n"
        "Return a JSON object with:\n"
        '- "severity": "critical" | "high" | "medium" | "low"\n'
        '- "magnitude": relative impact (0.0–1.0)\n'
        '- "affected_dimensions": affected data dimensions\n'
        '- "estimated_effect": brief quantification\n'
        '- "trend_acceleration": "accelerating" | "decelerating" | "stable" | "unknown"\n'
        '- "business_functions_impacted": affected teams\n'
        "Be conservative — do not overstate impact.\n</instructions>"
    )

    recommendation = (
        "<role>You are a data reliability engineer recommending actions.</role>\n<instructions>\n"
        + rec_prefix
        + "\n\n## Anomalies to Address\n{anomalies_text}\n\n"
        "## Root Causes\n{root_causes_text}\n\n"
        "## Impact Assessment\n{impact_text}\n\n"
        "Generate 2-4 specific, actionable recommendations. For each:\n"
        '- "action": Specific next step\n'
        '- "rationale": Why this action\n'
        '- "urgency": "immediate" | "today" | "this_week"\n'
        '- "effort": "low" | "medium" | "high"\n'
        '- "expected_outcome": Expected improvement\n'
        '- "owner": Suggested team or role\n'
        "Return ONLY a JSON array of recommendations.\n</instructions>"
    )

    # Narrative is mode-aware but reuses the same template structure
    narrative = """\
<role>You are a data storyteller explaining findings to business stakeholders.</role>
<instructions>
Summarize the following investigation into 2-3 paragraphs suitable for a business stakeholder.

Focus on:
1. What happened (the anomaly pattern and its significance)
2. Why it happened (validated root causes and driver analysis)
3. What to do about it (recommended actions)

Use clear, jargon-free language. Prioritize actionable insight over technical detail.

Anomalies: {anomalies_text}
Root Causes: {root_causes_text}
Impact: {impact_text}
Recommendations: {recommendations_text}
</instructions>"""

    return root_cause, impact, recommendation, narrative


# ── Mode context builders registry ──────────────────────────────────────────

MODE_CONTEXT_BUILDERS = {
    "metric_change": build_metric_change_context,
    "spike_regression": build_spike_context,
    "largest_contributors": build_contributor_context,
    "reconciliation": build_reconciliation_context,
}

MODE_PROMPTS = {
    "metric_change": ROOT_CAUSE_CHANGE_PROMPT,
    "spike_regression": ROOT_CAUSE_SPIKE_PROMPT,
    "largest_contributors": ROOT_CAUSE_CONTRIBUTOR_PROMPT,
    "reconciliation": ROOT_CAUSE_RECONCILIATION_PROMPT,
}

MODE_REGISTRY = set(MODE_CONTEXT_BUILDERS.keys())


# ── Helpers ─────────────────────────────────────────────────────────────────

def _format_anomalies_detailed(anomalies: list[dict]) -> str:
    """Format anomalies with more detailed context for mode-specific prompts."""
    if not anomalies:
        return "No anomalies detected."
    lines = []
    for i, a in enumerate(anomalies[:10], 1):
        col = a.get("column", "?")
        count = a.get("outlier_count", 0)
        pct = a.get("outlier_percentage", 0)
        sev = a.get("severity", "unknown")
        direction = a.get("direction", "mixed")
        method = a.get("method", "z-score")
        threshold = a.get("threshold", 3.0)

        lines.append(
            f"#{i}: {col}"
        )
        lines.append(f"  Outliers: {count} / {pct:.1f}%  |  Severity: {sev}  |  Direction: {direction}")
        lines.append(f"  Method: {method} (threshold={threshold})")

    if len(anomalies) > 10:
        lines.append(f"... and {len(anomalies) - 10} more anomalies")

    return "\n".join(lines)

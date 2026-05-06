"""
Stage 6 — Narrator (Deterministic, Templated)

Takes ComputeResult[] + PrimitiveSpec[] and fills slot-based card templates to produce Card[].
No LLM used at this stage — slots are filled from computed evidence and spec column metadata only.
This keeps the narrator fast, owned, and auditable.
"""

import json
import logging
import math
from pathlib import Path
from typing import Optional

from db.schemas_pipeline import (
    Card,
    CardConfidence,
    ComputeResult,
    CriticStatus,
    PrimitiveSpec,
    PrimitiveType,
    TimeGrain,
)

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_TEMPLATES: dict[str, dict] = {}


def _load_templates() -> None:
    for template_file in _TEMPLATE_DIR.glob("*.json"):
        try:
            with open(template_file) as f:
                template = json.load(f)
                primitive = template.get("primitive")
                if primitive:
                    _TEMPLATES[primitive] = template
        except Exception as exc:
            logger.warning("Failed to load template %s: %s", template_file, exc)


_load_templates()


# ── Column label helpers ─────────────────────────────────────────────────────

def _prettify(col: str) -> str:
    return col.replace("_", " ").title()


def _entity_label(col: str) -> str:
    """Prettify an entity column name, stripping trailing ' Id'."""
    label = _prettify(col)
    if label.lower().endswith(" id"):
        label = label[:-3].strip()
    return label


def _plural(label: str) -> str:
    return label if label.endswith("s") else label + "s"


def _grain_label(grain: Optional[TimeGrain]) -> str:
    if grain is None:
        return "period"
    g = grain.value if hasattr(grain, "value") else str(grain)
    return {"day": "daily", "week": "weekly", "month": "monthly"}.get(g, g)


# ── Formatting helpers ───────────────────────────────────────────────────────

def _fmt_pct(value: Optional[float]) -> str:
    if value is None or not math.isfinite(value):
        return "N/A"
    return f"{value * 100:.1f}%"


def _fmt_pct_change(value: Optional[float]) -> str:
    if value is None or not math.isfinite(value):
        return "N/A"
    pct = value * 100
    return f"+{pct:.1f}%" if pct > 0 else f"{pct:.1f}%"


def _fmt_number(value: Optional[float]) -> str:
    if value is None or not math.isfinite(value):
        return "N/A"
    return f"{value:,.0f}"


def _fmt_decimal(value: Optional[float], places: int = 2) -> str:
    if value is None or not math.isfinite(value):
        return "N/A"
    return f"{value:.{places}f}"


def _direction(delta: Optional[float]) -> str:
    if delta is None:
        return "stable"
    if delta > 0.01:
        return "up"
    if delta < -0.01:
        return "down"
    return "stable"


def _direction_verb(delta: Optional[float]) -> str:
    if delta is None:
        return "remained"
    if delta > 0:
        return "increased"
    if delta < 0:
        return "decreased"
    return "remained"


# ── Confidence and caveats ───────────────────────────────────────────────────

def _compute_confidence(result: ComputeResult) -> CardConfidence:
    if result.compute_error:
        return CardConfidence.low
    fail_count = sum(1 for c in result.critic_checks if c.status == CriticStatus.fail)
    warning_count = sum(1 for c in result.critic_checks if c.status == CriticStatus.warning)
    if fail_count > 0 or warning_count > 2:
        return CardConfidence.low
    if warning_count > 0:
        return CardConfidence.moderate
    return CardConfidence.high


def _extract_caveats(result: ComputeResult, template: dict) -> list[str]:
    caveats: list[str] = []
    caveat_templates = template.get("caveats", {})
    seg = result.segment_breakdown or {}
    for check in result.critic_checks:
        if check.status in (CriticStatus.fail, CriticStatus.warning):
            caveat_tpl = caveat_templates.get(check.name)
            if caveat_tpl:
                try:
                    caveat = caveat_tpl.format(
                        coverage_pct=_fmt_pct(result.coverage_pct),
                        cov=_fmt_decimal(result.cov),
                        row_count=result.row_count,
                        period_count=int(seg.get("period_count", 0)),
                    )
                    caveats.append(caveat)
                except KeyError:
                    caveats.append(caveat_tpl)
    return caveats


# ── Slot fillers per primitive ───────────────────────────────────────────────

def _fill_entity_concentration(
    result: ComputeResult, spec: PrimitiveSpec, template: dict
) -> Card:
    seg = result.segment_breakdown or {}
    entity_label = _entity_label(spec.entity_col or "entity")
    measure_label = _prettify(spec.measure_col)
    entity_label_plural = _plural(entity_label)
    top_n = seg.get("top_n", spec.top_n)
    ratio = result.current_value

    thresholds = template.get("concentration_thresholds", {})
    if ratio and ratio >= thresholds.get("high", 0.5):
        conc_level = "high_concentration"
    elif ratio and ratio >= thresholds.get("moderate", 0.3):
        conc_level = "moderate_concentration"
    else:
        conc_level = "low_concentration"

    title = template.get("title_template", "").format(
        top_n=top_n,
        entity_col_label=entity_label,
    )
    headline = template.get("headline_template", "").format(
        concentration_pct=_fmt_pct(ratio),
        top_n=top_n,
        measure_col_label=measure_label,
        entity_col_label_plural=entity_label_plural,
    )
    delta_narrative = None
    if result.comparison_value is not None:
        delta_narrative = template.get("delta_narrative_template", "").format(
            delta_direction=_direction(result.delta),
            comparison_pct=_fmt_pct(result.comparison_value),
        )
    key_insight = template.get("key_insight_phrases", {}).get(
        conc_level,
        f"Top {top_n} {entity_label_plural} account for {_fmt_pct(ratio)} of {measure_label}",
    ).format(
        measure_col_label=measure_label,
        entity_col_label_plural=entity_label_plural,
    )

    return Card(
        kpi_id=result.kpi_id,
        primitive=result.primitive,
        title=title,
        headline=headline,
        metric_value=ratio,
        comparison_value=result.comparison_value,
        delta_narrative=delta_narrative,
        key_insight=key_insight,
        confidence=_compute_confidence(result),
        segment_breakdown=seg,
        category=template.get("category", "risk"),
        caveats=_extract_caveats(result, template),
        template_id=template.get("template_id", ""),
    )


def _fill_period_delta(
    result: ComputeResult, spec: PrimitiveSpec, template: dict
) -> Card:
    measure_label = _prettify(spec.measure_col)
    grain = _grain_label(spec.grain)
    current = result.current_value
    comparison = result.comparison_value
    delta = result.delta
    delta_pct = result.delta_pct

    title = template.get("title_template", "").format(
        measure_col_label=measure_label,
        grain_label=grain,
    )
    headline = template.get("headline_template", "").format(
        current_value_formatted=_fmt_number(current),
        measure_col_label=measure_label,
        grain_label=grain,
    )
    delta_narrative = None
    if comparison is not None and delta is not None:
        delta_narrative = template.get("delta_narrative_template", "").format(
            delta_direction_verb=_direction_verb(delta),
            abs_delta_formatted=_fmt_number(abs(delta)),
            delta_pct_formatted=_fmt_pct_change(delta_pct),
            prior_grain=grain,
        )

    thresholds = template.get("significance_thresholds", {})
    sig_key: Optional[str] = None
    if delta_pct and abs(delta_pct) >= thresholds.get("significant", 0.1):
        sig_key = "significant_up" if delta and delta > 0 else "significant_down"

    key_insight = None
    if sig_key:
        phrase = template.get("key_insight_phrases", {}).get(sig_key)
        if phrase:
            key_insight = phrase.format(measure_col_label=measure_label)

    return Card(
        kpi_id=result.kpi_id,
        primitive=result.primitive,
        title=title,
        headline=headline,
        metric_value=current,
        comparison_value=comparison,
        delta_narrative=delta_narrative,
        key_insight=key_insight,
        confidence=_compute_confidence(result),
        category=template.get("category", "performance"),
        caveats=_extract_caveats(result, template),
        template_id=template.get("template_id", ""),
    )


def _fill_segment_mix(
    result: ComputeResult, spec: PrimitiveSpec, template: dict
) -> Card:
    seg = result.segment_breakdown or {}
    dimension_label = _prettify(spec.dimension_col or "segment")
    measure_label = _prettify(spec.measure_col)

    # segment_breakdown keys are segment names, values are shares (ordered desc by compute engine)
    top_segs = ", ".join(list(seg.keys())[:3]) if seg else "mixed"
    segment_count = len(seg)
    top_share = result.current_value or 0.0

    title = template.get("title_template", "").format(
        dimension_col_label=dimension_label,
    )
    headline = template.get("headline_template", "").format(
        measure_col_label=measure_label,
        top_segments=top_segs,
    )

    if segment_count <= 2:
        mix_key = "bifurcated"
    elif top_share > 0.6:
        mix_key = "concentrated"
    else:
        mix_key = "balanced"

    key_insight = template.get("key_insight_phrases", {}).get(
        mix_key, "Mix is varied across segments"
    ).format(
        measure_col_label=measure_label,
        dimension_col_label=dimension_label,
        top_segments=top_segs,
    )

    return Card(
        kpi_id=result.kpi_id,
        primitive=result.primitive,
        title=title,
        headline=headline,
        metric_value=top_share,
        segment_breakdown=seg,
        key_insight=key_insight,
        confidence=_compute_confidence(result),
        category=template.get("category", "diagnostic"),
        caveats=_extract_caveats(result, template),
        template_id=template.get("template_id", ""),
    )


def _fill_trend_stability(
    result: ComputeResult, spec: PrimitiveSpec, template: dict
) -> Card:
    measure_label = _prettify(spec.measure_col)
    grain = _grain_label(spec.grain)
    seg = result.segment_breakdown or {}
    period_count = seg.get("period_count", 0)
    cov = result.cov

    title = template.get("title_template", "").format(
        measure_col_label=measure_label,
    )
    headline = template.get("headline_template", "").format(
        cov_formatted=_fmt_decimal(cov, 2),
        period_count=int(period_count),
        grain_label=grain,
    )

    thresholds = template.get("stability_thresholds", {})
    if cov is None or cov < thresholds.get("very_stable", 0.1):
        stability_key = "very_stable"
    elif cov < thresholds.get("stable", 0.25):
        stability_key = "stable"
    elif cov < thresholds.get("volatile", 0.5):
        stability_key = "volatile"
    else:
        stability_key = "highly_volatile"

    key_insight = template.get("key_insight_phrases", {}).get(
        stability_key, "Trend shows moderate variation"
    ).format(measure_col_label=measure_label)

    return Card(
        kpi_id=result.kpi_id,
        primitive=result.primitive,
        title=title,
        headline=headline,
        metric_value=cov,
        key_insight=key_insight,
        confidence=_compute_confidence(result),
        category=template.get("category", "diagnostic"),
        caveats=_extract_caveats(result, template),
        template_id=template.get("template_id", ""),
    )


def _fill_cohort_behavior(
    result: ComputeResult, spec: PrimitiveSpec, template: dict
) -> Card:
    entity_label = _entity_label(spec.entity_col or "entity")
    entity_label_plural = _plural(entity_label)
    seg = result.segment_breakdown or {}
    repeat_rate = result.current_value

    title = template.get("title_template", "").format(
        entity_col_label=entity_label,
    )
    headline = template.get("headline_template", "").format(
        repeat_rate_pct=_fmt_pct(repeat_rate),
        entity_col_label_plural=entity_label_plural,
    )

    thresholds = template.get("retention_thresholds", {})
    if repeat_rate and repeat_rate >= thresholds.get("high", 0.5):
        retention_key = "high_retention"
    elif repeat_rate and repeat_rate >= thresholds.get("moderate", 0.25):
        retention_key = "moderate_retention"
    else:
        retention_key = "low_retention"

    key_insight = template.get("key_insight_phrases", {}).get(
        retention_key, "Repeat activity is mixed"
    ).format(
        entity_col_label=entity_label,
        entity_col_label_plural=entity_label_plural,
    )

    return Card(
        kpi_id=result.kpi_id,
        primitive=result.primitive,
        title=title,
        headline=headline,
        metric_value=repeat_rate,
        segment_breakdown=seg,
        key_insight=key_insight,
        confidence=_compute_confidence(result),
        category=template.get("category", "diagnostic"),
        caveats=_extract_caveats(result, template),
        template_id=template.get("template_id", ""),
    )


def _fill_coverage_quality(
    result: ComputeResult, spec: PrimitiveSpec, template: dict
) -> Card:
    # coverage_pct is already a ratio in [0,1]; current_value holds the same
    coverage = result.current_value if result.current_value is not None else result.coverage_pct

    title = template.get("title_template", "")
    headline = template.get("headline_template", "").format(
        coverage_pct_formatted=_fmt_pct(coverage),
    )

    thresholds = template.get("coverage_thresholds", {})
    if coverage >= thresholds.get("excellent", 0.95):
        coverage_key = "excellent"
    elif coverage >= thresholds.get("good", 0.9):
        coverage_key = "good"
    elif coverage >= thresholds.get("fair", 0.7):
        coverage_key = "fair"
    else:
        coverage_key = "poor"

    key_insight = template.get("key_insight_phrases", {}).get(
        coverage_key, "Data coverage is adequate"
    )

    return Card(
        kpi_id=result.kpi_id,
        primitive=result.primitive,
        title=title,
        headline=headline,
        metric_value=coverage,
        key_insight=key_insight,
        confidence=_compute_confidence(result),
        category=template.get("category", "diagnostic"),
        caveats=_extract_caveats(result, template),
        template_id=template.get("template_id", ""),
    )


def _fill_anomaly_detection(
    result: ComputeResult, spec: PrimitiveSpec, template: dict
) -> Card:
    measure_label = _prettify(spec.measure_col)
    grain = _grain_label(spec.grain)
    # current_value is already max(recent z_scores) — see compute._parse_anomaly_detection
    z_score = result.current_value
    magnitude = abs(z_score) if z_score is not None else 0.0

    title = template.get("title_template", "").format(
        measure_col_label=measure_label,
    )
    headline = template.get("headline_template", "").format(
        latest_z_score_magnitude=_fmt_decimal(magnitude, 1),
        grain_label=grain,
    )

    thresholds = template.get("anomaly_thresholds", {})
    if magnitude >= thresholds.get("significant", 2.5):
        anomaly_key = "significant_anomaly"
    elif magnitude >= thresholds.get("moderate", 2.0):
        anomaly_key = "moderate_anomaly"
    else:
        anomaly_key = "normal"

    key_insight = template.get("key_insight_phrases", {}).get(
        anomaly_key, "Recent period is within normal variation"
    ).format(grain_label=grain)

    return Card(
        kpi_id=result.kpi_id,
        primitive=result.primitive,
        title=title,
        headline=headline,
        metric_value=z_score,
        segment_breakdown=result.segment_breakdown,
        key_insight=key_insight,
        confidence=_compute_confidence(result),
        category=template.get("category", "risk"),
        caveats=_extract_caveats(result, template),
        template_id=template.get("template_id", ""),
    )


# ── Dispatch ─────────────────────────────────────────────────────────────────

_FILLERS = {
    PrimitiveType.entity_concentration: _fill_entity_concentration,
    PrimitiveType.period_delta: _fill_period_delta,
    PrimitiveType.segment_mix: _fill_segment_mix,
    PrimitiveType.trend_stability: _fill_trend_stability,
    PrimitiveType.cohort_behavior: _fill_cohort_behavior,
    PrimitiveType.coverage_quality: _fill_coverage_quality,
    PrimitiveType.anomaly_detection: _fill_anomaly_detection,
}


def _make_metric_only_card(result: ComputeResult) -> Card:
    return Card(
        kpi_id=result.kpi_id,
        primitive=result.primitive,
        title=result.kpi_id[:40],
        headline=f"{result.kpi_id}: {_fmt_number(result.current_value)}",
        metric_value=result.current_value,
        comparison_value=result.comparison_value,
        confidence=_compute_confidence(result),
        category="diagnostic",
        caveats=[],
        template_id="metric_only",
    )


# ── Public API ────────────────────────────────────────────────────────────────

async def narrate(
    results: list[ComputeResult],
    specs: list[PrimitiveSpec],
) -> list[Card]:
    """
    Convert ComputeResult[] to Card[] by filling templated slots.
    Requires the matching PrimitiveSpec list to derive human-readable column labels.
    Falls back to metric-only cards if template is missing, spec is not found,
    or slot-filling raises an exception.
    """
    spec_by_id = {s.kpi_id: s for s in specs}
    cards: list[Card] = []

    for result in results:
        spec = spec_by_id.get(result.kpi_id)
        template = _TEMPLATES.get(result.primitive.value)
        filler = _FILLERS.get(result.primitive)

        if not spec or not template or not filler:
            if not spec:
                logger.warning("No spec found for kpi_id=%s — using metric-only card", result.kpi_id)
            else:
                logger.warning("No template for %s — using metric-only card", result.primitive.value)
            cards.append(_make_metric_only_card(result))
            continue

        try:
            card = filler(result, spec, template)
            cards.append(card)
        except Exception as exc:
            logger.warning(
                "Slot-filling failed for %s (%s): %s — using metric-only card",
                result.kpi_id, result.primitive.value, exc,
            )
            cards.append(_make_metric_only_card(result))

    logger.info("Narrated %d cards from %d results", len(cards), len(results))
    return cards

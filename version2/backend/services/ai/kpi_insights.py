"""
KPI Insights & Display
======================
Deterministic insight generation, dashboard story, display helpers,
and provenance building.
Extracted from intelligent_kpi_generator.py.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from .kpi_types import ColumnProfile, ColumnRole, ProvenanceInfo

logger = logging.getLogger(__name__)


# ── Phrasing variants ─────────────────────────────────────────────────────────

_DELTA_VARIANTS = [
    "{icon} {abs_delta:.1f}% {direction}",
    "{direction_word} by {abs_delta:.1f}% {icon}",
    "showing {direction_word} of {abs_delta:.1f}%",
    "{abs_delta:.1f}% {direction} from prior period",
]

_ANOMALY_VARIANTS = [
    "{severity}: {abs_z:.1f}σ deviation from baseline",
    "⚠ {severity} — {abs_z:.1f} standard deviations from norm",
    "{abs_z:.1f}σ outlier — {severity} alert",
]

_TREND_VARIANTS = [
    "{arrow} projected {expected_fmt}",
    "trending toward {expected_fmt}",
    "on track for {expected_fmt}",
    "forecast: {expected_fmt}",
]

_DRIVER_VARIANTS = [
    "top segment: {driver_name} ({driver_pct:.0f}%)",
    "{driver_name} leads ({driver_pct:.0f}% of total)",
    "{driver_pct:.0f}% driven by {driver_name}",
    "{driver_name} accounts for {driver_pct:.0f}%",
]

_ENTITY_CONCENTRATION_VARIANTS = [
    "top {entity_type} '{entity_value}' accounts for {pct:.0f}%",
    "concentrated: {entity_value} is {pct:.0f}% of total ({entity_type})",
    "{pct:.0f}% comes from the top {entity_type}: {entity_value}",
    "{entity_value} ({entity_type}) drives {pct:.0f}% of overall",
]

_ACTION_VARIANTS = [
    "What caused the {severity} change in {title}?",
    "Drill into what drove the {severity} {title} shift.",
    "Investigate the {severity} {title} movement.",
    "Analyze {title} fluctuation drivers.",
]

_ACTION_VARIANTS_DRIVER = [
    "How does {title} break down across {dim}?",
    "Break {title} down by {dim}.",
    "Show {title} split by {dim}.",
    "Analyze {title} across {dim} segments.",
]

_ACTION_VARIANTS_DELTA = [
    "Which segments drove the {delta:+.0f}% change in {title}?",
    "Dig into what caused the {delta:+.0f}% {title} shift.",
    "Which {title} segments changed the most?",
]

_ACTION_VARIANTS_DEFAULT = [
    "Show me {title} breakdown by month.",
    "Break down {title} over time.",
    "Trend {title} monthly.",
]


# ── Rotational phrasing helpers ───────────────────────────────────────────────


def _rotate_phrasing(seed: str, variants: List[str]) -> str:
    idx = abs(hash(seed)) % len(variants)
    return variants[idx]


def _direction_word(is_up: bool) -> str:
    return "increase" if is_up else "decrease"


# ── Provenance ────────────────────────────────────────────────────────────────


def build_provenance(
    profile: ColumnProfile,
    df: pl.DataFrame,
    column: str,
    aggregation: str = "sum",
    is_estimated: bool = False,
    estimate_ratio: Optional[float] = None,
    source_table: str = "upload",
    formula_override: Optional[str] = None,
) -> ProvenanceInfo:
    if formula_override:
        formula_desc = formula_override
    else:
        formula_desc = f"{aggregation.upper()}({column})"

    null_count = profile.n_nulls
    total_rows = len(df)
    rec_count = total_rows - null_count
    null_pct = (null_count / total_rows * 100) if total_rows > 0 else 0

    confidence = 1.0
    if null_pct > 30:
        confidence -= min(0.3, null_pct / 100)
    if is_estimated and estimate_ratio and estimate_ratio < 0.5:
        confidence -= 0.15
    if total_rows < 100:
        confidence -= 0.2
    elif total_rows < 1000:
        confidence -= 0.05
    confidence = max(0.0, min(1.0, confidence))

    if confidence >= 0.8:
        label = "High"
    elif confidence >= 0.5:
        label = "Medium"
    else:
        label = "Low"

    formula_with_rows = f"{formula_desc} across {rec_count:,} records"

    return ProvenanceInfo(
        source_table=source_table,
        column=column,
        aggregation=aggregation,
        formula_description=formula_with_rows,
        record_count=rec_count,
        null_count=null_count,
        null_pct=null_pct,
        total_rows=total_rows,
        downsampled=is_estimated,
        downsample_ratio=estimate_ratio,
        confidence_score=confidence,
        confidence_label=label,
        refreshed_at="",
    )


# ── Display Helpers ───────────────────────────────────────────────────────────


def _infer_format(profile: ColumnProfile, value: Any) -> str:
    name = profile.name.lower()
    if any(t in name for t in ("revenue", "sales", "cost", "amount", "price", "value", "profit", "income", "expense", "budget", "salary", "fee", "gmv")):
        return "currency"
    if profile.role == ColumnRole.RATE or profile.is_bounded_01:
        return "percentage"
    if any(t in name for t in ("rate", "ratio", "percent", "pct", "margin")):
        return "percentage"
    if any(t in name for t in ("duration", "latency", "days", "hours", "ms", "seconds")):
        return "decimal"
    if profile.is_integer_valued or profile.role == ColumnRole.COUNT:
        return "integer"
    if isinstance(value, float) and 0 <= value <= 1:
        return "percentage"
    return "decimal"


def _infer_icon(profile: ColumnProfile) -> str:
    cat = profile.business_category
    icon_map = {
        "revenue": "DollarSign", "cost": "Activity", "volume": "ShoppingCart",
        "users": "Users", "rate_metric": "Percent", "churn_risk": "Activity",
        "price": "DollarSign", "performance": "Target", "duration": "Clock", "quantity": "Package",
    }
    return icon_map.get(cat, "BarChart3")


def _build_subtitle(profile: ColumnProfile, n_rows: int, time_col: Optional[str], domain: Optional[str]) -> str:
    agg_word = {"sum": "Total", "mean": "Average", "median": "Median", "max": "Peak", "min": "Floor"}.get(profile.aggregation, profile.aggregation.title())
    domain_part = f" · {domain.replace('_', ' ').title()}" if domain and domain != "general" else ""
    return f"{agg_word} across {n_rows:,} records{domain_part}"


# ── Deterministic Insight Generation ─────────────────────────────────────────


def _generate_deterministic_insight(
    profile: ColumnProfile,
    value: float,
    comparison: Optional[Dict[str, Any]],
    anomaly: Dict[str, Any],
    trend: Dict[str, Any],
    top_driver: Optional[Dict[str, Any]],
    fmt: str,
    entity_info: Optional[Dict[str, Any]] = None,
    segment_compare: Optional[Dict[str, Any]] = None,
    business_rules: Optional[List[str]] = None,
) -> Tuple[str, str]:
    # Lazy import to avoid circular dependency — _humanize_title is in kpi_merge
    from .kpi_merge import _humanize_title, _fmt_val

    title = _humanize_title(profile)
    seed = profile.name or title
    fmt_value = _fmt_val(value, fmt)

    signals: list[str] = []

    # ── Business-rule signal ──
    matching_rules = []
    if business_rules:
        col_lower = profile.name.lower()
        for rule in business_rules:
            rule_lower = rule.lower()
            if col_lower in rule_lower or rule_lower in col_lower:
                matching_rules.append(rule[:80])
                if len(matching_rules) >= 2:
                    break
    if matching_rules:
        first_rule = matching_rules[0].rstrip(".")
        signals.insert(0, f"per business rule: {first_rule}")

    if comparison:
        delta = comparison.get("delta_percent")
        direction = comparison.get("delta_direction")
        if direction and direction != "neutral" and delta is not None:
            is_good = comparison.get("is_good", True)
            icon = "📈" if is_good else "📉"
            is_up = direction == "up"
            template = _rotate_phrasing(f"delta:{seed}", _DELTA_VARIANTS)
            signals.append(
                template.format(
                    icon=icon, abs_delta=abs(delta), direction=direction,
                    direction_word=_direction_word(is_up),
                )
            )

    if anomaly.get("is_anomaly"):
        severity = anomaly.get("anomaly_severity", "noticeable")
        z = anomaly.get("z_score", 0)
        template = _rotate_phrasing(f"anomaly:{seed}", _ANOMALY_VARIANTS)
        signals.append(template.format(severity=severity.upper(), abs_z=abs(z)))

    trend_dir = trend.get("trend_direction", "flat")
    expected = trend.get("expected_value")
    if trend_dir != "flat" and expected is not None:
        expected_fmt = _fmt_val(expected, fmt)
        arrow = "↗" if trend_dir == "up" else "↘"
        template = _rotate_phrasing(f"trend:{seed}", _TREND_VARIANTS)
        signals.append(template.format(arrow=arrow, expected_fmt=expected_fmt))

    if top_driver:
        driver_name = top_driver.get("segment", "")
        driver_pct = top_driver.get("pct_of_total", 0)
        if driver_name and driver_pct:
            template = _rotate_phrasing(f"driver:{seed}", _DRIVER_VARIANTS)
            signals.append(template.format(driver_name=driver_name, driver_pct=driver_pct))

    # ── Entity-concentration signal ──
    if entity_info:
        conc_pct = entity_info.get("entity_concentration_pct")
        top_val = entity_info.get("top_entity_value")
        ent_type = entity_info.get("entity_type", "entity")
        if conc_pct is not None and top_val and conc_pct >= 20:
            template = _rotate_phrasing(f"entity_conc:{seed}", _ENTITY_CONCENTRATION_VARIANTS)
            signals.append(
                template.format(entity_type=ent_type, entity_value=top_val, pct=conc_pct)
            )

    # ── Cross-segment comparison signal ──
    if segment_compare and not comparison:
        seg_val = segment_compare.get("delta_percent")
        seg_dir = segment_compare.get("delta_direction")
        top_seg = segment_compare.get("top_segment", "")
        bottom_seg = segment_compare.get("bottom_segment", "")
        dim = segment_compare.get("segment_dimension", "segment")
        if seg_val is not None and seg_dir and seg_val != 0:
            icon = "📈" if seg_val > 0 else "📉"
            seg_signal = f"{icon} {top_seg}s average {abs(seg_val):.0f}% {'higher' if seg_val > 0 else 'lower'} than {bottom_seg}s ({dim})"
            signals.append(seg_signal)

    if signals:
        insight = f"{title}: {fmt_value} — {'; '.join(signals)}."
    else:
        insight = f"{title} is {fmt_value}."

    action = _generate_action_prompt(title, profile, top_driver, comparison, anomaly, seed)
    return insight, action


def _generate_action_prompt(
    title: str,
    profile: ColumnProfile,
    top_driver: Optional[Dict[str, Any]],
    comparison: Optional[Dict[str, Any]],
    anomaly: Dict[str, Any],
    seed: str = "",
) -> str:
    if anomaly.get("is_anomaly"):
        severity = anomaly.get("anomaly_severity", "recent")
        template = _rotate_phrasing(f"action_anomaly:{seed}", _ACTION_VARIANTS)
        return template.format(severity=severity, title=title)
    if top_driver:
        dim = top_driver.get("dimension", "")
        if dim:
            template = _rotate_phrasing(f"action_driver:{seed}", _ACTION_VARIANTS_DRIVER)
            return template.format(title=title, dim=dim)
    if comparison and comparison.get("delta_percent"):
        delta = comparison["delta_percent"]
        if abs(delta) > 10:
            template = _rotate_phrasing(f"action_delta:{seed}", _ACTION_VARIANTS_DELTA)
            return template.format(title=title, delta=delta)
    template = _rotate_phrasing(f"action_default:{seed}", _ACTION_VARIANTS_DEFAULT)
    return template.format(title=title)


def _generate_dashboard_story(
    kpis: List[Dict[str, Any]], domain: str, period: str | None = None
) -> str:
    # Lazy import to avoid circular dependency
    from .kpi_merge import _fmt_val

    real_kpis = [k for k in kpis if not k.get("column", "").startswith("_")]
    if not real_kpis:
        real_kpis = kpis

    hero = next((k for k in real_kpis if k.get("importance") == "hero"), None)
    anomalies = [k for k in real_kpis if k.get("is_anomaly")]
    top_changes = sorted(
        [k for k in real_kpis if k.get("delta_percent") is not None],
        key=lambda k: abs(k["delta_percent"]),
        reverse=True,
    )[:2]
    top_changes = [
        k for k in top_changes
        if not (hero and k.get("column") == hero.get("column"))
    ]

    domain_label = domain.replace("_", " ").title() if domain and domain != "general" else ""

    if not hero and not anomalies and not top_changes:
        label = domain_label or "your"
        return f"Dashboard showing {len(real_kpis)} key metrics for {label} data."

    up_verbs = ["rose", "climbed", "surged", "grew", "increased", "strengthened", "jumped"]
    down_verbs = ["fell", "dropped", "declined", "contracted", "slipped", "dipped"]

    def _verb_for(delta: float, seed_tag: str) -> str:
        choices = up_verbs if delta > 0 else down_verbs
        return _rotate_phrasing(f"v:{seed_tag}:{delta:.1f}", choices)

    _PERIOD_LABELS = {
        "last_30d": "the last 30 days", "last_quarter": "last quarter",
        "last_year": "the past year", "this_month": "this month",
        "last_month": "last month", "this_quarter": "this quarter",
        "this_year": "this year", "today": "today",
        "week": "this week", "month": "this month",
        "quarter": "this quarter", "year": "this year",
    }
    period_natural = _PERIOD_LABELS.get(period, period) if period else None
    if period and period != "all" and period_natural:
        period_ref = _rotate_phrasing(
            f"pref:{period}:{domain}",
            [f"{period_natural}", f"over {period_natural}", f"during {period_natural}", f"in {period_natural}"],
        )
    else:
        period_ref = _rotate_phrasing(
            f"pref:all:{domain}",
            ["this period", "this cycle", "currently", "now"],
        )

    sentences: list[str] = []

    if hero:
        fmt_val = _fmt_val(hero.get("value", 0), hero.get("format", "number"))
        delta = hero.get("delta_percent")
        title = hero["title"]

        if delta:
            verb = _verb_for(delta, f"hv:{hero.get('column','')}")
            abs_delta = abs(delta)
            hero_structs = [
                f"{title} {verb} to {fmt_val}, up {abs_delta:.1f}% {period_ref}",
                f"{title} {verb} {abs_delta:.1f}% to {fmt_val} {period_ref}",
                f"{fmt_val} in {title}, up {abs_delta:.1f}% {period_ref}",
                f"{period_ref.capitalize()}, {title} {verb} {abs_delta:.1f}% to {fmt_val}",
            ]
            sentences.append(
                _rotate_phrasing(f"hs:{hero.get('column','')}:{delta:.1f}:{len(real_kpis)}", hero_structs)
            )
        else:
            sentences.append(f"{title} at {fmt_val} {period_ref}")

    for i, k in enumerate(top_changes):
        d = k["delta_percent"]
        verb = _verb_for(d, f"cv:{k.get('column','')}")
        abs_d = abs(d)
        connector = _rotate_phrasing(
            f"cn:{k.get('column','')}:{d:.1f}:{i}",
            [""] + ["while "] + ["and "] + ["with "] + (["meanwhile, "] if i > 0 else []),
        )
        sentences.append(f"{connector}{k['title']} {verb} {abs_d:.1f}%")

    if anomalies:
        a = anomalies[0]
        sev = a.get("anomaly_severity", "unusual")
        a_title = a["title"]
        anomaly_opts = [
            f"{sev.title()} movement detected in {a_title}.",
            f"Notable: {a_title} showing {sev} activity.",
            f"Watch {a_title} — {sev} shift this period.",
            f"{a_title} flagged for {sev} behavior.",
        ]
        sentences.append(_rotate_phrasing(f"ano:{a.get('column','')}:{sev}", anomaly_opts))

    if not sentences:
        label = domain_label or "your"
        return f"Dashboard showing {len(real_kpis)} key metrics for {label} data."

    if domain_label:
        prefix = _rotate_phrasing(
            f"dpre:{domain}:{len(real_kpis)}:{len(sentences)}",
            [f"{domain_label}: ", f"{domain_label} — ", f"{domain_label} overview: ", ""],
        )
    else:
        prefix = ""

    narrative = prefix + " ".join(sentences[:3])
    if not narrative.endswith("."):
        narrative += "."
    return narrative

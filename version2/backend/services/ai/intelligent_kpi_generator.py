"""
IntelligentKPIGenerator — Production v5 (Deterministic + Domain-Aware)
======================================================================
Thinks like a data scientist:
  1. Profile every column statistically
  2. Classify column roles
  3. Detect business domain
  4. Generate template KPIs if domain is detected
  5. Gate candidates: decision-relevance + direction-clarity + non-redundancy
  6. Select hero + primaries
  7. Compute all values, comparisons, sparklines from real data
  8. Generate deterministic insights — NO LLM calls, purely data-driven
  9. Return production-ready KPI card dicts

This module re-exports all sub-module symbols and contains the main
IntelligentKPIGenerator orchestrator class.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

# ── Import all sub-module symbols for backward compatibility ──────────────────

from .personas import get_persona

from .kpi_types import (
    _CATEGORY_PATTERNS,
    _COUNT_RE,
    _DATE_FORMATS,
    _ID_RE,
    _INTEGER_DTYPES,
    _NUMERIC_DTYPES,
    _RATE_RE,
    _TIME_RE,
    ColumnProfile,
    ColumnRole,
    DEFAULT_MAX_MEMORY_MB,
    DEFAULT_MAX_SAFE_ROWS,
    ProvenanceInfo,
    SMALL_DATASET_THRESHOLD,
)

from .kpi_profiler import (
    _classify_role,
    _coerce_string_columns,
    get_business_category,
    _profile_column,
    _profile_numeric,
    _select_aggregation,
)

from .kpi_gate import (
    _passes_gate,
    _select_candidates,
    _select_hero,
)

from .kpi_compute import (
    _compute_accent_color,
    _compute_comparison,
    _compute_kpi_value,
    _compute_rolling_baseline,
    _compute_segment_comparison,
    _compute_sparkline,
    _compute_top_driver,
    _compute_trend_forecast,
    _detect_anomaly,
    _detect_time_period,
    _find_time_column,
    _format_period_label,
)

from .kpi_domain import (
    _compute_domain_scores,
    _detect_domain_hybrid,
    _llm_classify_domain,
    dtype_abbrev,
)

from .kpi_insights import (
    _ACTION_VARIANTS,
    _ACTION_VARIANTS_DEFAULT,
    _ACTION_VARIANTS_DELTA,
    _ACTION_VARIANTS_DRIVER,
    _ANOMALY_VARIANTS,
    _build_subtitle,
    _DELTA_VARIANTS,
    _direction_word,
    _DRIVER_VARIANTS,
    _ENTITY_CONCENTRATION_VARIANTS,
    _generate_action_prompt,
    _generate_dashboard_story,
    _generate_deterministic_insight,
    _infer_format,
    _infer_icon,
    _rotate_phrasing,
    _TREND_VARIANTS,
    build_provenance,
)

from .kpi_templates import (
    _build_template_kpi_card,
    _evaluate_template_formula,
    _generate_template_kpis,
    _template_icon_name,
)

from .kpi_merge import (
    _agg_series,
    _attach_story,
    _fmt_val,
    _humanize_title,
    _inject_entity_synthetic_profiles,
    _merge_template_and_auto_kpis,
)

# ── External service imports (only needed by main class) ─────────────────────

from services.intelligence.entity_aware_profile import (
    build_entity_aware_profiles,
    EntityAwareProfile,
    profiles_by_entity,
)

from services.intelligence.root_cause_chain import (
    compute_chains_for_kpis,
    compute_chain,
    RootCauseChain,
)

from services.intelligence.decision_engine import (
    compute_decisions_for_kpis,
)

from services.intelligence.metric_graph import (
    build_metric_graph,
    attach_metric_decompositions,
)

from services.intelligence.dataset_memo import DatasetMemo, DatasetMemoCache

logger = logging.getLogger(__name__)


# ── Main Generator ────────────────────────────────────────────────────────────


class IntelligentKPIGenerator:
    """
    Production KPI generator. Thinks like a data scientist.
    Output format maps 1:1 to EnterpriseKpiCard props.

    Memory management: automatically downsamples DataFrames that exceed
    ``max_memory_mb`` to prevent OOM crashes on large datasets.
    """

    def __init__(
        self,
        max_memory_mb: int = DEFAULT_MAX_MEMORY_MB,
        max_safe_rows: int = DEFAULT_MAX_SAFE_ROWS,
    ):
        self.max_memory_mb = max_memory_mb
        self.max_safe_rows = max_safe_rows

    def _downsample_if_needed(
        self, df: pl.DataFrame
    ) -> Tuple[pl.DataFrame, bool, Optional[float]]:
        try:
            memory_mb = df.estimated_size() / (1024 * 1024)
        except Exception:
            return df, False, None

        if memory_mb <= self.max_memory_mb:
            return df, False, None

        rows = len(df)
        logger.warning(
            f"[KPI] DataFrame is {memory_mb:.0f}MB ({rows:,} rows) — "
            f"exceeds {self.max_memory_mb}MB limit. Downsampling to "
            f"{self.max_safe_rows:,} rows for OOM safety."
        )

        if rows <= self.max_safe_rows:
            return df, False, None

        # Stratified sampling
        try:
            cat_col = None
            for col in df.columns:
                dtype = df[col].dtype
                if dtype in (pl.Utf8, pl.Categorical):
                    n_unique = df[col].n_unique()
                    if 2 <= n_unique <= min(100, rows // 10):
                        cat_col = col
                        break
                elif dtype in _INTEGER_DTYPES:
                    n_unique = df[col].n_unique()
                    if 2 <= n_unique <= min(20, rows // 10):
                        cat_col = col
                        break

            if cat_col:
                n_categories = df[cat_col].n_unique()
                samples_per_cat = max(self.max_safe_rows // n_categories, 2)

                sampled_frames = []
                for category in df[cat_col].unique().to_list():
                    group = df.filter(pl.col(cat_col) == category)
                    n_to_sample = min(samples_per_cat, len(group))
                    if n_to_sample > 0:
                        sampled_frames.append(group.sample(n=n_to_sample, seed=42))

                if sampled_frames:
                    sampled = pl.concat(sampled_frames)
                    if len(sampled) < self.max_safe_rows * 0.9:
                        remaining = self.max_safe_rows - len(sampled)
                        extra = df.sample(n=min(remaining, len(df)), seed=42)
                        sampled = pl.concat([sampled, extra])
                    if len(sampled) > self.max_safe_rows:
                        sampled = sampled.sample(n=self.max_safe_rows, seed=42)
                    ratio = round(len(sampled) / rows, 4) if rows > 0 else None
                    return sampled, True, ratio
        except Exception as e:
            logger.debug(f"[KPI] Stratified sampling failed, using random: {e}")

        # Random fallback
        sampled = df.sample(n=self.max_safe_rows, seed=42)
        ratio = round(self.max_safe_rows / rows, 4) if rows > 0 else None
        return sampled, True, ratio

    async def generate_intelligent_kpis(
        self,
        df: pl.DataFrame,
        domain: Optional[str] = None,
        max_kpis: int = 6,
        dataset_metadata: Optional[Dict[str, Any]] = None,
        dataset_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        metadata = dict(dataset_metadata or {})  # copy — never mutate caller's dict
        domain = domain or metadata.get("domain_intelligence", {}).get("domain", "general")

        # ── 0e. Persona — audience-aware emphasis ──────────────────────────────
        # "same dataset, different audience → different dashboard". The persona
        # re-ranks KPI selection (gate) + hero; it is stamped on each card so
        # the UI can show which audience the dashboard is tuned for.
        persona = metadata.get("persona") or metadata.get("audience")

        # ── 0d. Comparison period (resolved from the user's question upstream) ──
        # e.g. "prior_year" | "prior_period" | "rolling_baseline" — passed to
        # _compute_comparison so the KPI cards compare against the baseline the
        # question actually asked for, instead of the data-range default.
        comparison_period = metadata.get("comparison_period") or metadata.get("comparison")

        # ── 0c. Extract business rules ──
        business_rules: Optional[list[str]] = None
        raw_rules = metadata.get("business_rules") or metadata.get("beliefs")
        if isinstance(raw_rules, list):
            business_rules = [str(r) for r in raw_rules if r]
        elif isinstance(raw_rules, str):
            business_rules = [raw_rules]
        if business_rules:
            logger.info(f"[KPI] Injected {len(business_rules)} business rules into KPI generation")

        # ── 0a. Memory guard ──
        df, is_estimated, estimate_ratio = self._downsample_if_needed(df)

        # ── 0b. Coerce string columns ──
        df = _coerce_string_columns(df)

        # ── 1. Profile all columns ──
        profiles: List[ColumnProfile] = []
        for col in df.columns:
            p = _profile_column(df, col)
            if p is not None:
                profiles.append(p)

        if not profiles:
            logger.warning("[KPI] No column profiles built — empty dataset?")
            return []

        # ── 1b. Small dataset detection ──
        is_small_dataset = len(df) < SMALL_DATASET_THRESHOLD
        if is_small_dataset:
            logger.info(
                f"[KPI] Small dataset detected ({len(df)} rows < {SMALL_DATASET_THRESHOLD}) — "
                f"skipping entity-aware profiles, LLM domain classification, and synthetic injection"
            )

        # ── 1c. Build entity-aware profiles ──
        entity_aware_profiles: List[EntityAwareProfile] = []
        entity_profile_by_col: Dict[str, EntityAwareProfile] = {}
        if not is_small_dataset:
            try:
                entity_aware_profiles = build_entity_aware_profiles(df)
                logger.info(
                    f"[KPI] Built {len(entity_aware_profiles)} entity-aware profiles "
                    f"({len(profiles_by_entity(entity_aware_profiles))} entity groups)"
                )
            except Exception as e:
                logger.warning(f"[KPI] Entity-aware profiling skipped: {e}")
            entity_profile_by_col = {p.name: p for p in entity_aware_profiles}

        # ── 1d. Inject synthetic profiles ──
        if not is_small_dataset:
            _inject_entity_synthetic_profiles(df, profiles, entity_aware_profiles, logger)

        # ── 2. Detect domain ──
        time_col = _find_time_column(df)
        if is_small_dataset:
            _, domain_template_id, _ = _compute_domain_scores(profiles)
            column_mapping = None
            if domain_template_id:
                logger.info(f"[KPI] Small dataset: pattern-only domain = {domain_template_id}")
        else:
            cached_memo = DatasetMemoCache.get(dataset_id) if dataset_id else None
            if cached_memo and cached_memo.domain_detected:
                domain_template_id = cached_memo.domain_id
                column_mapping = cached_memo.column_mapping
                logger.info(
                    f"[KPI] Using cached domain from DatasetMemo: {domain_template_id} "
                    f"(saved LLM call — originally detected via {cached_memo.domain_method})"
                )
            else:
                domain_template_id, column_mapping = await _detect_domain_hybrid(
                    profiles, df, business_rules=business_rules
                )

        # ── 2b. Build Metric Relationship Graph ──
        metric_graph = None
        if not is_small_dataset:
            try:
                metric_graph = build_metric_graph(df, profiles, domain_template_id=domain_template_id)
                if not metric_graph.empty:
                    logger.info(
                        f"[KPI] Metric graph built: {metric_graph.metric_count} metrics, "
                        f"{len(metric_graph.edges)} relationships"
                    )
            except Exception as e:
                logger.debug(f"[KPI] Metric graph skipped: {e}")

        # ── 3. Generate template KPIs ──
        template_kpis: List[Dict[str, Any]] = []
        enrichment_profile = None
        if domain_template_id:
            logger.info(f"[KPI] Domain detected: {domain_template_id} — generating template KPIs")
            template_kpis = _generate_template_kpis(
                df, domain_template_id, profiles, time_col,
                llm_column_mapping=column_mapping,
                is_estimated=is_estimated, estimate_ratio=estimate_ratio,
                entity_profile_by_col=entity_profile_by_col,
                comparison=comparison_period,
            )
            for tk in template_kpis:
                tk["_template"] = domain_template_id

            # Stage 2 enrichment
            if not is_small_dataset:
                try:
                    from services.domain.domain_enrichment import enrich_domain
                    enrichment_profile = await enrich_domain(profiles, df, domain_template_id)
                    if enrichment_profile:
                        profile_dict = enrichment_profile.to_dict()
                        for tk in template_kpis:
                            tk["_domain_profile"] = profile_dict
                        logger.info(
                            f"[KPI] Stage 2 enrichment attached: "
                            f"{len(profile_dict['column_semantics'])} semantics, "
                            f"{len(profile_dict['suggested_metrics'])} metrics, "
                            f"{len(profile_dict['analytical_intents'])} intents"
                        )
                except Exception as e:
                    logger.warning(f"[KPI] Stage 2 enrichment skipped: {e}")

        # ── 4. Select candidates via gate ──
        candidates = _select_candidates(
            profiles, max_kpis, business_rules=business_rules, persona=persona
        )

        if not candidates:
            if template_kpis:
                logger.info(f"[KPI] No gate-passed candidates, using {len(template_kpis)} template KPIs")
                dash_story = _generate_dashboard_story(template_kpis, domain or "general", None)
                return _attach_story(template_kpis, dash_story, domain)
            logger.warning("[KPI] No candidates passed the KPI gate")
            return self._domain_aware_fallback(
                df, profiles, domain, max_kpis, metadata,
                is_estimated=is_estimated, estimate_ratio=estimate_ratio,
            )

        # ── 5. Surprising patterns engine ──
        surprise_cards: List[Dict[str, Any]] = []
        if not is_small_dataset:
            from .surprising_patterns import SurprisingPatternsEngine
            surprising_patterns_engine = SurprisingPatternsEngine(max_insights=4)
            surprise_insights = surprising_patterns_engine.discover_all(df, profiles, time_col)
            surprise_cards = [insight.to_card() for insight in surprise_insights]

        # ── 6. Build final KPI card dicts ──
        kpis: List[Dict[str, Any]] = []
        for profile in candidates:
            try:
                is_synthetic = profile.name.startswith("_")
                if is_synthetic:
                    value = profile.primary_value or 0
                else:
                    value = _compute_kpi_value(df, profile)
                comparison = _compute_comparison(df, profile, time_col, comparison_period)
                sparkline = _compute_sparkline(df, profile, time_col)
                fmt = _infer_format(profile, value)
                icon = _infer_icon(profile)
                subtitle = _build_subtitle(profile, len(df), time_col, domain)

                delta_dir = comparison["delta_direction"] if comparison else None
                accent = _compute_accent_color(profile.importance, delta_dir, profile.polarity)

                time_period = _detect_time_period(df, profile, time_col)
                period_values = time_period.get("period_values", [])

                baseline = _compute_rolling_baseline(period_values, window=3)
                baseline_value = baseline.get("baseline_value")
                baseline_std = baseline.get("baseline_std")

                anomaly = _detect_anomaly(value, baseline_value or 0, baseline_std or 0)
                trend = _compute_trend_forecast(period_values)
                top_driver = _compute_top_driver(df, profile.name) if not is_synthetic else None

                vs_baseline_pct = None
                if baseline_value and baseline_value != 0:
                    vs_baseline_pct = round(((value - baseline_value) / abs(baseline_value)) * 100, 1)

                vs_previous_pct = None
                prev_period_value = time_period.get("previous_period_value")
                if prev_period_value and prev_period_value != 0:
                    vs_previous_pct = round(((value - prev_period_value) / abs(prev_period_value)) * 100, 1)

                provenance = build_provenance(
                    profile=profile,
                    df=df,
                    column=profile.name,
                    aggregation=profile.aggregation,
                    is_estimated=is_estimated,
                    estimate_ratio=estimate_ratio,
                    source_table=metadata.get("name", "upload"),
                )

                entity_prof = entity_profile_by_col.get(profile.name)
                entity_type = entity_prof.entity_type if entity_prof else "Unknown"
                entity_concentration = entity_prof.entity_concentration_pct if entity_prof else None
                top_entity = entity_prof.top_entity_value if entity_prof else None
                entity_cardinality = entity_prof.entity_cardinality if entity_prof else None
                is_entity_attribute = entity_prof.is_entity_attribute if entity_prof else False

                entity_info_for_insight = {
                    "entity_type": entity_type,
                    "entity_concentration_pct": entity_concentration,
                    "top_entity_value": top_entity,
                    "entity_cardinality": entity_cardinality,
                } if entity_prof else None

                segment_comparison = _compute_segment_comparison(
                    df, profile.name, profile.polarity,
                ) if not comparison and not is_synthetic else None

                insight, action = _generate_deterministic_insight(
                    profile, value, comparison, anomaly, trend, top_driver, fmt,
                    entity_info=entity_info_for_insight,
                    business_rules=business_rules,
                    segment_compare=segment_comparison,
                )

                bench_val = profile.col_p75
                bench_label = "Top 25%" if bench_val else None

                kpi = {
                    "type": "kpi",
                    "column": profile.name,
                    "aggregation": profile.aggregation,
                    "importance": profile.importance,
                    "persona": persona,
                    "persona_label": get_persona(persona)["label"] if persona else None,
                    "business_category": profile.business_category,
                    "title": _humanize_title(profile),
                    "subtitle": subtitle,
                    "value": value,
                    "format": fmt,
                    "icon": icon,
                    "record_count": len(df) - profile.n_nulls,
                    "comparison_value": comparison["comparison_value"] if comparison else None,
                    "comparison_label": comparison["comparison_label"] if comparison else None,
                    "delta_percent": comparison["delta_percent"] if comparison else None,
                    "delta_direction": comparison["delta_direction"] if comparison else None,
                    "is_delta_positive": comparison["is_delta_positive"] if comparison else (profile.polarity == "higher_is_better"),
                    "accent_color": accent,
                    "sparkline_data": sparkline,
                    "benchmark_value": round(bench_val, 2) if bench_val else None,
                    "benchmark_label": bench_label,
                    "benchmark_text": f"{bench_label}: {_fmt_val(bench_val, fmt)}" if bench_val and bench_label else None,
                    "ai_suggestion": insight,
                    "action_prompt": action,
                    "dashboard_story": "",
                    "archetype": domain or "general",
                    "col_p75": profile.col_p75,
                    "col_median": profile.col_median,
                    "polarity": profile.polarity,
                    "period_label": time_period.get("period_label", ""),
                    "previous_period_label": time_period.get("previous_period_label", ""),
                    "period_type": time_period.get("period_type", ""),
                    "baseline_value": baseline_value,
                    "baseline_label": "3-month avg" if time_period.get("period_type") == "month" else "baseline",
                    "vs_baseline_pct": vs_baseline_pct,
                    "baseline_std": baseline_std,
                    "normal_range_low": baseline.get("normal_range_low"),
                    "normal_range_high": baseline.get("normal_range_high"),
                    "is_anomaly": anomaly.get("is_anomaly", False),
                    "anomaly_direction": anomaly.get("anomaly_direction", "normal"),
                    "z_score": anomaly.get("z_score", 0.0),
                    "anomaly_severity": anomaly.get("anomaly_severity", "normal"),
                    "expected_value": trend.get("expected_value"),
                    "trend_direction": trend.get("trend_direction", "flat"),
                    "top_driver": top_driver,
                    "vs_previous_pct": vs_previous_pct,
                    "entity_type": entity_type,
                    "entity_concentration_pct": entity_concentration,
                    "top_entity_value": top_entity,
                    "entity_cardinality": entity_cardinality,
                    "is_entity_attribute": is_entity_attribute,
                }
                kpi["is_estimated"] = is_estimated
                kpi["estimate_ratio"] = estimate_ratio
                kpi["provenance"] = provenance.to_dict()
                kpis.append(kpi)
            except Exception as e:
                logger.error(f"[KPI] Failed to build card for '{profile.name}': {e}")

        # ── 7. Merge template + auto KPIs ──
        merged = _merge_template_and_auto_kpis(template_kpis, kpis, max_kpis)

        # ── 8. Root cause chains ──
        if not is_small_dataset:
            try:
                merged = compute_chains_for_kpis(df, merged, time_col=time_col)
            except Exception as e:
                logger.warning(f"[KPI] Root cause chain computation skipped: {e}")

        # ── 9. Decision engine ──
        if not is_small_dataset:
            try:
                merged = compute_decisions_for_kpis(merged)
            except Exception as e:
                logger.warning(f"[KPI] Decision engine skipped: {e}")

        # ── 9b. Metric decomposition ──
        if metric_graph is not None and not metric_graph.empty:
            try:
                merged = attach_metric_decompositions(merged, metric_graph, df, time_col=time_col)
            except Exception as e:
                logger.warning(f"[KPI] Metric decomposition skipped: {e}")

        # ── 10. Attach enrichment profile ──
        if enrichment_profile and merged:
            profile_dict = enrichment_profile.to_dict()
            merged[0]["domain_profile"] = profile_dict
            merged[0]["nl_summary"] = profile_dict.get("natural_language_summary", "")

        dash_story = _generate_dashboard_story(merged, domain or "general")
        for k in merged:
            if k.get("importance") == "hero":
                k["dashboard_story"] = dash_story

        merged.extend(surprise_cards)

        logger.info(
            f"[KPI] Generated {len(merged)} items (template={len(template_kpis)}, "
            f"auto={len(kpis)}, surprising={len(surprise_cards)}) for domain='{domain}'"
        )
        return merged

    def _domain_aware_fallback(
        self,
        df: pl.DataFrame,
        profiles: List[ColumnProfile],
        domain: str,
        max_kpis: int,
        metadata: Dict[str, Any],
        is_estimated: bool = False,
        estimate_ratio: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        logger.info("[KPI] Using domain-aware fallback")
        numeric = [
            p for p in profiles
            if p.role in (ColumnRole.MEASURE, ColumnRole.COUNT, ColumnRole.RATE)
            and p.null_pct < 50
            and p.primary_value is not None
        ]
        if not numeric:
            return []

        numeric.sort(key=lambda p: abs(p.primary_value or 0), reverse=True)
        top = numeric[:max_kpis]
        top[0].importance = "hero"
        for p in top[1:]:
            p.importance = "high"

        time_col = _find_time_column(df)
        kpis = []
        for p in top:
            try:
                value = _compute_kpi_value(df, p)
                comparison = _compute_comparison(df, p, time_col, comparison_period)
                sparkline = _compute_sparkline(df, p, time_col)
                fmt = _infer_format(p, value)
                delta_dir = comparison["delta_direction"] if comparison else None
                accent = _compute_accent_color(p.importance, delta_dir, p.polarity)

                insight, action = _generate_deterministic_insight(
                    p, value, comparison,
                    {"is_anomaly": False, "anomaly_direction": "normal", "z_score": 0.0, "anomaly_severity": "normal"},
                    {}, None, fmt,
                )

                provenance = build_provenance(
                    profile=p, df=df, column=p.name, aggregation=p.aggregation,
                    is_estimated=is_estimated, estimate_ratio=estimate_ratio, source_table="upload",
                )

                kpis.append({
                    "type": "kpi",
                    "column": p.name,
                    "provenance": provenance.to_dict(),
                    "aggregation": p.aggregation,
                    "importance": p.importance,
                    "is_estimated": is_estimated,
                    "estimate_ratio": estimate_ratio,
                    "title": _humanize_title(p),
                    "subtitle": _build_subtitle(p, len(df), time_col, domain),
                    "value": value,
                    "format": fmt,
                    "icon": _infer_icon(p),
                    "record_count": len(df) - p.n_nulls,
                    "comparison_value": comparison["comparison_value"] if comparison else None,
                    "comparison_label": comparison["comparison_label"] if comparison else None,
                    "delta_percent": comparison["delta_percent"] if comparison else None,
                    "delta_direction": comparison["delta_direction"] if comparison else None,
                    "is_delta_positive": p.polarity == "higher_is_better",
                    "accent_color": accent,
                    "sparkline_data": sparkline,
                    "ai_suggestion": insight,
                    "action_prompt": action,
                })
            except Exception:
                continue

        dash_story = _generate_dashboard_story(kpis, domain)
        return _attach_story(kpis, dash_story, domain)

    async def generate_single_kpi(
        self,
        df: pl.DataFrame,
        column: str,
        aggregation: str = "sum",
        custom_title: Optional[str] = None,
        dataset_metadata: Optional[Dict[str, Any]] = None,
        comparison: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            df, is_estimated, estimate_ratio = self._downsample_if_needed(df)
            df = _coerce_string_columns(df)

            if column not in df.columns:
                return None

            clean = df[column].drop_nulls()
            if len(clean) == 0:
                return None

            value = _agg_series(df[column], aggregation)

            fmt = "number"
            if any(kw in column.lower() for kw in ["revenue", "cost", "price", "amount", "total"]):
                fmt = "currency"
            elif any(kw in column.lower() for kw in ["rate", "percent", "ratio"]):
                fmt = "percentage"

            polarity = "higher_is_better"
            if any(kw in column.lower() for kw in ["cost", "churn", "error", "loss", "defect"]):
                polarity = "lower_is_better"

            profile = ColumnProfile(
                name=column, aggregation=aggregation, role=ColumnRole.MEASURE,
                importance="medium", business_category="general", polarity=polarity,
                col_p75=None, col_median=None,
                n_nulls=int(df[column].null_count()), n_rows=len(df), n_unique=int(df[column].n_unique()),
            )
            title = custom_title or _humanize_title(profile)

            time_col = _find_time_column(df)
            sparkline = _compute_sparkline(df, profile, time_col)

            # Comparison: honor the question-resolved baseline when given;
            # otherwise fall back to the first-half split (backward compatible).
            comp = None
            if comparison in ("prior_year", "prior_period", "rolling_baseline"):
                comp = _compute_comparison(df, profile, time_col, comparison)
            if comp is None:
                mid = len(df) // 2
                v1_val = _agg_series(df[:mid][column], aggregation)
                v2_val = _agg_series(df[mid:][column], aggregation)
                delta_pct = round(((v2_val - v1_val) / abs(v1_val)) * 100, 1) if v1_val else None
                comp = {
                    "comparison_value": v1_val,
                    "comparison_label": "vs previous period",
                    "delta_percent": delta_pct,
                    "delta_direction": "up" if delta_pct and delta_pct > 0 else ("down" if delta_pct and delta_pct < 0 else "neutral"),
                    "is_delta_positive": polarity == "higher_is_better",
                    "is_good": (delta_pct or 0) > 0 if polarity == "higher_is_better" else (delta_pct or 0) < 0,
                } if delta_pct is not None else None

            sparkline_vals = sparkline.get("data", [])
            baseline = _compute_rolling_baseline(sparkline_vals, window=3)
            baseline_value = baseline.get("baseline_value")
            baseline_std = baseline.get("baseline_std")
            vs_baseline_pct = (
                round(((value - baseline_value) / abs(baseline_value)) * 100, 1)
                if baseline_value and baseline_value != 0 else None
            )

            anomaly = _detect_anomaly(value, baseline_value or 0, baseline_std or 0)
            trend = _compute_trend_forecast(sparkline_vals)
            top_driver = _compute_top_driver(df, column)
            time_period = _detect_time_period(df, profile, time_col)

            insight, action = _generate_deterministic_insight(
                profile, value, comp, anomaly, trend, top_driver, fmt,
            )

            return {
                "type": "kpi",
                "column": column,
                "aggregation": aggregation,
                "importance": "medium",
                "business_category": "general",
                "title": title,
                "subtitle": time_period.get("period_label", ""),
                "value": value,
                "format": fmt,
                "icon": "BarChart3",
                "record_count": len(clean),
                "is_estimated": is_estimated,
                "estimate_ratio": estimate_ratio,
                "comparison_value": comp["comparison_value"] if comp else None,
                "comparison_label": comp["comparison_label"] if comp else None,
                "delta_percent": comp["delta_percent"] if comp else None,
                "delta_direction": comp["delta_direction"] if comp else None,
                "is_delta_positive": comp["is_delta_positive"] if comp else True,
                "accent_color": _compute_accent_color("medium", comp["delta_direction"] if comp else "down", polarity),
                "sparkline_data": sparkline,
                "benchmark_value": None,
                "benchmark_label": None,
                "benchmark_text": None,
                "ai_suggestion": insight,
                "action_prompt": action,
                "dashboard_story": "",
                "archetype": "general",
                "col_p75": None,
                "col_median": None,
                "polarity": polarity,
                "period_label": time_period.get("period_label", ""),
                "previous_period_label": time_period.get("previous_period_label", ""),
                "period_type": time_period.get("period_type", ""),
                "baseline_value": baseline_value,
                "baseline_label": "baseline",
                "vs_baseline_pct": vs_baseline_pct,
                "baseline_std": baseline_std,
                "normal_range_low": baseline.get("normal_range_low"),
                "normal_range_high": baseline.get("normal_range_high"),
                "is_anomaly": anomaly.get("is_anomaly", False),
                "anomaly_direction": anomaly.get("anomaly_direction", "normal"),
                "z_score": anomaly.get("z_score", 0.0),
                "anomaly_severity": anomaly.get("anomaly_severity", "normal"),
                "expected_value": trend.get("expected_value"),
                "trend_direction": trend.get("trend_direction", "flat"),
                "top_driver": top_driver,
                "vs_previous_pct": comp["delta_percent"] if comp else None,
            }
        except Exception as e:
            logger.debug(f"[KPI] Single KPI generation failed for '{column}': {e}")
            return None


# Singleton
intelligent_kpi_generator = IntelligentKPIGenerator()

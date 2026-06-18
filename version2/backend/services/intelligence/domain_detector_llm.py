"""
intelligence/domain_detector_llm.py — LLM-based domain enrichment (Layer 3)

Consumes RawProfilingResult (pure facts) and calls an LLM to classify the
dataset domain by reasoning from actual data values — not just column names.

This is the enrichment layer that runs ON TOP OF the deterministic pipeline.
The deterministic domain_hypothesis.py always runs first and produces
candidates. The LLM adds a verdict with confidence, reasoning, and optional
column mapping.

Design:
  - Single LLM call, cheap model (Mistral Small 3.2), <1s
  - Returns LLMDomainVerdict — structured enrichment, NOT a replacement
  - On failure → deterministic fallback (DomainHypothesisResult with no llm_verdict)
  - No DataFrame access needed — all stats are in RawColumnProfile already
"""

from __future__ import annotations

import logging
from typing import Optional

import polars as pl

from services.profiling.models import RawColumnProfile, RawProfilingResult

from .models import (
    DomainCandidate,
    DomainHypothesisResult,
    LLMDomainVerdict,
)

logger = logging.getLogger(__name__)


# ── Dtype abbreviation for the prompt ────────────────────────────────────────


def _dtype_abbrev(dtype_str: str) -> str:
    """Shorten dtype string for prompt display."""
    if "Int" in dtype_str or "UInt" in dtype_str or "Float" in dtype_str:
        return "numeric"
    if "Date" in dtype_str or "Datetime" in dtype_str or "Duration" in dtype_str:
        return "datetime"
    if "Utf8" in dtype_str or "String" in dtype_str or "Categorical" in dtype_str:
        return "text"
    if "Bool" in dtype_str:
        return "boolean"
    return dtype_str[:12]


# ── LLM Domain Detection Prompt ─────────────────────────────────────────────

DOMAIN_DETECTION_PROMPT = """\
You are a data domain classifier. Your job is to analyze a dataset's columns and describe what domain it belongs to.

HOW TO REASON:
1. Sample values and VALUE RANGES are your strongest signal — trust them over column names.
   - A "value" column with samples [32000, 28500, 48000] and range [5000, 180000] is NOT the same as "value" with samples [0.023, -0.015, 0.009]
   - A "score" column that ranges [0, 100] with samples [85, 72, 91] is an exam/test score, not a medical score
2. For categorical columns, the VALUE DISTRIBUTION tells you more than the category names.
   - fuelType: Petrol(65%), Diesel(25%) is clearly different from fuelType: E10(40%), E85(30%), Diesel(30%)
3. Column NAMES are your weakest signal — disambiguate using the actual data values.
4. Describe what the data IS — what business process it captures, what entities it records.
5. If you cannot determine the domain with high confidence, set domain_id to "unknown" and explain what single piece of information would resolve the ambiguity.
6. If the data matches a well-known pattern, include a domain_id (e.g. "automotive-metrics", "ecommerce-metrics", "healthcare-metrics"). Otherwise set domain_id to "unknown".

Output a JSON object with these fields:
- domain: a SHORT description of what this data is (3-8 words, never a full sentence). This is the primary output.
- domain_id: optional standard identifier if one clearly matches (use "unknown" if none fits)
- confidence: 0.0-1.0 score
- reasoning: 1-2 sentences explaining the key signals that determined the classification
- column_mapping: dictionary mapping template column types to actual column names (empty object if uncertain)

DATASET COLUMNS:
{columns_str}

OUTPUT (valid JSON only):
{{
  "domain": "vehicle listings with pricing and specs",
  "domain_id": "automotive-metrics",
  "confidence": 0.92,
  "reasoning": "Price range $5K-$185K with mileage, engine_size, transmission, and fuel type distribution (Petrol 65%, Diesel 25%) — standard vehicle listing columns.",
  "column_mapping": {{
    "mileage": "mileage",
    "price": "price"
  }}
}}

Return ONLY valid JSON. No markdown fences. No text before or after."""


# ── Helpers to build column info from RawProfilingResult ─────────────────────


def _build_column_lines(result: RawProfilingResult) -> str:
    """Build the column info string for the LLM prompt from RawProfilingResult.

    Uses stats, sample_values, and top_values already computed by the
    profiling engine — no DataFrame access needed.
    """
    lines: list[str] = []

    for c in result.columns:
        dtype_short = _dtype_abbrev(c.dtype)
        null_pct = round(c.cardinality.null_pct, 1)
        unique = c.cardinality.unique_count
        total = c.cardinality.total_count

        # Sample values
        sample_str = ""
        if c.sample_values:
            samples = [v[:60] for v in c.sample_values if v]
            if samples:
                sample_str = f"  samples: {', '.join(samples[:3])}"

        # Distribution for low-cardinality text columns
        dist_str = ""
        if c.top_values and 2 <= unique <= 15 and "Utf8" in c.dtype:
            total_top = sum(v.count for v in c.top_values)
            pairs = []
            for tv in c.top_values[:8]:
                pct = round(tv.count / max(total_top, 1) * 100)
                pairs.append(f"{tv.value}({pct}%)")
            if pairs:
                dist_str = f"  distribution: {', '.join(pairs)}"

        # Stats line differs by type
        if c.stats and c.stats.col_min is not None:
            stats_line = (
                f"  range: [{c.stats.col_min:.2f}, {c.stats.col_max:.2f}]  "
                f"mean: {c.stats.col_mean:.2f}  med: {c.stats.col_median:.2f}  "
                f"cardinality: {unique}/{total}  nulls: {null_pct}%"
            )
        else:
            stats_line = (
                f"  cardinality: {unique}/{total}  nulls: {null_pct}%"
            )

        lines.append(f"- {c.name} [{dtype_short}]")
        lines.append(stats_line)
        if sample_str:
            lines.append(sample_str)
        if dist_str:
            lines.append(dist_str)

    return "\n".join(lines)


# ── LLM Domain Detector ─────────────────────────────────────────────────────


class LLMDomainDetector:
    """LLM-based domain enrichment.

    Consumes RawProfilingResult (facts) and returns a DomainHypothesisResult
    with an LLMDomainVerdict attached. The deterministic domain matcher
    (DomainHypothesisEngine) runs separately — this is enrichment, not
    replacement.

    Usage:
        llm_result = await llm_domain_detector.detect(profiling_result)
        if llm_result.llm_verdict:
            intelligence_result.domain.llm_verdict = llm_result.llm_verdict
    """

    async def detect(
        self,
        profiling_result: RawProfilingResult,
        df: Optional[pl.DataFrame] = None,
    ) -> DomainHypothesisResult:
        """Classify domain using an LLM with data value context.

        Args:
            profiling_result: RawProfilingResult from the profiling engine.
                             Contains all stats, sample values, and
                             distributions needed for the prompt.
            df: Optional DataFrame (not used — all data is in profiling_result).

        Returns:
            DomainHypothesisResult with llm_verdict set if the LLM
            returned a valid classification. On failure, returns an empty
            result with method="llm_failed".
        """
        # Build column info from profiling result (no DataFrame needed)
        columns_str = _build_column_lines(profiling_result)

        prompt = DOMAIN_DETECTION_PROMPT.format(columns_str=columns_str)

        try:
            from services.kpi.templates import ALL_TEMPLATES
        except ImportError:
            ALL_TEMPLATES = {}

        try:
            from services.llm_router import llm_router

            response = await llm_router.call(
                prompt=prompt,
                model_role="intent_engine",
                expect_json=True,
                temperature=0.1,
                is_conversational=False,
                max_tokens=800,
            )

            if not isinstance(response, dict) or "domain_id" not in response:
                logger.warning("[LLMDomain] LLM returned invalid or unparseable response")
                return DomainHypothesisResult(method="llm_failed")

            domain_id = response.get("domain_id", "") or ""
            confidence = float(response.get("confidence", 0.0) or 0.0)
            column_mapping = response.get("column_mapping", {}) or {}
            domain_desc = response.get("domain", "") or ""
            reasoning = response.get("reasoning", "") or ""

            # Build column mapping: map template type names to actual column names
            col_names = {c.name.lower(): c.name for c in profiling_result.columns}
            valid_mapping: dict[str, str] = {}
            for k, v in column_mapping.items():
                if v in profiling_result.column_by_name(v):
                    valid_mapping[k] = v
                elif v.lower() in col_names:
                    valid_mapping[k] = col_names[v.lower()]

            # Verify: does domain_id match a known template?
            matches_template = domain_id in ALL_TEMPLATES and confidence >= 0.5

            if matches_template:
                # LLM returned a known template — create a domain candidate for it
                domain_name = domain_id.replace("-metrics", "").replace("-", " ").title()

                # Find which columns matched from the mapping
                matched_cols = list(valid_mapping.values())

                candidate = DomainCandidate(
                    domain_id=domain_id,
                    domain_name=domain_name,
                    score=confidence * 100,  # normalize to 0-100 scale
                    matched_columns=matched_cols,
                    matched_required=len(matched_cols),
                    matched_optional=0,
                    total_required=len(ALL_TEMPLATES[domain_id].required_columns),
                )

                verdict = LLMDomainVerdict(
                    domain=domain_desc,
                    domain_id=domain_id,
                    confidence=confidence,
                    reasoning=reasoning,
                    column_mapping=valid_mapping,
                )

                logger.info(
                    "[LLMDomain] Classified: %s (confidence=%.2f, reasoning='%s', mapped=%d cols)",
                    domain_id, confidence, reasoning[:80], len(valid_mapping),
                )

                return DomainHypothesisResult(
                    candidates=[candidate],
                    top_candidate=candidate,
                    method="llm",
                    llm_verdict=verdict,
                )

            # LLM returned a free-form description but no template match
            # Still capture the verdict for display
            verdict = LLMDomainVerdict(
                domain=domain_desc,
                domain_id=domain_id,
                confidence=confidence,
                reasoning=reasoning,
                column_mapping=valid_mapping,
            )

            logger.info(
                "[LLMDomain] Free-form: '%s' (domain_id='%s', confidence=%.2f) — no template match",
                domain_desc, domain_id, confidence,
            )

            return DomainHypothesisResult(
                method="llm",
                llm_verdict=verdict,
            )

        except Exception as e:
            logger.warning(f"[LLMDomain] LLM call failed: {e}")
            return DomainHypothesisResult(method="llm_failed")


# Singleton
llm_domain_detector = LLMDomainDetector()

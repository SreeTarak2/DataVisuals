"""
InsightReflectionAgent — Self-improving critic for AI-generated content quality.

Architecture:
    QualityScorer           → Rates insights on novelty, actionability, specificity, correctness
    PromptAdjuster          → Adjusts prompt temperature / constraints based on failure patterns
    FeedbackLoopStore       → Persists quality scores + adjustments per dataset type
    ThresholdCalibrator     → Adjusts confidence thresholds based on historical accuracy

Design principles:
    - Zero-latency scoring: uses heuristics + lightweight LLM call (not heavy models)
    - Persistent learning: stores per-dataset-type quality history for trend analysis
    - Non-blocking: runs as fire-and-forget after the primary response is sent
    - Conservative: never lowers quality without evidence; never raises thresholds too aggressively
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class ReflectionScore:
    """Quality assessment for a single AI-generated output."""

    overall_score: float = 0.0
    novelty: float = 0.0
    actionability: float = 0.0
    specificity: float = 0.0
    correctness: float = 0.0
    failure_modes: list[str] = field(default_factory=list)
    prompt_adjustments: dict = field(default_factory=dict)
    threshold_updates: dict = field(default_factory=dict)


@dataclass
class QualityHistoryEntry:
    """A single entry in the quality feedback history."""

    dataset_type: str
    output_type: str  # "kpi", "insight", "chart", "narrative"
    overall_score: float
    dimensions: dict
    failure_modes: list[str]
    prompt_adjustments: dict
    timestamp: str = ""


# ── Prompt ───────────────────────────────────────────────────────────────────

QUALITY_SCORE_PROMPT = """\
<role>You are a quality assurance specialist evaluating AI-generated data insights.</role>
<instructions>
Evaluate the quality of the following AI-generated output.

## User Query
{user_query}

## AI Output
{ai_output}

## Dataset Context (truncated)
{schema_context}

## Task
Score the output on four dimensions (0.0–1.0):

1. **novelty**: Does this provide new information, or is it generic/obvious?
   - 1.0 = genuinely surprising, non-obvious insight
   - 0.5 = somewhat interesting but expected
   - 0.0 = generic statement anyone could make

2. **actionability**: Can the user act on this insight?
   - 1.0 = specific recommendation with concrete next steps
   - 0.5 = general guidance without specifics
   - 0.0 = purely informational, no action implied

3. **specificity**: How specific and data-grounded is it?
   - 1.0 = cites exact numbers, columns, thresholds
   - 0.5 = mentions data vaguely
   - 0.0 = no data references at all

4. **correctness**: Does the output correctly reflect the data?
   - 1.0 = accurate, well-reasoned
   - 0.5 = minor inaccuracies
   - 0.0 = contains factual errors or hallucinations

Also identify any **failure modes** from these options:
- "overly_generic": Could apply to any dataset
- "missing_temporal_context": No time reference when relevant
- "overconfident_claim": Makes strong claim without data support
- "hallucination": References columns or values not in schema
- "vague_recommendation": Suggests action without specifics
- "ignores_null_data": Draws conclusions ignoring missing values
- "no_business_context": Technical but not business-relevant

Return a JSON object with:
{{
    "novelty": 0.0-1.0,
    "actionability": 0.0-1.0,
    "specificity": 0.0-1.0,
    "correctness": 0.0-1.0,
    "failure_modes": ["list", "of", "identified", "modes"],
    "rationale": "Brief explanation of ratings"
}}
</instructions>"""


# ── InsightReflectionAgent ───────────────────────────────────────────────────


class InsightReflectionAgent:
    """
    Self-improving critic that evaluates AI output quality and adjusts prompts.

    Usage:
        agent = InsightReflectionAgent()
        score = await agent.reflect(
            user_query="...",
            ai_output="...",
            schema_context="...",
            dataset_type="ecommerce",
            output_type="kpi",
        )
        # score.overall_score, score.failure_modes, score.prompt_adjustments
    """

    # ── Quality thresholds ───────────────────────────────────────────────────
    EXCELLENT_THRESHOLD = 0.85
    GOOD_THRESHOLD = 0.70
    POOR_THRESHOLD = 0.50
    FAIL_THRESHOLD = 0.30

    # ── Default adjustments per failure mode ──────────────────────────────────
    FAILURE_ADJUSTMENTS: dict[str, dict[str, Any]] = {
        "overly_generic": {
            "add_examples": True,
            "temperature_change": -0.15,
            "instruction_add": "Be specific — cite exact columns and values.",
        },
        "missing_temporal_context": {
            "add_examples": True,
            "temperature_change": -0.05,
            "instruction_add": "Include time-based context when discussing trends.",
        },
        "overconfident_claim": {
            "temperature_change": -0.1,
            "instruction_add": "Qualify claims: use 'suggests', 'indicates', or confidence intervals.",
        },
        "hallucination": {
            "temperature_change": -0.2,
            "instruction_add": "Only reference columns explicitly listed in the schema. Never invent data.",
        },
        "vague_recommendation": {
            "add_examples": True,
            "temperature_change": -0.1,
            "instruction_add": "Every recommendation must include a specific next step and expected outcome.",
        },
        "ignores_null_data": {
            "instruction_add": "Note missing values and their impact on conclusions.",
        },
        "no_business_context": {
            "add_examples": True,
            "temperature_change": -0.1,
            "instruction_add": "Frame findings in business terms: what decision does this inform?",
        },
    }

    def __init__(self):
        self._llm_router = None
        self._quality_history: dict[str, list[QualityHistoryEntry]] = {}
        self._current_thresholds: dict[str, dict[str, float]] = {}

    @property
    def llm_router(self):
        if self._llm_router is None:
            from services.llm_router import llm_router
            self._llm_router = llm_router
        return self._llm_router

    @property
    def belief_store(self):
        """Lazy-loaded belief store for novelty checking."""
        try:
            from services.agents.belief_store import get_belief_store
            return get_belief_store()
        except Exception:
            return None

    async def reflect(
        self,
        user_query: str = "",
        ai_output: str = "",
        schema_context: str = "",
        dataset_type: str = "general",
        output_type: str = "insight",
        user_id: str = "",
    ) -> ReflectionScore:
        """
        Evaluate an AI-generated output and produce quality scores + adjustments.

        Args:
            user_query: The original user question
            ai_output: The AI-generated response
            schema_context: Dataset schema context (truncated)
            dataset_type: Domain/type of dataset (e.g., "ecommerce", "finance")
            output_type: Type of output ("kpi", "insight", "chart", "narrative")
            user_id: User ID for belief store novelty check

        Returns:
            ReflectionScore with quality dimensions, failure modes, and adjustments
        """
        if not ai_output or len(ai_output.strip()) < 10:
            return ReflectionScore(
                overall_score=0.0,
                failure_modes=["empty_output"],
                prompt_adjustments={"instruction_add": "Ensure output is non-empty and substantive."},
            )

        # ── Step 1: Score quality via LLM ───────────────────────────────────
        quality_result = await self._score_quality(user_query, ai_output, schema_context)

        # ── Step 2: Check novelty against belief store ───────────────────────
        novelty_boost = 0.0
        if user_id and self.belief_store:
            try:
                surprisal, _ = await self.belief_store.calculate_semantic_surprisal(
                    user_id, ai_output[:500]
                )
                # Higher surprisal = more novel
                novelty_boost = min(0.2, surprisal * 0.2)
            except Exception as e:
                logger.debug(f"[Reflection] Novelty check failed: {e}")

        # ── Step 3: Compute overall score ────────────────────────────────────
        novelty = min(1.0, quality_result.get("novelty", 0.5) + novelty_boost)
        actionability = quality_result.get("actionability", 0.5)
        specificity = quality_result.get("specificity", 0.5)
        correctness = quality_result.get("correctness", 0.5)
        failure_modes = quality_result.get("failure_modes", [])

        overall = round((novelty * 0.25 + actionability * 0.30 + specificity * 0.25 + correctness * 0.20), 2)

        # ── Step 4: Determine prompt adjustments ─────────────────────────────
        prompt_adjustments = self._compute_adjustments(failure_modes, overall)

        # ── Step 5: Update thresholds if needed ──────────────────────────────
        threshold_updates = await self._calibrate_thresholds(
            dataset_type, output_type, overall
        )

        # ── Step 6: Store in history ─────────────────────────────────────────
        self._store_history(
            dataset_type=dataset_type,
            output_type=output_type,
            overall_score=overall,
            dimensions={
                "novelty": round(novelty, 2),
                "actionability": round(actionability, 2),
                "specificity": round(specificity, 2),
                "correctness": round(correctness, 2),
            },
            failure_modes=failure_modes,
            prompt_adjustments=prompt_adjustments,
        )

        return ReflectionScore(
            overall_score=overall,
            novelty=round(novelty, 2),
            actionability=round(actionability, 2),
            specificity=round(specificity, 2),
            correctness=round(correctness, 2),
            failure_modes=failure_modes,
            prompt_adjustments=prompt_adjustments,
            threshold_updates=threshold_updates,
        )

    async def _score_quality(
        self, user_query: str, ai_output: str, schema_context: str
    ) -> dict:
        prompt = QUALITY_SCORE_PROMPT.format(
            user_query=user_query or "[No query — pipeline-generated]",
            ai_output=ai_output[:2000],
            schema_context=schema_context[:800] or "[Not provided]",
        )
        try:
            result = await self.llm_router.call(
                prompt=prompt,
                model_role="simple_query",
                expect_json=True,
                temperature=0.1,
                max_tokens=500,
            )
            if isinstance(result, dict) and result:
                return {
                    "novelty": max(0.0, min(1.0, float(result.get("novelty", 0.5)))),
                    "actionability": max(0.0, min(1.0, float(result.get("actionability", 0.5)))),
                    "specificity": max(0.0, min(1.0, float(result.get("specificity", 0.5)))),
                    "correctness": max(0.0, min(1.0, float(result.get("correctness", 0.5)))),
                    "failure_modes": result.get("failure_modes", []),
                }
            if not result:
                logger.warning("[Reflection] Quality scoring LLM returned empty result")
            return {}
        except Exception as e:
            logger.warning(f"[Reflection] Quality scoring failed: {e}")
            return {}

    def _compute_adjustments(
        self, failure_modes: list[str], overall_score: float
    ) -> dict[str, Any]:
        """Aggregate adjustments from identified failure modes."""
        if not failure_modes or overall_score >= self.GOOD_THRESHOLD:
            return {}

        adjustments: dict[str, Any] = {
            "temperature_change": 0.0,
            "add_examples": False,
            "instruction_add": "",
        }

        for mode in failure_modes:
            mode_adjust = self.FAILURE_ADJUSTMENTS.get(mode)
            if not mode_adjust:
                continue
            adjustments["temperature_change"] += mode_adjust.get("temperature_change", 0.0)
            if mode_adjust.get("add_examples"):
                adjustments["add_examples"] = True
            add_inst = mode_adjust.get("instruction_add", "")
            if add_inst and add_inst not in adjustments["instruction_add"]:
                if adjustments["instruction_add"]:
                    adjustments["instruction_add"] += " "
                adjustments["instruction_add"] += add_inst

        # Clamp temperature change
        adjustments["temperature_change"] = round(
            max(-0.5, min(0.0, adjustments["temperature_change"])), 2
        )

        return adjustments

    async def _calibrate_thresholds(
        self, dataset_type: str, output_type: str, overall_score: float
    ) -> dict:
        """Adjust confidence thresholds based on historical accuracy."""
        key = f"{dataset_type}__{output_type}"
        history = self._quality_history.get(key, [])
        if len(history) < 5:
            return {}  # Not enough data for calibration

        recent = history[-10:]
        avg_score = sum(h.overall_score for h in recent) / len(recent)
        std_dev = math.sqrt(
            sum((h.overall_score - avg_score) ** 2 for h in recent) / len(recent)
        )

        # If average is low, suggest lowering confidence thresholds
        updates = {}
        if avg_score < self.POOR_THRESHOLD:
            new_min = max(0.3, self._current_thresholds.get(key, {}).get("confidence_min", 0.5) - 0.05)
            updates["confidence_min"] = round(new_min, 2)
            updates["reason"] = f"Avg quality {avg_score:.2f} below {self.POOR_THRESHOLD} threshold"

        if std_dev > 0.2:
            updates["requires_review"] = True
            updates["reason"] = f"Quality variance {std_dev:.2f} indicates instability"

        if updates:
            self._current_thresholds[key] = {
                **self._current_thresholds.get(key, {}),
                **{k: v for k, v in updates.items() if k != "reason"},
            }

        return updates

    def _store_history(
        self,
        dataset_type: str,
        output_type: str,
        overall_score: float,
        dimensions: dict,
        failure_modes: list[str],
        prompt_adjustments: dict,
    ) -> None:
        key = f"{dataset_type}__{output_type}"
        if key not in self._quality_history:
            self._quality_history[key] = []
        self._quality_history[key].append(
            QualityHistoryEntry(
                dataset_type=dataset_type,
                output_type=output_type,
                overall_score=overall_score,
                dimensions=dimensions,
                failure_modes=failure_modes,
                prompt_adjustments=prompt_adjustments,
                timestamp=datetime.utcnow().isoformat(),
            )
        )
        # Cap history at 100 entries per key
        if len(self._quality_history[key]) > 100:
            self._quality_history[key] = self._quality_history[key][-100:]

    # ── Public helpers ───────────────────────────────────────────────────────

    def get_history(
        self, dataset_type: str = "", output_type: str = ""
    ) -> list[dict]:
        """Get quality history, optionally filtered."""
        results = []
        for key, entries in self._quality_history.items():
            dt, ot = key.split("__", 1)
            if dataset_type and dt != dataset_type:
                continue
            if output_type and ot != output_type:
                continue
            for entry in entries:
                results.append(asdict(entry))
        return results

    def get_trend(self, dataset_type: str, output_type: str) -> dict:
        """Get quality trend for a dataset/output type pair."""
        key = f"{dataset_type}__{output_type}"
        entries = self._quality_history.get(key, [])
        if len(entries) < 3:
            return {"trend": "insufficient_data", "entries": len(entries)}

        recent = entries[-5:]
        avg = sum(e.overall_score for e in recent) / len(recent)
        prev_avg = sum(e.overall_score for e in entries[-10:-5]) / max(len(entries[-10:-5]), 1)

        return {
            "trend": "improving" if avg > prev_avg + 0.05 else "declining" if avg < prev_avg - 0.05 else "stable",
            "current_avg": round(avg, 2),
            "previous_avg": round(prev_avg, 2),
            "entries": len(entries),
            "common_failure_modes": self._get_common_failure_modes(entries),
        }

    def _get_common_failure_modes(self, entries: list[QualityHistoryEntry]) -> list[dict]:
        mode_counts: dict[str, int] = {}
        for entry in entries:
            for mode in entry.failure_modes:
                mode_counts[mode] = mode_counts.get(mode, 0) + 1
        total = len(entries)
        return [
            {"mode": mode, "count": count, "pct": round(count / total * 100, 1)}
            for mode, count in sorted(mode_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

    def get_thresholds(self) -> dict[str, dict]:
        """Get current calibrated thresholds."""
        return self._current_thresholds


# ── Singleton ────────────────────────────────────────────────────────────────

insight_reflection_agent = InsightReflectionAgent()

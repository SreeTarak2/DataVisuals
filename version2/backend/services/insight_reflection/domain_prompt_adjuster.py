"""
DomainPromptAdjuster — Per-Domain Prompt Quality Aggregator
=============================================================
Aggregates InsightReflectionAgent quality scores per dataset domain
(ecommerce, finance, healthcare, etc.) and produces prompt template
adjustments when a domain consistently scores below threshold.

Architecture:
    DomainQualityStore   → MongoDB-backed aggregation of scores by (domain, output_type)
    TrendAnalyzer        → Detects improving/declining quality per domain
    PromptAdjuster      → Produces domain-level prompt adjustments

Design principles:
    - Needs at least 5 quality evaluations per domain before making adjustments
    - Adjustments are additive (new += old) — never resets
    - Conservative: never lowers quality without evidence
    - Domain adjustments are stored in MongoDB and survive restarts

Usage:
    adjuster = DomainPromptAdjuster()
    await adjuster.record_evaluation(domain, output_type, score, failure_modes)
    adjustments = await adjuster.get_adjustments(domain, output_type)
    # adjustments -> {"instruction_add": "...", "temperature_change": -0.1, ...}
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
class DomainEvaluation:
    """A single quality evaluation for a domain/output_type pair."""

    domain: str
    output_type: str  # "kpi", "insight", "chart", "narrative"
    overall_score: float
    failure_modes: list[str]
    dimensions: dict
    timestamp: str = ""


@dataclass
class DomainAdjustment:
    """Aggregated prompt adjustments for a domain/output_type pair."""

    domain: str
    output_type: str
    instruction_add: str = ""
    temperature_change: float = 0.0
    add_examples: bool = False
    evaluation_count: int = 0
    trend: str = "insufficient_data"  # improving | declining | stable
    common_failures: list[dict] = field(default_factory=list)
    last_updated: str = ""


# ── Domain failure mode → prompt adjustment mapping ─────────────────────────


DOMAIN_FAILURE_ADJUSTMENTS: dict[str, dict[str, Any]] = {
    # When the AI is too generic across all domains
    "overly_generic": {
        "instruction_add": "Be specific — cite exact column names and values from the dataset.",
        "temperature_change": -0.15,
        "add_examples": True,
    },
    # When the AI is too technical
    "no_business_context": {
        "instruction_add": "Frame findings in business terms: what decision does this inform?",
        "temperature_change": -0.1,
        "add_examples": True,
    },
    # When the AI hallucinates
    "hallucination": {
        "instruction_add": "Only reference columns explicitly listed in the schema. Never invent data.",
        "temperature_change": -0.2,
        "add_examples": False,
    },
}


class DomainPromptAdjuster:
    """
    Aggregates quality scores per domain and produces prompt adjustments.

    Uses MongoDB for persistence so domain learning survives restarts.
    Evaluations are stored in the 'domain_quality_history' collection.
    Current adjustments are stored in the 'domain_prompt_adjustments' collection.
    """

    # Minimum evaluations before making adjustments
    MIN_EVALUATIONS = 5

    # Quality thresholds
    EXCELLENT_THRESHOLD = 0.85
    GOOD_THRESHOLD = 0.70
    POOR_THRESHOLD = 0.50

    # Max instructions to accumulate per domain
    MAX_INSTRUCTIONS = 3

    def __init__(self):
        self._db = None
        self._cache: dict[str, DomainAdjustment] = {}

    @property
    def db(self):
        """Lazy-loaded MongoDB handle."""
        if self._db is None:
            try:
                from db.database import get_database
                self._db = get_database()
            except Exception:
                self._db = None
        return self._db

    async def record_evaluation(
        self,
        domain: str,
        output_type: str,
        overall_score: float,
        failure_modes: list[str],
        dimensions: dict | None = None,
    ) -> None:
        """
        Record a quality evaluation for a domain.

        This is called after every AI response to accumulate quality history.

        Args:
            domain: Dataset domain (e.g., "ecommerce", "finance", "healthcare")
            output_type: Type of output (e.g., "kpi", "insight", "chart", "narrative")
            overall_score: Quality score from InsightReflectionAgent (0.0-1.0)
            failure_modes: List of failure modes identified
            dimensions: Optional dict of per-dimension scores
        """
        evaluation = DomainEvaluation(
            domain=domain,
            output_type=output_type,
            overall_score=overall_score,
            failure_modes=failure_modes,
            dimensions=dimensions or {},
            timestamp=datetime.utcnow().isoformat(),
        )

        # Store in MongoDB
        if self.db is not None:
            try:
                await self.db.domain_quality_history.insert_one(asdict(evaluation))
                logger.debug(
                    f"[DomainPromptAdjuster] Recorded evaluation for {domain}/{output_type}: "
                    f"score={overall_score:.2f}, failures={failure_modes}"
                )
            except Exception as e:
                logger.warning(f"[DomainPromptAdjuster] MongoDB insert failed: {e}")

        # Invalidate cache for this domain
        key = f"{domain}__{output_type}"
        self._cache.pop(key, None)

    async def get_trend(
        self,
        domain: str,
        output_type: str,
        min_evaluations: int | None = None,
    ) -> DomainAdjustment:
        """
        Get aggregated quality trend and adjustments for a domain/output_type.

        Args:
            domain: Dataset domain
            output_type: Type of output
            min_evaluations: Override minimum evaluations threshold

        Returns:
            DomainAdjustment with aggregated instructions and trend info
        """
        min_evals = min_evaluations or self.MIN_EVALUATIONS
        key = f"{domain}__{output_type}"

        # Check cache
        if key in self._cache:
            return self._cache[key]

        # Load recent evaluations from MongoDB
        evaluations = await self._load_evaluations(domain, output_type)

        if len(evaluations) < min_evals:
            adjustment = DomainAdjustment(
                domain=domain,
                output_type=output_type,
                instruction_add="",
                temperature_change=0.0,
                evaluation_count=len(evaluations),
                trend="insufficient_data",
                last_updated=datetime.utcnow().isoformat(),
            )
            self._cache[key] = adjustment
            return adjustment

        # Compute average score and variance
        recent = evaluations[-20:]  # Last 20 evaluations
        scores = [e.overall_score for e in recent]
        avg_score = sum(scores) / len(scores)

        # Collect all failure modes
        all_failures: list[str] = []
        for e in recent:
            all_failures.extend(e.failure_modes)

        # Count failure mode frequencies
        failure_counts: dict[str, int] = {}
        for f in all_failures:
            failure_counts[f] = failure_counts.get(f, 0) + 1

        total = len(recent)
        common_failures = sorted(
            [
                {"mode": mode, "count": count, "pct": round(count / total * 100, 1)}
                for mode, count in failure_counts.items()
            ],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]

        # Compute trend (compare recent 5 vs previous 5)
        if len(recent) >= 10:
            recent_5 = [e.overall_score for e in recent[-5:]]
            prev_5 = [e.overall_score for e in recent[-10:-5]]
            recent_avg = sum(recent_5) / 5
            prev_avg = sum(prev_5) / 5
            if recent_avg > prev_avg + 0.05:
                trend = "improving"
            elif recent_avg < prev_avg - 0.05:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # Only produce adjustments if quality is below threshold
        if avg_score >= self.GOOD_THRESHOLD:
            adjustment = DomainAdjustment(
                domain=domain,
                output_type=output_type,
                instruction_add="",
                temperature_change=0.0,
                evaluation_count=len(evaluations),
                trend=trend,
                common_failures=common_failures,
                last_updated=datetime.utcnow().isoformat(),
            )
            self._cache[key] = adjustment
            return adjustment

        # Aggregate adjustments from common failure modes
        instruction_parts: list[str] = []
        temperature_total = 0.0
        needs_examples = False

        for failure_info in common_failures:
            mode = failure_info["mode"]
            pct = failure_info["pct"]
            mapping = DOMAIN_FAILURE_ADJUSTMENTS.get(mode)
            if mapping and pct >= 30.0:  # Only act if failure appears in >= 30% of evaluations
                inst = mapping.get("instruction_add", "")
                if inst and inst not in instruction_parts:
                    instruction_parts.append(inst)
                temperature_total += mapping.get("temperature_change", 0.0)
                if mapping.get("add_examples"):
                    needs_examples = True

        # Clamp temperature and truncate instructions
        temperature_change = round(max(-0.5, min(0.0, temperature_total)), 2)
        instruction_add = " ".join(instruction_parts[:self.MAX_INSTRUCTIONS])

        # Load or merge with stored adjustments
        stored = await self._load_stored_adjustments(domain, output_type)

        if stored and stored.get("instruction_add"):
            # Merge: keep existing instruction if still relevant, add new ones
            existing = stored.get("instruction_add", "")
            if existing not in instruction_add:
                instruction_parts = [existing] + instruction_parts[:self.MAX_INSTRUCTIONS - 1]
                instruction_add = " ".join(instruction_parts)

        adjustment = DomainAdjustment(
            domain=domain,
            output_type=output_type,
            instruction_add=instruction_add,
            temperature_change=temperature_change,
            add_examples=needs_examples,
            evaluation_count=len(evaluations),
            trend=trend,
            common_failures=common_failures,
            last_updated=datetime.utcnow().isoformat(),
        )

        # Persist to MongoDB
        if self.db is not None:
            try:
                await self.db.domain_prompt_adjustments.update_one(
                    {"domain": domain, "output_type": output_type},
                    {"$set": asdict(adjustment)},
                    upsert=True,
                )
            except Exception as e:
                logger.warning(f"[DomainPromptAdjuster] MongoDB persist failed: {e}")

        self._cache[key] = adjustment
        return adjustment

    async def get_adjustments(
        self,
        domain: str,
        output_type: str = "insight",
    ) -> dict[str, Any]:
        """
        Get prompt adjustments for a domain.

        Returns a dict that can be merged into the system prompt:
        {
            "instruction_add": "Be specific — cite exact columns...",
            "temperature_change": -0.15,
            "add_examples": true,
            "evaluation_count": 12,
            "trend": "declining"
        }

        Args:
            domain: Dataset domain
            output_type: Type of output

        Returns:
            Dict with adjustment fields, or empty dict if insufficient data
        """
        adjustment = await self.get_trend(domain, output_type)
        if adjustment.evaluation_count < self.MIN_EVALUATIONS:
            return {}
        return asdict(adjustment)

    async def format_for_prompt(
        self,
        domain: str,
        output_type: str = "insight",
    ) -> str:
        """
        Format domain adjustments as a block for system prompt injection.

        Returns:
            Empty string if no adjustments, otherwise a formatted block like:
            "DOMAIN-SPECIFIC QUALITY IMPROVEMENTS (ecommerce):\n\n
            • Be specific — cite exact column names and values from the dataset.\n
            • Frame findings in business terms: what decision does this inform?"
        """
        adjustment = await self.get_trend(domain, output_type)
        if not adjustment.instruction_add and not adjustment.add_examples:
            return ""

        parts = [f"DOMAIN-SPECIFIC QUALITY IMPROVEMENTS ({domain}):"]
        if adjustment.instruction_add:
            for inst in adjustment.instruction_add.split(". "):
                inst = inst.strip()
                if inst:
                    parts.append(f"• {inst}.")
        if adjustment.add_examples:
            parts.append("• Include specific numerical examples from the dataset to illustrate findings.")
        return "\n".join(parts)

    async def _load_evaluations(
        self,
        domain: str,
        output_type: str,
        limit: int = 50,
    ) -> list[DomainEvaluation]:
        """Load recent evaluations from MongoDB."""
        if self.db is None:
            return []

        try:
            cursor = (
                self.db.domain_quality_history.find(
                    {"domain": domain, "output_type": output_type}
                )
                .sort("timestamp", -1)
                .limit(limit)
            )
            docs = await cursor.to_list(length=limit)
            return [
                DomainEvaluation(
                    domain=d.get("domain", domain),
                    output_type=d.get("output_type", output_type),
                    overall_score=d.get("overall_score", 0.5),
                    failure_modes=d.get("failure_modes", []),
                    dimensions=d.get("dimensions", {}),
                    timestamp=d.get("timestamp", ""),
                )
                for d in docs
            ]
        except Exception as e:
            logger.warning(f"[DomainPromptAdjuster] Failed to load evaluations: {e}")
            return []

    async def _load_stored_adjustments(
        self,
        domain: str,
        output_type: str,
    ) -> dict | None:
        """Load previously stored adjustments from MongoDB."""
        if self.db is None:
            return None

        try:
            doc = await self.db.domain_prompt_adjustments.find_one(
                {"domain": domain, "output_type": output_type}
            )
            return doc
        except Exception:
            return None


# Singleton instance
domain_prompt_adjuster = DomainPromptAdjuster()

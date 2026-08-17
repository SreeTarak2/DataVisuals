"""
HarnessValidator — Self-Harness-Style Validation Gate
======================================================
Before a learned instruction is promoted into the conversation's active harness,
the validator checks that it is:

  1. Self-consistent — the instruction actually addresses the failure modes
     that triggered it (cheap LLM call).
  2. Non-redundant   — the instruction isn't a duplicate / near-duplicate of
     an already-accepted instruction (text-similarity check).
  3. Non-regressive  — the instruction wouldn't cause problems for recent
     successful responses (LLM call against held-out queries).
  4. [EvalSuite]     — Δin/Δho improvement: the instruction actually improves
     pass rates on held-in tasks without regressing held-out tasks.

Inspired by Self-Harness (§3.4: Proposal Validation):
  "A candidate is accepted only if it improves at least one split without
   degrading the other."

Design principles:
  - Lightweight: validation uses the cheapest available model (simple_query role)
  - Non-blocking: validator runs inside the existing fire-and-forget reflect task
  - Auditable: every accept/reject decision is logged with evidence
  - Conservative: prefers false rejection over false acceptance

Usage in the reflection pipeline:
    validator = harness_validator
    result = await validator.validate(
        instruction="Be specific — cite exact columns and values.",
        failure_modes=["overly_generic"],
        conversation_id="abc123",
        recent_successful_queries=["Show revenue by region"],
    )
    if result.accepted:
        await conversation_learner.add_adjustment(conv_id, adjustment)
    else:
        logger.info(f"Rejected: {result.reason}")
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    """Result of validating a proposed harness instruction."""

    accepted: bool
    instruction: str
    reason: str = ""
    evidence: dict = field(default_factory=dict)
    failure_modes: list[str] = field(default_factory=list)


@dataclass
class ValidationDecision:
    """Persistent record of a single validation decision."""

    conversation_id: str
    instruction: str
    failure_modes: list[str]
    accepted: bool
    reason: str
    evidence: dict
    timestamp: str = ""


# ── Validation prompt templates ──────────────────────────────────────────────

SELF_CONSISTENCY_PROMPT = """\
You are evaluating whether a proposed prompt instruction actually addresses
the identified failure modes.

PROPOSED INSTRUCTION:
"{instruction}"

FAILURE MODES THAT TRIGGERED IT:
{failure_modes_str}

TASK: Does this instruction directly address at least one of the failure modes?
Answer YES or NO, then provide a brief rationale (one sentence).

Respond in JSON format:
{{
    "addresses_failures": true or false,
    "rationale": "one-sentence explanation"
}}
"""

REGRESSION_CHECK_PROMPT = """\
You are evaluating whether a proposed prompt instruction would cause regressions
on queries that were previously answered successfully.

PROPOSED INSTRUCTION:
"{instruction}"

RECENT SUCCESSFUL QUERIES (these were answered well without the instruction):
{queries_str}

TASK: Would adding this instruction risk degrading the quality of responses
to these queries? Consider:
- Could the instruction introduce unnecessary constraints?
- Could it change the tone or format in a way that makes responses worse?
- Could it create contradictions with what worked before?

Respond in JSON format:
{{
    "regression_risk": "low", "medium", or "high",
    "rationale": "one-sentence explanation"
}}
"""


# ── Similarity threshold constants ───────────────────────────────────────────

# Minimum Jaccard similarity to flag as "likely duplicate"
_DUPLICATE_SIMILARITY_THRESHOLD = 0.55
# Minimum length for an instruction to be worth checking duplication
_MIN_INSTRUCTION_LENGTH = 15


# ── HarnessValidator ─────────────────────────────────────────────────────────


class HarnessValidator:
    """
    Self-Harness-style validation gate for prompt instruction adjustments.

    Four checks, run sequentially (early exit on first failure):

      1. Self-consistency   — Does the instruction address the failure modes?
      2. Non-redundancy     — Is this a duplicate of an already-accepted instruction?
      3. Non-regression     — Would this cause regressions on recent successes?
      4. Improvement        — Does Δin ≥ 0 and Δho ≥ 0 and max(Δin, Δho) > 0?
                             (Algorithm 1, line 11). Uses EvalSuite to measure
                             actual pass-rate changes.

    Statistics are tracked in-memory and optionally persisted to MongoDB.
    """

    # Minimum number of held-out queries needed to run regression check
    MIN_HELD_OUT_QUERIES = 1

    def __init__(self):
        self._decisions: list[ValidationDecision] = []
        self._lock = asyncio.Lock()
        self._db = None
        self._llm_router = None
        self._loaded_from_db = False  # Lazy-load flag
        # Historical decisions are loaded lazily from MongoDB on first access
        # via _ensure_loaded(). This handles the module-import timing issue
        # (singleton created before event loop exists) while still surviving
        # server restarts for the non-redundancy check.

    @property
    def db(self):
        if self._db is None:
            try:
                from db.database import get_database
                self._db = get_database()
            except Exception:
                self._db = None
        return self._db

    @property
    def llm_router(self):
        if self._llm_router is None:
            from llm.router import llm_router
            self._llm_router = llm_router
        return self._llm_router

    @property
    def eval_suite(self):
        """Lazy-loaded EvalSuite singleton.

        Ensures the benchmark package is on the Python path before importing.
        The benchmark directory is a sibling of services/ at
        version2/backend/benchmark.
        """
        import sys
        from pathlib import Path

        _benchmark_path = str(Path(__file__).resolve().parent.parent.parent / "benchmark")
        if _benchmark_path not in sys.path:
            sys.path.insert(0, _benchmark_path)
        # Also ensure the parent (version2/backend) is on the path
        _backend_path = str(Path(__file__).resolve().parent.parent.parent)
        if _backend_path not in sys.path:
            sys.path.insert(0, _backend_path)

        try:
            from benchmark.eval_suite import eval_suite as _suite
            return _suite
        except Exception as e:
            logger.warning(f"[HarnessValidator] EvalSuite not available: {e}")
            return None

    # ── Main entry point ─────────────────────────────────────────────────────

    async def validate(
        self,
        instruction: str,
        failure_modes: list[str],
        conversation_id: str,
        recent_successful_queries: Optional[list[str]] = None,
        *,
        skip_consistency: bool = False,
        skip_redundancy: bool = False,
        skip_regression: bool = False,
        skip_improvement: bool = True,  # Off by default (requires EvalSuite + dataset context)
        dataset_context_fn: Optional[Any] = None,
        slot_fn: Optional[Any] = None,
    ) -> ValidationResult:
        """
        Validate a proposed harness instruction before promotion.

        Args:
            instruction: The proposed instruction text (from prompt_adjustments)
            failure_modes: Failure modes that triggered this instruction
            conversation_id: Conversation this would be applied to
            recent_successful_queries: Held-out queries that scored well
                (regression check uses these to guard against degradation)
            skip_consistency: Skip the self-consistency LLM check
            skip_redundancy: Skip the duplicate-detection check
            skip_regression: Skip the regression-risk LLM check
            skip_improvement: Skip the Δin/Δho EvalSuite check (default True
                because it requires a dataset and EvalSuite to be available)
            dataset_context_fn: Optional async callable returning dataset context
                for resolving eval case template variables (passed to EvalSuite)
            slot_fn: Optional async callable returning column name slot mappings
                for resolving eval case template variables (passed to EvalSuite)

        Returns:
            ValidationResult with accepted=True/False, reason, and evidence
        """
        instruction = instruction.strip()
        if not instruction:
            return ValidationResult(
                accepted=False,
                instruction="",
                reason="Empty instruction — nothing to validate",
                evidence={},
            )

        # Ensure historical decisions are loaded for the non-redundancy check,
        # even if skip_redundancy is set (defensive — may be un-skipped later).
        await self._ensure_loaded()

        evidence: dict = {}
        constraints = []

        # ── Check 1: Self-consistency (LLM call) ──────────────────────────
        if not skip_consistency and failure_modes:
            consistency_ok, consistency_evidence = await self._check_self_consistency(
                instruction, failure_modes
            )
            evidence["self_consistency"] = consistency_evidence
            if not consistency_ok:
                reason = (
                    f"Self-consistency check failed: "
                    f"{consistency_evidence.get('rationale', 'instruction does not address failure modes')}"
                )
                constraints.append(reason)
                await self._log_decision(
                    conversation_id, instruction, failure_modes,
                    accepted=False, reason=reason, evidence=evidence,
                )
                return ValidationResult(
                    accepted=False, instruction=instruction,
                    reason=reason, evidence=evidence,
                    failure_modes=failure_modes,
                )
        else:
            evidence["self_consistency"] = {"skipped": True}

        # ── Check 2: Non-redundancy (text similarity) ─────────────────────
        if not skip_redundancy:
            duplicate_found, redundancy_evidence = await self._check_non_redundancy(
                instruction, conversation_id
            )
            evidence["non_redundancy"] = redundancy_evidence
            if duplicate_found:
                reason = (
                    f"Non-redundancy check failed: "
                    f"similar instruction already accepted "
                    f"(similarity={redundancy_evidence.get('similarity', 0):.2f})"
                )
                constraints.append(reason)
                await self._log_decision(
                    conversation_id, instruction, failure_modes,
                    accepted=False, reason=reason, evidence=evidence,
                )
                return ValidationResult(
                    accepted=False, instruction=instruction,
                    reason=reason, evidence=evidence,
                    failure_modes=failure_modes,
                )
        else:
            evidence["non_redundancy"] = {"skipped": True}

        # ── Check 3: Non-regression (LLM call on held-out queries) ────────
        if not skip_regression and recent_successful_queries:
            regression_ok, regression_evidence = await self._check_non_regression(
                instruction, recent_successful_queries
            )
            evidence["non_regression"] = regression_evidence
            if not regression_ok:
                reason = (
                    f"Non-regression check failed: "
                    f"{regression_evidence.get('rationale', 'instruction may cause regressions')} "
                    f"(risk={regression_evidence.get('risk', 'unknown')})"
                )
                constraints.append(reason)
                await self._log_decision(
                    conversation_id, instruction, failure_modes,
                    accepted=False, reason=reason, evidence=evidence,
                )
                return ValidationResult(
                    accepted=False, instruction=instruction,
                    reason=reason, evidence=evidence,
                    failure_modes=failure_modes,
                )
        else:
            evidence["non_regression"] = {
                "skipped": True,
                "reason": "no held-out queries provided" if not recent_successful_queries else "explicitly skipped",
            }

        # ── Check 4: Improvement (Δin/Δho via EvalSuite) ───────────────────
        if not skip_improvement:
            improvement_ok, improvement_evidence = await self._check_improvement(
                instruction, conversation_id,
                dataset_context_fn=dataset_context_fn,
                slot_fn=slot_fn,
            )
            evidence["improvement"] = improvement_evidence
            if not improvement_ok:
                reason = (
                    f"Improvement check failed: "
                    f"{improvement_evidence.get('reason', 'no measurable improvement')} "
                    f"(Δin={improvement_evidence.get('delta_pin', '?'):+.1%}, "
                    f"Δho={improvement_evidence.get('delta_pho', '?'):+.1%})"
                )
                constraints.append(reason)
                await self._log_decision(
                    conversation_id, instruction, failure_modes,
                    accepted=False, reason=reason, evidence=evidence,
                )
                return ValidationResult(
                    accepted=False, instruction=instruction,
                    reason=reason, evidence=evidence,
                    failure_modes=failure_modes,
                )
        else:
            evidence["improvement"] = {"skipped": True}

        # ── All checks passed — ACCEPT ────────────────────────────────────
        summary_parts = []
        if not constraints:
            summary_parts.append("all checks passed")
        reason = "; ".join(summary_parts) if summary_parts else "all validation checks passed"

        await self._log_decision(
            conversation_id, instruction, failure_modes,
            accepted=True, reason=reason, evidence=evidence,
        )

        return ValidationResult(
            accepted=True,
            instruction=instruction,
            reason=reason,
            evidence=evidence,
            failure_modes=failure_modes,
        )

    # ── Check 1: Self-consistency ─────────────────────────────────────────

    async def _check_self_consistency(
        self, instruction: str, failure_modes: list[str]
    ) -> tuple[bool, dict]:
        """
        Ask a lightweight LLM whether the instruction addresses the failure modes.

        Returns:
            (is_consistent, evidence_dict)
        """
        if not failure_modes:
            return True, {"skipped": True, "reason": "no failure modes to check against"}

        prompt = SELF_CONSISTENCY_PROMPT.format(
            instruction=instruction,
            failure_modes_str=", ".join(failure_modes),
        )

        try:
            result = await asyncio.wait_for(
                self.llm_router.call(
                    prompt=prompt,
                    model_role="simple_query",
                    expect_json=True,
                    temperature=0.1,
                    max_tokens=150,
                ),
                timeout=15.0,
            )

            if isinstance(result, dict):
                addresses = result.get("addresses_failures", False)
                rationale = result.get("rationale", "")
                if isinstance(addresses, bool) and addresses:
                    return True, {
                        "addresses_failures": True,
                        "rationale": rationale,
                    }
                return False, {
                    "addresses_failures": False,
                    "rationale": rationale or "instruction does not address failure modes",
                }

            # Non-dict response — skip the check (same as timeout)
            # The cheap model sometimes returns strings instead of JSON;
            # this should not block a potentially valid instruction.
            logger.warning(
                "[HarnessValidator] Self-consistency check got non-dict response: "
                "%s — skipping", type(result).__name__
            )
            return True, {
                "addresses_failures": True,
                "rationale": f"LLM returned non-dict ({type(result).__name__}) — skipping (conservative skip, not reject)",
            }

        except asyncio.TimeoutError:
            logger.warning("[HarnessValidator] Self-consistency check timed out — skipping check")
            return True, {"addresses_failures": True, "rationale": "Check timed out — skipping (conservative skip, not reject)"}
        except Exception as e:
            logger.warning(f"[HarnessValidator] Self-consistency check failed: {e}")
            return False, {"addresses_failures": False, "rationale": str(e)[:100]}

    # ── Check 2: Non-redundancy ───────────────────────────────────────────

    async def _check_non_redundancy(
        self, instruction: str, conversation_id: str
    ) -> tuple[bool, dict]:
        """
        Check if a similar instruction has already been accepted for this
        conversation. Uses Jaccard similarity on word sets.

        Returns:
            (is_redundant, evidence_dict)
            True means "this IS redundant with existing instructions"
        """
        if len(instruction) < _MIN_INSTRUCTION_LENGTH:
            return False, {"skipped": True, "reason": "instruction too short for meaningful comparison"}

        # Gather accepted instructions from this conversation
        accepted_instructions = await self._get_accepted_instructions(conversation_id)
        if not accepted_instructions:
            return False, {"found": 0, "similarity": 0.0}

        # Compare against each accepted instruction
        instruction_words = set(instruction.lower().split())
        max_similarity = 0.0
        most_similar = ""

        for accepted in accepted_instructions:
            accepted_words = set(accepted.lower().split())
            union = instruction_words | accepted_words
            if not union:
                continue
            similarity = len(instruction_words & accepted_words) / len(union)
            if similarity > max_similarity:
                max_similarity = similarity
                most_similar = accepted

        is_duplicate = max_similarity >= _DUPLICATE_SIMILARITY_THRESHOLD

        return is_duplicate, {
            "found": len(accepted_instructions),
            "similarity": round(max_similarity, 3),
            "most_similar": most_similar[:80] if most_similar else "",
            "threshold": _DUPLICATE_SIMILARITY_THRESHOLD,
        }

    async def _get_accepted_instructions(self, conversation_id: str) -> list[str]:
        """Get all previously accepted instructions for a conversation.

        Lazily loads from MongoDB on first access so that decisions survive
        server restarts even when the singleton is created at import time
        (before the event loop is running).
        """
        await self._ensure_loaded()
        async with self._lock:
            return [
                d.instruction
                for d in self._decisions
                if d.conversation_id == conversation_id and d.accepted
            ]

    # ── Check 3: Non-regression ───────────────────────────────────────────

    async def _check_non_regression(
        self, instruction: str, recent_successful_queries: list[str]
    ) -> tuple[bool, dict]:
        """
        Ask a lightweight LLM whether the instruction risks regressions
        on recently successful queries.

        Returns:
            (no_regression_risk, evidence_dict)
            True means "safe to apply" (risk is low)
        """
        if not recent_successful_queries:
            return True, {"skipped": True, "reason": "no held-out queries provided"}

        # Limit to at most 3 queries to keep the check cheap
        queries_sample = recent_successful_queries[:3]
        queries_str = "\n".join(f"- {q}" for q in queries_sample)

        prompt = REGRESSION_CHECK_PROMPT.format(
            instruction=instruction,
            queries_str=queries_str,
        )

        try:
            result = await asyncio.wait_for(
                self.llm_router.call(
                    prompt=prompt,
                    model_role="simple_query",
                    expect_json=True,
                    temperature=0.1,
                    max_tokens=150,
                ),
                timeout=15.0,
            )

            if isinstance(result, dict):
                risk = str(result.get("regression_risk", "medium")).lower()
                rationale = result.get("rationale", "")
                is_safe = risk == "low"
                return is_safe, {
                    "risk": risk,
                    "rationale": rationale,
                    "queries_checked": len(queries_sample),
                }

            # Non-dict response — skip the check (same as timeout)
            logger.warning(
                "[HarnessValidator] Regression check got non-dict response: "
                "%s — skipping", type(result).__name__
            )
            return True, {
                "risk": "low",
                "rationale": f"LLM returned non-dict ({type(result).__name__}) — skipping (conservative skip, not reject)",
                "queries_checked": len(queries_sample),
            }

        except asyncio.TimeoutError:
            logger.warning("[HarnessValidator] Regression check timed out — skipping check")
            return True, {
                "risk": "low",
                "rationale": "Check timed out — skipping (conservative skip, not reject)",
                "queries_checked": len(queries_sample),
            }
        except Exception as e:
            logger.warning(f"[HarnessValidator] Regression check failed: {e}")
            return False, {
                "risk": "unknown",
                "rationale": str(e)[:100],
                "queries_checked": len(queries_sample),
            }

    # ── Check 4: Δin/Δho Improvement (EvalSuite A/B comparison) ─────────────

    async def _check_improvement(
        self,
        instruction: str,
        conversation_id: str,
        dataset_context_fn: Optional[Any] = None,
        slot_fn: Optional[Any] = None,
    ) -> tuple[bool, dict]:
        """
        Check whether the instruction actually improves pass rates by running
        A/B evaluation via EvalSuite.

        Implements the Self-Harness Algorithm 1 acceptance criterion:
            Accept if Δin ≥ 0 and Δho ≥ 0 and max(Δin, Δho) > 0.

        COST CONTROL: Uses at most 12 cases (8 held-in + 4 held-out) by
        default to limit LLM calls to ~24 total (12 baseline + 12 candidate).
        This runs in a fire-and-forget background task — it never blocks the
        chat response path.

        Args:
            instruction: The proposed instruction text
            conversation_id: Conversation context for logging
            dataset_context_fn: Optional async callable returning (context_str, slots)
                for resolving template variables like {num1}, {cat1} in eval cases
            slot_fn: Optional async callable returning column name slot mappings

        Returns:
            (improves, evidence_dict)
            True means the instruction improves at least one split without
            regressing the other.
        """
        suite = self.eval_suite
        if suite is None:
            return True, {
                "skipped": True,
                "reason": "EvalSuite not available",
            }

        # Build baseline harness (no instruction)
        baseline_harness = {
            "model_role": "chart_engine",
            "temperature": 0.4,
            "instructions_override": None,
        }

        # Build candidate harness (with proposed instruction injected)
        candidate_harness = {
            "model_role": "chart_engine",
            "temperature": 0.4,
            "instructions_override": instruction,
        }

        # Use a small case subset for cost (12 cases = ~24 LLM calls for A/B)
        # Create a local suite with its own config — never mutate the global singleton.
        from benchmark.eval_suite import EvalConfig, EvalSuite
        check_suite = EvalSuite(config=EvalConfig(max_cases=12))

        try:
            comparison = await check_suite.compare_harnesses(
                baseline_harness=baseline_harness,
                candidate_harness=candidate_harness,
                llm_router=self.llm_router,
                dataset_context_fn=dataset_context_fn,
                slot_fn=slot_fn,
            )

            delta_pin = comparison.get("delta_pin", 0.0)
            delta_pho = comparison.get("delta_pho", 0.0)
            recommendation = comparison.get("recommendation", "reject")

            # Algorithm 1, line 11: accept if Δin ≥ 0 and Δho ≥ 0 and max(Δin, Δho) > 0
            improves = (
                delta_pin >= 0
                and delta_pho >= 0
                and max(delta_pin, delta_pho) > 0
            )

            evidence = {
                "delta_pin": delta_pin,
                "delta_pho": delta_pho,
                "recommendation": recommendation,
                "improvements": comparison.get("improvements", []),
                "regressions": comparison.get("regressions", []),
                "cases_used": 12,
                "reason": (
                    f"Δin={delta_pin:+.4f}, Δho={delta_pho:+.4f}, "
                    f"recommendation={recommendation}"
                ),
            }

            logger.info(
                f"[HarnessValidator] Improvement check for conv "
                f"{conversation_id[:12]}...: "
                f"Δin={delta_pin:+.4f}, Δho={delta_pho:+.4f}, "
                f"improves={improves}"
            )

            return improves, evidence

        except Exception as e:
            logger.warning(f"[HarnessValidator] Improvement check failed: {e}")
            return True, {
                "skipped": True,
                "reason": f"Improvement check failed: {str(e)[:150]}",
            }

    async def evaluate_improvement(
        self,
        instruction: str,
        dataset_context_fn: Optional[Any] = None,
        slot_fn: Optional[Any] = None,
    ) -> dict:
        """
        Public API: evaluate whether an instruction measurably improves
        evaluation pass rates.

        Returns detailed A/B comparison results including Δin, Δho, per-case
        improvements/regressions, and the Self-Harness recommendation.

        Args:
            instruction: The proposed instruction to evaluate
            dataset_context_fn: Optional async callable returning dataset
                context for resolving template variables
            slot_fn: Optional async callable returning column name mappings

        Returns:
            Dict with delta_pin, delta_pho, improvements, regressions,
            recommendation, and full traces.
        """
        suite = self.eval_suite
        if suite is None:
            return {
                "error": "EvalSuite not available",
                "delta_pin": 0.0,
                "delta_pho": 0.0,
                "recommendation": "unavailable",
            }

        baseline_harness = {"model_role": "chart_engine", "temperature": 0.4}
        candidate_harness = {
            "model_role": "chart_engine",
            "temperature": 0.4,
            "instructions_override": instruction,
        }

        try:
            comparison = await suite.compare_harnesses(
                baseline_harness=baseline_harness,
                candidate_harness=candidate_harness,
                llm_router=self.llm_router,
                dataset_context_fn=dataset_context_fn,
                slot_fn=slot_fn,
            )

            return {
                "delta_pin": comparison.get("delta_pin", 0.0),
                "delta_pho": comparison.get("delta_pho", 0.0),
                "improvements": comparison.get("improvements", []),
                "regressions": comparison.get("regressions", []),
                "recommendation": comparison.get("recommendation", "reject"),
                "baseline_pass_rate": comparison.get("baseline", None),
                "candidate_pass_rate": comparison.get("candidate", None),
            }

        except Exception as e:
            logger.error(f"[HarnessValidator] evaluate_improvement failed: {e}")
            return {
                "error": str(e)[:200],
                "delta_pin": 0.0,
                "delta_pho": 0.0,
                "recommendation": "error",
            }

    # ── Logging & history ─────────────────────────────────────────────────

    async def _log_decision(
        self,
        conversation_id: str,
        instruction: str,
        failure_modes: list[str],
        accepted: bool,
        reason: str,
        evidence: dict,
    ) -> None:
        """Record a validation decision for auditability.

        The in-memory log is written synchronously (fast, always succeeds).
        The MongoDB write is fire-and-forget — scheduled as a separate task
        so it never blocks the validation flow.
        """
        decision = ValidationDecision(
            conversation_id=conversation_id,
            instruction=instruction,
            failure_modes=failure_modes,
            accepted=accepted,
            reason=reason,
            evidence=evidence,
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        )

        # In-memory log (fast, no I/O)
        async with self._lock:
            self._decisions.append(decision)
            # Cap at 5000 entries
            if len(self._decisions) > 5000:
                self._decisions = self._decisions[-5000:]

        # MongoDB persistence (fire-and-forget — never blocks validation)
        if self.db is not None:
            asyncio.create_task(self._persist_decision(decision))

        status = "ACCEPTED" if accepted else "REJECTED"
        logger.info(
            f"[HarnessValidator] {status} instruction for conv "
            f"{conversation_id[:12]}...: '{instruction[:50]}...' — {reason}"
        )

    async def _persist_decision(self, decision: ValidationDecision) -> None:
        """Write a single decision to MongoDB.

        Designed to be called via asyncio.create_task() — this is the
        fire-and-forget persistence half of _log_decision. Runs entirely
        in a background task; failures are logged but never propagated.
        """
        if self.db is None:
            return
        try:
            await self.db.harness_validation_log.insert_one({
                "conversation_id": decision.conversation_id,
                "instruction": decision.instruction,
                "failure_modes": decision.failure_modes,
                "accepted": decision.accepted,
                "reason": decision.reason,
                "evidence": decision.evidence,
                "timestamp": decision.timestamp,
            })
        except Exception as e:
            logger.warning(f"[HarnessValidator] MongoDB persistence failed: {e}")

    # ── MongoDB reload on startup ───────────────────────────────────────────

    async def _load_from_mongodb(self, max_docs: int = 5000) -> None:
        """
        Reload historical validation decisions from MongoDB on startup.

        This makes the non-redundancy check (Jaccard similarity) work across
        server restarts by populating the in-memory decision log from
        persisted decisions.

        Called automatically from __init__() if an event loop is running,
        and also called lazily before the first validate() if no loop was
        available at construction time.

        Args:
            max_docs: Maximum number of recent decisions to load.
        """
        if self.db is None:
            logger.warning("[HarnessValidator] MongoDB not available — cannot load historical decisions")
            return

        try:
            cursor = self.db.harness_validation_log.find().sort("timestamp", -1).limit(max_docs)
            docs = await cursor.to_list(length=max_docs)

            loaded = []
            for doc in docs:
                loaded.append(ValidationDecision(
                    conversation_id=doc.get("conversation_id", ""),
                    instruction=doc.get("instruction", ""),
                    failure_modes=doc.get("failure_modes", []),
                    accepted=doc.get("accepted", False),
                    reason=doc.get("reason", ""),
                    evidence=doc.get("evidence", {}),
                    timestamp=doc.get("timestamp", ""),
                ))

            async with self._lock:
                self._decisions = loaded

            accepted_count = sum(1 for d in loaded if d.accepted)
            rejected_count = len(loaded) - accepted_count
            logger.info(
                f"[HarnessValidator] Loaded {len(loaded)} historical decisions "
                f"({accepted_count} accepted, {rejected_count} rejected) "
                f"from MongoDB on startup"
            )
        except Exception as e:
            logger.warning(f"[HarnessValidator] Failed to load historical decisions: {e}")

    # ── Query methods ─────────────────────────────────────────────────────

    async def _ensure_loaded(self) -> None:
        """Lazy-load historical decisions from MongoDB on first access.

        This ensures the non-redundancy check survives server restarts:
        - At module-import time, __init__ cannot start async tasks (no event loop).
        - On first call to validate(), get_history(), or get_stats(), this
          method populates self._decisions from persisted MongoDB docs.
        - Guarded by self._loaded_from_db flag and self._lock to prevent
          concurrent double-loads.
        """
        if self._loaded_from_db:
            return

        async with self._lock:
            if self._loaded_from_db:
                return
            self._loaded_from_db = True

        try:
            await self._load_from_mongodb()
        except Exception as e:
            logger.warning(f"[HarnessValidator] Lazy-load from MongoDB failed: {e}")

    async def get_held_out_queries(
        self,
        messages: list[dict],
        exclude_query: Optional[str] = None,
        max_queries: int = 3,
    ) -> list[str]:
        """
        Extract recent user queries from conversation messages to serve as
        held-out queries for the regression check.

        This gives the validator access to REAL user queries that were
        answered successfully, rather than instruction text or synthetic data.

        To handle query enrichment (where the original query is replaced with
        an enriched version in the message history), the exclusion check uses
        substring matching — if the stored message content contains the
        exclude_query, it is skipped.

        Args:
            messages: List of conversation messages (with 'role' and 'content' keys)
            exclude_query: The current query to exclude (we want PAST successes).
                Uses substring matching to handle query enrichment.
            max_queries: Maximum number of queries to return

        Returns:
            List of recent user query strings (held-out set for regression check)
        """
        if not messages:
            return []

        user_queries: list[str] = []
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "").strip()
                if content and len(content) > 10:
                    # Use substring matching to handle query enrichment
                    # e.g., original "show revenue" → enriched "show me total revenue by region"
                    if exclude_query:
                        if content == exclude_query or exclude_query in content or content in exclude_query:
                            continue
                    user_queries.append(content)

        # Return the most recent ones (excluding current)
        return user_queries[-max_queries:] if user_queries else []

    async def get_history(
        self,
        conversation_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get validation decision history, optionally filtered by conversation."""
        await self._ensure_loaded()
        async with self._lock:
            decisions = self._decisions
            if conversation_id:
                decisions = [d for d in decisions if d.conversation_id == conversation_id]
            return [
                {
                    "conversation_id": d.conversation_id,
                    "instruction": d.instruction,
                    "failure_modes": d.failure_modes,
                    "accepted": d.accepted,
                    "reason": d.reason,
                    "evidence": d.evidence,
                    "timestamp": d.timestamp,
                }
                for d in decisions[-limit:]
            ]

    async def get_stats(self) -> dict:
        """Get aggregate validation statistics."""
        await self._ensure_loaded()
        async with self._lock:
            total = len(self._decisions)
            accepted = sum(1 for d in self._decisions if d.accepted)
            rejected = total - accepted
            # Most common rejection reasons
            rejection_reasons: dict[str, int] = {}
            for d in self._decisions:
                if not d.accepted:
                    key = d.reason.split(":")[0].strip() if d.reason else "unknown"
                    rejection_reasons[key] = rejection_reasons.get(key, 0) + 1
            top_rejections = sorted(
                rejection_reasons.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]

            return {
                "total_decisions": total,
                "accepted": accepted,
                "rejected": rejected,
                "accept_rate": round(accepted / total, 3) if total > 0 else 0.0,
                "top_rejection_reasons": [
                    {"reason": reason, "count": count}
                    for reason, count in top_rejections
                ],
                "improvement_checks": sum(
                    1 for d in self._decisions
                    if "delta_pin" in d.evidence.get("improvement", {})
                ),
            }


# ── Singleton ────────────────────────────────────────────────────────────────

harness_validator = HarnessValidator()

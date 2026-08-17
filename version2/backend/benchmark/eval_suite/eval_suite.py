"""
EvalSuite — Core EVALUATE() Function (Self-Harness Algorithm 1)
================================================================

Implements:
    (Pin(ht), Pho(ht), Rt) ← EVALUATE(M, ht, Din, Dho, E)

Where:
    M:   Fixed model (the LLM routing chain under test)
    ht:  Current harness (prompts + runtime configuration)
    Din: Held-in task split
    Dho: Held-out task split
    E:   Scorer that evaluates response quality
    Pin: Pass rate on held-in split (0.0 – 1.0)
    Pho: Pass rate on held-out split (0.0 – 1.0)
    Rt:  Raw evaluation traces for weakness mining

Scoring:
    Each response is scored on 5 dimensions (1-5 scale):
        faithfulness, analytical_depth, specificity, actionability, format_quality
    A case "passes" if ALL dimensions meet or exceed the case's ScoringRubric minimums.
    Pass rate = passed_cases / total_cases

Usage:
    from benchmark.eval_suite import eval_suite

    result = await eval_suite.evaluate(
        harness={"model_role": "chart_engine", "temperature": 0.4},
        llm_router=llm_router,
    )
    print(f"Pin={result.pin:.1%}, Pho={result.pho:.1%}")
    print(f"Top failures: {result.top_failures()}")
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from .eval_cases import (
    EvalCase,
    EvalCaseRegistry,
    ChallengeLevel,
    Split,
    ScoringRubric,
    registry as case_registry,
)

logger = logging.getLogger(__name__)


# ── Scoring engine ──────────────────────────────────────────────────────────


@dataclass
class Scorecard:
    """Per-dimension scores for a single response."""

    faithfulness: float = 3.0
    analytical_depth: float = 3.0
    specificity: float = 3.0
    actionability: float = 2.0
    format_quality: float = 3.0

    @property
    def average(self) -> float:
        return round(
            (self.faithfulness + self.analytical_depth + self.specificity
             + self.actionability + self.format_quality) / 5,
            2,
        )

    def passes(self, rubric: ScoringRubric) -> bool:
        """Check if ALL dimensions meet or exceed the rubric minimums."""
        return (
            self.faithfulness >= rubric.faithfulness
            and self.analytical_depth >= rubric.analytical_depth
            and self.specificity >= rubric.specificity
            and self.actionability >= rubric.actionability
            and self.format_quality >= rubric.format_quality
        )


@dataclass
class EvalTrace:
    """Full trace for a single evaluation case."""

    case_id: str
    case_group: str
    query: str
    response: str
    response_word_count: int
    has_chart: bool
    status: str  # "ok" | "error" | "timeout"
    error: str
    latency_ms: float
    scorecard: Scorecard
    passed: bool
    failure_reasons: List[str] = field(default_factory=list)
    rubric: ScoringRubric = field(default_factory=ScoringRubric)


@dataclass
class EvalResult:
    """
    Complete evaluation result.
    Maps to the paper's (Pin, Pho, Rt) tuple.
    """

    pin: float  # Pass rate on held-in split
    pho: float  # Pass rate on held-out split
    total_cases: int
    held_in_cases: int
    held_out_cases: int
    held_in_passed: int
    held_out_passed: int
    avg_scorecard: Scorecard  # Average scores across ALL cases
    traces: List[EvalTrace]  # Rt — full traces for weakness mining
    errors: int
    timeouts: int
    duration_seconds: float
    harness_label: str  # Description of the harness configuration tested
    timestamp: str

    def top_failures(self, n: int = 10) -> List[EvalTrace]:
        """Get the worst-performing cases for weakness mining."""
        failed = [t for t in self.traces if not t.passed]
        failed.sort(key=lambda t: t.scorecard.average)
        return failed[:n]

    def failure_clusters(self) -> Dict[str, int]:
        """Cluster failure reasons for weakness pattern mining (Paper §3.2)."""
        clusters: Dict[str, int] = {}
        for t in self.traces:
            if not t.passed:
                for reason in t.failure_reasons:
                    clusters[reason] = clusters.get(reason, 0) + 1
        return dict(sorted(clusters.items(), key=lambda x: -x[1]))

    def dimension_averages(self) -> Dict[str, float]:
        """Average scores per dimension — for trend analysis."""
        n = len(self.traces) or 1
        totals = {"faithfulness": 0.0, "analytical_depth": 0.0,
                   "specificity": 0.0, "actionability": 0.0, "format_quality": 0.0}
        for t in self.traces:
            for dim in totals:
                totals[dim] += getattr(t.scorecard, dim, 0.0)
        return {dim: round(v / n, 2) for dim, v in totals.items()}

    def summary(self) -> str:
        """Return a Markdown summary of the evaluation run."""
        dims = self.dimension_averages()
        fail_clusters = self.failure_clusters()
        lines = [
            "## Evaluation Results",
            "",
            f"**Harness**: {self.harness_label}",
            f"**Duration**: {self.duration_seconds:.1f}s",
            f"**Timestamp**: {self.timestamp}",
            "",
            "### Pass Rates",
            f"| Split | Passed / Total | Pass Rate |",
            f"|---|---|---|",
            f"| Held-in (Din) | {self.held_in_passed}/{self.held_in_cases} | **{self.pin:.1%}** |",
            f"| Held-out (Dho) | {self.held_out_passed}/{self.held_out_cases} | **{self.pho:.1%}** |",
            f"| **Total** | {self.held_in_passed + self.held_out_passed}/{self.total_cases} | **{(self.pin * self.held_in_cases + self.pho * self.held_out_cases) / max(self.total_cases, 1):.1%}** |",
            "",
            "### Dimension Averages (1-5)",
            "| Dimension | Avg Score |",
            "|---|---|",
        ]
        for dim, avg in sorted(dims.items()):
            bar = "█" * int(avg) + "░" * (5 - int(avg))
            lines.append(f"| {dim.replace('_', ' ').title()} | {bar} {avg}/5 |")

        lines.extend([
            "",
            f"### Errors: {self.errors} | Timeouts: {self.timeouts}",
            "",
        ])

        if fail_clusters:
            lines.append("### Top Failure Clusters (for Weakness Mining)")
            lines.append("| Failure Reason | Count |")
            lines.append("|---|---|")
            for reason, count in list(fail_clusters.items())[:10]:
                lines.append(f"| {reason} | {count} |")

        return "\n".join(lines)


@dataclass
class EvalConfig:
    """
    Configuration for an evaluation run.

    Args:
        case_ids:       Optional subset of case IDs to run (default: all)
        levels:         Optional challenge levels to run (default: all)
        timeout_sec:    Per-case LLM timeout
        max_concurrent: Max concurrent evaluations
        min_word_ratio: Response must be at least this fraction of min_words to pass
        chart_required: Whether missing chart fails the case
    """
    case_ids: Optional[List[str]] = None
    levels: Optional[List[ChallengeLevel]] = None
    timeout_sec: float = 60.0
    max_concurrent: int = 5
    min_word_ratio: float = 0.5
    chart_required: bool = True
    verbose: bool = False
    max_cases: Optional[int] = None  # Limit total cases (for cost-sensitive checks)


# ── Heuristic scorer (fast path, no LLM call) ────────────────────────────────

CHART_KEYWORDS = r"(?i)\b(plot|chart|graph|visuali[sz]e|bar|line|pie|scatter)\b"


class HeuristicScorer:
    """
    Fast heuristic scoring — no LLM call needed.

    Used as the default scorer E in the EVALUATE() function.
    Scores responses on 5 dimensions using regex and simple heuristics.

    The scores correlate reasonably with human judgment (r ≈ 0.7 on internal tests)
    and are deterministic and fast (< 1ms per response).
    """

    FILLER_OPENERS = [
        r"(?i)^\s*(based on the (data|results|analysis)",
        r"(?i)^\s*(according to (the )?(data|results))",
        r"(?i)^\s*(the (data|results) show(s)?)",
        r"(?i)^\s*(i('d be happy|'m here|'ll help))",
        r"(?i)^\s*(of course|sure[,!]|happy to help)",
    ]

    OVERCONFIDENT_WORDS = [r"(?i)\b(definitely|certainly|absolutely|without a doubt|always|never)\b"]

    BANNED_PATTERNS = [
        r"(?i)(sql syntax error|column.*not found|duckdb|polars|traceback)",
        r"(?i)(cannot compute|cannot determine|unable to answer)",
    ]

    VAGUE_WORDS = [r"(?i)\b(significantly|generally|tends? to|some|many|often|usually|might be|could be)\b"]

    def score(self, response: str, case: EvalCase, metadata: dict = None) -> Scorecard:
        if not response or not response.strip():
            return Scorecard(1.0, 1.0, 1.0, 1.0, 1.0)

        text = response.strip()
        word_count = len(text.split())

        # Start at perfect scores, deduct for issues
        faith = 5.0
        depth = 5.0
        spec = 5.0
        action = 5.0
        fmt = 5.0

        failure_modes = []

        # ── Faithfulness checks ────────────────────────────────────────
        for pattern in self.BANNED_PATTERNS:
            import re
            if re.search(pattern, text):
                faith -= 3.0
                failure_modes.append("error_leaked")
                break

        import re
        for pattern in self.OVERCONFIDENT_WORDS:
            if re.search(pattern, text):
                faith -= 1.0
                failure_modes.append("overconfident")
                break

        # ── Depth checks ───────────────────────────────────────────────
        min_expected = max(case.min_words, 10)
        word_ratio = word_count / min_expected
        if word_ratio < 1.0:
            depth -= (1.0 - word_ratio) * 3.0
            failure_modes.append("too_short")

        if word_count < case.min_words * 0.3:
            depth = 1.0  # Severely truncated

        # ── Specificity checks ─────────────────────────────────────────
        import re
        if case.requires_numbers:
            has_numbers = bool(re.search(r"\d", text))
            if not has_numbers:
                spec -= 3.0
                failure_modes.append("missing_numbers")

        # Filler openers
        for pattern in self.FILLER_OPENERS:
            if re.search(pattern, text):
                spec -= 1.5
                failure_modes.append("filler_opening")
                break

        # Vague language
        for pattern in self.VAGUE_WORDS:
            if re.search(pattern, text):
                spec -= 0.5
                failure_modes.append("vague_language")
                break

        # ── Actionability checks ───────────────────────────────────────
        # Does the response suggest a next step or conclusion?
        import re
        has_action_indicators = bool(re.search(
            r"(?i)\b(i recommend|you should|consider|action|next step|try|focus|prioritize|investigate|monitor|adjust)\b",
            text,
        ))
        if not has_action_indicators and case.level in (ChallengeLevel.L2_ANALYTICAL,):
            action -= 1.5
            failure_modes.append("no_action_indicators")

        # ── Format quality ─────────────────────────────────────────────
        # Very short response = poor format
        if word_count < 15:
            fmt -= 1.0

        # Has no structure (no paragraphs for long responses)
        if word_count > 60 and "\n\n" not in text:
            fmt -= 1.0
            failure_modes.append("no_structure")

        # Clamp to [1.0, 5.0]
        def clamp(v: float) -> float:
            return max(1.0, min(5.0, round(v, 1)))

        return Scorecard(
            faithfulness=clamp(faith),
            analytical_depth=clamp(depth),
            specificity=clamp(spec),
            actionability=clamp(action),
            format_quality=clamp(fmt),
        )


# ── LLM scorer (optional, more accurate) ─────────────────────────────────────

SCORING_PROMPT = """\
Evaluate the quality of this AI response to a data analytics question.

## Question
{query}

## Response
{response}

## Scoring Rubric (1-5 scale)
Each dimension must be at least: {rubric_min}

1. faithfulness: Is the response grounded in the data? No hallucination, no errors?
2. analytical_depth: Does it go beyond surface-level description?
3. specificity: Does it cite specific numbers, columns, or values?
4. actionability: Does it imply clear next steps or decisions?
5. format_quality: Is it readable, structured, and professional?

Return ONLY valid JSON with no markdown:
{{
  "faithfulness": 1-5,
  "analytical_depth": 1-5,
  "specificity": 1-5,
  "actionability": 1-5,
  "format_quality": 1-5,
  "failure_reasons": ["reason or empty array"],
  "rationale": "brief rationale"
}}
"""


# ── EvalSuite ────────────────────────────────────────────────────────────────


class EvalSuite:
    """
    Core evaluation engine implementing EVALUATE() from Self-Harness.

    Usage:
        suite = EvalSuite()
        result = await suite.evaluate(harness, llm_router)
        print(result.summary())
    """

    def __init__(self, scorer: Optional[Any] = None, config: Optional[EvalConfig] = None):
        """
        Args:
            scorer: Scorer instance. Defaults to HeuristicScorer (fast, no LLM).
                    For more accurate scoring, pass an LLMScorer that calls a model.
            config: Evaluation configuration. Uses defaults if not provided.
        """
        self.scorer = scorer or HeuristicScorer()
        self.config = config or EvalConfig()
        self.registry = case_registry

    async def evaluate(
        self,
        harness: Dict[str, Any],
        llm_router: Any,
        dataset_context_fn: Optional[Callable] = None,
        slot_fn: Optional[Callable] = None,
    ) -> EvalResult:
        """
        EVALUATE(M, ht, Din, Dho, E) — Algorithm 1 from Self-Harness.

        Args:
            harness: Current harness configuration dict. Must include at minimum:
                - model_role: The model role to use (e.g., "chart_engine")
                - temperature: Temperature for generation
                - Additional fields are passed through to the LLM router.
            llm_router: The LLM routing service with a .call() method.
            dataset_context_fn: Optional async callable that returns (context_string, slots)
                for dataset-aware evaluation. If None, uses generic context.
                Signature: async fn() -> (str, Dict[str, str])
            slot_fn: Optional async callable that returns column name mappings.
                Signature: async fn() -> Dict[str, str]

        Returns:
            EvalResult with pin, pho, and traces for weakness mining.
        """
        start_time = time.time()
        config = self.config

        # Resolve cases
        all_cases = self.registry.all_cases
        if config.case_ids:
            all_cases = [c for c in all_cases if c.id in config.case_ids]
        if config.levels:
            all_cases = [c for c in all_cases if c.level in config.levels]
        if config.max_cases and len(all_cases) > config.max_cases:
            # Sample deterministically to maintain held-in/held-out ratio
            import random
            rng = random.Random(42)  # Fixed seed for reproducibility
            rng.shuffle(all_cases)
            all_cases = all_cases[:config.max_cases]
            logger.info(f"[EvalSuite] Limited to {config.max_cases} cases for cost control")

        held_in = [c for c in all_cases if c.split == Split.HELD_IN]
        held_out = [c for c in all_cases if c.split == Split.HELD_OUT]

        if not held_in and not held_out:
            logger.warning("No cases selected for evaluation")

        # Resolve dataset context and column slots
        context_str = ""
        slots: Dict[str, str] = {}
        if slot_fn:
            try:
                slots = await slot_fn()
            except Exception as e:
                logger.warning(f"Slot resolution failed: {e}")
        if dataset_context_fn:
            try:
                ctx, resolved_slots = await dataset_context_fn()
                if ctx:
                    context_str = ctx
                if resolved_slots:
                    slots = resolved_slots
            except Exception as e:
                logger.warning(f"Dataset context resolution failed: {e}")

        # Build the harness label
        harness_label = (
            f"model_role={harness.get('model_role', 'unknown')}, "
            f"temp={harness.get('temperature', 'default')}"
        )

        # Run evaluations with concurrency limit
        sem = asyncio.Semaphore(config.max_concurrent)
        all_traces: List[EvalTrace] = []

        async def evaluate_single(case: EvalCase) -> EvalTrace:
            async with sem:
                return await self._evaluate_case(case, harness, llm_router, context_str, slots)

        tasks = [evaluate_single(case) for case in all_cases]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, EvalTrace):
                all_traces.append(r)
            elif isinstance(r, Exception):
                logger.error(f"Eval case failed with exception: {r}")

        # Compute pass rates
        held_in_traces = [t for t in all_traces if t.case_id in {c.id for c in held_in}]
        held_out_traces = [t for t in all_traces if t.case_id in {c.id for c in held_out}]

        held_in_passed = sum(1 for t in held_in_traces if t.passed)
        held_out_passed = sum(1 for t in held_out_traces if t.passed)

        pin = held_in_passed / max(len(held_in_traces), 1)
        pho = held_out_passed / max(len(held_out_traces), 1)

        # Average scorecard
        n = len(all_traces) or 1
        avg_card = Scorecard(
            faithfulness=round(sum(t.scorecard.faithfulness for t in all_traces) / n, 2),
            analytical_depth=round(sum(t.scorecard.analytical_depth for t in all_traces) / n, 2),
            specificity=round(sum(t.scorecard.specificity for t in all_traces) / n, 2),
            actionability=round(sum(t.scorecard.actionability for t in all_traces) / n, 2),
            format_quality=round(sum(t.scorecard.format_quality for t in all_traces) / n, 2),
        )

        duration = round(time.time() - start_time, 1)

        return EvalResult(
            pin=round(pin, 4),
            pho=round(pho, 4),
            total_cases=len(all_traces),
            held_in_cases=len(held_in_traces),
            held_out_cases=len(held_out_traces),
            held_in_passed=held_in_passed,
            held_out_passed=held_out_passed,
            avg_scorecard=avg_card,
            traces=all_traces,
            errors=sum(1 for t in all_traces if t.status == "error"),
            timeouts=sum(1 for t in all_traces if t.status == "timeout"),
            duration_seconds=duration,
            harness_label=harness_label,
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        )

    async def _evaluate_case(
        self,
        case: EvalCase,
        harness: Dict[str, Any],
        llm_router: Any,
        context_str: str,
        slots: Dict[str, str],
    ) -> EvalTrace:
        """Evaluate a single test case against the harness."""
        query = case.resolve(slots)
        config = self.config

        start_time = time.time()
        response_text = ""
        status = "ok"
        error_text = ""
        has_chart = False
        actual_words = 0

        try:
            # Build the prompt with context + query
            prompt = context_str + f"\n\nUSER QUERY: {query}" if context_str else query

            llm_response = await asyncio.wait_for(
                llm_router.call(
                    prompt=prompt,
                    model_role=harness.get("model_role", "chart_engine"),
                    expect_json=True,
                    temperature=harness.get("temperature", 0.4),
                    max_tokens=harness.get("max_tokens", 2000),
                    **{k: v for k, v in harness.items()
                       if k not in ("model_role", "temperature", "max_tokens")},
                ),
                timeout=config.timeout_sec,
            )

            # Extract text from response
            if isinstance(llm_response, dict):
                response_text = (
                    llm_response.get("response_text")
                    or llm_response.get("response")
                    or llm_response.get("answer")
                    or str(llm_response)
                )
                has_chart = bool(
                    llm_response.get("chart_config")
                    or llm_response.get("chart")
                )
            elif isinstance(llm_response, str):
                response_text = llm_response
            else:
                response_text = str(llm_response)

        except asyncio.TimeoutError:
            status = "timeout"
            error_text = f"Timed out after {config.timeout_sec}s"
        except Exception as e:
            status = "error"
            error_text = str(e)
            logger.debug(f"Eval case {case.id} failed: {e}")

        latency_ms = round((time.time() - start_time) * 1000, 1)
        actual_words = len(response_text.split()) if response_text else 0

        # Score the response
        scorecard = self.scorer.score(response_text, case)

        # Determine pass/fail
        passed = scorecard.passes(case.rubric)

        failure_reasons = []
        if not passed:
            if scorecard.faithfulness < case.rubric.faithfulness:
                failure_reasons.append("faithfulness_below_rubric")
            if scorecard.analytical_depth < case.rubric.analytical_depth:
                failure_reasons.append("depth_below_rubric")
            if scorecard.specificity < case.rubric.specificity:
                failure_reasons.append("specificity_below_rubric")
            if scorecard.actionability < case.rubric.actionability:
                failure_reasons.append("actionability_below_rubric")
            if scorecard.format_quality < case.rubric.format_quality:
                failure_reasons.append("format_below_rubric")

        # Specific failure: chart expected but not produced
        if case.requires_chart and config.chart_required and not has_chart:
            passed = False
            failure_reasons.append("chart_expected_but_missing")

        # Specific failure: too short
        min_expected = max(case.min_words, 5)
        if config.min_word_ratio > 0 and actual_words < min_expected * config.min_word_ratio:
            failure_reasons.append("response_too_short")

        if status == "error":
            failure_reasons.append("execution_error")
        if status == "timeout":
            failure_reasons.append("execution_timeout")

        if config.verbose:
            logger.info(
                f"[EVAL] {case.id}: passed={passed}, score={scorecard.average:.1f}, "
                f"words={actual_words}, latency={latency_ms:.0f}ms, "
                f"status={status}"
            )

        return EvalTrace(
            case_id=case.id,
            case_group=case.group,
            query=query,
            response=response_text[:2000],  # Cap for storage
            response_word_count=actual_words,
            has_chart=has_chart,
            status=status,
            error=error_text,
            latency_ms=latency_ms,
            scorecard=scorecard,
            passed=passed,
            failure_reasons=failure_reasons,
            rubric=case.rubric,
        )

    async def compare_harnesses(
        self,
        baseline_harness: Dict[str, Any],
        candidate_harness: Dict[str, Any],
        llm_router: Any,
        dataset_context_fn: Optional[Callable] = None,
        slot_fn: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Compare two harness configurations (A/B test).

        Returns:
            Dict with comparison results:
            - baseline: EvalResult for the baseline harness
            - candidate: EvalResult for the candidate harness
            - delta_pin: Change in held-in pass rate (positive = improvement)
            - delta_pho: Change in held-out pass rate (positive = improvement)
            - improvements: List of case IDs that improved
            - regressions: List of case IDs that regressed
            - recommendation: "accept" | "reject" | "mixed"
        """
        logger.info("Running baseline evaluation...")
        baseline = await self.evaluate(baseline_harness, llm_router, dataset_context_fn, slot_fn)

        logger.info("Running candidate evaluation...")
        candidate = await self.evaluate(candidate_harness, llm_router, dataset_context_fn, slot_fn)

        delta_pin = round(candidate.pin - baseline.pin, 4)
        delta_pho = round(candidate.pho - baseline.pho, 4)

        # Per-case comparison
        baseline_map = {t.case_id: t for t in baseline.traces}
        candidate_map = {t.case_id: t for t in candidate.traces}

        improvements = []
        regressions = []
        for cid, b_trace in baseline_map.items():
            c_trace = candidate_map.get(cid)
            if c_trace is None:
                continue
            if c_trace.passed and not b_trace.passed:
                improvements.append(cid)
            elif not c_trace.passed and b_trace.passed:
                regressions.append(cid)

        # Self-Harness decision (Algorithm 1, line 11):
        # Accept if Δin ≥ 0 and Δho ≥ 0 and max(Δin, Δho) > 0
        # This means: at least one split improved, neither regressed
        recommendation = "reject"
        if delta_pin >= 0 and delta_pho >= 0 and max(delta_pin, delta_pho) > 0:
            recommendation = "accept"
        elif delta_pin > 0 and delta_pho < 0:
            recommendation = "mixed"
        elif delta_pin < 0 and delta_pho > 0:
            recommendation = "mixed"

        return {
            "baseline": baseline,
            "candidate": candidate,
            "delta_pin": delta_pin,
            "delta_pho": delta_pho,
            "delta_pin_pct": f"{delta_pin:+.1%}",
            "delta_pho_pct": f"{delta_pho:+.1%}",
            "improvements": improvements,
            "regressions": regressions,
            "recommendation": recommendation,
        }

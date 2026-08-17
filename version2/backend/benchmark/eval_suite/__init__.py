"""
Eval Suite — Self-Harness Evaluation Infrastructure
====================================================
Implements the EVALUATE() function from Algorithm 1 of Self-Harness:

    (Pin(ht), Pho(ht), Rt) ← EVALUATE(M, ht, Din, Dho, E)

Where:
- M: Fixed model (your LLM routing chain)
- ht: Current harness (prompts + runtime configuration)
- Din: Held-in task split (70% of cases)
- Dho: Held-out task split (30% of cases)
- E: Scorer that evaluates response quality
- Pin: Pass rate on held-in split
- Pho: Pass rate on held-out split
- Rt: Raw traces for weakness mining

Components:
    eval_cases.py    — Curated test cases with held-in/held-out splits
    eval_suite.py    — Core EVALUATE() orchestrator
    eval_runner.py   — CLI for running evaluations and comparisons

Usage:
    from benchmark.eval_suite import eval_suite, EvalCase, EvalResult
    result = await eval_suite.evaluate(harness, llm_router, db)
    print(f"Held-in: {result.pin:.1%}, Held-out: {result.pho:.1%}")
"""

from .eval_suite import EvalSuite, EvalResult, EvalConfig
from .eval_cases import EvalCase, EvalCaseRegistry, ChallengeLevel

eval_suite = EvalSuite()

__all__ = [
    "eval_suite",
    "EvalSuite",
    "EvalResult",
    "EvalConfig",
    "EvalCase",
    "EvalCaseRegistry",
    "ChallengeLevel",
]

"""
Eval Runner — CLI for Running Self-Harness Evaluations
=======================================================

Usage:
    # Quick sanity check (heuristic scorer, no LLM)
    python -m benchmark.eval_suite.eval_runner quick

    # Full evaluation against a dataset
    python -m benchmark.eval_suite.eval_runner run --dataset <dataset_id>

    # Compare baseline vs candidate harness
    python -m benchmark.eval_suite.eval_runner compare --baseline-temp 0.4 --candidate-temp 0.3

    # List available test cases
    python -m benchmark.eval_suite.eval_runner list

    # Show summary stats about the evaluation registry
    python -m benchmark.eval_suite.eval_runner stats

    # Run specific challenge level
    python -m benchmark.eval_suite.eval_runner run --level analytical

    # Verbose mode with per-case logging
    python -m benchmark.eval_suite.eval_runner run --verbose

Output:
    - Console summary with pass rates and dimension averages
    - results/eval_{timestamp}.json — full evaluation trace
    - results/compare_{timestamp}.json — comparison report
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from benchmark.eval_suite import (
    eval_suite,
    EvalConfig,
    EvalResult,
    ChallengeLevel,
    EvalCaseRegistry,
    registry as case_registry,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

RESULTS_DIR = Path(__file__).parent.parent / "results"


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{seconds / 60:.1f}m"


def _print_result(result: EvalResult):
    """Print a formatted evaluation result to console."""
    total_passed = result.held_in_passed + result.held_out_passed
    total_rate = total_passed / max(result.total_cases, 1)

    print("\n" + "=" * 64)
    print(f"  Evaluation: {result.harness_label}")
    print(f"  Duration:   {_format_duration(result.duration_seconds)}")
    print(f"  Timestamp:  {result.timestamp}")
    print("=" * 64)

    print(f"\n  📊 Pass Rates")
    print(f"  {'Split':<20} {'Passed':<16} {'Rate':<10}")
    print(f"  {'-'*46}")
    print(f"  {'Held-in (Din)':<20} {result.held_in_passed}/{result.held_in_cases:<10} "
          f"{result.pin:>6.1%}")
    print(f"  {'Held-out (Dho)':<20} {result.held_out_passed}/{result.held_out_cases:<10} "
          f"{result.pho:>6.1%}")
    print(f"  {'Total':<20} {total_passed}/{result.total_cases:<10} {total_rate:>6.1%}")

    print(f"\n  📈 Dimension Averages (out of 5)")
    dims = result.dimension_averages()
    for dim, avg in sorted(dims.items()):
        bar = "█" * int(avg) + "░" * (5 - int(avg))
        print(f"    {dim.replace('_', ' ').title():<22} {bar}  {avg}/5")

    print(f"\n  ⚠️  Errors: {result.errors} | Timeouts: {result.timeouts}")

    if result.traces:
        failures = [t for t in result.traces if not t.passed]
        if failures:
            print(f"\n  🔴 Top {min(5, len(failures))} Failures")
            for t in failures[:5]:
                print(f"    ✗ {t.case_id}: {', '.join(t.failure_reasons[:3])}")
                if t.error:
                    print(f"      Error: {t.error[:100]}")
    print("=" * 64 + "\n")


def _print_comparison(comparison: Dict[str, Any]):
    """Print formatted A/B comparison results."""
    baseline: EvalResult = comparison["baseline"]
    candidate: EvalResult = comparison["candidate"]

    print("\n" + "=" * 70)
    print("  🔄 Harness A/B Comparison")
    print("=" * 70)

    print(f"\n  {'Metric':<30} {'Baseline':<18} {'Candidate':<18} {'Δ':<10}")
    print(f"  {'-'*76}")

    pin_str = f"{baseline.pin:.1%} [{baseline.held_in_passed}/{baseline.held_in_cases}]"
    pin_can = f"{candidate.pin:.1%} [{candidate.held_in_passed}/{candidate.held_in_cases}]"
    pin_delta = comparison["delta_pin_pct"]
    print(f"  {'Held-in Pass Rate (Pin)':<30} {pin_str:<18} {pin_can:<18} {pin_delta:<10}")

    pho_str = f"{baseline.pho:.1%} [{baseline.held_out_passed}/{baseline.held_out_cases}]"
    pho_can = f"{candidate.pho:.1%} [{candidate.held_out_passed}/{candidate.held_out_cases}]"
    pho_delta = comparison["delta_pho_pct"]
    print(f"  {'Held-out Pass Rate (Pho)':<30} {pho_str:<18} {pho_can:<18} {pho_delta:<10}")

    print(f"\n  🏆 Recommendation: {comparison['recommendation'].upper()}")
    if comparison["improvements"]:
        print(f"  ✅ Improvements ({len(comparison['improvements'])}):")
        for cid in comparison["improvements"][:10]:
            print(f"     + {cid}")
    if comparison["regressions"]:
        print(f"  ❌ Regressions ({len(comparison['regressions'])}):")
        for cid in comparison["regressions"][:10]:
            print(f"     - {cid}")

    print("=" * 70 + "\n")


async def cmd_quick(args: argparse.Namespace):
    """Quick heuristic sanity check — no LLM needed."""
    print("Running quick heuristic sanity check...")

    # Null router stub for heuristic-only eval (no LLM calls)
    class _NullRouter:
        """Stub that signals evaluate() to skip LLM calls entirely."""
        _is_null_router = True

        async def call(self, *args, **kwargs):
            return {"response_text": "[null router — heuristic check only]"}

    result = await eval_suite.evaluate(
        harness={"model_role": "heuristic_test", "temperature": 0.4},
        llm_router=_NullRouter(),
    )

    _print_result(result)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output = {
        "type": "quick",
        "timestamp": timestamp,
        "result": result,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_path = RESULTS_DIR / f"eval_{timestamp}.json"
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"Results saved to: {results_path}")


async def cmd_run(args: argparse.Namespace):
    """Run a full evaluation against a dataset."""
    print(f"Running evaluation (level={args.level or 'all'}, verbose={args.verbose})...")

    # Resolve challenge levels
    levels = None
    if args.level:
        level_map = {
            "basic": ChallengeLevel.L1_BASIC,
            "analytical": ChallengeLevel.L2_ANALYTICAL,
            "multi_turn": ChallengeLevel.L3_MULTI_TURN,
            "edge": ChallengeLevel.L4_EDGE,
        }
        matched = level_map.get(args.level.lower())
        if not matched:
            print(f"Unknown level '{args.level}'. Options: basic, analytical, multi_turn, edge")
            return
        levels = [matched]

    config = EvalConfig(
        levels=levels,
        verbose=args.verbose,
        max_concurrent=args.concurrency or 5,
    )

    # Build harness
    harness = {
        "model_role": args.model_role or "chart_engine",
        "temperature": args.temperature or 0.4,
    }

    # If a dataset ID is provided, build dataset context and slot resolvers
    slot_fn = None
    dataset_context_fn = None

    if args.dataset:
        dataset_id = args.dataset
        user_id = args.user or "eval_user"

        async def resolve_slots():
            """Resolve column name slots from the dataset schema."""
            try:
                from db.database import get_database
                from bson import ObjectId

                db = get_database()
                doc = await db.uploads.find_one({"_id": ObjectId(dataset_id)})
                if not doc or not doc.get("metadata"):
                    return {}

                metadata = doc["metadata"]
                schema = metadata.get("schema", {})
                columns = list(schema.keys()) if schema else []
                num_cols = [c for c in columns if schema[c].get("dtype", "").startswith(("int", "float"))]
                cat_cols = [c for c in columns if c not in num_cols]
                time_cols = [c for c in columns if any(kw in c.lower() for kw in ["date", "time", "year", "month"])]

                return {
                    "num1": num_cols[0] if num_cols else columns[0] if columns else "value",
                    "num2": num_cols[1] if len(num_cols) > 1 else num_cols[0] if num_cols else "value2",
                    "cat1": cat_cols[0] if cat_cols else columns[-1] if columns else "category",
                    "cat2": cat_cols[1] if len(cat_cols) > 1 else cat_cols[0] if cat_cols else "category2",
                    "time1": time_cols[0] if time_cols else columns[0] if columns else "date",
                }
            except Exception as e:
                logger.warning(f"Slot resolution failed: {e}")
                return {}

        async def resolve_dataset_context():
            """Build context string for the dataset."""
            try:
                from db.database import get_database
                from bson import ObjectId
                from services.datasets.dataset_loader import create_context_string

                db = get_database()
                doc = await db.uploads.find_one({"_id": ObjectId(dataset_id)})
                if not doc or not doc.get("metadata"):
                    return "", {}

                metadata = doc["metadata"]
                context_str = create_context_string(metadata)
                slots = await resolve_slots()
                return context_str, slots
            except Exception as e:
                logger.warning(f"Dataset context resolution failed: {e}")
                return "", {}

        slot_fn = resolve_slots
        dataset_context_fn = resolve_dataset_context

    # Run evaluation
    from llm.router import llm_router

    result = await eval_suite.evaluate(
        harness=harness,
        llm_router=llm_router if args.dataset else None,
        dataset_context_fn=dataset_context_fn if args.dataset else None,
        slot_fn=slot_fn if args.dataset else None,
    )

    _print_result(result)

    # Save results
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output = {
        "type": "evaluation",
        "timestamp": timestamp,
        "config": {
            "harness": harness,
            "level": args.level,
            "dataset": args.dataset,
            "verbose": args.verbose,
        },
        "result": result,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_path = RESULTS_DIR / f"eval_{timestamp}.json"
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"Full results saved to: {results_path}")

    # Print failure clusters for weakness mining
    if result.traces:
        clusters = result.failure_clusters()
        if clusters:
            print("\n  📋 Failure Clusters (for Weakness Mining)")
            print(f"  {'Failure Reason':<45} {'Count':<8}")
            print(f"  {'-'*53}")
            for reason, count in list(clusters.items())[:10]:
                print(f"  {reason:<45} {count:<8}")


async def cmd_compare(args: argparse.Namespace):
    """Compare baseline vs candidate harness configurations."""
    print(f"Comparing baseline (temp={args.baseline_temp}) vs candidate (temp={args.candidate_temp})...")

    baseline_harness = {
        "model_role": args.model_role or "chart_engine",
        "temperature": args.baseline_temp or 0.4,
    }
    candidate_harness = {
        "model_role": args.model_role or "chart_engine",
        "temperature": args.candidate_temp or 0.3,
    }

    from llm.router import llm_router

    comparison = await eval_suite.compare_harnesses(
        baseline_harness=baseline_harness,
        candidate_harness=candidate_harness,
        llm_router=llm_router,
    )

    _print_comparison(comparison)

    # Save comparison results
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output = {
        "type": "comparison",
        "timestamp": timestamp,
        "config": {
            "baseline": baseline_harness,
            "candidate": candidate_harness,
        },
        "comparison": {
            "delta_pin": comparison["delta_pin"],
            "delta_pho": comparison["delta_pho"],
            "recommendation": comparison["recommendation"],
            "improvements": comparison["improvements"],
            "regressions": comparison["regressions"],
        },
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_path = RESULTS_DIR / f"compare_{timestamp}.json"
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"Comparison saved to: {results_path}")


async def cmd_list(args: argparse.Namespace):
    """List all registered test cases."""
    registry = EvalCaseRegistry()
    print(f"\n{'ID':<30} {'Level':<12} {'Split':<10} {'Min Words':<10}")
    print(f"{'-'*62}")
    for case in registry.all_cases:
        print(f"{case.id:<30} {case.level.value:<12} {case.split.value:<10} {case.min_words:<10}")

    stats = registry.stats
    print(f"\nStats: {stats['total']} total cases")
    print(f"  Held-in:  {stats['held_in']} ({stats['held_in']/stats['total']*100:.0f}%)")
    print(f"  Held-out: {stats['held_out']} ({stats['held_out']/stats['total']*100:.0f}%)")
    print(f"  By Level:")
    for level, count in stats["by_level"].items():
        print(f"    {level}: {count}")
    print(f"  By Group:")
    for group, count in stats["by_group"].items():
        print(f"    {group}: {count}")


async def cmd_stats(args: argparse.Namespace):
    """Show aggregate stats about the evaluation suite."""
    from benchmark.eval_suite.eval_cases import registry as cr

    stats = cr.stats
    print("\n📊 Evaluation Suite Stats")
    print("=" * 40)
    print(f"  Total cases:   {stats['total']}")
    print(f"  Held-in (Din): {stats['held_in']} ({stats['held_in']/max(stats['total'],1)*100:.0f}%)")
    print(f"  Held-out (Dho):{stats['held_out']} ({stats['held_out']/max(stats['total'],1)*100:.0f}%)")
    print(f"\n  By Challenge Level:")
    for level, count in stats["by_level"].items():
        print(f"    {level:<20} {count}")
    print(f"\n  By Group:")
    for group, count in sorted(stats["by_group"].items()):
        print(f"    {group:<30} {count}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Self-Harness Evaluation Suite CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m benchmark.eval_suite.eval_runner quick
  python -m benchmark.eval_suite.eval_runner run --dataset <id> --verbose
  python -m benchmark.eval_suite.eval_runner compare --baseline-temp 0.4 --candidate-temp 0.3
  python -m benchmark.eval_suite.eval_runner list
  python -m benchmark.eval_suite.eval_runner stats
  python -m benchmark.eval_suite.eval_runner run --level analytical
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # quick
    p_quick = subparsers.add_parser("quick", help="Quick heuristic sanity check (no LLM needed)")

    # run
    p_run = subparsers.add_parser("run", help="Run full evaluation against a dataset")
    p_run.add_argument("--dataset", "-d", type=str, default=None,
                       help="Dataset ID to evaluate against")
    p_run.add_argument("--user", "-u", type=str, default="eval_user",
                       help="User ID for access control")
    p_run.add_argument("--level", "-l", type=str, default=None,
                       choices=["basic", "analytical", "multi_turn", "edge"],
                       help="Filter by challenge level")
    p_run.add_argument("--model-role", "-m", type=str, default="chart_engine",
                       help="LLM model role to use")
    p_run.add_argument("--temperature", "-t", type=float, default=0.4,
                       help="Temperature for generation")
    p_run.add_argument("--concurrency", "-c", type=int, default=5,
                       help="Max concurrent evaluations")
    p_run.add_argument("--verbose", "-v", action="store_true",
                       help="Enable per-case logging")

    # compare
    p_compare = subparsers.add_parser("compare", help="A/B compare harness configurations")
    p_compare.add_argument("--model-role", "-m", type=str, default="chart_engine",
                           help="LLM model role to use")
    p_compare.add_argument("--baseline-temp", type=float, default=0.4,
                           help="Baseline temperature")
    p_compare.add_argument("--candidate-temp", type=float, default=0.3,
                           help="Candidate temperature")
    p_compare.add_argument("--dataset", "-d", type=str, default=None,
                           help="Dataset ID (optional)")

    # list
    subparsers.add_parser("list", help="List all registered test cases")

    # stats
    subparsers.add_parser("stats", help="Show evaluation suite statistics")

    return parser.parse_args()


async def main():
    args = parse_args()

    command_map = {
        "quick": cmd_quick,
        "run": cmd_run,
        "compare": cmd_compare,
        "list": cmd_list,
        "stats": cmd_stats,
    }

    handler = command_map.get(args.command)
    if handler:
        await handler(args)
    else:
        print(f"Unknown command: {args.command}")


if __name__ == "__main__":
    asyncio.run(main())

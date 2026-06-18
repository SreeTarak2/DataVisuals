"""
Confidence Calibration Analysis
================================

Benchmark question: When Signal says X confidence, is it right X% of the time?

This script analyzes the 92-dataset benchmark results and answers:
1. Primary confidence calibration — does 0.80 confidence mean 80% accuracy?
2. Abstention calibration — when Signal says "no entity" (0.0), how often is that right?
3. Entity-level calibration — how does entity_confidence map to entity validity?
4. Participant calibration — how does participation_score map to participant accuracy?
5. Evidence trace consistency — do higher-contribution columns correlate with correct predictions?

Usage:
    cd version2/backend
    python benchmark/calibration_analysis.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BENCHMARK_DIR = Path(__file__).parent
RESULTS_DIR = BENCHMARK_DIR / "results"


def load_latest_results() -> dict:
    """Load the most recent benchmark results file."""
    result_files = sorted(RESULTS_DIR.glob("results_*.json"))
    if not result_files:
        print("No benchmark results found. Run benchmark first.")
        sys.exit(1)
    with open(result_files[-1]) as f:
        return json.load(f)


BIN_EDGES = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.01]


def bin_confidence(conf: float) -> str:
    """Assign a confidence value to a bin label."""
    for i in range(len(BIN_EDGES) - 1):
        lo, hi = BIN_EDGES[i], BIN_EDGES[i + 1]
        if lo <= conf < hi:
            return f"{lo:.1f}-{hi:.1f}"
    return "unknown"


def primary_calibration(results: list) -> dict:
    """
    Primary object confidence calibration.

    For each dataset with a non-abstention prediction (confidence > 0),
    bin by primary_confidence and compute actual accuracy within each bin.
    Also tracks the calibration error: |expected_accuracy - actual_accuracy|.

    Abstention datasets (confidence = 0.0, no entities expected) are
    analyzed separately.
    """
    bins: dict[str, dict] = {}
    for r in results:
        conf = r["evidence_strength"]
        correct = r["primary_correct"]

        # Skip abstention cases (evidence_strength = 0.0, no entities)
        # — analyzed separately
        if conf == 0.0:
            continue

        label = bin_confidence(conf)
        if label not in bins:
            bins[label] = {"count": 0, "correct": 0, "expected_sum": 0.0}
        bins[label]["count"] += 1
        bins[label]["correct"] += 1 if correct else 0
        bins[label]["expected_sum"] += conf

    table = []
    for label in sorted(bins.keys()):
        b = bins[label]
        actual_accuracy = b["correct"] / b["count"] if b["count"] > 0 else 0.0
        expected_accuracy = b["expected_sum"] / b["count"] if b["count"] > 0 else 0.0
        cal_error = abs(expected_accuracy - actual_accuracy)
        table.append({
            "bin": label,
            "count": b["count"],
            "correct": b["correct"],
            "expected_accuracy": round(expected_accuracy, 3),
            "actual_accuracy": round(actual_accuracy, 3),
            "calibration_error": round(cal_error, 3),
        })

    return {
        "samples": sum(b["count"] for b in bins.values()),
        "bins": table,
        "mean_abs_error": round(
            sum(b["calibration_error"] for b in table) / len(table) if table else 0.0,
            3,
        ),
    }


def abstention_calibration(results: list) -> dict:
    """
    Abstention calibration — when Signal says "no valid entity" (confidence=0.0),
    how often is that correct?

    Also checks: when confidence > 0 but no primary was predicted, was that correct?
    """
    abstention_cases = [r for r in results if r["evidence_strength"] == 0.0]
    non_abstention = [r for r in results if r["evidence_strength"] > 0.0]

    correct_abstain = sum(1 for r in abstention_cases if r["abstention_correct"])
    correct_non_abstain = sum(1 for r in non_abstention if r["abstention_correct"])

    total_abstain = len(abstention_cases)
    total_non_abstain = len(non_abstention)

    return {
        "total_datasets": len(results),
        "abstention_cases": total_abstain,
        "non_abstention_cases": total_non_abstain,
        "abstention_accuracy": round(correct_abstain / total_abstain, 3) if total_abstain > 0 else 0.0,
        "non_abstention_accuracy": round(correct_non_abstain / total_non_abstain, 3) if total_non_abstain > 0 else 0.0,
        "overall_abstention_accuracy": round(
            (correct_abstain + correct_non_abstain) / len(results), 3
        ),
    }


def participant_calibration(results: list) -> dict:
    """
    Participant confidence calibration.

    For datasets with valid participants (both expected and predicted),
    compare the participation_score distribution to actual participant accuracy.
    
    Since we don't have per-participant confidence in the benchmark output,
    we use dataset-level participant precision as a proxy, correlated with
    primary_confidence and entity_count.
    """
    # Group datasets by primary_confidence bin and compute avg participant precision
    bins: dict[str, dict] = {}
    for r in results:
        if r["entity_count"] < 2:  # Skip single-entity datasets (no participants)
            continue

        conf = r["evidence_strength"]
        if conf == 0.0:
            continue

        label = bin_confidence(conf)
        if label not in bins:
            bins[label] = {"count": 0, "sum_precision": 0.0, "sum_recall": 0.0}
        bins[label]["count"] += 1
        bins[label]["sum_precision"] += r["participant_precision"]
        bins[label]["sum_recall"] += r["participant_recall"]

    table = []
    for label in sorted(bins.keys()):
        b = bins[label]
        table.append({
            "bin": label,
            "count": b["count"],
            "avg_participant_precision": round(b["sum_precision"] / b["count"], 3) if b["count"] > 0 else 0.0,
            "avg_participant_recall": round(b["sum_recall"] / b["count"], 3) if b["count"] > 0 else 0.0,
        })

    return {
        "multi_entity_datasets": sum(b["count"] for b in bins.values()),
        "bins": table,
    }


def ambiguity_calibration(results: list) -> dict:
    """
    Ambiguity detection calibration.

    When the system says High ambiguity (ambiguity.level == "high"),
    how often is the prediction acceptably within the ambiguous set?
    """
    high_ambig = [r for r in results if r.get("ambiguity_level") == "high"]
    low_ambig = [r for r in results if r.get("ambiguity_level") in ("low", None)]

    # Among high-ambiguity datasets, how many have correct primary?
    correct_in_high = sum(1 for r in high_ambig if r["primary_correct"])
    ambiguous_accepted = sum(1 for r in high_ambig if r.get("ambiguity_accepted", False))

    return {
        "high_ambiguity_count": len(high_ambig),
        "low_ambiguity_count": len(low_ambig),
        "correct_in_high_ambiguity": correct_in_high,
        "accepted_as_ambiguous": ambiguous_accepted,
        "high_ambig_accuracy": round(correct_in_high / len(high_ambig), 3) if high_ambig else 0.0,
    }


def evidence_trace_consistency(results: list) -> dict:
    """
    Check that evidence traces are internally consistent.

    The sum of all evidence_trace contributions should approximately equal
    0.45 * column_dominance_score for each dataset.
    """
    mismatches = []
    for r in results:
        trace = r.get("evidence_trace", [])
        if not trace:
            continue
        trace_sum = sum(t["contribution"] for t in trace)
        dom_score = r.get("evidence_strength", 0.0)
        # The trace sum should be close to the contribution from column_dominance
        # which is 0.45 * dom_score_raw. But we use primary_confidence as a proxy.
        mismatch = abs(trace_sum - (dom_score * 0.45))
        if mismatch > 0.05:  # Allow small rounding errors
            mismatches.append({
                "dataset": r["dataset"],
                "trace_sum": round(trace_sum, 4),
                "expected": round(dom_score * 0.45, 4),
                "mismatch": round(mismatch, 4),
            })

    return {
        "datasets_with_traces": sum(1 for r in results if r.get("evidence_trace")),
        "internal_mismatches": len(mismatches),
        "details": mismatches[:5],  # Show first 5 mismatches
    }


def calibration_summary(results: list) -> dict:
    """
    Expected Calibration Error (ECE) — the standard calibration metric.

    ECE = sum_{b} (N_b / N) * |acc(b) - conf(b)|
    """
    # Filter to non-abstention datasets
    non_abstention = [r for r in results if r["evidence_strength"] > 0.0]
    total = len(non_abstention)

    bins: dict[str, dict] = {}
    for r in non_abstention:
        conf = r["evidence_strength"]
        correct = r["primary_correct"]
        label = bin_confidence(conf)
        if label not in bins:
            bins[label] = {"count": 0, "correct": 0, "conf_sum": 0.0}
        bins[label]["count"] += 1
        bins[label]["correct"] += 1 if correct else 0
        bins[label]["conf_sum"] += conf

    ece = 0.0
    for label, b in bins.items():
        if b["count"] == 0:
            continue
        acc = b["correct"] / b["count"]
        avg_conf = b["conf_sum"] / b["count"]
        weight = b["count"] / total
        ece += weight * abs(acc - avg_conf)

    return {
        "expected_calibration_error": round(ece, 4),
        "total_non_abstention": total,
        "bin_count": len(bins),
    }


def print_report(primary: dict, abstention: dict, participants: dict,
                 ambiguity: dict, evidence: dict, summary: dict):
    """Print formatted calibration report."""
    print("=" * 72)
    print("  SIGNAL CONFIDENCE CALIBRATION REPORT")
    print("  Phase 3B — 92-dataset benchmark")
    print("=" * 72)

    # ── 1. Primary Confidence Calibration ──
    print("\n" + "─" * 72)
    print("  [1] PRIMARY CONFIDENCE CALIBRATION")
    print("  ───────────────────────────────")
    print(f"  Datasets with predictions:  {primary['samples']}")
    print(f"  Mean absolute bin error:    {primary['mean_abs_error']}")
    print()
    print(f"  {'Bin':<14} {'Count':<8} {'Expected':<12} {'Actual':<12} {'Error':<8}")
    print(f"  {'───':<14} {'─────':<8} {'────────':<12} {'──────':<12} {'─────':<8}")
    for b in primary["bins"]:
        expected_pct = f"{b['expected_accuracy']:.1%}"
        actual_pct = f"{b['actual_accuracy']:.1%}"
        cal_pct = f"{b['calibration_error']:.1%}"
        print(f"  {b['bin']:<14} {b['count']:<8} {expected_pct:<12} {actual_pct:<12} {cal_pct:<8}")

    # ── 2. Abstention Calibration ──
    print("\n" + "─" * 72)
    print("  [2] ABSTENTION CALIBRATION")
    print("  ─────────────────────────")
    print(f"  Total datasets:                  {abstention['total_datasets']}")
    print(f"  Abstention cases (conf=0.0):     {abstention['abstention_cases']}")
    print(f"  Non-abstention cases (conf>0):   {abstention['non_abstention_cases']}")
    print(f"  Abstention accuracy:             {abstention['abstention_accuracy']:.1%}")
    print(f"  Non-abstention accuracy:         {abstention['non_abstention_accuracy']:.1%}")
    print(f"  Overall abstention accuracy:     {abstention['overall_abstention_accuracy']:.1%}")

    # ── 3. Participant Calibration ──
    print("\n" + "─" * 72)
    print("  [3] PARTICIPANT CALIBRATION")
    print("  ──────────────────────────")
    print(f"  Multi-entity datasets:  {participants['multi_entity_datasets']}")
    print()
    for b in participants["bins"]:
        print(f"  Bin {b['bin']:<10}  ({b['count']} datasets)  "
              f"Prec={b['avg_participant_precision']:.1%}  "
              f"Recall={b['avg_participant_recall']:.1%}")

    # ── 4. Ambiguity Calibration ──
    print("\n" + "─" * 72)
    print("  [4] AMBIGUITY CALIBRATION")
    print("  ────────────────────────")
    print(f"  High-ambiguity datasets:    {ambiguity['high_ambiguity_count']}")
    print(f"  Low-ambiguity datasets:     {ambiguity['low_ambiguity_count']}")
    print(f"  Correct in high-ambiguity:  {ambiguity['correct_in_high_ambiguity']}")
    print(f"  Accepted as ambiguous:      {ambiguity['accepted_as_ambiguous']}")
    print(f"  High-ambiguity accuracy:    {ambiguity['high_ambig_accuracy']:.1%}")

    # ── 5. Evidence Trace Consistency ──
    print("\n" + "─" * 72)
    print("  [5] EVIDENCE TRACE CONSISTENCY")
    print("  ─────────────────────────────")
    print(f"  Datasets with traces:    {evidence['datasets_with_traces']}")
    print(f"  Internal mismatches:     {evidence['internal_mismatches']}")
    if evidence["details"]:
        print()
        for m in evidence["details"]:
            print(f"  ⚠  {m['dataset']:<45} trace={m['trace_sum']} expected={m['expected']}")

    # ── 6. Expected Calibration Error ──
    print("\n" + "─" * 72)
    print("  [6] EXPECTED CALIBRATION ERROR (ECE)")
    print("  ───────────────────────────────────")
    print(f"  ECE:                    {summary['expected_calibration_error']:.4f}")
    print(f"  Total non-abstention:   {summary['total_non_abstention']}")
    print(f"  Bins:                   {summary['bin_count']}")
    print()

    # ── Interpretation ──
    print("─" * 72)
    print("  INTERPRETATION")
    print("  ───────────────")
    ece = summary["expected_calibration_error"]
    if ece < 0.05:
        print("  ✅ Well-calibrated. Confidence closely matches accuracy.")
    elif ece < 0.10:
        print("  ⚠  Moderately calibrated. Some confidence-accuracy gaps exist.")
    else:
        print("  ❌ Poorly calibrated. Confidence does not match accuracy.")

    # Check specific bins for over/under confidence
    print()
    for b in primary["bins"]:
        diff = b["actual_accuracy"] - b["expected_accuracy"]
        if abs(diff) > 0.10:
            direction = "overconfident" if diff < 0 else "underconfident"
            print(f"  ⚠  Bin {b['bin']}: {direction} by {abs(diff):.1%} "
                  f"(expected {b['expected_accuracy']:.1%}, actual {b['actual_accuracy']:.1%})")

    print("=" * 72)


def main():
    data = load_latest_results()
    results = data["results"]

    print(f"Loaded {len(results)} datasets from {data['timestamp']}")
    print()

    primary = primary_calibration(results)
    abstention = abstention_calibration(results)
    participants = participant_calibration(results)
    ambiguity = ambiguity_calibration(results)
    evidence = evidence_trace_consistency(results)
    summary = calibration_summary(results)

    print_report(primary, abstention, participants, ambiguity, evidence, summary)

    # Save detailed calibration data
    output = {
        "timestamp": data["timestamp"],
        "total_datasets": len(results),
        "primary_calibration": primary,
        "abstention_calibration": abstention,
        "participant_calibration": participants,
        "ambiguity_calibration": ambiguity,
        "evidence_trace_consistency": evidence,
        "ece_summary": summary,
    }

    output_path = RESULTS_DIR / f"calibration_{data['timestamp']}.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nDetailed calibration data saved to: {output_path}")


if __name__ == "__main__":
    main()

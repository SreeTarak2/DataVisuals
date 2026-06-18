"""
Benchmark runner — evaluates entity discovery against ground-truth manifest.

Usage:
    cd version2/backend
    python -m benchmark.run_benchmark

Output:
    - Console summary with metrics
    - results/results_{timestamp}.json  (detailed per-dataset)
    - results/failure_report_{timestamp}.json  (categorized failures)
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd

# Ensure the backend package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.knowledge_graph.models import (
    ColumnProfile,
    DiscoveredEntity,
)
from services.knowledge_graph.schema_profiler import schema_profiler
from services.knowledge_graph.signal_engine import signal_engine
from services.knowledge_graph.entity_discovery import entity_discovery
from services.knowledge_graph.primary_object_discovery import primary_object_discovery
from services.knowledge_graph.participation_discovery import participation_discovery
from services.knowledge_graph.reference_signal_detector import reference_signal_detector

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

BENCHMARK_DIR = Path(__file__).parent
DATASETS_DIR = BENCHMARK_DIR / "datasets"
RESULTS_DIR = BENCHMARK_DIR / "results"
MANIFEST_PATH = BENCHMARK_DIR / "manifest.json"


def df_to_column_profiles(df: pd.DataFrame) -> List[ColumnProfile]:
    """Convert a pandas DataFrame to a list of ColumnProfile objects."""
    profiles = []
    total_rows = len(df)

    for col_name in df.columns:
        col_data = df[col_name]
        non_null = col_data.dropna()
        null_count = total_rows - len(non_null)
        distinct_count = non_null.nunique()
        sample_values = non_null.head(10).astype(str).tolist()

        is_numeric = pd.api.types.is_numeric_dtype(col_data)
        is_string = pd.api.types.is_string_dtype(col_data)
        is_bool = pd.api.types.is_bool_dtype(col_data)

        if is_bool:
            data_type = "boolean"
        elif is_numeric:
            if col_data.dtype in ("int64", "Int64", "int32", "Int32"):
                data_type = "integer"
            else:
                data_type = "decimal"
        elif is_string or col_data.dtype == "object":
            data_type = "string"
        else:
            raw_type = str(col_data.dtype)
            data_type = schema_profiler._infer_type_from_name(col_name, sample_values, raw_type)

        profiles.append(
            ColumnProfile(
                name=col_name,
                data_type=data_type,
                null_ratio=round(null_count / total_rows, 4) if total_rows > 0 else 0.0,
                distinct_count=distinct_count,
                distinct_ratio=round(distinct_count / total_rows, 4) if total_rows > 0 else 0.0,
                sample_values=sample_values[:5],
                is_unique=distinct_count == total_rows and total_rows > 0,
                is_primary_key=False,
            )
        )
    return profiles


def load_manifest() -> dict:
    """Load the ground-truth manifest."""
    with open(MANIFEST_PATH) as f:
        return json.load(f)


MAX_ROWS = 5000


def evaluate_dataset(dataset_path: str, expected: dict) -> dict:
    """Run Signal on a single dataset and return predicted + metrics."""
    filename = os.path.basename(dataset_path)
    table_name = filename.replace(".csv", "")

    try:
        df = pd.read_csv(dataset_path, nrows=MAX_ROWS, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(dataset_path, nrows=MAX_ROWS, encoding="latin1")
    columns = df_to_column_profiles(df)

    # Run entity discovery pipeline
    report = entity_discovery.discover(columns, table_name)

    # Run primary object discovery
    primary = primary_object_discovery.discover(report.entities, table_name, len(columns))

    # Run participation discovery
    participants = participation_discovery.discover(report.entities, primary)

    # Run reference signal detection (Phase 3: Relationship Foundations)
    reference_signals = reference_signal_detector.detect(
        primary, participants, report.entities, columns
    )
    relationship_report = reference_signal_detector.build_report(primary, reference_signals)

    predicted_primary = primary.label if primary.is_valid else None
    predicted_participants = sorted({p.label for p in participants if p.is_valid})
    predicted_references = sorted({s.target_entity for s in reference_signals if s.is_valid})

    expected_primary = expected.get("expected_primary_object")
    expected_participants = sorted(expected.get("expected_participants", []))

    # ── Metrics ──────────────────────────────────────────────────────────

    # Primary object accuracy
    primary_correct = predicted_primary == expected_primary

    # Participant precision
    if predicted_participants:
        correct_predicted = sum(1 for p in predicted_participants if p in expected_participants)
        precision = correct_predicted / len(predicted_participants)
    else:
        precision = 1.0 if not expected_participants else 0.0

    # Participant recall
    if expected_participants:
        correct_found = sum(1 for p in expected_participants if p in predicted_participants)
        recall = correct_found / len(expected_participants)
    else:
        recall = 1.0 if not predicted_participants else 0.0

    # Reference signal accuracy
    expected_references = expected_participants
    if predicted_references:
        ref_correct = sum(1 for r in predicted_references if r in expected_references)
        reference_precision = ref_correct / len(predicted_references)
    else:
        reference_precision = 1.0 if not expected_references else 0.0

    if expected_references:
        ref_found = sum(1 for r in expected_references if r in predicted_references)
        reference_recall = ref_found / len(expected_references)
    else:
        reference_recall = 1.0 if not predicted_references else 0.0

    # Abstention accuracy
    abstention_correct = True
    if expected_primary is None and predicted_primary is not None:
        abstention_correct = False
    if not expected_participants and predicted_participants:
        abstention_correct = False

    # ── Ambiguity Analysis ────────────────────────────────────────────────
    ambiguity = primary.ambiguity
    alternatives = primary.alternatives
    alt_labels = {a.label for a in alternatives}

    # Check if the prediction is ambiguous but acceptable:
    # The expected primary is in the alternatives list AND ambiguity is high
    ambiguity_accepted = False
    if (
        not primary_correct
        and predicted_primary is not None
        and expected_primary is not None
        and predicted_primary != expected_primary
        and expected_primary in alt_labels
        and ambiguity is not None
        and ambiguity.level == "high"
    ):
        ambiguity_accepted = True

    # Failure:
    #   - Abstention errors always fail
    #   - Primary/participant errors only fail if NOT acceptably ambiguous
    #     (when the primary is ambiguous, the participant set naturally shifts
    #     because a different primary implies different foreign-key references)
    is_failure = not abstention_correct or (
        (not primary_correct or precision < 1.0 or recall < 1.0)
        and not ambiguity_accepted
    )

    # ── Outcome: one of correct / ambiguous / incorrect ─────────────────
    if abstention_correct and primary_correct and precision >= 1.0 and recall >= 1.0:
        outcome = "correct"
    elif ambiguity_accepted:
        outcome = "ambiguous"
    else:
        outcome = "incorrect"

    return {
        "dataset": filename,
        "expected_primary": expected_primary,
        "predicted_primary": predicted_primary,
        "primary_correct": primary_correct,
        "ambiguity_accepted": ambiguity_accepted,
        "ambiguity_level": ambiguity.level if ambiguity else None,
        "ambiguity_score": ambiguity.score if ambiguity else None,
        "alternatives": [a.label for a in alternatives],
        "expected_participants": expected_participants,
        "predicted_participants": predicted_participants,
        "participant_precision": round(precision, 3),
        "participant_recall": round(recall, 3),
        "reference_precision": round(reference_precision, 3),
        "reference_recall": round(reference_recall, 3),
        "reference_count": relationship_report.reference_count,
        "reference_cardinalities": {s.target_entity: s.cardinality for s in reference_signals if s.is_valid},
        "abstention_correct": abstention_correct,
        "is_failure": outcome == "incorrect",
        "outcome": outcome,
        "evidence_strength": primary.evidence_strength,
        "entity_count": len(report.entities),
        "table_name": table_name,
        "evidence_trace": [
            {"column": e.column_name, "role": e.role, "contribution": e.contribution}
            for e in primary.evidence_trace
        ],
    }


def categorize_failure(result: dict) -> Optional[str]:
    """Determine the failure category for a result."""
    if not result["abstention_correct"]:
        return "abstention"
    if not result["primary_correct"]:
        return "primary_object"
    if result["participant_recall"] < 1.0:
        return "participation_recall"
    if result["participant_precision"] < 1.0:
        return "participation_precision"
    return None


def run_benchmark() -> dict:
    """Run the full benchmark suite."""
    manifest = load_manifest()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    all_results = []
    failures = []

    print(f"{'Dataset':<35} {'Primary':<12} {'Prec':<8} {'Recall':<8} {'Abstain':<8} {'Status':<8}")
    print("-" * 79)

    for filename, expected in sorted(manifest.items()):
        dataset_path = DATASETS_DIR / filename
        if not dataset_path.exists():
            print(f"{filename:<35} {'MISSING':<12} {'':<8} {'':<8} {'':<8} {'SKIP':<8}")
            continue

        result = evaluate_dataset(str(dataset_path), expected)
        all_results.append(result)

        outcome = result["outcome"]
        if outcome == "correct":
            status_label = "✓"
        elif outcome == "ambiguous":
            status_label = "AMB"
        else:
            status_label = "FAIL"

        primary_str = str(result["predicted_primary"] or "∅")
        abstain_str = "✓" if result["abstention_correct"] else "✗"

        print(
            f"{filename:<35} {primary_str:<12} "
            f"{result['participant_precision']:<8.3f} "
            f"{result['participant_recall']:<8.3f} "
            f"{abstain_str:<8} {status_label:<8}"
        )

        if outcome == "incorrect":
            category = categorize_failure(result)
            failures.append(
                {
                    "dataset": filename,
                    "category": category,
                    "expected_primary": result["expected_primary"],
                    "predicted_primary": result["predicted_primary"],
                    "expected_participants": result["expected_participants"],
                    "predicted_participants": result["predicted_participants"],
                    "reason": _failure_reason(result),
                }
            )

    # ── Aggregate Metrics ────────────────────────────────────────────────
    total = len(all_results)
    if total == 0:
        print("\nNo datasets evaluated.")
        return {"total": 0}

    primary_correct_count = sum(1 for r in all_results if r["primary_correct"])
    abstention_correct_count = sum(1 for r in all_results if r["abstention_correct"])
    correct_count = sum(1 for r in all_results if r["outcome"] == "correct")
    ambiguous_count = sum(1 for r in all_results if r["outcome"] == "ambiguous")
    incorrect_count = sum(1 for r in all_results if r["outcome"] == "incorrect")
    avg_precision = sum(r["participant_precision"] for r in all_results) / total if total else 0
    avg_recall = sum(r["participant_recall"] for r in all_results) / total if total else 0
    avg_ref_precision = sum(r["reference_precision"] for r in all_results) / total if total else 0
    avg_ref_recall = sum(r["reference_recall"] for r in all_results) / total if total else 0
    total_refs = sum(r["reference_count"] for r in all_results)

    metrics = {
        "total_datasets": total,
        "correct": correct_count,
        "ambiguous": ambiguous_count,
        "incorrect": incorrect_count,
        "primary_object_accuracy": round(primary_correct_count / total, 3),
        "participant_precision": round(avg_precision, 3),
        "participant_recall": round(avg_recall, 3),
        "reference_precision": round(avg_ref_precision, 3),
        "reference_recall": round(avg_ref_recall, 3),
        "total_references": total_refs,
        "abstention_accuracy": round(abstention_correct_count / total, 3),
        "failure_count": len(failures),
    }

    print("\n" + "=" * 60)
    print(f"  Datasets Evaluated:       {total}")
    print(f"  ├─ Correct:               {correct_count}")
    print(f"  ├─ Ambiguous:             {ambiguous_count}")
    print(f"  └─ Incorrect:             {incorrect_count}")
    print(f"  Primary Object Accuracy:  {metrics['primary_object_accuracy']:.1%}")
    print(f"  Participant Precision:    {metrics['participant_precision']:.1%}")
    print(f"  Participant Recall:       {metrics['participant_recall']:.1%}")
    print(f"  Reference Precision:      {metrics['reference_precision']:.1%}")
    print(f"  Reference Recall:         {metrics['reference_recall']:.1%}")
    print(f"  Total Reference Signals:  {total_refs}")
    print(f"  Abstention Accuracy:      {metrics['abstention_accuracy']:.1%}")
    print(f"  True Failures:            {incorrect_count}")
    print("=" * 60)

    # ── Save Results ─────────────────────────────────────────────────────
    output = {
        "timestamp": timestamp,
        "metrics": metrics,
        "results": all_results,
        "failures": failures,
    }

    results_path = RESULTS_DIR / f"results_{timestamp}.json"
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nFull results saved to: {results_path}")

    failures_path = RESULTS_DIR / f"failure_report_{timestamp}.json"
    with open(failures_path, "w") as f:
        json.dump(
            {
                "timestamp": timestamp,
                "total_datasets": total,
                "failure_count": len(failures),
                "failures": failures,
                "failure_categories": _count_categories(failures),
            },
            f,
            indent=2,
            default=str,
        )
    print(f"Failure report saved to: {failures_path}")

    return output


def _failure_reason(result: dict) -> str:
    if not result["abstention_correct"]:
        return f"Expected no primary, got '{result['predicted_primary']}'"
    if not result["primary_correct"]:
        return (
            f"Expected primary '{result['expected_primary']}', got '{result['predicted_primary']}'"
        )
    if result["participant_recall"] < 1.0:
        missing = set(result["expected_participants"]) - set(result["predicted_participants"])
        return f"Missing participants: {missing}"
    if result["participant_precision"] < 1.0:
        extra = set(result["predicted_participants"]) - set(result["expected_participants"])
        return f"Extra participants: {extra}"
    return "unknown"


def _count_categories(failures: list) -> dict:
    counts = {}
    for f in failures:
        cat = f["category"]
        counts[cat] = counts.get(cat, 0) + 1
    return counts


if __name__ == "__main__":
    run_benchmark()

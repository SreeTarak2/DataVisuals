"""
Relationship Benchmark Runner

Tests the cross-dataset relationship inference engine against deliberate trap
scenarios designed to expose false positives and false negatives.

Usage:
    python benchmark/relationships/run_relationship_benchmark.py

Each test case consists of 2+ Parquet files simulating tables from a DB
connection. The runner calls ``_infer_from_datasets()`` on each set and
checks whether the results match expectations.

Output:
    Prints a pass/fail report and writes results to
    ``benchmark/relationships/results.json``.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import polars as pl

# Ensure the backend root is on sys.path so we can import the service
BACKEND_DIR = Path(__file__).resolve().parent.parent
os.chdir(str(BACKEND_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.databases.db_connection_service import (
    DatabaseConnectionService,
    _score_identifier_likeness,
)

BENCHMARK_DIR = Path(__file__).parent
TRAPS_DIR = BENCHMARK_DIR / "traps"
MANIFEST_PATH = BENCHMARK_DIR / "manifest.json"
RESULTS_PATH = BENCHMARK_DIR / "results.json"


def load_test_case(category: str) -> dict:
    """Load a test case: read manifest entry + load Parquet schemas and paths."""
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    entry = manifest.get(category)
    if not entry:
        raise ValueError(f"Unknown category: {category}")

    trap_dir = TRAPS_DIR / category
    table_schemas = {}
    datasets = []

    for tbl_name in entry["tables"]:
        parquet_path = trap_dir / f"{tbl_name}.parquet"
        if not parquet_path.exists():
            raise FileNotFoundError(f"Missing Parquet file: {parquet_path}")

        schema = pl.read_parquet_schema(str(parquet_path))
        table_schemas[tbl_name] = {col: str(dtype) for col, dtype in schema.items()}
        datasets.append({
            "dataset_id": f"bench_{category}_{tbl_name}",
            "name": tbl_name,
            "table_name": tbl_name,
            "file_path": str(parquet_path),
        })

    return {
        "entry": entry,
        "datasets": datasets,
        "table_schemas": table_schemas,
    }


async def run_test_case(service: DatabaseConnectionService, category: str) -> dict:
    """Run one test case and return pass/fail details."""
    test = load_test_case(category)
    entry = test["entry"]

    results = await service._infer_from_datasets(
        datasets=test["datasets"],
        table_schemas=test["table_schemas"],
    )

    detection = entry["detection"]
    passed = True
    errors = []

    if detection == "required":
        # Must detect at least min_relationships relationships
        if len(results) < entry.get("min_relationships", 1):
            passed = False
            errors.append(
                f"Expected ≥{entry.get('min_relationships', 1)} relationships, "
                f"got {len(results)}"
            )

        # Verify expected source→target
        expected_source = entry.get("expected_source")
        expected_target = entry.get("expected_target")
        if expected_source and expected_target:
            found = any(
                r["source_table"] == expected_source and r["target_table"] == expected_target
                for r in results
            )
            if not found:
                passed = False
                errors.append(
                    f"Expected {expected_source} → {expected_target} not found "
                    f"among {len(results)} results"
                )

        # Verify minimum confidence
        min_conf = entry.get("min_confidence", 0.0)
        if results:
            max_conf = max(r["confidence"] for r in results)
            if max_conf < min_conf:
                passed = False
                errors.append(
                    f"Max confidence {max_conf} < minimum {min_conf}"
                )

    elif detection == "forbidden":
        # Must NOT detect this as a relationship
        if results:
            max_conf = max(r["confidence"] for r in results)
            max_allowed = entry.get("max_confidence", 0.30)
            if max_conf > max_allowed:
                passed = False
                errors.append(
                    f"Detected relationship with confidence {max_conf} "
                    f"when maximum allowed is {max_allowed}"
                )
            else:
                # Still check if the method was value_overlap (should be)
                for r in results:
                    if r.get("method") == "value_overlap":
                        # Allowed — below threshold
                        pass

    elif detection == "ambiguous":
        # May detect, but confidence should not be too high
        max_allowed = entry.get("max_confidence", 0.75)
        if results:
            max_conf = max(r["confidence"] for r in results)
            if max_conf > max_allowed:
                passed = False
                errors.append(
                    f"Ambiguous case has confidence {max_conf} > {max_allowed}"
                )

    elif detection == "multiple":
        # Must detect multiple relationships
        min_rels = entry.get("min_relationships", 2)
        if len(results) < min_rels:
            passed = False
            errors.append(
                f"Expected ≥{min_rels} relationships, got {len(results)}"
            )

        # Verify expected pairs exist
        expected_pairs = entry.get("expected_pairs", [])
        for pair in expected_pairs:
            found = any(
                r["source_table"] == pair["source"] and r["target_table"] == pair["target"]
                for r in results
            )
            if not found:
                passed = False
                errors.append(
                    f"Expected pair {pair['source']} → {pair['target']} not found"
                )

        # Verify ordering of ranked pairs
        orderings = entry.get("verify_ordering", [])
        for order in orderings:
            higher = order.get("higher")
            lower = order.get("lower")
            if not higher or not lower:
                continue

            # Find the index of each pair in the (confidence-sorted) results
            higher_idx = None
            lower_idx = None
            for idx, r in enumerate(results):
                if r["source_table"] == higher["source"] and r["target_table"] == higher["target"]:
                    higher_idx = idx
                if r["source_table"] == lower["source"] and r["target_table"] == lower["target"]:
                    lower_idx = idx

            if higher_idx is None:
                passed = False
                errors.append(
                    f"Higher-ranked pair {higher['source']} → {higher['target']} not found in results"
                )
            elif lower_idx is None:
                passed = False
                errors.append(
                    f"Lower-ranked pair {lower['source']} → {lower['target']} not found in results"
                )
            elif higher_idx >= lower_idx:
                passed = False
                errors.append(
                    f"Ranking violation: {higher['source']}→{higher['target']} (idx {higher_idx}) "
                    f"should rank above {lower['source']}→{lower['target']} (idx {lower_idx})"
                )

    return {
        "category": category,
        "description": entry["description"],
        "passed": passed,
        "errors": errors,
        "results": results,
        "result_count": len(results),
    }


def format_results(test_results: list[dict]) -> str:
    """Format benchmark results as a readable report."""
    total = len(test_results)
    passed_count = sum(1 for r in test_results if r["passed"])
    failed_count = total - passed_count

    lines = []
    lines.append("=" * 72)
    lines.append("  RELATIONSHIP INFERENCE BENCHMARK RESULTS")
    lines.append("=" * 72)
    lines.append("")

    for tr in test_results:
        status = "✅ PASS" if tr["passed"] else "❌ FAIL"
        lines.append(f"  {status}  [{tr['category']}]")
        lines.append(f"       {tr['description']}")
        lines.append(f"       Results: {tr['result_count']} relationship(s)")

        if tr["results"]:
            for r in tr["results"]:
                method = r.get("method", "?")
                conf = r["confidence"]
                overlap = r.get("overlap_ratio", None)
                src = r["source_table"]
                sc = r["source_column"]
                tgt = r["target_table"]
                tc = r["target_column"]
                overlap_str = f"  overlap={overlap}" if overlap else ""
                lines.append(
                    f"         {src}.{sc} → {tgt}.{tc}  "
                    f"({method}, conf={conf}{overlap_str})"
                )

        if tr["errors"]:
            for err in tr["errors"]:
                lines.append(f"         ⚠  {err}")

        lines.append("")

    lines.append("-" * 72)
    lines.append(f"  Total: {total}  |  Passed: {passed_count}  |  Failed: {failed_count}")
    lines.append("=" * 72)

    return "\n".join(lines)


async def main():
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    service = DatabaseConnectionService()

    test_results = []
    for category in manifest:
        print(f"  Running: {category}...")
        tr = await run_test_case(service, category)
        test_results.append(tr)

    # Print report
    report = format_results(test_results)
    print("\n" + report)

    # Save results
    serializable = []
    for tr in test_results:
        serializable.append({
            "category": tr["category"],
            "description": tr["description"],
            "passed": tr["passed"],
            "errors": tr["errors"],
            "result_count": tr["result_count"],
            "results": [
                {
                    "source_table": r["source_table"],
                    "source_column": r["source_column"],
                    "target_table": r["target_table"],
                    "target_column": r["target_column"],
                    "confidence": r["confidence"],
                    "method": r.get("method"),
                    "overlap_ratio": r.get("overlap_ratio"),
                    "fk_sample_size": r.get("fk_sample_size"),
                }
                for r in tr["results"]
            ],
        })

    with open(RESULTS_PATH, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"\nResults saved to {RESULTS_PATH}")

    # Return exit code
    return 0 if all(r["passed"] for r in test_results) else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

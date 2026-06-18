"""
Profiling Bridge Validator
===========================
Compares pandas-based profiling (used by benchmark) vs. Polars-based profiling
(used by the real upload pipeline in process_dataset.py) across all datasets.

This catches type-system mismatches where Polars dtype strings don't
normalize correctly through the ColumnProfile model validator, causing
different entity discovery behavior between benchmark and production.

Usage:
    python -m benchmark.validate_profiling_bridge
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import polars as pl

from services.knowledge_graph.models import ColumnProfile
from services.knowledge_graph.entity_discovery import entity_discovery
from services.knowledge_graph.primary_object_discovery import primary_object_discovery
from services.knowledge_graph.signal_engine import signal_engine

BENCHMARK_DIR = Path(__file__).parent
DATASETS_DIR = BENCHMARK_DIR / "datasets"
MANIFEST_PATH = BENCHMARK_DIR / "manifest.json"

MAX_ROWS = 5000


# ── Profiling Method 1: Pandas (current benchmark) ──────────────────────

def profile_pandas(dataset_path: str) -> Tuple[List[ColumnProfile], int]:
    """Profile using pandas — exactly as benchmark's df_to_column_profiles does."""
    try:
        df = pd.read_csv(dataset_path, nrows=MAX_ROWS, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(dataset_path, nrows=MAX_ROWS, encoding="latin1")

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
            # This branch is hit for exotic dtypes. The real benchmark hits a crash here
            # (_infer_type_from_name doesn't exist). We handle it gracefully.
            # Polars Date/Datetime types can end up here if pandas reads them as objects
            # but they still fall through to this branch (e.g. pandas dtype "timedelta[ns]")
            col_name_lower = col_name.lower()
            if any(kw in col_name_lower for kw in ["date", "time", "timestamp"]):
                data_type = "string"
            else:
                data_type = str(col_data.dtype)

        profiles.append(ColumnProfile(
            name=col_name,
            data_type=data_type,
            null_ratio=round(null_count / total_rows, 4) if total_rows > 0 else 0.0,
            distinct_count=distinct_count,
            distinct_ratio=round(distinct_count / total_rows, 4) if total_rows > 0 else 0.0,
            sample_values=sample_values[:5],
            is_unique=distinct_count == total_rows and total_rows > 0,
            is_primary_key=False,
        ))
    return profiles, len(df)


# ── Profiling Method 2: Polars (real pipeline) ──────────────────────────

def profile_polars(dataset_path: str) -> Tuple[List[ColumnProfile], int]:
    """Profile using Polars — mimicking the real process_dataset() pipeline.

    This follows the same flow as _build_kg_column_profiles() in process.py.
    """
    # Read with Polars (same as process_dataset → load_dataset)
    try:
        df = pl.read_csv(dataset_path, n_rows=MAX_ROWS, infer_schema_length=10000)
    except Exception:
        # Fallback for encoding issues
        df = pl.read_csv(dataset_path, n_rows=MAX_ROWS, infer_schema_length=10000, encoding="utf8-lossy")

    profiles = []
    total_rows = len(df)

    for col in df.columns:
        col_data = df[col]
        dtype_str = str(col_data.dtype)
        n_unique = col_data.n_unique()
        n_null = col_data.null_count()
        null_ratio = n_null / total_rows if total_rows > 0 else 0.0
        distinct_ratio = n_unique / total_rows if total_rows > 0 else 0.0
        is_unique = distinct_ratio >= 0.99 and null_ratio == 0.0

        # Get sample values (same as pipeline)
        sample_vals = []
        try:
            vals = col_data.drop_nulls().unique().to_list()[:10]
            sample_vals = [str(v) for v in vals if v is not None]
        except Exception:
            pass

        # The pipeline stores the RAW dtype string as data_type
        # The ColumnProfile model's validator normalizes it:
        # "Int64" → "integer", "Utf8" → "string", "Float64" → "decimal", etc.
        data_type_raw = dtype_str

        profiles.append(ColumnProfile(
            name=col,
            data_type=data_type_raw,
            null_ratio=round(null_ratio, 4) if total_rows > 0 else 0.0,
            distinct_count=n_unique,
            distinct_ratio=round(distinct_ratio, 4) if total_rows > 0 else 0.0,
            sample_values=sample_vals[:5],
            is_unique=is_unique,
            is_primary_key=is_unique,
        ))
    return profiles, len(df)


# ── Comparator ──────────────────────────────────────────────────────────

def compare_profiles(pd_profiles: List[ColumnProfile], pl_profiles: List[ColumnProfile]) -> Dict[str, Any]:
    """Compare pandas and Polars column profiles side by side."""
    pd_map = {p.name: p for p in pd_profiles}
    pl_map = {p.name: p for p in pl_profiles}

    mismatches = []
    all_columns = sorted(set(list(pd_map.keys()) + list(pl_map.keys())))

    for col in all_columns:
        p_col = pd_map.get(col)
        q_col = pl_map.get(col)

        if p_col is None:
            mismatches.append({"column": col, "issue": "only_in_polars", "pd": None, "pl": q_col.data_type})
            continue
        if q_col is None:
            mismatches.append({"column": col, "issue": "only_in_pandas", "pd": p_col.data_type, "pl": None})
            continue

        # Compare normalized data types
        p_type = p_col.data_type
        q_type = q_col.data_type

        if p_type != q_type:
            mismatches.append({
                "column": col,
                "issue": "type_mismatch",
                "pd_type": p_type,
                "pl_type": q_type,
                "pd_raw_dtype": str(p_type),
                "pl_raw_dtype": str(q_type),
            })

        # Compare distinct counts (pandas nunique vs polars n_unique)
        if p_col.distinct_count != q_col.distinct_count:
            mismatches.append({
                "column": col,
                "issue": "distinct_count_mismatch",
                "pd_distinct": p_col.distinct_count,
                "pl_distinct": q_col.distinct_count,
                "pd_total": None,
                "pl_total": None,
            })

    return {
        "total_columns_pd": len(pd_profiles),
        "total_columns_pl": len(pl_profiles),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def run_entity_discovery(profiles: List[ColumnProfile], table_name: str) -> dict:
    """Run entity discovery and return a summary dict."""
    report = entity_discovery.discover(profiles, table_name)
    primary = primary_object_discovery.discover(report.entities, table_name, len(profiles))
    return {
        "entity_count": report.entity_count,
        "entities": [{"label": e.label, "confidence": e.confidence, "valid": e.is_valid} for e in report.entities],
        "primary_label": primary.label,
        "evidence_strength": primary.evidence_strength,
        "primary_valid": primary.is_valid,
    }


def main():
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    results = {
        "timestamp": None,
        "summary": {"total_datasets": 0, "type_mismatches": 0, "distinct_mismatches": 0, "discovery_mismatches": 0},
        "datasets": [],
    }

    type_mismatch_count = 0
    distinct_mismatch_count = 0
    discovery_mismatch_count = 0

    print(f"{'Dataset':<45} {'Cols':<5} {'Mismatches':<12} {'Discovery':<12}")
    print("-" * 74)

    for filename in sorted(manifest.keys()):
        dataset_path = DATASETS_DIR / filename
        if not dataset_path.exists():
            continue

        table_name = filename.replace(".csv", "")

        # Profile both ways
        pd_profiles, pd_rows = profile_pandas(str(dataset_path))
        pl_profiles, pl_rows = profile_polars(str(dataset_path))

        # Compare profiles
        comparison = compare_profiles(pd_profiles, pl_profiles)
        type_mismatch_count += comparison["mismatch_count"]

        # Run entity discovery on both
        pd_discovery = run_entity_discovery(pd_profiles, table_name)
        pl_discovery = run_entity_discovery(pl_profiles, table_name)

        # Check if discovery results differ
        discovery_diff = (
            pd_discovery["primary_label"] != pl_discovery["primary_label"]
            or pd_discovery["primary_valid"] != pl_discovery["primary_valid"]
            or pd_discovery["entity_count"] != pl_discovery["entity_count"]
        )
        if discovery_diff:
            discovery_mismatch_count += 1

        status = "✓" if not comparison["mismatches"] and not discovery_diff else "✗ MISMATCH"
        mismatch_str = f"{comparison['mismatch_count']} types" if comparison["mismatches"] else "none"
        discovery_str = "differs" if discovery_diff else "same"

        print(f"{filename:<45} {pd_rows:<5} {mismatch_str:<12} {discovery_str:<12} {status}")

        dataset_result = {
            "dataset": filename,
            "rows": pd_rows,
            "pandas_columns": len(pd_profiles),
            "polars_columns": len(pl_profiles),
            "profile_comparison": comparison,
            "pandas_discovery": pd_discovery,
            "polars_discovery": pl_discovery,
            "discovery_differs": discovery_diff,
        }

        # Detail type mismatches
        if comparison["mismatches"]:
            detail_indent = "  "
            print(f"{detail_indent}Mismatches for {filename}:")
            for m in comparison["mismatches"]:
                pl_raw = m.get("pl_raw_dtype", "?")
                issue = m.get("issue", "")
                pd_type = m.get("pd_type", m.get("pd", "?"))
                pl_type = m.get("pl_type", m.get("pl", "?"))
                print(f"{detail_indent}  - {m['column']}: {issue}  pd={pd_type}  pl={pl_type}  raw={pl_raw}")

        results["datasets"].append(dataset_result)

    results["summary"] = {
        "total_datasets": len(results["datasets"]),
        "type_mismatches": type_mismatch_count,
        "distinct_mismatches": sum(1 for d in results["datasets"] if any(m["issue"] == "distinct_count_mismatch" for m in d["profile_comparison"]["mismatches"])),
        "discovery_mismatches": discovery_mismatch_count,
    }

    print("\n" + "=" * 60)
    print(f"  Total datasets:      {results['summary']['total_datasets']}")
    print(f"  Type mismatches:     {results['summary']['type_mismatches']}")
    print(f"  Distinct mismatches: {results['summary']['distinct_mismatches']}")
    print(f"  Discovery diffs:     {results['summary']['discovery_mismatches']}")
    print("=" * 60)

    if results["summary"]["type_mismatches"] == 0 and results["summary"]["discovery_mismatches"] == 0:
        print("\n✅ BRIDGE VALIDATED: pandas and Polars profiling produce identical results.")
        print("   The benchmark accurately represents production entity discovery behavior.")
    else:
        print(f"\n⚠️  BRIDGE GAP FOUND: {results['summary']['type_mismatches']} type mismatches,")
        print(f"   {results['summary']['discovery_mismatches']} discovery outcome differences.")
        print("   Investigate mismatches above before expanding the benchmark corpus.")

    # Save detailed report
    from datetime import datetime, timezone
    results_dir = BENCHMARK_DIR / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = results_dir / f"profiling_bridge_{timestamp}.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nDetailed report saved to: {report_path}")

    return results["summary"]["type_mismatches"] == 0 and results["summary"]["discovery_mismatches"] == 0


if __name__ == "__main__":
    bridge_ok = main()
    sys.exit(0 if bridge_ok else 1)

"""
Validate entity discovery pipeline against real-world datasets.

Usage:
    cd version2/backend
    python scripts/validate_discovery.py
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import polars as pl
from services.knowledge_graph.models import ColumnProfile as KGColumnProfile
from services.knowledge_graph.entity_discovery import entity_discovery

DATA_DIR = os.path.expanduser("~/Downloads/DataSage Data")

DATASETS = [
    "store_customers.csv",
    "bmw.csv",
    "SuperStoreOrders - SuperStoreOrders.csv",
    "blinkit_dataset.csv",
    "GlobalWeatherRepository.csv",
    "drugs_side_effects_drugs_com.csv",
    "mental_health_survey_dataset_300k.csv",
    "gold_prices_10y.csv",
    "student_academic_performance.csv",
]


def profile_csv(path: str, table_name: str):
    df = pl.read_csv(path, try_parse_dates=True, null_values=["", "NA", "N/A", "null"])
    profiles = []
    for col in df.columns:
        col_data = df[col]
        n_unique = col_data.n_unique()
        n_total = len(df)
        n_null = col_data.null_count()
        distinct_ratio = n_unique / n_total if n_total > 0 else 0.0
        null_ratio = n_null / n_total if n_total > 0 else 0.0

        sample_vals = (
            col_data.drop_nulls().unique().to_list()[:10] if col_data.dtype != pl.Null else []
        )
        sample_strs = [str(v) for v in sample_vals if v is not None]

        profiles.append(
            KGColumnProfile(
                name=col,
                data_type=str(col_data.dtype),
                null_ratio=null_ratio,
                distinct_count=n_unique,
                distinct_ratio=distinct_ratio,
                sample_values=sample_strs,
                is_unique=distinct_ratio >= 0.99 and null_ratio == 0.0,
                is_primary_key=distinct_ratio >= 0.99 and null_ratio == 0.0,
            )
        )
    return profiles, len(df)


def run():
    results = []
    for ds_name in DATASETS:
        path = os.path.join(DATA_DIR, ds_name)
        if not os.path.exists(path):
            print(f"  [SKIP] {ds_name} — not found")
            continue

        table_name = os.path.splitext(ds_name)[0]
        print(f"\n{'=' * 70}")
        print(f"  DATASET: {ds_name}")
        print(f"{'=' * 70}")

        profiles, row_count = profile_csv(path, table_name)
        print(f"  Rows: {row_count:,}  |  Columns: {len(profiles)}")

        report = entity_discovery.discover(profiles, table_name)

        print(f"  Entities: {report.entity_count}")
        print(f"  Unknown columns: {len(report.unknown_columns)}")
        print(f"  Quality score: {report.data_quality_score}")
        print(f"  Trust score: {report.trust_score}")

        if report.entities:
            print(f"\n  ── Discovered Entities ──")
            for e in report.entities:
                id_col = e.identifier_column or "(none)"
                print(
                    f"    {e.label:25s}  id={id_col:25s}  conf={e.confidence:.3f}  valid={e.is_valid}"
                )
                for col in e.columns:
                    role = e.role_counts
                    print(f"      ├─ {col}")

        if report.unknown_columns:
            print(f"\n  ── Unknown Columns ──")
            for col in report.unknown_columns:
                print(f"    {col}")

        results.append(
            {
                "dataset": ds_name,
                "row_count": row_count,
                "column_count": len(profiles),
                "entity_count": report.entity_count,
                "unknown_count": len(report.unknown_columns),
                "quality_score": report.data_quality_score,
                "trust_score": report.trust_score,
                "entities": [
                    {
                        "label": e.label,
                        "columns": e.columns,
                        "identifier": e.identifier_column,
                        "confidence": e.confidence,
                        "valid": e.is_valid,
                    }
                    for e in report.entities
                ],
                "unknown_columns": report.unknown_columns,
            }
        )

    print(f"\n\n{'=' * 70}")
    print(f"  SUMMARY")
    print(f"{'=' * 70}")
    for r in results:
        status = "✓" if r["entity_count"] > 0 else "✗ NO ENTITIES"
        print(
            f"  {status} {r['dataset']:40s}  entities={r['entity_count']:2d}  unknown={r['unknown_count']:2d}  quality={r['quality_score']:5.1f}  trust={r['trust_score']:5.1f}"
        )

    # Print full report as JSON for inspection
    print(f"\n\n── RAW REPORT JSON ──")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    run()

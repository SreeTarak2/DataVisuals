"""
Generate Parquet file pairs for the relationship benchmark.

Creates `benchmark/relationships/traps/<category>/` with Parquet files
designed to test specific failure modes of the relationship inference engine.

Each test case consists of 2+ Parquet files simulating tables from a
DB connection. The benchmark runner calls ``_infer_from_datasets()``
on each set and checks whether the results match expectations.
"""

import json
import os
import shutil
from pathlib import Path

import polars as pl

BENCHMARK_DIR = Path(__file__).parent
TRAPS_DIR = BENCHMARK_DIR / "traps"
MANIFEST_PATH = BENCHMARK_DIR / "manifest.json"


def write_parquet(table_name: str, df: pl.DataFrame, category: str):
    """Write a DataFrame to Parquet inside the trap category directory."""
    out_dir = TRAPS_DIR / category
    out_dir.mkdir(parents=True, exist_ok=True)
    path = str(out_dir / f"{table_name}.parquet")
    df.write_parquet(path, compression="zstd")
    return path


# ════════════════════════════════════════════════════════════════════════════
# Control: Genuine FK (should detect with high confidence)
# ════════════════════════════════════════════════════════════════════════════
def build_control():
    """orders.customer_id → customers.id (exact name match, star-schema)."""
    customers = pl.DataFrame({
        "id": list(range(1, 101)),
        "name": [f"Customer_{i}" for i in range(1, 101)],
        "email": [f"cust{i}@example.com" for i in range(1, 101)],
    })
    orders = pl.DataFrame({
        "order_id": list(range(1, 301)),
        "customer_id": [i % 100 + 1 for i in range(300)],
        "amount": [round(float(i * 10.5), 2) for i in range(300)],
        "order_date": [f"2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}" for i in range(300)],
    })
    write_parquet("customers", customers, "control")
    write_parquet("orders", orders, "control")
    return {
        "tables": ["orders", "customers"],
        "detection": "required",
        "min_relationships": 1,
        "expected_source": "orders",
        "expected_target": "customers",
        "min_confidence": 0.85,
        "description": "Genuine FK: orders.customer_id → customers.id (exact name match)",
    }


# ════════════════════════════════════════════════════════════════════════════
# Trap 1: False Overlap — status/segment share values but aren't a relationship
# ════════════════════════════════════════════════════════════════════════════
def build_false_overlap():
    """
    orders.status has values {A, B, C}. customers.segment has values {A, B, C}.
    100% value overlap, but names are attribute-like, not identifier-like.
    The identifier-likeness penalty should crush the confidence to near-zero.
    """
    values = ["A", "B", "C"]
    # Fact table with `status` column
    # NOTE: `order_id` starts at 1000 so its integer values don't overlap
    # with `customer_id` (1-100) — preventing an irrelevant false positive
    # that would distract from the actual status↔segment overlap test.
    orders = pl.DataFrame({
        "order_id": list(range(1000, 1300)),
        "status": [values[i % 3] for i in range(300)],
        "amount": [round(float(i * 5.0), 2) for i in range(300)],
    })
    # Dimension table with `segment` column that happens to share values
    customers = pl.DataFrame({
        "customer_id": list(range(1, 101)),
        "segment": [values[i % 3] for i in range(100)],
        "name": [f"Customer_{i}" for i in range(1, 101)],
    })
    write_parquet("orders", orders, "false_overlap")
    write_parquet("customers", customers, "false_overlap")
    return {
        "tables": ["orders", "customers"],
        "detection": "forbidden",
        "max_confidence": 0.30,
        "expected_via": "value_overlap",
        "description": "False overlap: orders.status ↔ customers.segment share values but are NOT a relationship — identifier-likeness should crush confidence",
    }


# ════════════════════════════════════════════════════════════════════════════
# Trap 2: Shared Codes — product_code and region_code share code values
# ════════════════════════════════════════════════════════════════════════════
def build_shared_codes():
    """
    products.product_code has codes like 'PRD001'-'PRD050'.
    regions.region_code has codes like 'PRD001'-'PRD050' (overlapping values).
    Both columns end with _code but neither is a genuine FK→PK pair.
    The identifier-likeness score is 0.95 for both (ends with _code), but
    the entity name and column name should prevent a name-match —
    only value_overlap would catch this. The overlap is only detected via
    value sampling, and both columns look like identifiers, so the
    confidence should be moderate (0.6-0.7) — this is an expected weakness
    that can only be resolved by semantic understanding.
    """
    # Products table
    products = pl.DataFrame({
        "product_id": list(range(1, 51)),
        "product_code": [f"PRD{i:03d}" for i in range(1, 51)],
        "product_name": [f"Product_{i}" for i in range(1, 51)],
        "price": [round(float(i * 2.5), 2) for i in range(1, 51)],
    })
    # Regions lookup table with overlapping codes
    regions = pl.DataFrame({
        "region_id": list(range(1, 11)),
        "region_code": [f"PRD{i:03d}" for i in range(1, 11)],  # Intentionally overlapping
        "region_name": [f"Region_{i}" for i in range(1, 11)],
    })
    write_parquet("products", products, "shared_codes")
    write_parquet("regions", regions, "shared_codes")
    return {
        "tables": ["products", "regions"],
        "detection": "ambiguous",
        "max_confidence": 0.75,
        "description": "Shared codes: products.product_code ↔ regions.region_code share code values but are NOT a genuine FK relationship",
    }


# ════════════════════════════════════════════════════════════════════════════
# Trap 3: Wrong FK Guess — customer_id matches both customers.id AND employees.id
# ════════════════════════════════════════════════════════════════════════════
def build_wrong_fk():
    """
    orders.customer_id (1-100) matches both:
      - customers.id (1-100)
      - employees.id (1-100) — INTENTIONAL trap
    Both look like valid FK targets. The engine should detect both
    relationships but the customer one should have higher confidence
    because the column name 'customer_id' matches the entity name 'customer'.
    """
    customers = pl.DataFrame({
        "id": list(range(1, 101)),
        "name": [f"Customer_{i}" for i in range(1, 101)],
    })
    employees = pl.DataFrame({
        "id": list(range(1, 101)),
        "name": [f"Employee_{i}" for i in range(1, 101)],
    })
    orders = pl.DataFrame({
        "order_id": list(range(1, 301)),
        "customer_id": [i % 100 + 1 for i in range(300)],
        "amount": [round(float(i * 7.5), 2) for i in range(300)],
    })
    write_parquet("customers", customers, "wrong_fk")
    write_parquet("employees", employees, "wrong_fk")
    write_parquet("orders", orders, "wrong_fk")
    return {
        "tables": ["orders", "customers", "employees"],
        "detection": "multiple",
        "min_relationships": 2,
        "expected_pairs": [
            {"source": "orders", "target": "customers"},
            {"source": "orders", "target": "employees"},
        ],
        "description": "Wrong FK guess: orders.customer_id matches both customers.id and employees.id — engine should detect both",
    }


# ════════════════════════════════════════════════════════════════════════════
# Trap 4: Multiple Parents — claim references policy, customer, and provider
# ════════════════════════════════════════════════════════════════════════════
def build_multiple_parents():
    """
    claims table has claim_id, policy_id, customer_id, provider_id.
    Each FK column references a different dimension table.
    All should be detected.
    """
    policies = pl.DataFrame({
        "id": list(range(1, 51)),
        "policy_name": [f"Policy_{i}" for i in range(1, 51)],
    })
    customers = pl.DataFrame({
        "id": list(range(1, 101)),
        "name": [f"Customer_{i}" for i in range(1, 101)],
    })
    providers = pl.DataFrame({
        "id": list(range(1, 31)),
        "name": [f"Provider_{i}" for i in range(1, 31)],
    })
    claims = pl.DataFrame({
        "claim_id": list(range(1, 201)),
        "policy_id": [i % 50 + 1 for i in range(200)],
        "customer_id": [i % 100 + 1 for i in range(200)],
        "provider_id": [i % 30 + 1 for i in range(200)],
        "amount": [round(float(i * 12.0), 2) for i in range(200)],
    })
    write_parquet("policies", policies, "multiple_parents")
    write_parquet("customers", customers, "multiple_parents")
    write_parquet("providers", providers, "multiple_parents")
    write_parquet("claims", claims, "multiple_parents")
    return {
        "tables": ["claims", "policies", "customers", "providers"],
        "detection": "multiple",
        "min_relationships": 3,
        "expected_pairs": [
            {"source": "claims", "target": "policies"},
            {"source": "claims", "target": "customers"},
            {"source": "claims", "target": "providers"},
        ],
        "description": "Multiple parents: claims references policies, customers, and providers — all should be detected",
    }


# ════════════════════════════════════════════════════════════════════════════
# Trap 5: _id-suffixed false overlap (stress-test identifier-likeness)
# ════════════════════════════════════════════════════════════════════════════
# KNOWN LIMITATION: This test is expected to FAIL with the current engine.
# Both columns end with `_id`, scoring 0.95 identifier-likeness. With 100%
# value overlap the engine detects this at ~0.90 confidence, even though
# there is no real relationship. This documents a known false-positive mode
# that needs a future improvement (e.g., requiring one side to be a bare
# `id` column, or adding cardinality-based sanity checks).
# ════════════════════════════════════════════════════════════════════════════
def build_id_overlap():
    """
    KNOWN LIMITATION — expected to FAIL.

    orders.status_id (values 10,20,30,40,50,60 repeating) and
    customers.segment_id (same values). Both columns end with ``_id``
    so they look like identifiers, but they're really attribute enums.

    The engine classifies ``status_id`` as FK-like and ``segment_id``
    as a PK fallback candidate. With 100% value overlap and both sides
    scoring 0.95 identifier-likeness, the confidence lands at ~0.90 —
    a clear false positive.
    """
    id_values = [10, 20, 30, 40, 50, 60]  # 6 uniques — beats the ≤5 guard
    orders = pl.DataFrame({
        "order_id": list(range(1000, 1300)),
        "status_id": [id_values[i % 6] for i in range(300)],
        "amount": [round(float(i * 5.0), 2) for i in range(300)],
    })
    customers = pl.DataFrame({
        "customer_id": list(range(1, 101)),
        "segment_id": [id_values[i % 6] for i in range(100)],
        "name": [f"Customer_{i}" for i in range(1, 101)],
    })
    write_parquet("orders", orders, "id_overlap")
    write_parquet("customers", customers, "id_overlap")
    return {
        "tables": ["orders", "customers"],
        "detection": "forbidden",
        "max_confidence": 0.30,
        "description": (
            "KNOWN LIMITATION: orders.status_id (values 10-60) → "
            "customers.customer_id (values 1-100). Both have _id suffix so "
            "identifier-likeness (0.95) can't distinguish — engine falsely "
            "detects the coincidental value overlap at ~0.90 confidence"
        ),
        "expected_behavior": "known_false_positive",
    }


# ════════════════════════════════════════════════════════════════════════════
# Trap 6: Wrong parent — entity name says employees, data says both
# ════════════════════════════════════════════════════════════════════════════
def build_wrong_parent():
    """
    orders.employee_id matches both employees.id AND customers.id by value.
    The entity name ``employee`` suggests ``employees`` is the correct target.

    Expected behavior:
      - ``orders.employee_id → employees.id`` via **name_match** (entity match:
        ``"employee" in "employees"``) at **0.95** confidence
      - ``orders.employee_id → customers.id`` via **value_overlap** at **~0.93**
        confidence
      - The name-matched relationship must rank ABOVE the value-overlap one
    """
    employees = pl.DataFrame({
        "id": list(range(1, 101)),
        "name": [f"Employee_{i}" for i in range(1, 101)],
    })
    customers = pl.DataFrame({
        "id": list(range(1, 101)),
        "name": [f"Customer_{i}" for i in range(1, 101)],
    })
    orders = pl.DataFrame({
        "order_id": list(range(1, 301)),
        "employee_id": [i % 100 + 1 for i in range(300)],
        "amount": [round(float(i * 8.0), 2) for i in range(300)],
    })
    write_parquet("employees", employees, "wrong_parent")
    write_parquet("customers", customers, "wrong_parent")
    write_parquet("orders", orders, "wrong_parent")
    return {
        "tables": ["orders", "employees", "customers"],
        "detection": "multiple",
        "min_relationships": 2,
        "expected_pairs": [
            {"source": "orders", "target": "employees"},
            {"source": "orders", "target": "customers"},
        ],
        "verify_ordering": [
            # The name-matched pair must rank higher than the value-overlap one
            {"higher": {"source": "orders", "target": "employees"},
             "lower": {"source": "orders", "target": "customers"}},
        ],
        "description": "Wrong parent: orders.employee_id matches both employees.id (name_match, 0.95) and customers.id (value_overlap, 0.93) — name match must rank higher",
    }


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════
def generate_all():
    """Generate all Parquet pairs and write the manifest."""
    # Clean traps directory
    if TRAPS_DIR.exists():
        shutil.rmtree(TRAPS_DIR)
    TRAPS_DIR.mkdir(parents=True, exist_ok=True)

    entries = {
        "control": build_control(),
        "false_overlap": build_false_overlap(),
        "shared_codes": build_shared_codes(),
        "wrong_fk": build_wrong_fk(),
        "multiple_parents": build_multiple_parents(),
        "id_overlap": build_id_overlap(),
        "wrong_parent": build_wrong_parent(),
    }

    with open(MANIFEST_PATH, "w") as f:
        json.dump(entries, f, indent=2)

    print(f"Generated {len(entries)} relationship benchmark cases:")
    for name, entry in entries.items():
        print(f"  {name:<20} {entry['description'][:60]}...")
    print(f"\nTraps directory: {TRAPS_DIR}")
    print(f"Manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    generate_all()

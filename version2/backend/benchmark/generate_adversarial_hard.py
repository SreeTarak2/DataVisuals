"""
Generate 20 hard adversarial datasets designed to potentially break
the entity discovery pipeline.

5 categories × 4 datasets each:

1. AMBIGUOUS — multiple entities competing for primary
2. GENERIC — vague column names that should yield Unknown
3. MIXED — valid entities but wrong primary likely
4. NOISY — enterprise-style abbreviated/obfuscated names
5. TRAPS — deceptive structures that look like entities but aren't
"""

import json, os, csv, random, sys
from pathlib import Path

random.seed(42)
BENCHMARK_DIR = Path(__file__).parent
DATASETS_DIR = BENCHMARK_DIR / "datasets"
MANIFEST_PATH = BENCHMARK_DIR / "manifest.json"


def write_csv(filename: str, columns: list, rows: list):
    path = DATASETS_DIR / filename
    os.makedirs(path.parent, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(row)


# ============================================================
# 1. AMBIGUOUS — multiple entities competing for primary
# ============================================================

def build_ambiguous_accounts():
    """account_id, owner_id, contact_id, balance, opened_date
    All entities look equally valid. Which is primary?"""
    cols = ["account_id", "owner_id", "contact_id", "balance", "opened_date"]
    rows = [[f"ACC{i:04d}", f"OWN{i:04d}", f"CNT{i:04d}",
             round(random.uniform(100, 10000), 2),
             f"2024-0{random.randint(1,9)}-{random.randint(10,28):02d}"]
            for i in range(1, 101)]
    write_csv("adv_hard_ambiguous_accounts.csv", cols, rows)


def build_ambiguous_entities():
    """entity_id, parent_id, child_id, root_id, label
    No clue which entity is the table about."""
    cols = ["entity_id", "parent_id", "child_id", "root_id", "label"]
    rows = [[f"ENT{i:04d}", f"PAR{i//2:04d}", f"CHD{i:04d}", f"ROOT{(i%10)+1:04d}",
             f"Entity_{i}"] for i in range(1, 101)]
    write_csv("adv_hard_ambiguous_entities.csv", cols, rows)


def build_ambiguous_references():
    """ref_id, source_id, target_id, origin_id, destination_id, type
    Pure FK soup — every column references something else."""
    cols = ["ref_id", "source_id", "target_id", "origin_id", "destination_id", "type"]
    rows = [[f"REF{i:04d}", f"SRC{i:04d}", f"TGT{i:04d}", f"ORG{i:04d}",
             f"DST{i:04d}", random.choice(["A", "B", "C"])]
            for i in range(1, 101)]
    write_csv("adv_hard_ambiguous_references.csv", cols, rows)


def build_ambiguous_competing():
    """lead_id, account_id, opportunity_id, contact_id
    CRM-style: who is the primary entity?"""
    cols = ["lead_id", "account_id", "opportunity_id", "contact_id", "value", "stage"]
    rows = [[f"LEAD{i:04d}", f"ACC{i:04d}", f"OPP{i:04d}", f"CNT{i:04d}",
             round(random.uniform(1000, 50000), 2),
             random.choice(["Prospecting", "Negotiation", "Closed"])]
            for i in range(1, 101)]
    write_csv("adv_hard_ambiguous_competing.csv", cols, rows)


# ============================================================
# 2. GENERIC — vague names, should yield Unknown
# ============================================================

def build_generic_core():
    """id, name, type, status, date — the classic ambiguous schema."""
    cols = ["id", "name", "type", "status", "date"]
    rows = [[i, f"Item_{i}", random.choice(["A", "B", "C"]),
             random.choice(["Active", "Inactive", "Pending"]),
             f"2025-0{random.randint(1,9):02d}-{random.randint(10,28):02d}"]
            for i in range(1, 101)]
    write_csv("adv_hard_generic_core.csv", cols, rows)


def build_generic_props():
    """key, value, description — generic KVP table."""
    cols = ["key", "value", "description"]
    rows = [[f"KEY_{i}", str(random.randint(1, 100)), f"Description for item {i}"]
            for i in range(1, 101)]
    write_csv("adv_hard_generic_props.csv", cols, rows)


def build_generic_metrics():
    """metric, value, unit, period — aggregated metrics, no entity."""
    cols = ["metric", "value", "unit", "period"]
    rows = [[f"metric_{i}", round(random.uniform(0, 100), 2),
             random.choice(["pct", "count", "dollars"]),
             f"2025-Q{random.randint(1,4)}"]
            for i in range(1, 51)]
    write_csv("adv_hard_generic_metrics.csv", cols, rows)


def build_generic_codes():
    """code, label, category, sort_order — lookup table."""
    cols = ["code", "label", "category", "sort_order"]
    rows = [[f"CD{i:03d}", f"Label {i}", random.choice(["A", "B", "C", "D"]), i]
            for i in range(1, 51)]
    write_csv("adv_hard_generic_codes.csv", cols, rows)


# ============================================================
# 3. MIXED — valid entities but the wrong primary is easily chosen
# ============================================================

def build_mixed_claims():
    """claim_id, policy_id, customer_id, provider_id, amount, status
    Table name suggests 'claim' but customer has a more specific pattern."""
    cols = ["claim_id", "policy_id", "customer_id", "provider_id", "amount", "status"]
    rows = [[f"CLM{i:04d}", f"POL{i:04d}", f"CUST{i:04d}", f"PROV{i:04d}",
             round(random.uniform(100, 50000), 2),
             random.choice(["Open", "Closed", "Pending"])]
            for i in range(1, 101)]
    write_csv("adv_hard_mixed_claims.csv", cols, rows)


def build_mixed_policies():
    """policy_id, customer_id, agent_id, product_id, premium, start_date
    Policy is primary but customer/agent/product have specific patterns."""
    cols = ["policy_id", "customer_id", "agent_id", "product_id", "premium", "start_date"]
    rows = [[f"POL{i:04d}", f"CUST{i:04d}", f"AGT{i:04d}", f"PRD{i:04d}",
             round(random.uniform(100, 1000), 2),
             f"2025-0{random.randint(1,9):02d}-{random.randint(10,28):02d}"]
            for i in range(1, 101)]
    write_csv("adv_hard_mixed_policies.csv", cols, rows)


def build_mixed_appointments():
    """appointment_id, patient_id, doctor_id, room_id, scheduled_date
    Table is 'appointments' — appointment should be primary,
    but patient/doctor have specific patterns."""
    cols = ["appointment_id", "patient_id", "doctor_id", "room_id", "scheduled_date", "duration"]
    rows = [[f"APT{i:04d}", f"PAT{i:04d}", f"DOC{i:04d}", f"RM{i:04d}",
             f"2025-0{random.randint(1,9):02d}-{random.randint(10,28):02d}",
             random.choice([15, 30, 45, 60])]
            for i in range(1, 101)]
    write_csv("adv_hard_mixed_appointments.csv", cols, rows)


def build_mixed_logistics():
    """shipment_id, order_id, warehouse_id, carrier_id, dispatch_date
    All participants have specific patterns, shipment has a generic one."""
    cols = ["shipment_id", "order_id", "warehouse_id", "carrier_id", "dispatch_date", "status"]
    rows = [[f"SHP{i:04d}", f"ORD{i:04d}", f"WH{i:04d}", f"CAR{i:04d}",
             f"2025-0{random.randint(1,9):02d}-{random.randint(10,28):02d}",
             random.choice(["Pending", "In Transit", "Delivered"])]
            for i in range(1, 101)]
    write_csv("adv_hard_mixed_logistics.csv", cols, rows)


# ============================================================
# 4. NOISY — enterprise-style obfuscated names
# ============================================================

def build_noisy_export():
    """tbl_rec_id, acct_num, usr_ref, created_ts, upd_ts
    Abbreviated enterprise export style."""
    cols = ["tbl_rec_id", "acct_num", "usr_ref", "created_ts", "upd_ts", "status_cd"]
    rows = [[f"REC{i:08d}", f"ACCT{i:06d}", f"USR{i:06d}",
             f"2025-0{random.randint(1,9):02d}-{random.randint(10,28):02d}T10:00:00",
             f"2025-0{random.randint(1,9):02d}-{random.randint(10,28):02d}T12:00:00",
             random.choice(["A", "I", "P"])]
            for i in range(1, 101)]
    write_csv("adv_hard_noisy_export.csv", cols, rows)


def build_noisy_legacy():
    """rec_num, cust_no, prod_ref, trx_amt, trx_dt
    Legacy system naming conventions."""
    cols = ["rec_num", "cust_no", "prod_ref", "trx_amt", "trx_dt"]
    rows = [[f"R{i:06d}", f"C{i:06d}", f"P{i:06d}",
             round(random.uniform(10, 1000), 2),
             f"2025-0{random.randint(1,9):02d}-{random.randint(10,28):02d}"]
            for i in range(1, 101)]
    write_csv("adv_hard_noisy_legacy.csv", cols, rows)


def build_noisy_sap():
    """MATNR, WERKS, LGORT, BESTQ, MEINS
    SAP-style column names — pure capital-letter abbreviations."""
    cols = ["MATNR", "WERKS", "LGORT", "BESTQ", "MEINS", "LABEL"]
    rows = [[f"MAT{i:06d}", f"PLANT{i:02d}", f"LOC{i:03d}",
             random.choice(["X", "Y", "Z"]),
             random.choice(["EA", "KG", "M"]),
             f"Material {i}"]
            for i in range(1, 101)]
    write_csv("adv_hard_noisy_sap.csv", cols, rows)


def build_noisy_obfuscated():
    """_key, _fld1, _fld2, _audit, _seq
    System-generated column names with underscores — no business meaning."""
    cols = ["_key", "_fld1", "_fld2", "_audit", "_seq", "_label"]
    rows = [[f"K{i:06d}", f"D1_{i}", f"D2_{i}", f"AUDIT_{i}", i, f"Item_{i}"]
            for i in range(1, 101)]
    write_csv("adv_hard_noisy_obfuscated.csv", cols, rows)


# ============================================================
# 5. TRAPS — deceptive structures
# ============================================================

def build_traps_date_only():
    """date, day_of_week, month, quarter, year
    Pure date dimensions — no business entity."""
    cols = ["date", "day_of_week", "month", "quarter", "year"]
    rows = [[f"2025-{m:02d}-{d:02d}",
             random.choice(["Mon", "Tue", "Wed"]),
             m, (m-1)//3 + 1, 2025]
            for m in range(1, 13)
            for d in range(1, 29)]
    write_csv("adv_hard_traps_date_only.csv", cols, rows)


def build_traps_single_id():
    """id, score, normalized_score, percentile
    Just one ID column with no other entity attributes — system row ID."""
    cols = ["id", "score", "normalized_score", "percentile"]
    rows = [[i, round(random.gauss(50, 15), 2),
             round(random.uniform(0, 1), 3),
             round(random.uniform(0, 100), 1)]
            for i in range(1, 101)]
    write_csv("adv_hard_traps_single_id.csv", cols, rows)


def build_traps_lookup_only():
    """country_code, country_name, region
    Simple lookup table — code is CODE, not IDENTIFIER."""
    cols = ["country_code", "country_name", "region"]
    countries = [
        ("US", "United States", "North America"),
        ("GB", "United Kingdom", "Europe"),
        ("IN", "India", "Asia"),
        ("JP", "Japan", "Asia"),
        ("BR", "Brazil", "South America"),
    ]
    write_csv("adv_hard_traps_lookup_only.csv", cols, countries)


def build_traps_hash_keys():
    """row_hash, payload, checksum, version
    System-internal table with no business entity."""
    cols = ["row_hash", "payload", "checksum", "version"]
    rows = [[f"0x{random.randint(0, 2**64):016x}",
             f"data_{i}",
             f"chk{random.randint(1000, 9999)}",
             random.randint(1, 5)]
            for i in range(1, 101)]
    write_csv("adv_hard_traps_hash_keys.csv", cols, rows)


# ============================================================
# Build manifest entries
# ============================================================

MANIFEST_ENTRIES = {
    # Ambiguous
    "adv_hard_ambiguous_accounts.csv": {
        "description": "account_id, owner_id, contact_id — multiple competing FK entities",
        "expected_primary_object": "account",
        "expected_participants": ["owner", "contact"],
    },
    "adv_hard_ambiguous_entities.csv": {
        "description": "entity_id, parent_id, child_id, root_id — generic entity names",
        "expected_primary_object": None,
        "expected_participants": [],
        "abstention_test": True,
    },
    "adv_hard_ambiguous_references.csv": {
        "description": "ref_id, source_id, target_id, origin_id — pure FK soup",
        "expected_primary_object": None,
        "expected_participants": [],
        "abstention_test": True,
    },
    "adv_hard_ambiguous_competing.csv": {
        "description": "lead_id, account_id, opportunity_id, contact_id — CRM ambiguity",
        "expected_primary_object": "lead",
        "expected_participants": ["account", "contact", "opportunity"],
    },
    # Generic
    "adv_hard_generic_core.csv": {
        "description": "id, name, type, status, date — classic ambiguous schema",
        "expected_primary_object": None,
        "expected_participants": [],
        "abstention_test": True,
    },
    "adv_hard_generic_props.csv": {
        "description": "key, value, description — generic KVP table",
        "expected_primary_object": None,
        "expected_participants": [],
        "abstention_test": True,
    },
    "adv_hard_generic_metrics.csv": {
        "description": "metric, value, unit, period — aggregated metrics",
        "expected_primary_object": None,
        "expected_participants": [],
        "abstention_test": True,
    },
    "adv_hard_generic_codes.csv": {
        "description": "code, label, category, sort_order — lookup table",
        "expected_primary_object": None,
        "expected_participants": [],
        "abstention_test": True,
    },
    # Mixed
    "adv_hard_mixed_claims.csv": {
        "description": "claim_id, policy_id, customer_id, provider_id — customer has strong pattern",
        "expected_primary_object": "claim",
        "expected_participants": ["policy", "customer", "provider"],
    },
    "adv_hard_mixed_policies.csv": {
        "description": "policy_id, customer_id, agent_id, product_id — policy should win",
        "expected_primary_object": "policy",
        "expected_participants": ["customer", "agent", "product"],
    },
    "adv_hard_mixed_appointments.csv": {
        "description": "appointment_id, patient_id, doctor_id, room_id — appointment should win",
        "expected_primary_object": "appointment",
        "expected_participants": ["patient", "doctor"],
    },
    "adv_hard_mixed_logistics.csv": {
        "description": "shipment_id, order_id, warehouse_id, carrier_id — shipment should win",
        "expected_primary_object": "shipment",
        "expected_participants": ["order", "warehouse"],
    },
    # Noisy
    "adv_hard_noisy_export.csv": {
        "description": "tbl_rec_id, acct_num, usr_ref, created_ts — abbreviated enterprise export",
        "expected_primary_object": None,
        "expected_participants": [],
        "abstention_test": True,
    },
    "adv_hard_noisy_legacy.csv": {
        "description": "rec_num, cust_no, prod_ref, trx_amt — legacy system naming",
        "expected_primary_object": None,
        "expected_participants": [],
        "abstention_test": True,
    },
    "adv_hard_noisy_sap.csv": {
        "description": "MATNR, WERKS, LGORT, BESTQ — SAP-style capital-letter columns",
        "expected_primary_object": None,
        "expected_participants": [],
        "abstention_test": True,
    },
    "adv_hard_noisy_obfuscated.csv": {
        "description": "_key, _fld1, _fld2 — system-generated names, no business meaning",
        "expected_primary_object": None,
        "expected_participants": [],
        "abstention_test": True,
    },
    # Traps
    "adv_hard_traps_date_only.csv": {
        "description": "date, day_of_week, month, quarter, year — pure date dimension",
        "expected_primary_object": None,
        "expected_participants": [],
        "abstention_test": True,
    },
    "adv_hard_traps_single_id.csv": {
        "description": "id, score, normalized_score, percentile — single system ID, no entity",
        "expected_primary_object": None,
        "expected_participants": [],
        "abstention_test": True,
    },
    "adv_hard_traps_lookup_only.csv": {
        "description": "country_code, country_name, region — simple lookup table",
        "expected_primary_object": None,
        "expected_participants": [],
        "abstention_test": True,
    },
    "adv_hard_traps_hash_keys.csv": {
        "description": "row_hash, payload, checksum, version — system-internal table",
        "expected_primary_object": None,
        "expected_participants": [],
        "abstention_test": True,
    },
}


if __name__ == "__main__":
    # Generate all datasets
    build_ambiguous_accounts()
    build_ambiguous_entities()
    build_ambiguous_references()
    build_ambiguous_competing()
    build_generic_core()
    build_generic_props()
    build_generic_metrics()
    build_generic_codes()
    build_mixed_claims()
    build_mixed_policies()
    build_mixed_appointments()
    build_mixed_logistics()
    build_noisy_export()
    build_noisy_legacy()
    build_noisy_sap()
    build_noisy_obfuscated()
    build_traps_date_only()
    build_traps_single_id()
    build_traps_lookup_only()
    build_traps_hash_keys()

    # Update manifest
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    manifest.update(MANIFEST_ENTRIES)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    print(f"Generated {len(MANIFEST_ENTRIES)} adversarial hard datasets.")
    print(f"Manifest now has {len(manifest)} entries.")

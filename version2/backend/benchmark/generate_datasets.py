"""
Synthetic Benchmark Dataset Generator
=======================================
Generates datasets with KNOWN ground truth across 5 categories,
designed to exercise specific entity discovery pipeline behaviors.

Categories:
  - clean:      10+ datasets with clear identifiers (basic detection)
  - denormalized: 15+ datasets with messy naming (spaces, abbreviations, mixed case)
  - adversarial:  10+ datasets designed to confuse false-positive detection
  - no_entity:    10+ datasets that should yield null primary (abstention)
  - multi_entity:  5+ datasets with reference signals between entities

Usage:
    cd version2/backend
    python -m benchmark.generate_datasets          # generate all (default 50+)
    python -m benchmark.generate_datasets --minimal # generate 26 (fill to 50)
    python -m benchmark.generate_datasets --clean 5 --denormalized 8
"""

import csv
import json
import os
import random
import re
import string
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

BENCHMARK_DIR = Path(__file__).parent
DATASETS_DIR = BENCHMARK_DIR / "datasets"
MANIFEST_PATH = BENCHMARK_DIR / "manifest.json"

random.seed(42)

# ── Helpers ────────────────────────────────────────────────────────────


def _write_csv(filename: str, rows: List[Dict[str, str]]):
    """Write a list of dicts to a CSV file in the datasets directory."""
    path = DATASETS_DIR / filename
    if not rows:
        # Write header-only
        path.write_text("")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _pick(names: List[str], k: int) -> List[str]:
    return random.sample(names, min(k, len(names)))


def _rand_date(start_year=2020, end_year=2025) -> str:
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    rand_days = random.randint(0, delta.days)
    return (start + timedelta(days=rand_days)).strftime("%Y-%m-%d")


def _rand_amount(min_v=10, max_v=5000) -> str:
    return f"{random.uniform(min_v, max_v):.2f}"


def _int_id(prefix: str, n: int) -> str:
    return f"{prefix}_{n:04d}"


def _col(name: str, values: List[str], null_pct: float = 0.0) -> List[str]:
    """Return values with optional nulls sprinkled in."""
    if null_pct <= 0:
        return values[:]
    result = list(values)
    for i in range(len(result)):
        if random.random() < null_pct:
            result[i] = ""
    return result


# ── Category 1: CLEAN (10+ datasets with clear identifiers) ────────────

CLEAN_DATASETS = [
    {
        "filename": "clean_customers.csv",
        "expected_primary_object": "customer",
        "expected_participants": [],
        "description": "Customer master data with customer_id",
        "generate": lambda: _clean_single_entity(
            entity="customer",
            columns=["customer_id", "customer_name", "email", "signup_date", "status"],
            id_col="customer_id",
            name_col="customer_name",
            n=200,
        ),
    },
    {
        "filename": "clean_orders.csv",
        "expected_primary_object": "order",
        "expected_participants": ["customer", "product"],
        "description": "Order transactions with customer and product references",
        "generate": lambda: _clean_orders(),
    },
    {
        "filename": "clean_products.csv",
        "expected_primary_object": "product",
        "expected_participants": [],
        "description": "Product catalog with product_id",
        "generate": lambda: _clean_single_entity(
            entity="product",
            columns=["product_id", "product_name", "category", "price", "stock_qty"],
            id_col="product_id",
            name_col="product_name",
            n=150,
        ),
    },
    {
        "filename": "clean_invoices.csv",
        "expected_primary_object": "invoice",
        "expected_participants": ["customer"],
        "description": "Invoices with customer reference",
        "generate": lambda: _clean_invoices(),
    },
    {
        "filename": "clean_employees.csv",
        "expected_primary_object": "employee",
        "expected_participants": [],
        "description": "Employee records with employee_id",
        "generate": lambda: _clean_single_entity(
            entity="employee",
            columns=["employee_id", "employee_name", "department", "hire_date", "salary", "email"],
            id_col="employee_id",
            name_col="employee_name",
            n=100,
        ),
    },
    {
        "filename": "clean_students.csv",
        "expected_primary_object": "student",
        "expected_participants": [],
        "description": "Student records with student_id",
        "generate": lambda: _clean_single_entity(
            entity="student",
            columns=["student_id", "student_name", "major", "enrollment_date", "gpa"],
            id_col="student_id",
            name_col="student_name",
            n=300,
        ),
    },
    {
        "filename": "clean_patients.csv",
        "expected_primary_object": "patient",
        "expected_participants": [],
        "description": "Patient records with patient_id",
        "generate": lambda: _clean_single_entity(
            entity="patient",
            columns=["patient_id", "patient_name", "dob", "diagnosis", "admission_date"],
            id_col="patient_id",
            name_col="patient_name",
            n=180,
        ),
    },
    {
        "filename": "clean_transactions.csv",
        "expected_primary_object": "transaction",
        "expected_participants": ["account"],
        "description": "Transactions with account reference",
        "generate": lambda: _clean_transactions(),
    },
    {
        "filename": "clean_suppliers.csv",
        "expected_primary_object": "supplier",
        "expected_participants": [],
        "description": "Supplier master data with supplier_id",
        "generate": lambda: _clean_single_entity(
            entity="supplier",
            columns=["supplier_id", "supplier_name", "contact_email", "category", "rating"],
            id_col="supplier_id",
            name_col="supplier_name",
            n=80,
        ),
    },
    {
        "filename": "clean_shipments.csv",
        "expected_primary_object": "shipment",
        "expected_participants": ["order", "supplier"],
        "description": "Shipments with order and supplier references",
        "generate": lambda: _clean_shipments(),
    },
]


def _clean_single_entity(entity: str, columns: List[str], id_col: str, name_col: str, n: int) -> List[Dict[str, str]]:
    rows = []
    for i in range(1, n + 1):
        row = {}
        for col in columns:
            if col == id_col:
                row[col] = f"{entity}_{i:04d}"
            elif col == name_col:
                row[col] = f"{entity.title()} {i}"
            elif col == "email":
                row[col] = f"{entity}{i}@example.com"
            elif col == "status":
                row[col] = random.choice(["active", "inactive", "pending"])
            elif col in ("signup_date", "hire_date", "enrollment_date", "admission_date"):
                row[col] = _rand_date(2020, 2024)
            elif col == "dob":
                row[col] = _rand_date(1960, 2005)
            elif col in ("price", "salary"):
                row[col] = _rand_amount(100, 10000)
            elif col == "stock_qty":
                row[col] = str(random.randint(0, 500))
            elif col == "gpa":
                row[col] = f"{random.uniform(2.0, 4.0):.2f}"
            elif col == "department":
                row[col] = random.choice(["Engineering", "Sales", "Marketing", "HR", "Finance"])
            elif col == "major":
                row[col] = random.choice(["Computer Science", "Biology", "Business", "Engineering"])
            elif col == "diagnosis":
                row[col] = random.choice(["Hypertension", "Diabetes", "Asthma", "Fracture"])
            elif col == "contact_email":
                row[col] = f"contact{i}@supplier.com"
            elif col == "category":
                row[col] = random.choice(["A", "B", "C"])
            elif col == "rating":
                row[col] = str(random.randint(1, 5))
            elif col == "customer_id":
                row[col] = f"cust_{random.randint(1, 50):04d}"
            elif col == "order_id":
                row[col] = f"ord_{random.randint(1, 100):04d}"
            elif col == "product_id":
                row[col] = f"prod_{random.randint(1, 30):04d}"
            elif col == "supplier_id":
                row[col] = f"supp_{random.randint(1, 20):04d}"
            elif col == "account_id":
                row[col] = f"acct_{random.randint(1, 50):04d}"
            else:
                row[col] = f"value_{i}"
        rows.append(row)
    return rows


def _clean_orders() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 501):
        row = {
            "order_id": f"ORD_{i:05d}",
            "customer_id": f"CUST_{random.randint(1, 100):04d}",
            "product_id": f"PROD_{random.randint(1, 50):04d}",
            "order_date": _rand_date(2023, 2025),
            "quantity": str(random.randint(1, 10)),
            "total_amount": _rand_amount(20, 2000),
            "status": random.choice(["pending", "shipped", "delivered", "cancelled"]),
        }
        rows.append(row)
    return rows


def _clean_invoices() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 301):
        row = {
            "invoice_id": f"INV_{i:05d}",
            "customer_id": f"CUST_{random.randint(1, 80):04d}",
            "amount": _rand_amount(100, 10000),
            "issue_date": _rand_date(2023, 2025),
            "due_date": _rand_date(2023, 2026),
            "status": random.choice(["paid", "unpaid", "overdue"]),
        }
        rows.append(row)
    return rows


def _clean_transactions() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 1001):
        row = {
            "transaction_id": f"TXN_{i:06d}",
            "account_id": f"ACCT_{random.randint(1, 60):04d}",
            "amount": _rand_amount(5, 5000),
            "timestamp": f"{_rand_date(2024, 2025)}T{random.randint(0,23):02d}:{random.randint(0,59):02d}:00",
            "type": random.choice(["deposit", "withdrawal", "transfer", "payment"]),
        }
        rows.append(row)
    return rows


def _clean_shipments() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 201):
        row = {
            "shipment_id": f"SHP_{i:05d}",
            "order_id": f"ORD_{random.randint(1, 150):04d}",
            "supplier_id": f"SUPP_{random.randint(1, 30):04d}",
            "carrier": random.choice(["UPS", "FedEx", "DHL", "USPS"]),
            "ship_date": _rand_date(2024, 2025),
            "delivery_date": _rand_date(2024, 2025),
            "status": random.choice(["in_transit", "delivered", "delayed"]),
        }
        rows.append(row)
    return rows


# ── Category 2: DENORMALIZED (15+ messy naming) ────────────────────────

DENORMALIZED_DATASETS = [
    {
        "filename": "denorm_spaces.csv",
        "expected_primary_object": "order",
        "expected_participants": ["customer", "product"],
        "description": "Spaces in column names, mixed case",
        "generate": lambda: _denorm_spaces(),
    },
    {
        "filename": "denorm_abbreviations.csv",
        "expected_primary_object": "customer",
        "expected_participants": [],
        "description": "Abbreviated column names (cust_id, fname, etc.)",
        "generate": lambda: _denorm_abbreviations(),
    },
    {
        "filename": "denorm_camel_case.csv",
        "expected_primary_object": "employee",
        "expected_participants": ["department"],
        "description": "CamelCase column names with department reference",
        "generate": lambda: _denorm_camel_case(),
    },
    {
        "filename": "denorm_mixed_case.csv",
        "expected_primary_object": "patient",
        "expected_participants": ["doctor"],
        "description": "Inconsistent casing across column names",
        "generate": lambda: _denorm_mixed_case(),
    },
    {
        "filename": "denorm_null_heavy.csv",
        "expected_primary_object": "student",
        "expected_participants": [],
        "description": "Many null values in columns",
        "generate": lambda: _denorm_null_heavy(),
    },
    {
        "filename": "denorm_duplicate_rows.csv",
        "expected_primary_object": "product",
        "expected_participants": [],
        "description": "Duplicate rows and integer IDs",
        "generate": lambda: _denorm_duplicates(),
    },
    {
        "filename": "denorm_non_ascii.csv",
        "expected_primary_object": "product",
        "expected_participants": [],
        "description": "Non-ASCII characters in data values",
        "generate": lambda: _denorm_non_ascii(),
    },
    {
        "filename": "denorm_url_columns.csv",
        "expected_primary_object": "product",
        "expected_participants": ["supplier"],
        "description": "URL/link columns mixed in with entity columns",
        "generate": lambda: _denorm_url_columns(),
    },
    {
        "filename": "denorm_all_lower.csv",
        "expected_primary_object": "invoice",
        "expected_participants": ["client"],
        "description": "All lowercase column names",
        "generate": lambda: _denorm_all_lower(),
    },
    {
        "filename": "denorm_underscore_heavy.csv",
        "expected_primary_object": "shipment",
        "expected_participants": ["warehouse"],
        "description": "Multiple underscores and long column names",
        "generate": lambda: _denorm_underscore_heavy(),
    },
    {
        "filename": "denorm_timestamp_variants.csv",
        "expected_primary_object": "transaction",
        "expected_participants": ["merchant"],
        "description": "Various timestamp formats (created_at, updated, ts)",
        "generate": lambda: _denorm_timestamps(),
    },
    {
        "filename": "denorm_phone_email.csv",
        "expected_primary_object": "contact",
        "expected_participants": [],
        "description": "Phone and email columns alongside entity fields",
        "generate": lambda: _denorm_contact(),
    },
    {
        "filename": "denorm_boolean_flags.csv",
        "expected_primary_object": "user",
        "expected_participants": [],
        "description": "Boolean flag columns (is_active, has_subscription) mixed with entity",
        "generate": lambda: _denorm_booleans(),
    },
    {
        "filename": "denorm_amount_variants.csv",
        "expected_primary_object": "order",
        "expected_participants": ["customer"],
        "description": "Multiple amount/price/cost/tax columns",
        "generate": lambda: _denorm_amounts(),
    },
    {
        "filename": "denorm_code_mixture.csv",
        "expected_primary_object": "product",
        "expected_participants": [],
        "description": "Columns with code/SKU/barcode patterns mixed in",
        "generate": lambda: _denorm_codes(),
    },
]


def _denorm_spaces() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 301):
        rows.append({
            "Order ID": f"ORD_{i:05d}",
            "Customer ID": f"CUST_{random.randint(1,80):04d}",
            "Product ID": f"PRD_{random.randint(1,40):04d}",
            "Order Date": _rand_date(2023, 2025),
            "Total Amount": _rand_amount(10, 3000),
            "Order Status": random.choice(["Pending", "Shipped", "Delivered"]),
        })
    return rows


def _denorm_abbreviations() -> List[Dict[str, str]]:
    first_names = ["Alice", "Bob", "Carol", "Dave", "Eve", "Frank", "Grace", "Hank"]
    last_names = ["Smith", "Jones", "Brown", "Davis", "Wilson", "Lee", "Clark", "Hall"]
    rows = []
    for i in range(1, 151):
        rows.append({
            "cust_id": f"C{i:05d}",
            "fname": random.choice(first_names),
            "lname": random.choice(last_names),
            "email_addr": f"cust{i}@mail.com",
            "ph_no": f"555-{random.randint(1000,9999)}",
            "signup_dt": _rand_date(2022, 2024),
            "cust_status": random.choice(["act", "inact", "pend"]),
        })
    return rows


def _denorm_camel_case() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 121):
        rows.append({
            "EmployeeID": f"EMP{i:04d}",
            "EmployeeName": f"Employee {i}",
            "DeptID": f"DEPT{random.randint(1,10):02d}",
            "HireDate": _rand_date(2018, 2024),
            "AnnualSalary": _rand_amount(40000, 150000),
        })
    return rows


def _denorm_mixed_case() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 101):
        rows.append({
            "PATIENT_ID": f"PAT{i:05d}",
            "Patient_Name": f"Patient {i}",
            "doctor_id": f"DOC{random.randint(1,20):03d}",
            "ADMISSION_date": _rand_date(2023, 2025),
            "Diagnosis": random.choice(["Flu", "Fracture", "Infection", "Surgery"]),
        })
    return rows


def _denorm_null_heavy() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 201):
        row = {
            "student_id": f"S{i:05d}",
            "student_name": f"Student {i}",
            "email": f"student{i}@univ.edu",
        }
        # 40% nulls in optional fields
        if random.random() > 0.6:
            row["phone"] = f"555-{random.randint(1000,9999)}"
        else:
            row["phone"] = ""
        if random.random() > 0.5:
            row["gpa"] = f"{random.uniform(2.0, 4.0):.2f}"
        else:
            row["gpa"] = ""
        if random.random() > 0.7:
            row["graduation_year"] = str(random.randint(2025, 2028))
        else:
            row["graduation_year"] = ""
        rows.append(row)
    return rows


def _denorm_duplicates() -> List[Dict[str, str]]:
    rows = []
    # Generate 100 unique products
    for i in range(1, 101):
        rows.append({
            "product_id": f"P{i:04d}",
            "product_name": f"Product {i}",
            "category": random.choice(["Electronics", "Clothing", "Food", "Books"]),
            "price": _rand_amount(5, 500),
        })
    # Duplicate 30 rows to test dedup handling
    for i in range(1, 31):
        rows.append({
            "product_id": f"P{i:04d}",
            "product_name": f"Product {i}",
            "category": random.choice(["Electronics", "Clothing", "Food", "Books"]),
            "price": _rand_amount(5, 500),
        })
    random.shuffle(rows)
    return rows


def _denorm_non_ascii() -> List[Dict[str, str]]:
    products = [
        ("Café au Lait", "Boissons"),
        ("Jalapeño Chips", "Snacks"),
        ("Schönbrunn", "Imports"),
        ("São Paulo Blend", "Coffee"),
        ("Münchner Bier", "Beverages"),
        ("Crème Brûlée", "Desserts"),
        ("Garçon Manqué", "Wine"),
        ("François' Baguette", "Bakery"),
        ("Zürich Rolex", "Luxury"),
        ("København Pastry", "Bakery"),
    ]
    rows = []
    for i in range(1, 61):
        name, cat = products[i % len(products)]
        rows.append({
            "product_id": f"PRD{i:04d}",
            "product_name": f"{name} #{i}",
            "category": cat,
            "price": _rand_amount(10, 2000),
            "description": f"Artisan {cat.lower()} product from {name} — qualité supérieure! ✓",
        })
    return rows


def _denorm_url_columns() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 101):
        rows.append({
            "product_id": f"PRD{i:04d}",
            "product_name": f"Product {i}",
            "category": random.choice(["Electronics", "Books", "Home"]),
            "price": _rand_amount(10, 1000),
            "product_url": f"https://shop.example.com/products/{i}",
            "image_link": f"https://cdn.example.com/img/{i}.jpg",
            "supplier_id": f"SUPP{random.randint(1,15):02d}",
            "supplier_website": f"https://supplier{random.randint(1,15)}.com",
        })
    return rows


def _denorm_all_lower() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 151):
        rows.append({
            "invoice_id": f"inv_{i:05d}",
            "client_id": f"cl_{random.randint(1,40):04d}",
            "invoice_amount": _rand_amount(100, 10000),
            "issued_at": _rand_date(2024, 2025),
            "payment_status": random.choice(["paid", "unpaid", "overdue"]),
        })
    return rows


def _denorm_underscore_heavy() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 81):
        rows.append({
            "shipment_tracking_id": f"TRACK_{i:05d}",
            "warehouse_location_id": f"WH_{random.randint(1,10):02d}",
            "estimated_delivery_date": _rand_date(2025, 2025),
            "current_status_code": random.choice(["IN_TRANSIT", "DELIVERED", "DELAYED"]),
            "carrier_service_name": random.choice(["UPS_Ground", "FedEx_Express", "DHL_Euro"]),
        })
    return rows


def _denorm_timestamps() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 301):
        rows.append({
            "txn_id": f"TXN{i:06d}",
            "merchant_id": f"MER{random.randint(1,30):03d}",
            "amount": _rand_amount(1, 2000),
            "created_at": f"{_rand_date(2024, 2025)} {random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}",
            "updated_at": f"{_rand_date(2024, 2025)} {random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}",
            "processed_at": f"{_rand_date(2024, 2025)} {random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}",
        })
    return rows


def _denorm_contact() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 121):
        rows.append({
            "contact_id": f"CT{i:04d}",
            "contact_name": f"Contact {i}",
            "email": f"contact{i}@example.com",
            "phone": f"555-{random.randint(1000,9999)}",
            "mobile": f"555-{random.randint(1000,9999)}",
            "address": f"{random.randint(100,9999)} Main St",
        })
    return rows


def _denorm_booleans() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 201):
        rows.append({
            "user_id": f"U{i:05d}",
            "user_name": f"User {i}",
            "is_active": random.choice(["true", "false"]),
            "has_subscription": random.choice(["true", "false"]),
            "is_verified": random.choice(["true", "false"]),
            "email": f"user{i}@platform.com",
        })
    return rows


def _denorm_amounts() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 301):
        rows.append({
            "order_id": f"O{i:05d}",
            "customer_id": f"C{random.randint(1,60):03d}",
            "subtotal": _rand_amount(10, 2000),
            "tax_amount": _rand_amount(1, 200),
            "shipping_cost": _rand_amount(5, 50),
            "discount_amount": _rand_amount(0, 100),
            "total_price": _rand_amount(10, 2500),
            "order_date": _rand_date(2024, 2025),
        })
    return rows


def _denorm_codes() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 101):
        rows.append({
            "product_id": f"PRD{i:04d}",
            "product_name": f"Product {i}",
            "sku_code": f"SKU-{random.randint(10000,99999)}",
            "barcode": f"{random.randint(100000000000,999999999999)}",
            "isbn": f"978-{random.randint(0,9)}-{random.randint(100,999)}-{random.randint(10000,99999)}-{random.randint(0,9)}",
            "category": random.choice(["Books", "Electronics", "Food"]),
            "price": _rand_amount(5, 500),
        })
    return rows


# ── Category 3: ADVERSARIAL (10+ designed to confuse) ──────────────────

ADVERSARIAL_DATASETS = [
    {
        "filename": "adv_no_identifier.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "All columns are attributes, no ID column at all",
        "generate": lambda: _adv_no_id(),
    },
    {
        "filename": "adv_unique_names.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Name column with all unique values (looks like ID to cardinality)",
        "generate": lambda: _adv_unique_names(),
    },
    {
        "filename": "adv_index_column.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Has Unnamed/index column that should be ignored",
        "generate": lambda: _adv_index_col(),
    },
    {
        "filename": "adv_all_numeric.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "All columns are numeric measures, no entity",
        "generate": lambda: _adv_all_numeric(),
    },
    {
        "filename": "adv_all_strings.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "All columns are generic strings, no entity",
        "generate": lambda: _adv_all_strings(),
    },
    {
        "filename": "adv_generic_names.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Columns named id/name/type/code — generic, no specific entity",
        "generate": lambda: _adv_generic_names(),
    },
    {
        "filename": "adv_zip_latency.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "High-cardinality location codes (zip codes, lat/lon) that look like IDs",
        "generate": lambda: _adv_zip_latency(),
    },
    {
        "filename": "adv_status_only.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Only status/boolean columns, no business entity",
        "generate": lambda: _adv_status_only(),
    },
    {
        "filename": "adv_boolean_id_lookalike.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Columns with _flag, is_ prefix making them look like booleans, but they're all we have",
        "generate": lambda: _adv_boolean_flags(),
    },
    {
        "filename": "adv_code_only.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Only code/SKU/reference columns with no descriptive fields",
        "generate": lambda: _adv_code_only(),
    },
]


def _adv_no_id() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 101):
        rows.append({
            "temperature": f"{random.uniform(-10, 40):.1f}",
            "humidity": f"{random.uniform(20, 100):.1f}",
            "wind_speed": f"{random.uniform(0, 50):.1f}",
            "pressure": f"{random.uniform(990, 1050):.1f}",
            "reading_time": _rand_date(2024, 2025),
        })
    return rows


def _adv_unique_names() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 3001):
        # All names are unique — looks like an ID to cardinality analysis
        rows.append({
            "player_name": f"Player_{i:05d}",
            "team": random.choice(["Dragons", "Tigers", "Lions", "Bears", "Wolves"]),
            "position": random.choice(["Forward", "Guard", "Center"]),
            "jersey_number": str(random.randint(0, 99)),
        })
    return rows


def _adv_index_col() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 501):
        rows.append({
            "": str(i),  # Empty header — becomes Unnamed: 0 in pandas
            "city": random.choice(["New York", "Los Angeles", "Chicago", "Houston"]),
            "population": str(random.randint(50000, 8000000)),
            "area_sq_km": str(random.randint(100, 10000)),
        })
    return rows


def _adv_all_numeric() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 101):
        rows.append({
            "score_1": str(random.uniform(0, 100)),
            "score_2": str(random.uniform(0, 100)),
            "score_3": str(random.uniform(0, 100)),
            "score_4": str(random.uniform(0, 100)),
            "score_5": str(random.uniform(0, 100)),
        })
    return rows


def _adv_all_strings() -> List[Dict[str, str]]:
    words = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"]
    rows = []
    for i in range(1, 201):
        rows.append({
            "col_a": random.choice(words),
            "col_b": random.choice(words),
            "col_c": random.choice(words),
            "col_d": random.choice(words),
            "col_e": random.choice(words),
        })
    return rows


def _adv_generic_names() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 201):
        rows.append({
            "id": str(i),
            "name": f"Item {i}",
            "type": random.choice(["A", "B", "C", "D"]),
            "code": f"CODE-{random.randint(1000,9999)}",
            "date": _rand_date(2024, 2025),
        })
    return rows


def _adv_zip_latency() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 501):
        rows.append({
            "zip_code": f"{random.randint(10000, 99999)}",
            "latitude": f"{random.uniform(25, 50):.6f}",
            "longitude": f"{random.uniform(-125, -65):.6f}",
            "population_density": str(random.randint(10, 50000)),
        })
    return rows


def _adv_status_only() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 101):
        rows.append({
            "status": random.choice(["active", "inactive", "pending"]),
            "category": random.choice(["A", "B", "C"]),
            "is_completed": random.choice(["true", "false"]),
            "priority": random.choice(["high", "medium", "low"]),
        })
    return rows


def _adv_boolean_flags() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 101):
        rows.append({
            "is_flag": random.choice(["true", "false"]),
            "has_warning": random.choice(["true", "false"]),
            "flag_active": random.choice(["true", "false"]),
            "is_yn": random.choice(["Y", "N"]),
        })
    return rows


def _adv_code_only() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 201):
        rows.append({
            "reference_code": f"REF-{i:04d}",
            "sku": f"SKU{i:06d}",
            "barcode": f"{random.randint(100000000000,999999999999)}",
            "catalog_number": f"CAT-{random.randint(100,999)}",
        })
    return rows


# ── Category 4: NO ENTITY (10+ time series / aggregates) ───────────────

NO_ENTITY_DATASETS = [
    {
        "filename": "noent_stock_prices.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Stock price time series (Date, Open, High, Low, Close, Volume)",
        "generate": lambda: _noent_stock(),
    },
    {
        "filename": "noent_monthly_revenue.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Monthly aggregated revenue by region",
        "generate": lambda: _noent_monthly_revenue(),
    },
    {
        "filename": "noent_daily_active_users.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Daily active user counts — pure metrics",
        "generate": lambda: _noent_dau(),
    },
    {
        "filename": "noent_survey_results.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Survey response aggregates (question, avg_score, count)",
        "generate": lambda: _noent_survey(),
    },
    {
        "filename": "noent_temperature_readings.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Sensor temperature readings over time",
        "generate": lambda: _noent_temps(),
    },
    {
        "filename": "noent_exchange_rates.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Currency exchange rate time series",
        "generate": lambda: _noent_forex(),
    },
    {
        "filename": "noent_website_metrics.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Website analytics metrics (pageviews, bounce_rate, sessions)",
        "generate": lambda: _noent_web_metrics(),
    },
    {
        "filename": "noent_inventory_counts.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Warehouse inventory counts by category (aggregated, no entity)",
        "generate": lambda: _noent_inventory(),
    },
    {
        "filename": "noent_quiz_scores.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Quiz score distributions (score_range, count, percentage)",
        "generate": lambda: _noent_quiz(),
    },
    {
        "filename": "noent_aggregated_orders.csv",
        "expected_primary_object": None,
        "expected_participants": [],
        "description": "Pre-aggregated order stats by month (no entity columns)",
        "generate": lambda: _noent_agg_orders(),
    },
]


def _noent_stock() -> List[Dict[str, str]]:
    rows = []
    price = 450.0
    for i in range(1, 1260):  # ~5 years of trading days
        date = _rand_date(2020, 2025)
        change = random.uniform(-5, 5)
        open_p = price
        close = round(open_p + change, 2)
        high = round(max(open_p, close) + random.uniform(0, 3), 2)
        low = round(min(open_p, close) - random.uniform(0, 3), 2)
        volume = random.randint(1000000, 10000000)
        rows.append({
            "Date": date,
            "Open": f"{open_p:.2f}",
            "High": f"{high:.2f}",
            "Low": f"{low:.2f}",
            "Close": f"{close:.2f}",
            "Volume": str(volume),
        })
        price = close
    return rows


def _noent_monthly_revenue() -> List[Dict[str, str]]:
    rows = []
    for year in [2022, 2023, 2024]:
        for month in range(1, 13):
            for region in ["North", "South", "East", "West"]:
                rows.append({
                    "year": str(year),
                    "month": f"{month:02d}",
                    "region": region,
                    "revenue": _rand_amount(10000, 500000),
                    "orders_count": str(random.randint(100, 5000)),
                })
    return rows


def _noent_dau() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 367):
        rows.append({
            "date": _rand_date(2024, 2025),
            "daily_active_users": str(random.randint(5000, 50000)),
            "new_signups": str(random.randint(100, 2000)),
            "sessions": str(random.randint(10000, 80000)),
            "avg_session_duration_sec": str(random.randint(120, 600)),
        })
    return rows


def _noent_survey() -> List[Dict[str, str]]:
    questions = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9", "Q10"]
    rows = []
    for q in questions:
        rows.append({
            "question_id": q,
            "question_text": f"Survey question {q}",
            "avg_score": f"{random.uniform(2.0, 5.0):.2f}",
            "response_count": str(random.randint(50, 500)),
            "std_dev": f"{random.uniform(0.5, 1.5):.2f}",
        })
    return rows


def _noent_temps() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 1001):
        rows.append({
            "timestamp": f"{_rand_date(2024, 2025)}T{random.randint(0,23):02d}:00:00",
            "temperature_c": f"{random.uniform(-5, 40):.1f}",
            "humidity_pct": f"{random.uniform(20, 95):.1f}",
            "sensor_id": f"SENSOR_{random.randint(1,10):02d}",
        })
    return rows


def _noent_forex() -> List[Dict[str, str]]:
    pairs = ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD"]
    rows = []
    for pair in pairs:
        for _ in range(60):
            rows.append({
                "currency_pair": pair,
                "date": _rand_date(2024, 2025),
                "rate": f"{random.uniform(0.6, 1.6):.4f}",
                "change_pct": f"{random.uniform(-2, 2):.2f}",
            })
    return rows


def _noent_web_metrics() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 91):
        rows.append({
            "date": _rand_date(2025, 2025),
            "pageviews": str(random.randint(1000, 50000)),
            "unique_visitors": str(random.randint(500, 20000)),
            "bounce_rate": f"{random.uniform(30, 70):.1f}",
            "avg_session_minutes": f"{random.uniform(2, 10):.1f}",
        })
    return rows


def _noent_inventory() -> List[Dict[str, str]]:
    categories = ["Electronics", "Clothing", "Food", "Books", "Tools"]
    warehouses = ["WH-01", "WH-02", "WH-03"]
    rows = []
    for cat in categories:
        for wh in warehouses:
            rows.append({
                "category": cat,
                "warehouse": wh,
                "total_units": str(random.randint(100, 10000)),
                "avg_unit_cost": _rand_amount(5, 500),
                "last_restock_date": _rand_date(2024, 2025),
            })
    return rows


def _noent_quiz() -> List[Dict[str, str]]:
    rows = []
    for score in range(0, 101, 5):
        rows.append({
            "score_range": f"{score}-{score+4}",
            "student_count": str(random.randint(5, 200)),
            "percentage": f"{random.uniform(0.5, 15):.2f}",
            "cumulative_pct": "0.0",
        })
    return rows


def _noent_agg_orders() -> List[Dict[str, str]]:
    rows = []
    for year in [2023, 2024, 2025]:
        for month in range(1, 13):
            rows.append({
                "year_month": f"{year}-{month:02d}",
                "total_orders": str(random.randint(500, 10000)),
                "avg_order_value": _rand_amount(25, 200),
                "total_revenue": _rand_amount(50000, 500000),
            })
    return rows


# ── Category 5: MULTI-ENTITY EDGE CASES (5+) ──────────────────────────

MULTI_ENTITY_DATASETS = [
    {
        "filename": "multi_order_details.csv",
        "expected_primary_object": "order",
        "expected_participants": ["customer", "product", "supplier"],
        "description": "Order details with customer, product, and supplier references",
        "generate": lambda: _multi_order_details(),
    },
    {
        "filename": "multi_hospital_visits.csv",
        "expected_primary_object": "visit",
        "expected_participants": ["patient", "doctor", "hospital"],
        "description": "Hospital visits with patient, doctor, and hospital references",
        "generate": lambda: _multi_hospital(),
    },
    {
        "filename": "multi_course_enrollments.csv",
        "expected_primary_object": "enrollment",
        "expected_participants": ["student", "course"],
        "description": "Course enrollments with student and course references",
        "generate": lambda: _multi_enrollments(),
    },
    {
        "filename": "multi_support_tickets.csv",
        "expected_primary_object": "ticket",
        "expected_participants": ["customer", "agent", "product"],
        "description": "Support tickets with customer, agent, and product references",
        "generate": lambda: _multi_tickets(),
    },
    {
        "filename": "multi_project_tasks.csv",
        "expected_primary_object": "task",
        "expected_participants": ["project", "assignee", "reviewer"],
        "description": "Project tasks with project, assignee, and reviewer references",
        "generate": lambda: _multi_tasks(),
    },
]


def _multi_order_details() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 501):
        rows.append({
            "order_id": f"ORD{i:06d}",
            "customer_id": f"CUST{random.randint(1,100):04d}",
            "product_id": f"PROD{random.randint(1,50):04d}",
            "supplier_id": f"SUPP{random.randint(1,20):03d}",
            "quantity": str(random.randint(1, 10)),
            "unit_price": _rand_amount(10, 500),
            "order_date": _rand_date(2024, 2025),
        })
    return rows


def _multi_hospital() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 301):
        rows.append({
            "visit_id": f"VIS{i:06d}",
            "patient_id": f"PAT{random.randint(1,200):04d}",
            "doctor_id": f"DOC{random.randint(1,30):03d}",
            "hospital_id": f"HOSP{random.randint(1,10):02d}",
            "admission_date": _rand_date(2024, 2025),
            "discharge_date": _rand_date(2024, 2025),
            "diagnosis": random.choice(["Pneumonia", "Fracture", "Appendicitis", "Observation"]),
        })
    return rows


def _multi_enrollments() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 601):
        rows.append({
            "enrollment_id": f"ENR{i:06d}",
            "student_id": f"STU{random.randint(1,200):04d}",
            "course_id": f"CRS{random.randint(1,30):03d}",
            "semester": random.choice(["2024-Fall", "2025-Spring", "2025-Fall"]),
            "grade": random.choice(["A", "B", "C", "D", "F", "W"]),
        })
    return rows


def _multi_tickets() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 401):
        rows.append({
            "ticket_id": f"TKT{i:06d}",
            "customer_id": f"CUST{random.randint(1,80):04d}",
            "agent_id": f"AGT{random.randint(1,20):03d}",
            "product_id": f"PROD{random.randint(1,15):03d}",
            "priority": random.choice(["Low", "Medium", "High", "Critical"]),
            "status": random.choice(["Open", "In Progress", "Resolved", "Closed"]),
            "created_date": _rand_date(2024, 2025),
        })
    return rows


def _multi_tasks() -> List[Dict[str, str]]:
    rows = []
    for i in range(1, 251):
        rows.append({
            "task_id": f"TSK{i:05d}",
            "project_id": f"PRJ{random.randint(1,15):03d}",
            "assignee_id": f"USR{random.randint(1,30):03d}",
            "reviewer_id": f"USR{random.randint(1,30):03d}",
            "status": random.choice(["To Do", "In Progress", "Review", "Done"]),
            "due_date": _rand_date(2025, 2025),
            "priority": random.choice(["P0", "P1", "P2", "P3"]),
        })
    return rows


# ── Generator ──────────────────────────────────────────────────────────

ALL_CATEGORIES = {
    "clean": CLEAN_DATASETS,
    "denormalized": DENORMALIZED_DATASETS,
    "adversarial": ADVERSARIAL_DATASETS,
    "no_entity": NO_ENTITY_DATASETS,
    "multi_entity": MULTI_ENTITY_DATASETS,
}


def generate(counts: Optional[Dict[str, int]] = None, verbose: bool = True) -> Dict[str, int]:
    """Generate datasets with specified counts per category.

    Args:
        counts: Dict of {category: count} e.g. {"clean": 10, "adversarial": 8}
                If None, generates ALL datasets.

    Returns:
        Dict of {category: actual_count_generated}
    """
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing manifest
    existing = {}
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            existing = json.load(f)

    generated = {}
    total_prior = len(existing)

    for category, datasets in ALL_CATEGORIES.items():
        target = counts.get(category, len(datasets)) if counts else len(datasets)
        to_generate = datasets[:target]

        count = 0
        for ds in to_generate:
            filename = ds["filename"]
            if verbose:
                print(f"  Generating {category}/{filename}...", end=" ")

            # Generate data
            rows = ds["generate"]()
            _write_csv(filename, rows)

            # Update manifest
            existing[filename] = {
                "description": ds["description"],
                "expected_primary_object": ds["expected_primary_object"],
                "expected_participants": ds["expected_participants"],
            }

            if ds["expected_primary_object"] is None:
                existing[filename]["abstention_test"] = True

            count += 1
            if verbose:
                print(f"{len(rows)} rows")

        generated[category] = count
        total = len(to_generate)

    # Write updated manifest
    with open(MANIFEST_PATH, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    total_new = len(existing) - total_prior

    if verbose:
        print(f"\n{'=' * 50}")
        print(f"  Generated: {sum(generated.values())} new datasets")
        for cat, count in generated.items():
            print(f"    {cat}: {count}")
        print(f"  Total in manifest: {len(existing)}")
        print(f"{'=' * 50}\n")

    return generated


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate synthetic benchmark datasets")
    parser.add_argument("--minimal", action="store_true", help="Generate just enough to reach 50 total datasets")
    for cat in ALL_CATEGORIES:
        parser.add_argument(f"--{cat}", type=int, help=f"Number of {cat} datasets to generate")

    args = parser.parse_args()

    if args.minimal:
        # Generate just enough datasets to reach 50 total
        counts = {"clean": 10, "denormalized": 15, "adversarial": 10, "no_entity": 10, "multi_entity": 5}
    else:
        counts = {}
        for cat in ALL_CATEGORIES:
            val = getattr(args, cat, None)
            if val is not None:
                counts[cat] = val

    if not counts and not args.minimal:
        # Default: generate ALL
        counts = None

    generate(counts)


if __name__ == "__main__":
    main()

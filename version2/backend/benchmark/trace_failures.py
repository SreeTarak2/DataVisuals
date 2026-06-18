"""Diagnostic: trace root causes of all 14 benchmark failures."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import json

from services.knowledge_graph.models import ColumnProfile, ColumnRole
from services.knowledge_graph.entity_discovery import entity_discovery
from services.knowledge_graph.primary_object_discovery import primary_object_discovery
from services.knowledge_graph.signal_engine import signal_engine
from services.knowledge_graph.grouping_engine import grouping_engine
from services.knowledge_graph.entity_validator import entity_validator

def trace_dataset(ds_name, expected_primary):
    df = pd.read_csv(f'benchmark/datasets/{ds_name}', nrows=5000)
    table_name = ds_name.replace('.csv', '')
    
    profiles = []
    total_rows = len(df)
    for col_name in df.columns:
        col_data = df[col_name]
        non_null = col_data.dropna()
        distinct_count = non_null.nunique()
        sample_values = non_null.head(10).astype(str).tolist()
        is_numeric = pd.api.types.is_numeric_dtype(col_data)
        is_string = pd.api.types.is_string_dtype(col_data) or col_data.dtype == 'object'
        
        if is_numeric:
            data_type = 'decimal' if 'float' in str(col_data.dtype) else 'integer'
        elif is_string:
            data_type = 'string'
        else:
            data_type = 'unknown'
        
        distinct_ratio = distinct_count / total_rows if total_rows > 0 else 0.0
        null_ratio = (total_rows - len(non_null)) / total_rows if total_rows > 0 else 0.0
        
        profiles.append(ColumnProfile(
            name=col_name,
            data_type=data_type,
            distinct_count=distinct_count,
            distinct_ratio=distinct_ratio,
            null_ratio=null_ratio,
            sample_values=sample_values,
        ))
    
    # Trace column classification
    print(f"\n{'='*60}")
    print(f"DATASET: {ds_name}  (expected primary: {expected_primary})")
    print(f"{'='*60}")
    for p in profiles:
        signal = signal_engine.classify(p)
        col_lower = p.column_name.lower().replace(' ', '_')
        print(f"  {p.column_name:35s} -> type={p.data_type:10s} distinct_ratio={p.distinct_ratio:.3f}  role={signal.role.value:12s}  hint={signal.entity_hint}  conf={signal.confidence:.3f}")
    
    # Trace entity discovery
    report = entity_discovery.discover(profiles, table_name)
    print(f"\n  Entities discovered:")
    for entity in report.entities:
        e = entity
        ent = entity_validator.validate(e, profiles, table_name)
        print(f"    {e.label:20s} source={e.source:15s} identifier={e.identifier_column:20s} "
              f"entity_conf={e.entity_confidence:.3f} "
              f"valid={ent.is_valid} valid_conf={ent.entity_confidence:.3f}")
    print(f"  Unknown columns: {len(report.unknown_columns)}")
    
    # Trace primary object discovery
    validated = []
    for entity in report.entities:
        valid = entity_validator.validate(entity, profiles, table_name)
        if valid.is_valid:
            validated.append(valid)
    
    primary = primary_object_discovery.select_primary(validated, report, table_name, profiles)
    if primary:
        print(f"  PRIMARY: {primary.label} (conf={primary.entity_confidence:.3f})")
        # Participation
        try:
            from services.knowledge_graph.participation_discovery import participation_discovery
            participants = participation_discovery.discover(primary, validated, profiles, table_name)
            if participants:
                print(f"  Participants: {[p.label for p in participants]}")
            else:
                print(f"  Participants: []")
        except Exception as e:
            print(f"  Participation error: {e}")
    else:
        print(f"  PRIMARY: None")

# === Primary Object Wrong ===
trace_dataset("clean_invoices.csv", "invoice")
trace_dataset("clean_shipments.csv", "shipment")
trace_dataset("clean_transactions.csv", "transaction")
trace_dataset("denorm_timestamp_variants.csv", "transaction")
trace_dataset("multi_course_enrollments.csv", "enrollment")
trace_dataset("multi_hospital_visits.csv", "visit")
trace_dataset("multi_project_tasks.csv", "task")
trace_dataset("multi_support_tickets.csv", "ticket")

# === Participation Recall ===
trace_dataset("denorm_camel_case.csv", "employee")
trace_dataset("denorm_mixed_case.csv", "patient")
trace_dataset("denorm_underscore_heavy.csv", "shipment")
trace_dataset("denorm_url_columns.csv", "product")
trace_dataset("multi_order_details.csv", "order")

# === Abstention ===
trace_dataset("noent_quiz_scores.csv", None)

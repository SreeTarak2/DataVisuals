"""Diagnostic: trace remaining 4 failures."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd

from services.knowledge_graph.models import ColumnProfile, ColumnRole
from services.knowledge_graph.entity_discovery import entity_discovery
from services.knowledge_graph.primary_object_discovery import primary_object_discovery
from services.knowledge_graph.signal_engine import signal_engine
from services.knowledge_graph.grouping_engine import grouping_engine
from services.knowledge_graph.entity_validator import entity_validator
from services.knowledge_graph.participation_discovery import participation_discovery

def trace_participation(ds_name):
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
    
    print(f"\n{'='*60}")
    print(f"DATASET: {ds_name}")
    print(f"{'='*60}")
    
    # Classify each column
    for p in profiles:
        col_lower = p.name.lower().replace(' ', '_')
        # Use the new camelCase normalization too
        name_snake = col_lower  # skip for brevity
        role, candidates, evidence = signal_engine.classify_column(p)
        hints = [c.label for c in candidates]
        hint_str = f"hints={hints}" if hints else "no_hints"
        print(f"  {p.name:30s} → role={role.value:12s} conf={p.distinct_ratio:.3f} {hint_str}")
    
    # Entity discovery
    report = entity_discovery.discover(profiles, table_name)
    print(f"\n  Entities discovered:")
    for entity in report.entities:
        print(f"    {entity.label:20s} id_col={entity.identifier_column or 'NONE':20s} "
              f"entity_conf={entity.entity_confidence:.3f} "
              f"candidate_conf={entity.candidate_confidence:.3f} "
              f"valid={entity.is_valid}")
    
    # Primary
    primary = primary_object_discovery.discover(report.entities, table_name, len(profiles))
    if primary.is_valid:
        print(f"\n  PRIMARY: {primary.label} (conf={primary.confidence:.3f})")
        
        # Participation
        participants = participation_discovery.discover(report.entities, primary)
        if participants:
            for p in participants:
                print(f"    Participant: {p.label:15s} id_col={p.identifier_column:20s} "
                      f"score={p.participation_score:.3f} naming={p.naming_evidence:.3f} "
                      f"entity_conf={p.entity_confidence:.3f} valid={p.is_valid}")
        else:
            print(f"    Participants: []")
    else:
        print(f"\n  PRIMARY: None")

trace_participation("denorm_camel_case.csv")
trace_participation("denorm_underscore_heavy.csv")
trace_participation("multi_project_tasks.csv")
trace_participation("noent_quiz_scores.csv")

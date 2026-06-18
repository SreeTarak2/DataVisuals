"""
data_quality — Continuous data quality monitoring and reporting.

Architecture:
    ├── CompletenessChecker   → Detects missing values per column
    ├── ConsistencyValidator  → Checks type consistency and constraint violations
    ├── DistributionDriftDetector → Statistical distribution shifts over time
    └── SchemaChangeDetector  → Compares schema against known baseline

Runs on dataset upload and on schedule for continuous monitoring.
"""

from .quality_agent import DataQualityAgent

__all__ = ["DataQualityAgent"]

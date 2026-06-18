"""
DataQualityAgent — Continuous data quality monitoring and reporting.

Architecture:
    CompletenessChecker       → Detects missing values per column
    ConsistencyValidator      → Checks type consistency and constraint violations
    DistributionDriftDetector → Statistical distribution shifts over time
    SchemaChangeDetector      → Compares schema against known baseline

Design principles:
    - Zero LLM cost: all checks are deterministic statistical/rules-based
    - Incremental: can run on upload and on schedule for drift detection
    - Comparable: results can be compared across runs to track quality trend
    - Non-blocking: fast enough to run synchronously on upload
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class QualityReport:
    """Complete data quality assessment for a dataset."""

    overall_score: float = 0.0
    completeness: dict = field(default_factory=dict)
    consistency: dict = field(default_factory=dict)
    distribution_drift: list[dict] = field(default_factory=list)
    schema_changes: list[dict] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    passed_checks: int = 0
    failed_checks: int = 0
    dataset_id: str = ""
    run_id: str = ""


@dataclass
class QualityIssue:
    """A single quality issue detected."""

    column: str
    issue_type: str  # "missing_values", "type_mismatch", "outlier", "duplicate", "constraint_violation"
    severity: str  # "high", "medium", "low"
    description: str
    pct_affected: float
    suggestion: str = ""


# ── CompletenessChecker ──────────────────────────────────────────────────────


class CompletenessChecker:
    """Detects missing values and completeness issues per column."""

    COMPLETENESS_WARN_THRESHOLD = 0.05  # 5% missing = warning
    COMPLETENESS_CRITICAL_THRESHOLD = 0.20  # 20% missing = critical

    @staticmethod
    def check(columns: list[dict], row_count: int) -> tuple[dict, list[dict]]:
        """
        Evaluate completeness for each column.

        Returns:
            (summary_dict, issues_list)
        """
        issues = []
        column_stats = {}

        for col in columns:
            name = col.get("name", "?")
            null_pct = col.get("null_percentage", 0.0)
            unique_count = col.get("unique_count", 0)

            column_stats[name] = {
                "null_percentage": null_pct,
                "unique_count": unique_count,
                "completeness": round(100.0 - null_pct, 1),
            }

            if null_pct >= CompletenessChecker.COMPLETENESS_CRITICAL_THRESHOLD:
                issues.append({
                    "column": name,
                    "issue_type": "missing_values",
                    "severity": "high",
                    "description": f"{null_pct:.1f}% of values are missing",
                    "pct_affected": null_pct,
                    "suggestion": f"Investigate data source or impute missing values in '{name}'",
                })
            elif null_pct >= CompletenessChecker.COMPLETENESS_WARN_THRESHOLD:
                issues.append({
                    "column": name,
                    "issue_type": "missing_values",
                    "severity": "medium",
                    "description": f"{null_pct:.1f}% of values are missing",
                    "pct_affected": null_pct,
                    "suggestion": f"Consider filling or flagging missing values in '{name}'",
                })

        # Also check for completely empty columns
        for col in columns:
            if col.get("unique_count", 0) == 0:
                issues.append({
                    "column": col["name"],
                    "issue_type": "empty_column",
                    "severity": "high",
                    "description": "Column contains no unique values (possibly empty)",
                    "pct_affected": 100.0,
                    "suggestion": f"Remove or investigate empty column '{col['name']}'",
                })

        return {
            "total_columns": len(columns),
            "columns_with_missing": sum(1 for i in issues if i["issue_type"] == "missing_values"),
            "columns_empty": sum(1 for i in issues if i["issue_type"] == "empty_column"),
            "column_stats": column_stats,
        }, issues


# ── ConsistencyValidator ─────────────────────────────────────────────────────


class ConsistencyValidator:
    """Validates type consistency and detects constraint violations."""

    @staticmethod
    def check(
        columns: list[dict],
        sample_rows: list[dict] | None = None,
    ) -> tuple[dict, list[dict]]:
        """
        Evaluate type consistency and constraint violations.

        Returns:
            (summary_dict, issues_list)
        """
        issues = []
        findings = {}

        for col in columns:
            name = col.get("name", "?")
            col_type = col.get("type", "unknown")
            unique_count = col.get("unique_count", 0)

            findings[name] = {"type": col_type, "unique_count": unique_count}

            # Check: categorical with too many unique values (potential ID column)
            if col_type in ("string", "text", "varchar", "object") and unique_count > 100:
                # Could be valid categorical or could be an ID column
                findings[name]["high_cardinality"] = True

            # Check: boolean-like columns
            if col_type in ("string", "text", "object") and unique_count == 2:
                findings[name]["potential_boolean"] = True

            # Check: date columns that could benefit from parsing
            if col_type == "string" and unique_count > 5:
                findings[name]["potential_date"] = None  # Need data to confirm

        # Sample-based checks (if available)
        sample_issues = []
        if sample_rows and len(sample_rows) > 0:
            # Check for mixed types in string columns
            for col in columns:
                name = col.get("name", "?")
                col_type = col.get("type", "unknown")
                if col_type in ("string", "text", "object", "mixed"):
                    values = [
                        row.get(name)
                        for row in sample_rows
                        if row.get(name) is not None
                    ]
                    if values:
                        types_in_sample = {type(v).__name__ for v in values}
                        if len(types_in_sample) > 1:
                            sample_issues.append({
                                "column": name,
                                "issue_type": "type_mismatch",
                                "severity": "medium",
                                "description": f"Mixed types in column: {types_in_sample}",
                                "pct_affected": 0.0,
                                "suggestion": "Ensure column has a consistent data type",
                            })

        issues.extend(sample_issues)

        return {
            "total_columns": len(columns),
            "type_issues": len(sample_issues),
            "column_findings": findings,
        }, issues


# ── DistributionDriftDetector ────────────────────────────────────────────────


class DistributionDriftDetector:
    """Detects statistical distribution shifts compared to a baseline."""

    DRIFT_WARN_THRESHOLD = 0.2  # 20% shift = warning
    DRIFT_CRITICAL_THRESHOLD = 0.5  # 50% shift = critical

    @staticmethod
    def check(
        columns: list[dict],
        baseline: dict[str, dict] | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """
        Detect distribution drift for numeric columns.

        Args:
            columns: Current column metadata with numeric_summary
            baseline: Previous column summary to compare against

        Returns:
            (drift_results_list, issues_list)
        """
        drifts = []
        issues = []

        for col in columns:
            name = col.get("name", "?")
            col_type = col.get("type", "")
            num_summary = col.get("numeric_summary", {})

            if col_type not in ("numeric", "float", "int", "integer") or not num_summary:
                continue

            current_mean = num_summary.get("mean", 0)
            current_std = num_summary.get("std", 0)

            if current_std == 0:
                continue

            drift_entry = {
                "column": name,
                "current_mean": round(current_mean, 4),
                "current_std": round(current_std, 4),
                "baseline_mean": None,
                "baseline_std": None,
                "drift_score": 0.0,
                "has_drift": False,
            }

            # Compare to baseline if available
            if baseline and name in baseline:
                b = baseline[name]
                b_mean = b.get("mean", 0)
                b_std = b.get("std", 0)

                drift_entry["baseline_mean"] = round(b_mean, 4)
                drift_entry["baseline_std"] = round(b_std, 4)

                # Normalized drift: how many stds did the mean shift?
                pooled_std = math.sqrt((current_std**2 + b_std**2) / 2) if current_std > 0 and b_std > 0 else current_std
                if pooled_std > 0:
                    drift_score = abs(current_mean - b_mean) / pooled_std
                    drift_score = min(1.0, drift_score / 3.0)  # Normalize: 3 stds = max
                    drift_entry["drift_score"] = round(drift_score, 4)
                    drift_entry["has_drift"] = drift_score > DistributionDriftDetector.DRIFT_WARN_THRESHOLD

                    if drift_score > DistributionDriftDetector.DRIFT_CRITICAL_THRESHOLD:
                        issues.append({
                            "column": name,
                            "issue_type": "distribution_shift",
                            "severity": "high",
                            "description": (
                                f"Significant distribution shift in '{name}': "
                                f"mean changed from {b_mean:.2f} to {current_mean:.2f}"
                            ),
                            "pct_affected": 0.0,
                            "suggestion": f"Investigate what changed in '{name}' — data source or real trend?",
                        })
                    elif drift_score > DistributionDriftDetector.DRIFT_WARN_THRESHOLD:
                        issues.append({
                            "column": name,
                            "issue_type": "distribution_shift",
                            "severity": "medium",
                            "description": (
                                f"Moderate distribution shift in '{name}': "
                                f"mean changed from {b_mean:.2f} to {current_mean:.2f}"
                            ),
                            "pct_affected": 0.0,
                            "suggestion": f"Monitor '{name}' for continued drift",
                        })

            drifts.append(drift_entry)

        return drifts, issues


# ── SchemaChangeDetector ─────────────────────────────────────────────────────


class SchemaChangeDetector:
    """Detects schema changes compared to a stored baseline."""

    @staticmethod
    def check(
        current_columns: list[dict],
        previous_columns: list[dict] | None = None,
    ) -> list[dict]:
        """
        Detect schema changes compared to previous run.

        Returns:
            List of schema change descriptions
        """
        changes = []

        if not previous_columns:
            return changes  # No baseline to compare

        current_names = {c.get("name", "") for c in current_columns}
        previous_names = {c.get("name", "") for c in previous_columns}

        # New columns
        added = current_names - previous_names
        for name in sorted(added):
            changes.append({
                "type": "column_added",
                "column": name,
                "severity": "low",
                "description": f"New column '{name}' added to dataset",
            })

        # Removed columns
        removed = previous_names - current_names
        for name in sorted(removed):
            changes.append({
                "type": "column_removed",
                "column": name,
                "severity": "high",
                "description": f"Column '{name}' removed from dataset",
            })

        # Type changes
        prev_types = {c.get("name", ""): c.get("type", "") for c in previous_columns}
        for col in current_columns:
            name = col.get("name", "")
            curr_type = col.get("type", "")
            prev_type = prev_types.get(name)
            if prev_type and curr_type and prev_type != curr_type:
                changes.append({
                    "type": "type_changed",
                    "column": name,
                    "severity": "medium",
                    "description": f"Column '{name}' type changed from '{prev_type}' to '{curr_type}'",
                })

        return changes


# ── DataQualityAgent ─────────────────────────────────────────────────────────


class DataQualityAgent:
    """
    Continuous data quality monitoring.

    Runs a suite of deterministic checks on column metadata and sample data,
    producing a structured QualityReport with scores and actionable issues.

    Usage:
        agent = DataQualityAgent()
        report = await agent.run_quality_check(
            columns=[...],
            sample_rows=[...],
            row_count=10000,
            dataset_id="dataset_123",
        )
    """

    def __init__(self):
        self.completeness_checker = CompletenessChecker()
        self.consistency_validator = ConsistencyValidator()
        self.drift_detector = DistributionDriftDetector()
        self.schema_detector = SchemaChangeDetector()
        self._previous_schemas: dict[str, list[dict]] = {}  # dataset_id → columns

    async def run_quality_check(
        self,
        columns: list[dict] | None = None,
        sample_rows: list[dict] | None = None,
        row_count: int = 0,
        dataset_id: str = "",
        previous_columns: list[dict] | None = None,
        run_id: str = "",
    ) -> QualityReport:
        """
        Run all quality checks and produce a structured report.

        Args:
            columns: Column metadata list
            sample_rows: Sample data rows for sample-based checks
            row_count: Total row count
            dataset_id: The dataset ID
            previous_columns: Previous column metadata for schema comparison
            run_id: Optional run ID for tracing

        Returns:
            QualityReport with scores and issues
        """
        if not columns:
            return QualityReport(
                overall_score=0.0,
                dataset_id=dataset_id,
                run_id=run_id,
            )

        all_issues: list[dict] = []

        # ── 1. Completeness ────────────────────────────────────────────────
        completeness_result, completeness_issues = self.completeness_checker.check(
            columns, row_count
        )
        all_issues.extend(completeness_issues)

        # ── 2. Consistency ─────────────────────────────────────────────────
        consistency_result, consistency_issues = self.consistency_validator.check(
            columns, sample_rows
        )
        all_issues.extend(consistency_issues)

        # ── 3. Drift detection (requires previous baseline) ─────────────────
        previous = previous_columns or self._previous_schemas.get(dataset_id)
        drifts, drift_issues = self.drift_detector.check(columns, self._build_baseline(previous))
        all_issues.extend(drift_issues)

        # ── 4. Schema changes ──────────────────────────────────────────────
        schema_changes = self.schema_detector.check(columns, previous)
        for change in schema_changes:
            all_issues.append({
                "column": change["column"],
                "issue_type": change["type"],
                "severity": change["severity"],
                "description": change["description"],
                "pct_affected": 0.0,
                "suggestion": self._suggestion_for_schema_change(change),
            })

        # ── 5. Score computation ───────────────────────────────────────────
        passed = sum(1 for col in columns if col.get("null_percentage", 0) < 0.05)
        total_checks = max(len(columns) * 2, 1)  # Rough estimate

        # Base score from completeness
        completeness_score = 1.0 - (completeness_result.get("columns_with_missing", 0) / max(len(columns), 1))
        # Penalize for high-severity issues
        severity_penalty = sum(
            0.2 if i.get("severity") == "high" else 0.1 if i.get("severity") == "medium" else 0.05
            for i in all_issues
        )
        overall_score = max(0.0, min(1.0, completeness_score - severity_penalty * 0.1))

        # ── 6. Store schema for future comparison ──────────────────────────
        if dataset_id:
            self._previous_schemas[dataset_id] = columns

        return QualityReport(
            overall_score=round(overall_score, 2),
            completeness=completeness_result,
            consistency=consistency_result,
            distribution_drift=drifts,
            schema_changes=schema_changes,
            issues=sorted(all_issues, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("severity", "low"), 3)),
            passed_checks=passed,
            failed_checks=len(all_issues),
            dataset_id=dataset_id,
            run_id=run_id,
        )

    @staticmethod
    def _build_baseline(columns: list[dict] | None) -> dict[str, dict] | None:
        """Convert column metadata to baseline dict for drift comparison."""
        if not columns:
            return None
        baseline = {}
        for col in columns:
            ns = col.get("numeric_summary", {})
            if ns:
                baseline[col["name"]] = {
                    "mean": ns.get("mean", 0),
                    "std": ns.get("std", 0),
                }
        return baseline if baseline else None

    @staticmethod
    def _suggestion_for_schema_change(change: dict) -> str:
        ctype = change.get("type", "")
        col = change.get("column", "")
        if ctype == "column_added":
            return f"Review new column '{col}' and integrate into existing pipelines"
        elif ctype == "column_removed":
            return f"Update dashboards and queries that reference removed column '{col}'"
        elif ctype == "type_changed":
            return f"Validate type change for '{col}' — may break existing queries"
        return "Review schema change"


# ── Singleton ────────────────────────────────────────────────────────────────

data_quality_agent = DataQualityAgent()

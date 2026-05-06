"""Guardrail Validator - Validates dataset against guardrail rules"""

import polars as pl
from typing import List, Dict, Any, Tuple
import re
from workers.guardrails.models import GuardrailRule, GuardrailViolation, GuardrailResult


class GuardrailValidator:
    """Validates datasets against defined guardrail rules"""

    def __init__(self):
        pass

    def validate(
        self, df: pl.DataFrame, rules: List[GuardrailRule], dataset_id: str
    ) -> GuardrailResult:
        """Validate dataset against all guardrail rules"""
        violations = []
        critical_count = 0
        warning_count = 0

        for rule in rules:
            if not rule.is_active:
                continue

            violation = self._check_rule(df, rule)
            if violation:
                violations.append(violation)
                if rule.severity == "critical":
                    critical_count += 1
                elif rule.severity == "warning":
                    warning_count += 1

        passed = critical_count == 0
        status = "passed" if passed else "failed"
        quarantine_reason = None

        if not passed:
            quarantine_reason = f"Dataset has {critical_count} critical violations preventing AI analysis"

        return GuardrailResult(
            dataset_id=dataset_id,
            total_rules_checked=len(rules),
            total_violations=len(violations),
            passed=passed,
            violations=violations,
            critical_violations=critical_count,
            warning_violations=warning_count,
            status=status,
            quarantine_reason=quarantine_reason,
        )

    def _check_rule(
        self, df: pl.DataFrame, rule: GuardrailRule
    ) -> GuardrailViolation | None:
        """Check a single rule against the dataframe"""
        if rule.column_name not in df.columns:
            return None

        series = df[rule.column_name]

        if rule.rule_type == "not_null":
            return self._check_not_null(series, rule)
        elif rule.rule_type == "unique":
            return self._check_unique(series, rule)
        elif rule.rule_type == "pattern":
            return self._check_pattern(series, rule)
        elif rule.rule_type == "range":
            return self._check_range(series, rule)
        elif rule.rule_type == "categorical":
            return self._check_categorical(series, rule)

        return None

    def _check_not_null(
        self, series: pl.Series, rule: GuardrailRule
    ) -> GuardrailViolation | None:
        """Check for null values"""
        null_mask = series.is_null()
        null_count = null_mask.sum()

        if null_count == 0:
            return None

        null_indices = [i for i, is_null in enumerate(null_mask.to_list()) if is_null][
            :10
        ]
        sample_values = [None] * min(5, null_count)

        return GuardrailViolation(
            rule_id=rule.rule_id,
            column_name=rule.column_name,
            row_indices=null_indices,
            violation_count=int(null_count),
            sample_values=sample_values,
            message=f"Found {null_count} null values in column '{rule.column_name}' (max allowed: 5%)",
        )

    def _check_unique(
        self, series: pl.Series, rule: GuardrailRule
    ) -> GuardrailViolation | None:
        """Check for duplicate values"""
        non_null = series.drop_nulls()
        total_count = len(non_null)
        unique_count = non_null.n_unique()

        if total_count == unique_count:
            return None

        duplicate_count = total_count - unique_count

        value_counts = non_null.value_counts().sort("count", descending=True)
        duplicate_values = value_counts.filter(pl.col("count") > 1).head(5)

        sample_values = duplicate_values[rule.column_name].to_list()[:5]

        dup_rows = []
        seen = set()
        for i, val in enumerate(non_null.to_list()):
            if val in seen and len(dup_rows) < 10:
                dup_rows.append(i)
            seen.add(val)

        return GuardrailViolation(
            rule_id=rule.rule_id,
            column_name=rule.column_name,
            row_indices=dup_rows,
            violation_count=int(duplicate_count),
            sample_values=sample_values,
            message=f"Found {duplicate_count} duplicate values in column '{rule.column_name}' which should be unique",
        )

    def _check_pattern(
        self, series: pl.Series, rule: GuardrailRule
    ) -> GuardrailViolation | None:
        """Check values against regex pattern"""
        pattern = rule.parameters.get("pattern")
        if not pattern:
            return None

        regex = re.compile(pattern)
        non_null = series.drop_nulls()
        violations = []

        for i, val in enumerate(non_null.to_list()):
            if val is not None and not regex.match(str(val)):
                violations.append((i, val))

        if not violations:
            return None

        violation_indices = [v[0] for v in violations[:10]]
        sample_bad_values = [v[1] for v in violations[:5]]

        return GuardrailViolation(
            rule_id=rule.rule_id,
            column_name=rule.column_name,
            row_indices=violation_indices,
            violation_count=len(violations),
            sample_values=sample_bad_values,
            message=f"Found {len(violations)} values in column '{rule.column_name}' that don't match expected pattern",
        )

    def _check_range(
        self, series: pl.Series, rule: GuardrailRule
    ) -> GuardrailViolation | None:
        """Check numeric values are within range"""
        min_val = rule.parameters.get("min")
        max_val = rule.parameters.get("max")

        if min_val is None or max_val is None:
            return None

        non_null = series.drop_nulls()
        below_min = non_null < min_val
        above_max = non_null > max_val
        violations_mask = below_min | above_max
        violation_count = violations_mask.sum()

        if violation_count == 0:
            return None

        violation_indices = [
            i
            for i, is_violation in enumerate(violations_mask.to_list())
            if is_violation
        ][:10]
        violating_values = non_null.filter(violations_mask).head(5).to_list()

        return GuardrailViolation(
            rule_id=rule.rule_id,
            column_name=rule.column_name,
            row_indices=violation_indices,
            violation_count=int(violation_count),
            sample_values=violating_values,
            message=f"Found {violation_count} values in column '{rule.column_name}' outside valid range [{min_val}, {max_val}]",
        )

    def _check_categorical(
        self, series: pl.Series, rule: GuardrailRule
    ) -> GuardrailViolation | None:
        """Check values are from allowed set"""
        allowed_values = rule.parameters.get("allowed_values", [])
        if not allowed_values:
            return None

        non_null = series.drop_nulls()
        allowed_set = set(str(v) for v in allowed_values)

        violations = []
        for i, val in enumerate(non_null.to_list()):
            if str(val) not in allowed_set:
                violations.append((i, val))

        if not violations:
            return None

        violation_indices = [v[0] for v in violations[:10]]
        sample_bad_values = [v[1] for v in violations[:5]]

        return GuardrailViolation(
            rule_id=rule.rule_id,
            column_name=rule.column_name,
            row_indices=violation_indices,
            violation_count=len(violations),
            sample_values=sample_bad_values,
            message=f"Found {len(violations)} values in column '{rule.column_name}' that are not in allowed categories",
        )


__all__ = ["GuardrailValidator"]

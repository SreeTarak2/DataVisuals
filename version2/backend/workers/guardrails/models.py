"""Data models for Auto-Data Guardrails"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class RuleType(str, Enum):
    NOT_NULL = "not_null"
    UNIQUE = "unique"
    PATTERN = "pattern"
    RANGE = "range"
    CATEGORICAL = "categorical"


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class GuardrailRule(BaseModel):
    """Defines a single data quality rule"""

    rule_id: str = Field(..., description="Unique identifier for the rule")
    column_name: str = Field(..., description="Target column name")
    rule_type: str = Field(
        ...,
        description="Type of validation (e.g., 'not_null', 'pattern', 'range', 'unique')",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Rule-specific parameters"
    )
    severity: str = Field(
        default="warning", description="Severity level: 'critical', 'warning', 'info'"
    )
    description: str = Field(..., description="Human-readable description of the rule")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(
        default=True, description="Whether the rule is currently enforced"
    )


class GuardrailViolation(BaseModel):
    """Represents a single rule violation"""

    rule_id: str = Field(..., description="ID of the violated rule")
    column_name: str = Field(..., description="Column where violation occurred")
    row_indices: List[int] = Field(
        default_factory=list, description="Sample row indices with violations (max 10)"
    )
    violation_count: int = Field(..., description="Total number of violations")
    sample_values: List[Any] = Field(
        default_factory=list, description="Sample violating values (max 5)"
    )
    message: str = Field(..., description="Human-readable violation message")


class GuardrailResult(BaseModel):
    """Result of guardrail validation"""

    dataset_id: str = Field(..., description="Dataset being validated")
    validation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_rules_checked: int = Field(..., description="Number of rules evaluated")
    total_violations: int = Field(..., description="Total violations found")
    passed: bool = Field(..., description="Whether all critical rules passed")
    violations: List[GuardrailViolation] = Field(
        default_factory=list, description="List of violations"
    )
    critical_violations: int = Field(
        default=0, description="Count of critical severity violations"
    )
    warning_violations: int = Field(
        default=0, description="Count of warning severity violations"
    )
    status: str = Field(
        default="pending",
        description="Validation status: 'passed', 'failed', 'quarantined'",
    )
    quarantine_reason: Optional[str] = Field(
        default=None, description="Reason for quarantine if failed"
    )


class QuarantineRecord(BaseModel):
    """Record of quarantined data"""

    id: str = Field(..., description="Unique identifier")
    dataset_id: str = Field(..., description="Dataset ID")
    row_indices: List[int] = Field(
        default_factory=list, description="Indices of quarantined rows"
    )
    reason: str = Field(..., description="Reason for quarantine")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = Field(default=False, description="Whether quarantine was resolved")
    resolution_notes: Optional[str] = Field(
        default=None, description="Notes about resolution"
    )


class GuardrailReport(BaseModel):
    """Comprehensive guardrail report"""

    result: GuardrailResult
    recommendations: List[str] = Field(default_factory=list)
    data_quality_impact: Dict[str, Any] = Field(default_factory=dict)
    export_format: str = Field(default="json")


__all__ = [
    "RuleType",
    "Severity",
    "GuardrailRule",
    "GuardrailViolation",
    "GuardrailResult",
    "QuarantineRecord",
    "GuardrailReport",
]

"""
Privacy Services
================
Comprehensive privacy and data protection services for DataSage.

Services:
- PII Detection: Automatically detect personally identifiable information
- Redaction: Safely redact sensitive data before LLM processing
- Privacy Settings: User-configurable privacy preferences
- Audit Logging: Compliance-ready event logging
"""

from .pii_detector import (
    PIIDetector,
    PIIType,
    PIIMatch,
    ColumnScanResult,
    DatasetScanResult,
    ConfidenceLevel,
    pii_detector,
)

from .redaction_service import (
    RedactionService,
    RedactionMode,
    RedactionResult,
    ColumnRedactionResult,
    DatasetRedactionResult,
    redaction_service,
)

from .privacy_settings_service import (
    PrivacySettingsService,
    GlobalPrivacySettings,
    DatasetPrivacySettings,
    UserPrivacySettings,
    DataRetentionPeriod,
    privacy_settings_service,
)

from .privacy_audit_service import (
    PrivacyAuditService,
    PrivacyEventType,
    PrivacyAuditEvent,
    privacy_audit_service,
)

__all__ = [
    # PII Detection
    "PIIDetector",
    "PIIType",
    "PIIMatch",
    "ColumnScanResult",
    "DatasetScanResult",
    "ConfidenceLevel",
    "pii_detector",
    # Redaction
    "RedactionService",
    "RedactionMode",
    "RedactionResult",
    "ColumnRedactionResult",
    "DatasetRedactionResult",
    "redaction_service",
    # Settings
    "PrivacySettingsService",
    "GlobalPrivacySettings",
    "DatasetPrivacySettings",
    "UserPrivacySettings",
    "DataRetentionPeriod",
    "privacy_settings_service",
    # Audit
    "PrivacyAuditService",
    "PrivacyEventType",
    "PrivacyAuditEvent",
    "privacy_audit_service",
]

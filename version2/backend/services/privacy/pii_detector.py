"""
PII Detection Service
====================
Automatically detects Personally Identifiable Information (PII) in datasets
to enable privacy-preserving data processing.

Patterns Detected:
- email: Email addresses
- phone: Phone numbers (various formats)
- ssn: Social Security Numbers
- credit_card: Credit card numbers
- name: Personal names (column headers + data patterns)
- address: Physical addresses
- ip_address: IP addresses
- password: Password-related fields

Confidence Thresholds:
- >90%: Auto-detect (high confidence)
- 60-90%: Flag for review (medium confidence)
- <60%: Skip detection (low confidence)
"""

import re
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class PIIType(Enum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    NAME = "name"
    ADDRESS = "address"
    IP_ADDRESS = "ip_address"
    PASSWORD = "password"
    DATE_OF_BIRTH = "date_of_birth"
    USER_ID = "user_id"
    UNKNOWN = "unknown"


class ConfidenceLevel(Enum):
    HIGH = "high"  # >90%
    MEDIUM = "medium"  # 60-90%
    LOW = "low"  # <60%


@dataclass
class PIIMatch:
    """Represents a PII match found in data."""

    pii_type: PIIType
    pattern: str
    confidence: float
    matched_values: List[str]
    column_name: Optional[str] = None
    match_count: int = 0

    @property
    def confidence_level(self) -> ConfidenceLevel:
        if self.confidence > 0.9:
            return ConfidenceLevel.HIGH
        elif self.confidence >= 0.6:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW


@dataclass
class ColumnScanResult:
    """Result of scanning a single column for PII."""

    column_name: str
    pii_type: Optional[PIIType]
    confidence: float
    sample_matches: List[str]
    should_redact: bool
    reason: str


@dataclass
class DatasetScanResult:
    """Complete result of scanning a dataset for PII."""

    dataset_id: str
    columns_scanned: int
    columns_with_pii: List[ColumnScanResult]
    total_pii_detections: int
    high_confidence_count: int
    medium_confidence_count: int
    scan_timestamp: str
    recommendations: List[str]


class PIIPatterns:
    """Regex patterns for PII detection."""

    # Email pattern (RFC 5322 simplified)
    EMAIL = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", re.IGNORECASE
    )

    # Phone patterns (various formats)
    PHONE_PATTERNS = [
        re.compile(r"^\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$"),  # US
        re.compile(r"^\+?44[-.\s]?\d{4}[-.\s]?\d{6}$"),  # UK
        re.compile(r"^\+?91[-.\s]?\d{5}[-.\s]?\d{5}$"),  # India
        re.compile(r"^\d{3}[-.\s]?\d{3}[-.\s]?\d{4}$"),  # Generic
    ]

    # SSN pattern (US)
    SSN = re.compile(r"^\d{3}[-\s]?\d{2}[-\s]?\d{4}$")

    # Credit card patterns (major brands)
    CREDIT_CARD = re.compile(
        r"^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|"
        r"3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12}|"
        r"(?:2131|1800|35\d{3})\d{11})$"
    )

    # IP Address patterns
    IP_V4 = re.compile(
        r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
        r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    )

    IP_V6 = re.compile(
        r"^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|"
        r"^(?:[0-9a-fA-F]{1,4}:){1,7}:$|"
        r"^(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}$"
    )

    # Sensitive column name patterns
    SENSITIVE_COLUMN_PATTERNS = {
        PIIType.EMAIL: [
            r"^email",
            r"^e[-_]?mail",
            r"^mail",
            r"^email[-_]?address",
            r"^correo",
            r"^courrier",
            r"contact[-_]?email",
        ],
        PIIType.PHONE: [
            r"^phone",
            r"^telephone",
            r"^tel$",
            r"^mobile",
            r"^cell",
            r"^fax",
            r"^contact[-_]?number",
            r"^phone[-_]?number",
        ],
        PIIType.SSN: [
            r"^ssn",
            r"^social[-_]?security",
            r"^national[-_]?id",
            r"^tax[-_]?id",
            r"^nino",
            r"^aadhaar",
            r"^sin$",
        ],
        PIIType.CREDIT_CARD: [
            r"^card[-_]?number",
            r"^credit[-_]?card",
            r"^cc[-_]?number",
            r"^card[-_]?no",
            r"^pan$",
            r"^account[-_]?number",
        ],
        PIIType.NAME: [
            r"^name",
            r"^first[-_]?name",
            r"^last[-_]?name",
            r"^full[-_]?name",
            r"^surname",
            r"^given[-_]?name",
            r"^customer[-_]?name",
            r"^client[-_]?name",
            r"^patient[-_]?name",
        ],
        PIIType.ADDRESS: [
            r"^address",
            r"^street",
            r"^city",
            r"^zip",
            r"^zip[-_]?code",
            r"^postal",
            r"^location",
            r"^residence",
            r"^home[-_]?address",
        ],
        PIIType.IP_ADDRESS: [
            r"^ip[-_]?address",
            r"^ip[-_]?addr",
            r"^ip$",
            r"^client[-_]?ip",
            r"^server[-_]?ip",
            r"^host[-_]?ip",
        ],
        PIIType.PASSWORD: [
            r"^password",
            r"^passwd",
            r"^pwd$",
            r"^secret",
            r"^api[-_]?key",
            r"^token$",
            r"^auth[-_]?token",
        ],
        PIIType.USER_ID: [
            r"^user[-_]?id",
            r"^customer[-_]?id",
            r"^client[-_]?id",
            r"^account[-_]?id",
            r"^uid$",
            r"^member[-_]?id",
        ],
        PIIType.DATE_OF_BIRTH: [
            r"^dob",
            r"^date[-_]?of[-_]?birth",
            r"^birth[-_]?date",
            r"^birthday",
            r"^born[-_]?on",
        ],
    }

    # Common first names for name detection
    COMMON_FIRST_NAMES = {
        "james",
        "john",
        "robert",
        "michael",
        "william",
        "david",
        "richard",
        "joseph",
        "thomas",
        "charles",
        "christopher",
        "daniel",
        "matthew",
        "anthony",
        "mark",
        "donald",
        "steven",
        "paul",
        "andrew",
        "joshua",
        "mary",
        "patricia",
        "jennifer",
        "linda",
        "elizabeth",
        "barbara",
        "susan",
        "jessica",
        "sarah",
        "karen",
        "lisa",
        "nancy",
        "betty",
        "helen",
        "sandra",
        "donna",
        "carol",
        "ruth",
        "sharon",
        "michelle",
        "alex",
        "sam",
        "chris",
        "taylor",
        "jordan",
        "morgan",
        "casey",
    }


class PIIDetector:
    """
    Main PII detection service.

    Scans dataset columns and values for personally identifiable information.
    Returns detection results with confidence scores for privacy decisions.
    """

    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.9
    MEDIUM_CONFIDENCE_THRESHOLD = 0.6

    def __init__(self):
        self.patterns = PIIPatterns()

    def scan_column_name(self, column_name: str) -> Optional[PIIMatch]:
        """
        Scan a column name for PII indicators.

        Args:
            column_name: Name of the column to scan

        Returns:
            PIIMatch if PII detected, None otherwise
        """
        col_lower = column_name.lower().strip()

        for pii_type, patterns in self.patterns.SENSITIVE_COLUMN_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, col_lower):
                    return PIIMatch(
                        pii_type=pii_type,
                        pattern=pattern,
                        confidence=0.95,  # Column name match = high confidence
                        matched_values=[column_name],
                        column_name=column_name,
                    )

        return None

    def detect_pii_type(self, value: str) -> Optional[PIIType]:
        """
        Detect the type of PII in a string value.

        Args:
            value: String value to analyze

        Returns:
            Detected PIIType or None
        """
        if not value or not isinstance(value, str):
            return None

        value = value.strip()

        # Check email
        if self.patterns.EMAIL.match(value):
            return PIIType.EMAIL

        # Check phone
        for pattern in self.patterns.PHONE_PATTERNS:
            if pattern.match(value):
                return PIIType.PHONE

        # Check SSN
        if (
            self.patterns.SSN.match(value)
            and len(value.replace("-", "").replace(" ", "")) == 9
        ):
            return PIIType.SSN

        # Check credit card (Luhn validation)
        if self.patterns.CREDIT_CARD.match(value.replace("-", "").replace(" ", "")):
            if self._luhn_check(value):
                return PIIType.CREDIT_CARD

        # Check IP addresses
        if self.patterns.IP_V4.match(value):
            return PIIType.IP_ADDRESS
        if self.patterns.IP_V6.match(value):
            return PIIType.IP_ADDRESS

        # Check for common names
        if value.lower() in self.patterns.COMMON_FIRST_NAMES:
            return PIIType.NAME

        return None

    def scan_column_values(
        self, column_name: str, values: List[str], sample_size: int = 100
    ) -> ColumnScanResult:
        """
        Scan a column's values for PII.

        Args:
            column_name: Name of the column
            values: List of values in the column
            sample_size: Number of values to sample

        Returns:
            ColumnScanResult with detection details
        """
        if not values:
            return ColumnScanResult(
                column_name=column_name,
                pii_type=None,
                confidence=0.0,
                sample_matches=[],
                should_redact=False,
                reason="No values to scan",
            )

        # Sample values if necessary
        sample = values[: min(sample_size, len(values))]
        sample = [str(v) for v in sample if v is not None and str(v).strip()]

        if not sample:
            return ColumnScanResult(
                column_name=column_name,
                pii_type=None,
                confidence=0.0,
                sample_matches=[],
                should_redact=False,
                reason="No non-null values to scan",
            )

        # Check column name first
        col_match = self.scan_column_name(column_name)

        # Detect PII types in values
        pii_types_detected: Dict[PIIType, int] = {}
        sample_matches: List[str] = []

        for value in sample:
            pii_type = self.detect_pii_type(value)
            if pii_type:
                pii_types_detected[pii_type] = pii_types_detected.get(pii_type, 0) + 1
                if len(sample_matches) < 5:  # Keep up to 5 sample matches
                    sample_matches.append(value)

        # Calculate detection rate and confidence
        if pii_types_detected:
            # Primary PII type is the one with most matches
            primary_type = max(pii_types_detected, key=pii_types_detected.get)
            detection_rate = pii_types_detected[primary_type] / len(sample)

            # Confidence based on detection rate
            confidence = min(detection_rate * 1.2, 1.0)  # Boost slightly

            # If column name also matched, increase confidence
            if col_match and col_match.pii_type == primary_type:
                confidence = min(confidence + 0.1, 1.0)

            should_redact = confidence >= self.MEDIUM_CONFIDENCE_THRESHOLD

            return ColumnScanResult(
                column_name=column_name,
                pii_type=primary_type,
                confidence=round(confidence, 3),
                sample_matches=sample_matches,
                should_redact=should_redact,
                reason=f"Detected {primary_type.value} in {detection_rate * 100:.1f}% of sample",
            )

        # Check if column name suggests PII even if values don't match patterns
        if col_match:
            return ColumnScanResult(
                column_name=column_name,
                pii_type=col_match.pii_type,
                confidence=col_match.confidence,
                sample_matches=sample_matches,
                should_redact=col_match.confidence >= self.HIGH_CONFIDENCE_THRESHOLD,
                reason=f"Column name indicates {col_match.pii_type.value} (values do not match pattern)",
            )

        return ColumnScanResult(
            column_name=column_name,
            pii_type=None,
            confidence=0.0,
            sample_matches=[],
            should_redact=False,
            reason="No PII detected",
        )

    def scan_dataset(
        self,
        dataset_id: str,
        columns: List[str],
        data: Dict[str, List[Any]],
        sample_size: int = 100,
    ) -> DatasetScanResult:
        """
        Scan an entire dataset for PII.

        Args:
            dataset_id: Unique identifier for the dataset
            columns: List of column names
            data: Dictionary mapping column names to value lists
            sample_size: Number of rows to sample per column

        Returns:
            DatasetScanResult with complete scan results
        """
        from datetime import datetime

        columns_with_pii: List[ColumnScanResult] = []

        for col in columns:
            if col in data:
                values = data[col]
                result = self.scan_column_values(col, values, sample_size)
                if result.pii_type:
                    columns_with_pii.append(result)

        high_count = sum(
            1
            for c in columns_with_pii
            if c.confidence >= self.HIGH_CONFIDENCE_THRESHOLD
        )
        medium_count = sum(
            1
            for c in columns_with_pii
            if self.MEDIUM_CONFIDENCE_THRESHOLD
            <= c.confidence
            < self.HIGH_CONFIDENCE_THRESHOLD
        )

        # Generate recommendations
        recommendations = []
        if high_count > 0:
            recommendations.append(
                f"{high_count} column(s) detected with high-confidence PII - consider auto-redaction"
            )
        if medium_count > 0:
            recommendations.append(
                f"{medium_count} column(s) detected with medium-confidence PII - review recommended"
            )
        if high_count + medium_count == 0:
            recommendations.append(
                "No PII detected - data appears safe to share with AI"
            )

        return DatasetScanResult(
            dataset_id=dataset_id,
            columns_scanned=len(columns),
            columns_with_pii=columns_with_pii,
            total_pii_detections=len(columns_with_pii),
            high_confidence_count=high_count,
            medium_confidence_count=medium_count,
            scan_timestamp=datetime.utcnow().isoformat(),
            recommendations=recommendations,
        )

    def _luhn_check(self, card_number: str) -> bool:
        """
        Validate credit card number using Luhn algorithm.

        Args:
            card_number: Card number to validate

        Returns:
            True if valid, False otherwise
        """
        # Remove non-digits
        digits = re.sub(r"\D", "", card_number)

        if not digits:
            return False

        total = 0
        reverse_digits = digits[::-1]

        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n

        return total % 10 == 0

    def get_redaction_candidates(
        self, scan_result: DatasetScanResult, auto_redact_threshold: float = 0.9
    ) -> List[Dict[str, Any]]:
        """
        Get list of columns that should be auto-redacted.

        Args:
            scan_result: Result from scan_dataset
            auto_redact_threshold: Minimum confidence for auto-redaction

        Returns:
            List of column redaction candidates with details
        """
        candidates = []

        for col_result in scan_result.columns_with_pii:
            if col_result.confidence >= auto_redact_threshold:
                candidates.append(
                    {
                        "column_name": col_result.column_name,
                        "pii_type": col_result.pii_type.value,
                        "confidence": col_result.confidence,
                        "sample_matches": col_result.sample_matches[
                            :3
                        ],  # First 3 samples
                        "action": "auto_redact",
                        "reason": col_result.reason,
                    }
                )
            elif col_result.confidence >= self.MEDIUM_CONFIDENCE_THRESHOLD:
                candidates.append(
                    {
                        "column_name": col_result.column_name,
                        "pii_type": col_result.pii_type.value,
                        "confidence": col_result.confidence,
                        "sample_matches": col_result.sample_matches[:3],
                        "action": "review",
                        "reason": col_result.reason,
                    }
                )

        return candidates


# Singleton instance
pii_detector = PIIDetector()

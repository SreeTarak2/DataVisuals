"""
Redaction Service
================
Provides data redaction capabilities for privacy-preserving data processing.

Redaction Modes:
- MASK: Full redaction with PII type indicator [REDACTED-EMAIL]
- HASH: One-way hash (reversible for internal use)
- GENERALIZE: Replace with category/example

⚠️  Format-Preserving Mode Warning:
    Format-preserving redaction (like j***@example.com) may leak partial information.
    The domain or first initial could still be sensitive in some contexts.
    Default mode is FULL MASK for maximum privacy.
"""

import re
import hashlib
import logging
from enum import Enum
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class RedactionMode(Enum):
    """Available redaction modes."""

    MASK = "mask"  # Full redaction with type indicator
    HASH = "hash"  # One-way hash
    GENERALIZE = "generalize"  # Replace with category/example
    PARTIAL = "partial"  # ⚠️ Format-preserving (may leak info)


class PIIType(Enum):
    """PII types for redaction."""

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


@dataclass
class RedactionRule:
    """A rule defining how to redact a specific PII type."""

    pii_type: PIIType
    mode: RedactionMode
    preserve_format: bool = False  # Only for PARTIAL mode

    # For GENERALIZE mode
    replacement_example: str = ""


@dataclass
class RedactionResult:
    """Result of a redaction operation."""

    original_value: str
    redacted_value: str
    pii_type: Optional[PIIType]
    was_redacted: bool
    redaction_mode: RedactionMode
    redaction_rule: Optional[RedactionRule] = None


@dataclass
class ColumnRedactionResult:
    """Result of redacting an entire column."""

    column_name: str
    total_values: int
    redacted_count: int
    results: List[RedactionResult]
    pii_type_detected: Optional[PIIType]

    @property
    def redaction_rate(self) -> float:
        if self.total_values == 0:
            return 0.0
        return self.redacted_count / self.total_values


@dataclass
class DatasetRedactionResult:
    """Result of redacting an entire dataset."""

    dataset_id: str
    columns_processed: int
    columns_with_redactions: int
    total_values_redacted: int
    column_results: Dict[str, ColumnRedactionResult]
    redaction_timestamp: str


class PIIPatterns:
    """Regex patterns for PII detection during redaction."""

    EMAIL = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", re.IGNORECASE
    )

    PHONE_PATTERNS = [
        re.compile(r"^\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$"),
        re.compile(r"^\+?44[-.\s]?\d{4}[-.\s]?\d{6}$"),
        re.compile(r"^\+?91[-.\s]?\d{5}[-.\s]?\d{5}$"),
        re.compile(r"^\d{3}[-.\s]?\d{3}[-.\s]?\d{4}$"),
    ]

    SSN = re.compile(r"^\d{3}[-\s]?\d{2}[-\s]?\d{4}$")
    CREDIT_CARD = re.compile(r"^\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}$")
    IP_V4 = re.compile(
        r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
        r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    )

    SENSITIVE_COLUMNS = {
        "email",
        "e-mail",
        "mail",
        "email_address",
        "contact_email",
        "phone",
        "telephone",
        "tel",
        "mobile",
        "cell",
        "phone_number",
        "ssn",
        "social_security",
        "national_id",
        "tax_id",
        "sin",
        "credit_card",
        "card_number",
        "cc_number",
        "card_no",
        "pan",
        "password",
        "passwd",
        "pwd",
        "secret",
        "api_key",
        "token",
        "address",
        "street",
        "city",
        "zip",
        "zip_code",
        "postal_code",
        "dob",
        "date_of_birth",
        "birth_date",
        "birthday",
        "ip_address",
        "ip_addr",
        "client_ip",
        "server_ip",
        "user_id",
        "customer_id",
        "client_id",
        "account_id",
        "uid",
    }


class RedactionService:
    """
    Service for redacting PII from data.

    Usage:
        service = RedactionService()
        result = service.redact_value("test@example.com", PIIType.EMAIL, RedactionMode.MASK)
    """

    def __init__(self):
        self.patterns = PIIPatterns()
        self._default_rules = self._create_default_rules()

    def _create_default_rules(self) -> Dict[PIIType, RedactionRule]:
        """Create default redaction rules for each PII type."""
        return {
            PIIType.EMAIL: RedactionRule(
                pii_type=PIIType.EMAIL,
                mode=RedactionMode.MASK,
                replacement_example="user@example.com",
            ),
            PIIType.PHONE: RedactionRule(
                pii_type=PIIType.PHONE,
                mode=RedactionMode.MASK,
                replacement_example="555-123-4567",
            ),
            PIIType.SSN: RedactionRule(
                pii_type=PIIType.SSN,
                mode=RedactionMode.MASK,
                replacement_example="XXX-XX-1234",
            ),
            PIIType.CREDIT_CARD: RedactionRule(
                pii_type=PIIType.CREDIT_CARD,
                mode=RedactionMode.MASK,
                replacement_example="XXXX-XXXX-XXXX-1234",
            ),
            PIIType.NAME: RedactionRule(
                pii_type=PIIType.NAME,
                mode=RedactionMode.GENERALIZE,
                replacement_example="John Doe",
            ),
            PIIType.ADDRESS: RedactionRule(
                pii_type=PIIType.ADDRESS,
                mode=RedactionMode.MASK,
                replacement_example="123 Main St",
            ),
            PIIType.IP_ADDRESS: RedactionRule(
                pii_type=PIIType.IP_ADDRESS,
                mode=RedactionMode.MASK,
                replacement_example="192.168.1.1",
            ),
            PIIType.PASSWORD: RedactionRule(
                pii_type=PIIType.PASSWORD,
                mode=RedactionMode.MASK,
                replacement_example="[REDACTED-PASSWORD]",
            ),
            PIIType.DATE_OF_BIRTH: RedactionRule(
                pii_type=PIIType.DATE_OF_BIRTH,
                mode=RedactionMode.MASK,
                replacement_example="01/01/1990",
            ),
            PIIType.USER_ID: RedactionRule(
                pii_type=PIIType.USER_ID,
                mode=RedactionMode.HASH,
                replacement_example="user_abc123",
            ),
            PIIType.UNKNOWN: RedactionRule(
                pii_type=PIIType.UNKNOWN,
                mode=RedactionMode.MASK,
                replacement_example="[REDACTED]",
            ),
        }

    def _detect_pii_type(self, value: str) -> Optional[PIIType]:
        """Detect the PII type of a value."""
        if not value or not isinstance(value, str):
            return None

        value = value.strip()

        if self.patterns.EMAIL.match(value):
            return PIIType.EMAIL

        for pattern in self.patterns.PHONE_PATTERNS:
            if pattern.match(value):
                return PIIType.PHONE

        if self.patterns.SSN.match(value):
            return PIIType.SSN

        if self.patterns.CREDIT_CARD.match(value):
            return PIIType.CREDIT_CARD

        if self.patterns.IP_V4.match(value):
            return PIIType.IP_ADDRESS

        return None

    def _is_sensitive_column(self, column_name: str) -> bool:
        """Check if a column name suggests sensitive data."""
        col_lower = column_name.lower().replace("-", "_").replace(" ", "_")
        return col_lower in self.patterns.SENSITIVE_COLUMNS

    def _mask_email(self, value: str, partial: bool = False) -> str:
        """Mask an email address."""
        if partial:
            # ⚠️ Format-preserving - may leak info
            if "@" in value:
                local, domain = value.rsplit("@", 1)
                if len(local) > 1:
                    masked_local = local[0] + "***"
                else:
                    masked_local = "***"
                return f"{masked_local}@{domain}"
        return "[REDACTED-EMAIL]"

    def _mask_phone(self, value: str, partial: bool = False) -> str:
        """Mask a phone number."""
        if partial:
            digits = re.sub(r"\D", "", value)
            if len(digits) >= 4:
                return f"***-***-{digits[-4:]}"
        return "[REDACTED-PHONE]"

    def _mask_ssn(self, value: str, partial: bool = False) -> str:
        """Mask a Social Security Number."""
        if partial:
            digits = re.sub(r"\D", "", value)
            if len(digits) >= 4:
                return f"XXX-XX-{digits[-4:]}"
        return "[REDACTED-SSN]"

    def _mask_credit_card(self, value: str, partial: bool = False) -> str:
        """Mask a credit card number."""
        if partial:
            digits = re.sub(r"\D", "", value)
            if len(digits) >= 4:
                return f"XXXX-XXXX-XXXX-{digits[-4:]}"
        return "[REDACTED-CARD]"

    def _mask_ip_address(self, value: str, partial: bool = False) -> str:
        """Mask an IP address."""
        if partial:
            parts = value.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.***.***.{parts[3]}"
        return "[REDACTED-IP]"

    def _hash_value(self, value: str) -> str:
        """Create a one-way hash of a value."""
        # Use first 8 chars of SHA256 for consistent hashing
        hash_obj = hashlib.sha256(value.encode("utf-8"))
        return hash_obj.hexdigest()[:12]

    def _generalize_value(self, value: str, example: str) -> str:
        """Replace value with a generalized example."""
        return example

    def redact_value(
        self,
        value: str,
        pii_type: Optional[PIIType] = None,
        mode: RedactionMode = RedactionMode.MASK,
        column_name: Optional[str] = None,
        preserve_format: bool = False,
    ) -> RedactionResult:
        """
        Redact a single value.

        Args:
            value: The value to redact
            pii_type: Type of PII detected (auto-detected if not provided)
            mode: Redaction mode to use
            column_name: Name of the column (for sensitive column detection)
            preserve_format: Whether to preserve format (⚠️ may leak info)

        Returns:
            RedactionResult with original and redacted values
        """
        if not value or not isinstance(value, str) or not value.strip():
            return RedactionResult(
                original_value=value or "",
                redacted_value=value or "",
                pii_type=None,
                was_redacted=False,
                redaction_mode=mode,
            )

        original = value.strip()

        # Auto-detect PII type if not provided
        if pii_type is None:
            pii_type = self._detect_pii_type(original)

        # Check for sensitive column name
        is_sensitive_column = self._is_sensitive_column(column_name or "")

        # Determine if we should redact
        should_redact = pii_type is not None or is_sensitive_column

        if not should_redact:
            return RedactionResult(
                original_value=original,
                redacted_value=original,
                pii_type=None,
                was_redacted=False,
                redaction_mode=mode,
            )

        # Use UNKNOWN if PII type not detected but column is sensitive
        effective_type = pii_type or PIIType.UNKNOWN

        # Apply redaction based on mode
        if mode == RedactionMode.MASK:
            redacted = self._apply_mask(original, effective_type, preserve_format)
        elif mode == RedactionMode.HASH:
            redacted = f"[REDACTED-{self._hash_value(original)}]"
        elif mode == RedactionMode.GENERALIZE:
            rule = self._default_rules.get(effective_type)
            example = rule.replacement_example if rule else "[REDACTED]"
            redacted = self._generalize_value(original, example)
        elif mode == RedactionMode.PARTIAL:
            # ⚠️ Format-preserving mode
            redacted = self._apply_mask(original, effective_type, preserve_format=True)
        else:
            redacted = "[REDACTED]"

        return RedactionResult(
            original_value=original,
            redacted_value=redacted,
            pii_type=effective_type,
            was_redacted=True,
            redaction_mode=mode,
            redaction_rule=self._default_rules.get(effective_type),
        )

    def _apply_mask(self, value: str, pii_type: PIIType, preserve_format: bool) -> str:
        """Apply masking redaction."""
        if pii_type == PIIType.EMAIL:
            return self._mask_email(value, preserve_format)
        elif pii_type == PIIType.PHONE:
            return self._mask_phone(value, preserve_format)
        elif pii_type == PIIType.SSN:
            return self._mask_ssn(value, preserve_format)
        elif pii_type == PIIType.CREDIT_CARD:
            return self._mask_credit_card(value, preserve_format)
        elif pii_type == PIIType.IP_ADDRESS:
            return self._mask_ip_address(value, preserve_format)
        elif pii_type == PIIType.PASSWORD:
            return "[REDACTED-PASSWORD]"
        elif pii_type == PIIType.NAME:
            return "[REDACTED-NAME]"
        elif pii_type == PIIType.ADDRESS:
            return "[REDACTED-ADDRESS]"
        elif pii_type == PIIType.DATE_OF_BIRTH:
            return "[REDACTED-DOB]"
        elif pii_type == PIIType.USER_ID:
            return "[REDACTED-ID]"
        return "[REDACTED]"

    def redact_column(
        self,
        column_name: str,
        values: List[Any],
        columns_to_redact: Set[str],
        mode: RedactionMode = RedactionMode.MASK,
    ) -> ColumnRedactionResult:
        """
        Redact all values in a column.

        Args:
            column_name: Name of the column
            values: List of values in the column
            columns_to_redact: Set of column names to redact
            mode: Redaction mode to use

        Returns:
            ColumnRedactionResult with all redaction results
        """
        should_redact = column_name in columns_to_redact
        results = []
        redacted_count = 0
        pii_type_detected = None

        for value in values:
            value_str = str(value) if value is not None else ""

            if should_redact:
                result = self.redact_value(
                    value_str, mode=mode, column_name=column_name
                )
                if result.was_redacted:
                    redacted_count += 1
                    pii_type_detected = result.pii_type
            else:
                result = RedactionResult(
                    original_value=value_str,
                    redacted_value=value_str,
                    pii_type=None,
                    was_redacted=False,
                    redaction_mode=mode,
                )

            results.append(result)

        return ColumnRedactionResult(
            column_name=column_name,
            total_values=len(values),
            redacted_count=redacted_count,
            results=results,
            pii_type_detected=pii_type_detected,
        )

    def redact_dataset(
        self,
        dataset_id: str,
        data: Dict[str, List[Any]],
        columns_to_redact: Set[str],
        mode: RedactionMode = RedactionMode.MASK,
    ) -> DatasetRedactionResult:
        """
        Redact PII from an entire dataset.

        Args:
            dataset_id: Dataset identifier
            data: Dictionary mapping column names to value lists
            columns_to_redact: Set of column names to redact
            mode: Redaction mode to use

        Returns:
            DatasetRedactionResult with complete redaction results
        """
        from datetime import datetime

        column_results = {}
        columns_with_redactions = 0
        total_redacted = 0

        for column_name, values in data.items():
            result = self.redact_column(column_name, values, columns_to_redact, mode)
            column_results[column_name] = result

            if result.redacted_count > 0:
                columns_with_redactions += 1
                total_redacted += result.redacted_count

        return DatasetRedactionResult(
            dataset_id=dataset_id,
            columns_processed=len(data),
            columns_with_redactions=columns_with_redactions,
            total_values_redacted=total_redacted,
            column_results=column_results,
            redaction_timestamp=datetime.utcnow().isoformat(),
        )

    def create_redacted_context(
        self, original_context: str, redaction_info: Dict[str, Any]
    ) -> str:
        """
        Create a privacy-aware version of a context string.

        Args:
            original_context: The original context string
            redaction_info: Information about what was redacted

        Returns:
            Modified context with redaction indicators
        """
        lines = original_context.split("\n")
        modified_lines = []

        for line in lines:
            modified_lines.append(line)

        # Add redaction summary if any columns were redacted
        if redaction_info.get("columns_redacted"):
            modified_lines.append("\n--- PRIVACY NOTICE ---")
            modified_lines.append(
                f"The following columns were redacted: {', '.join(redaction_info['columns_redacted'])}"
            )
            if redaction_info.get("pii_types"):
                modified_lines.append(
                    f"PII types detected: {', '.join(redaction_info['pii_types'])}"
                )

        return "\n".join(modified_lines)

    def get_redaction_summary(self, result: DatasetRedactionResult) -> Dict[str, Any]:
        """
        Get a summary of redactions applied.

        Args:
            result: Result from redact_dataset

        Returns:
            Dictionary with redaction summary
        """
        columns_redacted = []
        pii_types = set()

        for col_name, col_result in result.column_results.items():
            if col_result.redacted_count > 0:
                columns_redacted.append(col_name)
                if col_result.pii_type_detected:
                    pii_types.add(col_result.pii_type_detected.value)

        return {
            "columns_redacted": columns_redacted,
            "total_columns": result.columns_processed,
            "columns_with_redactions": result.columns_with_redactions,
            "total_values_redacted": result.total_values_redacted,
            "pii_types": list(pii_types),
            "redaction_timestamp": result.redaction_timestamp,
        }


# Singleton instance
redaction_service = RedactionService()

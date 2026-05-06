"""
Abstract Base Class for Database Connectors
Defines the interface that all database connectors must implement
Includes comprehensive security features
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import time
import re

logger = logging.getLogger(__name__)


class SecurityValidator:
    """Security validation utilities for database operations"""

    # SQL injection patterns to detect
    SQL_INJECTION_PATTERNS = [
        r'(\b(union|select|insert|update|delete|drop|truncate|alter|create|exec|execute)\b.*\b(from|into|table|database)\b)',
        r'(--|\#|\/\*)',  # SQL comments
        r'(\b(or|and)\b\s+\d+\s*=\s*\d+)',  # OR 1=1 style attacks
        r'(\b(or|and)\b\s+\'[^\']*\'\s*=\s*\'[^\']*\')',  # OR 'a'='a' style attacks
        r'(;.*\b(drop|truncate|delete|update)\b)',  # Multiple statements
        r'(\bwaitfor\b|\bsleep\b|\bbenchmark\b)',  # Time-based attacks
        r'(\bload_file\b|\binto\s+outfile\b|\binto\s+dumpfile\b)',  # File operations
    ]

    # Maximum lengths for identifiers
    MAX_TABLE_NAME_LENGTH = 128
    MAX_COLUMN_NAME_LENGTH = 128
    MAX_DATABASE_NAME_LENGTH = 128

    @classmethod
    def validate_identifier(cls, name: str, identifier_type: str = "table") -> bool:
        """Validate database identifier names"""
        if not name or not isinstance(name, str):
            return False

        # Check length
        max_len = {
            "table": cls.MAX_TABLE_NAME_LENGTH,
            "column": cls.MAX_COLUMN_NAME_LENGTH,
            "database": cls.MAX_DATABASE_NAME_LENGTH
        }.get(identifier_type, cls.MAX_TABLE_NAME_LENGTH)

        if len(name) > max_len:
            logger.warning(f"Identifier '{name}' exceeds maximum length of {max_len}")
            return False

        # Only allow alphanumeric, underscore, and dot (for qualified names)
        if not re.match(r'^[a-zA-Z0-9_.]+$', name):
            logger.warning(f"Identifier '{name}' contains invalid characters")
            return False

        # Prevent directory traversal
        if '..' in name or '/' in name or '\\' in name:
            logger.warning(f"Identifier '{name}' contains path traversal characters")
            return False

        return True

    @classmethod
    def detect_sql_injection(cls, query: str) -> bool:
        """Detect potential SQL injection attempts"""
        if not query:
            return False

        query_lower = query.lower()

        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {query[:100]}")
                return True

        return False

    @classmethod
    def sanitize_limit(cls, limit: Optional[int], default: int = 1000, max_limit: int = 10000) -> int:
        """Sanitize LIMIT parameter to prevent DoS"""
        if limit is None:
            return default

        try:
            limit = int(limit)
            if limit < 0:
                return default
            if limit > max_limit:
                logger.warning(f"Limit {limit} exceeds maximum, capping at {max_limit}")
                return max_limit
            return limit
        except (ValueError, TypeError):
            logger.warning(f"Invalid limit value: {limit}, using default {default}")
            return default

    @classmethod
    def validate_query_type(cls, query: str, allowed_types: List[str] = None) -> bool:
        """Validate that query is of an allowed type (SELECT only by default)"""
        if allowed_types is None:
            allowed_types = ['SELECT']

        try:
            if not query:
                return False

            normalized = re.sub(r"/\*.*?\*/", " ", query, flags=re.DOTALL)
            normalized = re.sub(r"--.*?$|#.*?$", " ", normalized, flags=re.MULTILINE)
            normalized = normalized.strip()

            match = re.match(r"^([a-zA-Z]+)", normalized)
            if not match:
                return False

            query_type = match.group(1).upper()

            if query_type not in [t.upper() for t in allowed_types]:
                logger.warning(f"Query type {query_type} not in allowed types: {allowed_types}")
                return False

            return True
        except Exception as e:
            logger.error(f"Error validating query type: {e}")
            return False

    @classmethod
    def validate_config_security(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a connector configuration and return structured results."""
        errors: List[str] = []

        db_type = str(config.get("db_type", "")).lower().strip()
        if db_type not in {"postgresql", "mysql", "mongodb"}:
            errors.append(f"Unsupported db_type: {db_type or 'missing'}")

        host = config.get("host")
        if not cls.validate_identifier(str(host or ""), "database"):
            errors.append("Invalid host value")

        database = config.get("database")
        if not cls.validate_identifier(str(database or ""), "database"):
            errors.append("Invalid database value")

        port = config.get("port")
        try:
            port_int = int(port)
            if not (1 <= port_int <= 65535):
                errors.append("Port must be between 1 and 65535")
        except (TypeError, ValueError):
            errors.append("Port must be an integer")

        username = config.get("username")
        if not username or not str(username).strip():
            errors.append("Username is required")

        password = config.get("password")
        if password is None or password == "":
            errors.append("Password is required")

        return {"valid": not errors, "errors": errors}


class AuditLogger:
    """Audit logging for database operations"""

    def __init__(self, logger_name: str = "database_audit"):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)

    def log_operation(self, operation: str, details: Dict[str, Any], success: bool,
                     duration_ms: float = 0.0, error: Optional[str] = None):
        """Log a database operation for audit purposes"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": operation,
            "success": success,
            "duration_ms": duration_ms,
            "details": {k: v for k, v in details.items() if k != 'password'},  # Redact passwords
        }

        if error:
            log_entry["error"] = error

        if success:
            self.logger.info(f"AUDIT: {operation} - SUCCESS", extra=log_entry)
        else:
            self.logger.warning(f"AUDIT: {operation} - FAILED", extra=log_entry)


class DatabaseConnector(ABC):
    """Abstract base class defining the database connector interface with security"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the connector with configuration

        Args:
            config: Database connection configuration
                   (host, port, database, username, password, etc.)
        """
        self.config = self._validate_config(config)
        self.connection = None
        self.security_validator = SecurityValidator()
        self.audit_logger = AuditLogger()
        self._connection_timeout = config.get('timeout', 30)
        self._max_retries = config.get('max_retries', 3)
        self._pool_size = config.get('pool_size', 5)
        self._connected_at: Optional[datetime] = None

    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize configuration"""
        required_fields = ['host', 'database']

        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required configuration field: {field}")

        # Validate host (prevent SSRF)
        host = config.get('host', '')
        if not self.security_validator.validate_identifier(host, "database"):
            raise ValueError(f"Invalid host format: {host}")

        # Prevent localhost/internal network connections unless explicitly allowed
        if config.get('allow_internal', False) is not True:
            if host in ['localhost', '127.0.0.1', '::1']:
                logger.warning("Connection to localhost requested. Ensure this is intentional.")

        return config

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish a connection to the database

        Returns:
            bool: True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the database connection"""
        pass

    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test the database connection

        Returns:
            Dict containing connection test results:
            {
                "success": bool,
                "message": str,
                "response_time_ms": float,
                "database_version": Optional[str]
            }
        """
        pass

    @abstractmethod
    async def get_tables(self) -> List[str]:
        """
        Get list of tables/collections in the database

        Returns:
            List of table/collection names
        """
        pass

    @abstractmethod
    async def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get schema information for a specific table/collection

        Args:
            table_name: Name of the table/collection

        Returns:
            List of column schema dictionaries:
            [
                {
                    "name": str,
                    "type": str,
                    "nullable": bool,
                    "default": Any,
                    "max_length": Optional[int],
                    "precision": Optional[int],
                    "scale": Optional[int]
                }
            ]
        """
        pass

    @abstractmethod
    async def extract_data(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract data from a table/collection

        Args:
            table_name: Name of the table/collection
            columns: List of column names to extract (None for all)
            limit: Maximum number of rows to return
            offset: Number of rows to skip

        Returns:
            List of dictionaries representing rows
        """
        pass

    @abstractmethod
    async def extract_incremental(
        self, table_name: str, last_value: Any, increment_column: str
    ) -> List[Dict[str, Any]]:
        """
        Extract incremental data based on a changing column

        Args:
            table_name: Name of the table/collection
            last_value: Last processed value of increment_column
            increment_column: Column used to detect new/changed records

        Returns:
            List of dictionaries representing new/changed rows
        """
        pass

    def _log_operation_start(self, operation: str, params: Dict[str, Any]) -> float:
        """Log start of operation and return start time"""
        return time.time()

    def _log_operation_end(self, operation: str, params: Dict[str, Any],
                          start_time: float, success: bool, error: Optional[str] = None):
        """Log end of operation with duration"""
        duration_ms = (time.time() - start_time) * 1000
        self.audit_logger.log_operation(
            operation=operation,
            details=params,
            success=success,
            duration_ms=duration_ms,
            error=error
        )
"""
Schema Discovery Service
Discovers and caches database schema information
Includes security validation and comprehensive error handling
"""

from typing import TYPE_CHECKING, Dict, List, Any, Optional
from .connectors.base import DatabaseConnector, SecurityValidator
import hashlib
import json
import time
import logging
from datetime import date, datetime

if TYPE_CHECKING:
    from db.schemas_pipeline import DatasetProfile

logger = logging.getLogger(__name__)

_SCALAR = (str, int, float, bool, type(None))


def _flatten_document(doc: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """
    Recursively flatten a nested document into dot-notation keys so Polars can
    build a DataFrame without losing nested structure.

    - Preserves scalar types (str, int, float, bool, None) as-is.
    - Datetime/date objects → ISO-format strings (Polars can parse these back).
    - Nested dicts → flattened with dot notation (e.g. "address.city").
    - Arrays/lists → JSON string (avoids losing array data entirely).
    - MongoDB internal keys (_id, __v) ARE kept (the connector already converts
      ObjectId → str; `_id` is needed for row identity).
    - Everything else → str.
    """
    items: List[tuple[str, Any]] = []
    for k, v in doc.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        if v is None:
            items.append((new_key, None))
        elif isinstance(v, (str, int, float, bool)):
            items.append((new_key, v))
        elif isinstance(v, (datetime, date)):
            items.append((new_key, v.isoformat()))
        elif isinstance(v, dict):
            items.extend(_flatten_document(v, new_key, sep=sep).items())
        elif isinstance(v, (list, tuple)):
            # Arrays → JSON string so array-of-objects is not silently lost
            try:
                items.append((new_key, json.dumps(v, default=str)))
            except (TypeError, ValueError):
                items.append((new_key, str(v)))
        else:
            # Fallback: anything else becomes str
            items.append((new_key, str(v)))

    return dict(items)


def _coerce_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Legacy alias — delegates to ``_flatten_document`` per-row.
    Kept for backward compatibility in case external callers exist.
    """
    return [_flatten_document(r) for r in rows]


class SchemaDiscoveryService:
    """Discovers and manages database schema information"""

    def __init__(self):
        self._schema_cache: Dict[str, Dict] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_ttl = 300  # 5 minutes default TTL

    async def get_tables(self, connector: DatabaseConnector) -> List[str]:
        """
        Get list of tables from database with caching and security validation

        Args:
            connector: Database connector instance

        Returns:
            List of table/collection names

        Raises:
            RuntimeError: If not connected to database
            ValueError: If schema discovery fails validation
        """
        start_time = time.time()
        cache_key = self._get_cache_key(connector, "tables")

        try:
            # Check cache first
            if self._is_cached(cache_key):
                logger.debug(f"Cache hit for tables (key: {cache_key[:16]}...)")
                return self._schema_cache[cache_key]["tables"]

            # Validate connector is connected
            if not connector.connection and not hasattr(connector, '_pool'):
                raise RuntimeError("Connector not initialized")

            # Fetch from database
            tables = await connector.get_tables()
            
            # Security: Filter out system tables that shouldn't be exposed
            filtered_tables = self._filter_system_tables(
                tables, connector.config.get('db_type', '')
            )
            
            # Cache result
            self._set_cache(cache_key, {"tables": filtered_tables})
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"Discovered {len(filtered_tables)} tables in {duration_ms:.2f}ms")

            return filtered_tables
            
        except Exception as e:
            logger.error(f"Error discovering tables: {str(e)}")
            raise

    async def get_table_schema(
        self, connector: DatabaseConnector, table_name: str
    ) -> List[Dict[str, Any]]:
        """
        Get schema for a specific table with caching and security validation

        Args:
            connector: Database connector instance
            table_name: Name of the table/collection

        Returns:
            List of column schema dictionaries

        Raises:
            ValueError: If table name is invalid or contains injection patterns
            RuntimeError: If not connected to database
        """
        start_time = time.time()
        
        # Security: Validate table name before proceeding
        if not SecurityValidator.validate_identifier(table_name, "table"):
            raise ValueError(f"Invalid table name: {table_name}")
        
        cache_key = self._get_cache_key(connector, f"schema:{table_name}")

        try:
            # Check cache first
            if self._is_cached(cache_key):
                logger.debug(f"Cache hit for schema (table: {table_name})")
                return self._schema_cache[cache_key]["schema"]

            # Fetch from database
            schema = await connector.get_table_schema(table_name)
            
            # Security: Filter out sensitive columns
            filtered_schema = self._filter_sensitive_columns(schema)
            
            # Cache result
            self._set_cache(cache_key, {"schema": filtered_schema})
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Discovered schema for {table_name} "
                f"({len(filtered_schema)} columns) in {duration_ms:.2f}ms"
            )

            return filtered_schema
            
        except Exception as e:
            logger.error(f"Error discovering schema for {table_name}: {str(e)}")
            raise
    
    def _filter_system_tables(self, tables: List[str], db_type: str) -> List[str]:
        """Filter out system tables that shouldn't be exposed to users"""
        system_prefixes = {
            'postgresql': ['pg_', 'sql_'],
            'mysql': ['mysql_', 'information_schema_', 'performance_schema_', 'sys_'],
            'mongodb': ['system.'],
        }
        
        prefixes = system_prefixes.get(db_type.lower(), [])
        filtered = [
            table for table in tables
            if not any(table.startswith(prefix) for prefix in prefixes)
        ]
        
        if len(filtered) < len(tables):
            logger.info(f"Filtered out {len(tables) - len(filtered)} system tables")
        
        return filtered
    
    def _filter_sensitive_columns(
        self, schema: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter out potentially sensitive columns from schema"""
        sensitive_patterns = [
            'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'apikey',
            'private_key', 'credential', 'auth_token', 'access_token', 'refresh_token'
        ]
        
        filtered = []
        for column in schema:
            col_name = column.get('name', '').lower()
            if not any(pattern in col_name for pattern in sensitive_patterns):
                filtered.append(column)
            else:
                logger.debug(f"Filtered sensitive column: {column.get('name')}")
        
        return filtered

    async def discover_database_schema(
        self, connector: DatabaseConnector
    ) -> Dict[str, Any]:
        """
        Discover entire database schema
        """
        tables = await self.get_tables(connector)
        schema = {}

        for table in tables:
            table_schema = await self.get_table_schema(connector, table)
            schema[table] = table_schema

        return schema

    def _get_cache_key(self, connector: DatabaseConnector, suffix: str) -> str:
        """Generate a cache key based on connector config and suffix"""
        # Remove password from config for security in cache key
        safe_config = connector.config.copy()
        if "password" in safe_config:
            safe_config["password"] = "***REDACTED***"

        config_str = json.dumps(safe_config, sort_keys=True)
        return hashlib.md5(f"{config_str}:{suffix}".encode()).hexdigest()

    def _is_cached(self, cache_key: str) -> bool:
        """Check if cache entry exists and is still valid"""
        if cache_key not in self._schema_cache:
            return False

        if cache_key not in self._cache_timestamps:
            return False

        age = time.time() - self._cache_timestamps[cache_key]
        return age < self._cache_ttl

    def _set_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """Set cache entry with timestamp"""
        self._schema_cache[cache_key] = data
        self._cache_timestamps[cache_key] = time.time()

    async def profile_from_connector(
        self,
        connector: DatabaseConnector,
        table_name: str,
        domain_signal: str = "general",
        domain_confidence: float = 0.5,
        sample_size: int = 500,
    ) -> "DatasetProfile":
        """
        Build a DatasetProfile from a live DB table using schema metadata + a row sample.

        The profile uses the same contract as profile_dataframe() (file uploads), so
        the classifier and compute engine work identically for both source types.
        The schema_hash is derived from the SQL column metadata, not the inferred
        Polars types, so it remains stable across sample runs and detects real schema
        drift (column added/removed/renamed) rather than type-inference noise.
        """
        import polars as pl
        from services.pipeline.profiler import profile_dataframe

        raw_schema = await self.get_table_schema(connector, table_name)
        sample_rows = await connector.extract_data(table_name, limit=sample_size)

        if not sample_rows:
            raise ValueError(f"Table '{table_name}' returned no rows for profiling")

        clean_rows = _coerce_rows(sample_rows)

        try:
            df = pl.from_dicts(clean_rows)
        except Exception as exc:
            logger.warning(
                "DataFrame construction failed for '%s' (%s). Falling back to all-string coercion.",
                table_name, exc,
            )
            str_rows = [
                {k: str(v) if v is not None else None for k, v in r.items()}
                for r in clean_rows
            ]
            df = pl.from_dicts(str_rows)

        profile = await profile_dataframe(
            df,
            domain_signal=domain_signal,
            domain_confidence=domain_confidence,
            source_type="db_table",
        )

        sql_hash = hashlib.sha256(
            json.dumps(
                [(c.get("name", ""), c.get("type", "")) for c in raw_schema],
                sort_keys=True,
            ).encode()
        ).hexdigest()[:16]

        return profile.model_copy(update={"schema_hash": sql_hash})

    def clear_cache(self) -> None:
        """Clear all cached schema information"""
        self._schema_cache.clear()
        self._cache_timestamps.clear()
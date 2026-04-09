"""
Schema Discovery Service
Discovers and caches database schema information
"""

from typing import Dict, List, Any, Optional
from .connectors.base import DatabaseConnector
import hashlib
import json
import time


class SchemaDiscoveryService:
    """Discovers and manages database schema information"""

    def __init__(self):
        self._schema_cache: Dict[str, Dict] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_ttl = 300  # 5 minutes default TTL

    async def get_tables(self, connector: DatabaseConnector) -> List[str]:
        """
        Get list of tables from database with caching

        Args:
            connector: Database connector instance

        Returns:
            List of table/collection names
        """
        cache_key = self._get_cache_key(connector, "tables")

        # Check cache
        if self._is_cached(cache_key):
            return self._schema_cache[cache_key]["tables"]

        # Fetch from database
        tables = await connector.get_tables()

        # Cache result
        self._set_cache(cache_key, {"tables": tables})

        return tables

    async def get_table_schema(
        self, connector: DatabaseConnector, table_name: str
    ) -> List[Dict[str, Any]]:
        """
        Get schema for a specific table with caching

        Args:
            connector: Database connector instance
            table_name: Name of the table/collection

        Returns:
            List of column schema dictionaries
        """
        cache_key = self._get_cache_key(connector, f"schema:{table_name}")

        # Check cache
        if self._is_cached(cache_key):
            return self._schema_cache[cache_key]["schema"]

        # Fetch from database
        schema = await connector.get_table_schema(table_name)

        # Cache result
        self._set_cache(cache_key, {"schema": schema})

        return schema

    async def discover_database_schema(
        self, connector: DatabaseConnector
    ) -> Dict[str, Any]:
        """
        Discover entire database schema

        Args:
            connector: Database connector instance

        Returns:
            Complete database schema information
        """
        tables = await self.get_tables(connector)
        schema = {}

        for table in tables:
            table_schema = await self.get_table_schema(connector, table)
            schema[table] = table_schema

        return schema

    def _get_cache_key(self, connector: DatabaseConnector, suffix: str) -> str:
        """Generate a cache key based on connector config and suffix"""
        config_str = json.dumps(connector.config, sort_keys=True)
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

    def clear_cache(self) -> None:
        """Clear all cached schema information"""
        self._schema_cache.clear()
        self._cache_timestamps.clear()

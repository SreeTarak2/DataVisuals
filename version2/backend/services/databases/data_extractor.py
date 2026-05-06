"""
Data Extraction Service
Handles extracting data from databases for ETL processes
Includes security validation and audit logging
"""

from typing import Dict, List, Any, Optional, AsyncIterator
from .connectors.base import DatabaseConnector
import asyncio
import time
import logging

logger = logging.getLogger(__name__)


class DataExtractor:
    """Extracts data from databases for ETL processes"""

    def __init__(self, batch_size: int = 1000):
        """
        Initialize data extractor

        Args:
            batch_size: Number of rows to fetch per batch
        """
        self.batch_size = batch_size

    async def extract_full_table(
        self,
        connector: DatabaseConnector,
        table_name: str,
        columns: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract entire table content

        Args:
            connector: Database connector instance
            table_name: Name of the table/collection
            columns: List of columns to extract (None for all)

        Returns:
            List of dictionaries representing all rows
        """
        # For smaller tables, we can extract all at once
        # For larger tables, we'd use pagination
        return await connector.extract_data(
            table_name=table_name, columns=columns, limit=None, offset=None
        )

    async def extract_paginated(
        self,
        connector: DatabaseConnector,
        table_name: str,
        columns: Optional[List[str]] = None,
        page_size: Optional[int] = None,
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        """
        Extract table data in pages using async iterator

        Args:
            connector: Database connector instance
            table_name: Name of the table/collection
            columns: List of columns to extract (None for all)
            page_size: Number of rows per page (defaults to batch_size)

        Yields:
            Lists of dictionaries representing rows (one page at a time)
        """
        page_size = page_size or self.batch_size
        offset = 0

        while True:
            batch = await connector.extract_data(
                table_name=table_name, columns=columns, limit=page_size, offset=offset
            )

            if not batch:
                break

            yield batch
            offset += len(batch)

            # If we got less than a full page, we're done
            if len(batch) < page_size:
                break

    async def extract_incremental(
        self,
        connector: DatabaseConnector,
        table_name: str,
        last_value: Any,
        increment_column: str,
        columns: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract incremental data based on changing column

        Args:
            connector: Database connector instance
            table_name: Name of the table/collection
            last_value: Last processed value of increment_column
            increment_column: Column used to detect new/changed records
            columns: List of columns to extract (None for all)

        Returns:
            List of dictionaries representing new/changed rows
        """
        return await connector.extract_incremental(
            table_name=table_name,
            last_value=last_value,
            increment_column=increment_column,
        )

    async def extract_by_query(
        self,
        connector: DatabaseConnector,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract data using custom SQL query (PostgreSQL/MySQL only)

        Args:
            connector: Database connector instance
            query: SQL query to execute (SELECT only)
            params: Query parameters for parameterized queries

        Returns:
            List of dictionaries representing query results

        Raises:
            ValueError: If query contains SQL injection patterns or is not SELECT
            NotImplementedError: If used with MongoDB connector
        """
        start_time = time.time()
        
        # Validate query type (SELECT only)
        if not connector.security_validator.validate_query_type(query, allowed_types=['SELECT']):
            raise ValueError("Only SELECT queries are allowed for security reasons")
        
        # Check for SQL injection patterns
        if connector.security_validator.detect_sql_injection(query):
            raise ValueError("Potential SQL injection detected in query")
        
        connector_name = type(connector).__name__

        # MongoDB doesn't support SQL queries
        if connector_name == "MongoDBConnector":
            raise NotImplementedError("Custom SQL queries are not supported for MongoDB")
        
        try:
            # For PostgreSQL
            if connector_name == "PostgreSQLConnector":
                if not connector._pool:
                    raise RuntimeError("Not connected to database")
                
                async with connector._pool.acquire() as conn:
                    if params:
                        rows = await conn.fetch(query, *params.values())
                    else:
                        rows = await conn.fetch(query)
                    result = [dict(row) for row in rows]
            
            # For MySQL
            elif connector_name == "MySQLConnector":
                if not connector._pool:
                    raise RuntimeError("Not connected to database")
                
                try:
                    import aiomysql
                except ImportError as exc:
                    raise RuntimeError("MySQL support requires aiomysql to be installed") from exc

                async with connector._pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cur:
                        if params:
                            await cur.execute(query, list(params.values()))
                        else:
                            await cur.execute(query)
                        rows = await cur.fetchall()
                        result = list(rows)
            else:
                raise NotImplementedError(f"Custom queries not supported for {type(connector).__name__}")
            
            duration_ms = (time.time() - start_time) * 1000
            connector.audit_logger.log_operation(
                operation="extract_by_query",
                details={"query_preview": query[:100], "params_count": len(params) if params else 0},
                success=True,
                duration_ms=duration_ms
            )
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            connector.audit_logger.log_operation(
                operation="extract_by_query",
                details={"query_preview": query[:100]},
                success=False,
                duration_ms=duration_ms,
                error=str(e)
            )
            raise
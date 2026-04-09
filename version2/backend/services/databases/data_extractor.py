"""
Data Extraction Service
Handles extracting data from databases for ETL processes
"""

from typing import Dict, List, Any, Optional, AsyncIterator
from .connectors.base import DatabaseConnector
import asyncio


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
        Extract data using custom SQL query
        Note: This would need to be implemented in each connector

        Args:
            connector: Database connector instance
            query: SQL query to execute
            params: Query parameters

        Returns:
            List of dictionaries representing query results
        """
        # This would require extending the DatabaseConnector interface
        # For now, we'll raise NotImplementedError to show where it would go
        raise NotImplementedError(
            "Custom query extraction requires connector-specific implementation"
        )

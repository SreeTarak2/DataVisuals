"""
Abstract Base Class for Database Connectors
Defines the interface that all database connectors must implement
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class DatabaseConnector(ABC):
    """Abstract base class defining the database connector interface"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the connector with configuration

        Args:
            config: Database connection configuration
                   (host, port, database, username, password, etc.)
        """
        self.config = config
        self.connection = None

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

"""
Database Connector Factory
Implements the Factory pattern for creating database connector instances
"""

from typing import Dict, Any, Optional, List
from .connectors.base import DatabaseConnector
from .connectors.postgresql import PostgreSQLConnector
from .connectors.mysql import MySQLConnector
from .connectors.mongodb import MongoDBConnector


class DatabaseConnectorFactory:
    """Factory for creating database connector instances"""

    @staticmethod
    def create_connector(
        db_type: str, config: Dict[str, Any]
    ) -> Optional[DatabaseConnector]:
        """
        Create a database connector instance based on database type

        Args:
            db_type: Type of database ('postgresql', 'mysql', 'mongodb')
            config: Database connection configuration

        Returns:
            DatabaseConnector instance or None if db_type not supported
        """
        db_type_lower = db_type.lower().strip()

        if db_type_lower == "postgresql":
            return PostgreSQLConnector(config)
        elif db_type_lower == "mysql":
            return MySQLConnector(config)
        elif db_type_lower == "mongodb":
            return MongoDBConnector(config)
        else:
            # Unsupported database type
            return None

    @staticmethod
    def get_supported_types() -> List[str]:
        """
        Get list of supported database types

        Returns:
            List of supported database type strings
        """
        return ["postgresql", "mysql", "mongodb"]

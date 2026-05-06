"""
Database Connector Factory
Implements the Factory pattern for creating database connector instances
Includes security validation and audit logging
"""

from typing import Dict, Any, Optional, List, TYPE_CHECKING
from .connectors.base import DatabaseConnector, SecurityValidator
import logging
import time

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .connectors.postgresql import PostgreSQLConnector
    from .connectors.mysql import MySQLConnector
    from .connectors.mongodb import MongoDBConnector


class DatabaseConnectorFactory:
    """Factory for creating database connector instances"""

    @staticmethod
    def create_connector(
        db_type: str, config: Dict[str, Any], validate_config: bool = True
    ) -> Optional[DatabaseConnector]:
        """
        Create a database connector instance based on database type

        Args:
            db_type: Type of database ('postgresql', 'mysql', 'mongodb')
            config: Database connection configuration
            validate_config: Whether to validate config before creating connector

        Returns:
            DatabaseConnector instance or None if db_type not supported

        Raises:
            ValueError: If config validation fails
        """
        start_time = time.time()
        
        # Validate database type
        db_type_lower = db_type.lower().strip()
        supported_types = DatabaseConnectorFactory.get_supported_types()
        
        if db_type_lower not in supported_types:
            logger.warning(f"Unsupported database type requested: {db_type}")
            return None
        
        # Validate config if requested
        if validate_config:
            validation_result = SecurityValidator.validate_config_security(config)
            if not validation_result['valid']:
                logger.error(f"Config validation failed: {validation_result['errors']}")
                raise ValueError(f"Invalid configuration: {', '.join(validation_result['errors'])}")
        
        # Create connector based on type
        try:
            if db_type_lower == "postgresql":
                from .connectors.postgresql import PostgreSQLConnector

                connector = PostgreSQLConnector(config)
            elif db_type_lower == "mysql":
                from .connectors.mysql import MySQLConnector

                connector = MySQLConnector(config)
            elif db_type_lower == "mongodb":
                from .connectors.mongodb import MongoDBConnector

                connector = MongoDBConnector(config)
            else:
                return None
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"Created {db_type_lower} connector in {duration_ms:.2f}ms")
            return connector
            
        except Exception as e:
            logger.error(f"Failed to create {db_type_lower} connector: {str(e)}")
            raise

    @staticmethod
    def get_supported_types() -> List[str]:
        """
        Get list of supported database types

        Returns:
            List of supported database type strings
        """
        return ["postgresql", "mysql", "mongodb"]
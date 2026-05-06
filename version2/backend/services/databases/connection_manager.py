"""
Database Connection Manager
Handles creation, pooling, and management of database connections with security
"""

from typing import Dict, Optional, Any
from .connectors.base import DatabaseConnector
from .factory import DatabaseConnectorFactory
import logging
import asyncio

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages database connections and connection pools with security features"""

    def __init__(self, max_connections_per_db: int = 10):
        self._connections: Dict[str, DatabaseConnector] = {}
        self._connection_pools: Dict[str, Any] = {}
        self._max_connections_per_db = max_connections_per_db
        self._lock = asyncio.Lock()
        self._usage_counts: Dict[str, int] = {}

    async def get_connection(
        self, connection_id: str, config: Dict
    ) -> Optional[DatabaseConnector]:
        """Get or create a database connection with thread-safe locking"""
        async with self._lock:
            # Check if connection already exists
            if connection_id in self._connections:
                connector = self._connections[connection_id]
                # Verify connection is still alive
                if connector.connection is not None:
                    self._usage_counts[connection_id] = self._usage_counts.get(connection_id, 0) + 1
                    return connector
                else:
                    # Connection is dead, remove it
                    logger.warning(f"Connection {connection_id} is dead, removing")
                    await self.close_connection(connection_id)

            # Check if we've hit the max connections limit
            if len(self._connections) >= self._max_connections_per_db:
                logger.warning(f"Max connections limit reached ({self._max_connections_per_db})")
                # Could implement LRU eviction here if needed
                return None

            # Create new connection using factory
            db_type = config.get('type', 'postgresql')
            connector = DatabaseConnectorFactory.create_connector(db_type, config)

            if connector is None:
                logger.error(f"Failed to create connector for type: {db_type}")
                return None

            # Connect to database
            connected = await connector.connect()
            if not connected:
                logger.error(f"Failed to connect to database: {connection_id}")
                return None

            # Store connection
            self._connections[connection_id] = connector
            self._usage_counts[connection_id] = 1

            logger.info(f"Created new connection: {connection_id} (type: {db_type})")
            return connector

    async def close_connection(self, connection_id: str) -> None:
        """Close and remove a database connection"""
        async with self._lock:
            if connection_id in self._connections:
                try:
                    await self._connections[connection_id].disconnect()
                except Exception as e:
                    logger.error(f"Error closing connection {connection_id}: {e}")

                del self._connections[connection_id]
                self._usage_counts.pop(connection_id, None)
                logger.info(f"Closed connection: {connection_id}")

    async def close_all_connections(self) -> None:
        """Close all managed connections"""
        async with self._lock:
            connection_ids = list(self._connections.keys())
            for connection_id in connection_ids:
                await self.close_connection(connection_id)

            logger.info(f"Closed all {len(connection_ids)} connections")

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get statistics about managed connections"""
        return {
            "total_connections": len(self._connections),
            "active_connections": len([c for c in self._connections.values() if c.connection is not None]),
            "connection_ids": list(self._connections.keys()),
            "usage_counts": dict(self._usage_counts),
            "max_connections_limit": self._max_connections_per_db,
        }

    async def health_check(self) -> Dict[str, bool]:
        """Perform health check on all connections"""
        results = {}

        for connection_id, connector in self._connections.items():
            try:
                test_result = await connector.test_connection()
                results[connection_id] = test_result.get('success', False)
            except Exception as e:
                logger.error(f"Health check failed for {connection_id}: {e}")
                results[connection_id] = False

        return results
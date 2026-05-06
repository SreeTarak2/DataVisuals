"""
PostgreSQL Database Connector
Implements DatabaseConnector for PostgreSQL databases with full security
"""

from typing import Optional, Any, List, Dict
from .base import DatabaseConnector, SecurityValidator
import asyncpg
import time
import logging

logger = logging.getLogger(__name__)


class PostgreSQLConnector(DatabaseConnector):
    """PostgreSQL database connector implementation with security features"""

    def __init__(self, config: dict):
        super().__init__(config)
        self._pool: Optional[asyncpg.Pool] = None
        self._connection_string: Optional[str] = None

    def _build_connection_string(self) -> str:
        """Build PostgreSQL connection string from config"""
        config = self.config
        user = config.get('username', 'postgres')
        password = config.get('password', '')
        host = config.get('host', 'localhost')
        port = config.get('port', 5432)
        database = config.get('database', 'postgres')
        ssl_mode = config.get('ssl_mode', 'prefer')

        # URL encode password if it contains special characters
        import urllib.parse
        encoded_password = urllib.parse.quote_plus(password)

        conn_string = (
            f"postgresql://{user}:{encoded_password}@{host}:{port}/{database}"
            f"?ssl={ssl_mode}&connect_timeout={self._connection_timeout}"
        )

        return conn_string

    async def connect(self) -> bool:
        """Connect to PostgreSQL database with connection pooling"""
        start_time = self._log_operation_start("connect", {"host": self.config.get('host')})

        try:
            if self._pool is not None:
                return True

            self._connection_string = self._build_connection_string()

            # Create connection pool with security settings
            self._pool = await asyncpg.create_pool(
                dsn=self._connection_string,
                min_size=1,
                max_size=self._pool_size,
                command_timeout=self._connection_timeout,
                max_inactive_connection_lifetime=300.0,
            )

            # Test the pool by acquiring a connection
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

            self._connected_at = time.time()
            self._log_operation_end("connect", {"host": self.config.get('host')}, start_time, True)
            return True

        except asyncpg.PostgresError as e:
            error_msg = f"PostgreSQL connection error: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("connect", {"host": self.config.get('host')}, start_time, False, error_msg)
            return False
        except Exception as e:
            error_msg = f"Unexpected connection error: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("connect", {"host": self.config.get('host')}, start_time, False, error_msg)
            return False

    async def disconnect(self) -> None:
        """Disconnect from PostgreSQL database and close pool"""
        start_time = self._log_operation_start("disconnect", {"host": self.config.get('host')})

        try:
            if self._pool:
                await self._pool.close()
                self._pool = None
                self._connection_string = None
                self._connected_at = None
                self._log_operation_end("disconnect", {"host": self.config.get('host')}, start_time, True)
        except Exception as e:
            error_msg = f"Error during disconnect: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("disconnect", {"host": self.config.get('host')}, start_time, False, error_msg)

    async def test_connection(self) -> Dict[str, Any]:
        """Test PostgreSQL connection and get database version"""
        start_time = time.time()

        try:
            if not self._pool:
                connected = await self.connect()
                if not connected:
                    return {
                        "success": False,
                        "message": "Failed to establish connection",
                        "response_time_ms": (time.time() - start_time) * 1000,
                        "database_version": None,
                    }

            async with self._pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                await conn.fetchval("SELECT 1")

            response_time = (time.time() - start_time) * 1000

            return {
                "success": True,
                "message": "Connection successful",
                "response_time_ms": response_time,
                "database_version": version,
            }

        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "response_time_ms": (time.time() - start_time) * 1000,
                "database_version": None,
            }

    async def get_tables(self) -> List[str]:
        """Get list of tables in PostgreSQL database"""
        start_time = self._log_operation_start("get_tables", {"database": self.config.get('database')})

        try:
            if not self._pool:
                raise RuntimeError("Not connected to database")

            schema = self.config.get('schema', 'public')

            # Validate schema name
            if not self.security_validator.validate_identifier(schema, "table"):
                raise ValueError(f"Invalid schema name: {schema}")

            async with self._pool.acquire() as conn:
                query = """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = $1
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """
                rows = await conn.fetch(query, schema)
                tables = [row['table_name'] for row in rows]

            self._log_operation_end("get_tables", {"database": self.config.get('database'), "schema": schema}, start_time, True)
            return tables

        except Exception as e:
            error_msg = f"Error getting tables: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("get_tables", {"database": self.config.get('database')}, start_time, False, error_msg)
            raise

    async def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get schema for PostgreSQL table"""
        start_time = self._log_operation_start("get_table_schema", {"table": table_name})

        try:
            if not self.security_validator.validate_identifier(table_name, "table"):
                raise ValueError(f"Invalid table name: {table_name}")

            if not self._pool:
                raise RuntimeError("Not connected to database")

            schema = self.config.get('schema', 'public')
            if not self.security_validator.validate_identifier(schema, "table"):
                raise ValueError(f"Invalid schema name: {schema}")

            async with self._pool.acquire() as conn:
                query = """
                    SELECT
                        column_name as name,
                        data_type as type,
                        CASE WHEN is_nullable = 'YES' THEN true ELSE false END as nullable,
                        column_default as default,
                        character_maximum_length as max_length,
                        numeric_precision as precision,
                        numeric_scale as scale
                    FROM information_schema.columns
                    WHERE table_schema = $1 AND table_name = $2
                    ORDER BY ordinal_position
                """
                rows = await conn.fetch(query, schema, table_name)

                result = []
                for row in rows:
                    result.append({
                        "name": row['name'],
                        "type": row['type'],
                        "nullable": row['nullable'] or False,
                        "default": row['default'],
                        "max_length": int(row['max_length']) if row['max_length'] else None,
                        "precision": int(row['precision']) if row['precision'] else None,
                        "scale": int(row['scale']) if row['scale'] else None,
                    })

            self._log_operation_end("get_table_schema", {"table": table_name}, start_time, True)
            return result

        except Exception as e:
            error_msg = f"Error getting table schema: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("get_table_schema", {"table": table_name}, start_time, False, error_msg)
            raise

    async def extract_data(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Extract data from PostgreSQL table with security validation"""
        start_time = self._log_operation_start("extract_data", {"table": table_name, "columns": columns})

        try:
            # Validate table name
            if not self.security_validator.validate_identifier(table_name, "table"):
                raise ValueError(f"Invalid table name: {table_name}")

            # Validate column names if provided
            if columns:
                for col in columns:
                    if not self.security_validator.validate_identifier(col, "column"):
                        raise ValueError(f"Invalid column name: {col}")

            # Sanitize limit and offset
            safe_limit = self.security_validator.sanitize_limit(limit, default=1000, max_limit=10000)
            safe_offset = self.security_validator.sanitize_limit(offset, default=0, max_limit=100000)

            if not self._pool:
                raise RuntimeError("Not connected to database")

            # Build query safely using parameterized identifiers
            column_clause = "*"
            if columns:
                # Quote identifiers to prevent SQL injection
                quoted_columns = [f'"{col}"' for col in columns]
                column_clause = ", ".join(quoted_columns)

            query = f'SELECT {column_clause} FROM "{table_name}" LIMIT $1 OFFSET $2'

            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, safe_limit, safe_offset)
                result = [dict(row) for row in rows]

            self._log_operation_end("extract_data", {"table": table_name, "rows_returned": len(result)}, start_time, True)
            return result

        except Exception as e:
            error_msg = f"Error extracting data: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("extract_data", {"table": table_name}, start_time, False, error_msg)
            raise

    async def extract_incremental(
        self, table_name: str, last_value: Any, increment_column: str
    ) -> List[Dict[str, Any]]:
        """Extract incremental data from PostgreSQL table"""
        start_time = self._log_operation_start("extract_incremental", {"table": table_name, "column": increment_column})

        try:
            # Validate identifiers
            if not self.security_validator.validate_identifier(table_name, "table"):
                raise ValueError(f"Invalid table name: {table_name}")

            if not self.security_validator.validate_identifier(increment_column, "column"):
                raise ValueError(f"Invalid column name: {increment_column}")

            if not self._pool:
                raise RuntimeError("Not connected to database")

            # Build query with proper quoting
            query = f'''
                SELECT * FROM "{table_name}"
                WHERE "{increment_column}" > $1
                ORDER BY "{increment_column}" ASC
                LIMIT $2
            '''

            safe_limit = self.security_validator.sanitize_limit(None, default=1000, max_limit=10000)

            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, last_value, safe_limit)
                result = [dict(row) for row in rows]

            self._log_operation_end("extract_incremental", {"table": table_name, "rows_returned": len(result)}, start_time, True)
            return result

        except Exception as e:
            error_msg = f"Error extracting incremental data: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("extract_incremental", {"table": table_name}, start_time, False, error_msg)
            raise
"""
MySQL Database Connector
Implements DatabaseConnector for MySQL databases with full security
"""

from typing import Optional, Any, List, Dict
from .base import DatabaseConnector, SecurityValidator
import aiomysql
import asyncio
import time
import logging

logger = logging.getLogger(__name__)


class MySQLConnector(DatabaseConnector):
    """MySQL database connector implementation with security features"""

    def __init__(self, config: dict):
        super().__init__(config)
        self._pool: Optional[aiomysql.Pool] = None
        self._connection_params: Optional[Dict] = None

    def _build_connection_params(self) -> Dict:
        """Build MySQL connection parameters from config

        Priority:
        1. Parse from ``connection_url`` if provided (mysql://user:pass@host:port/db)
        2. Build from individual fields (host, port, username, password, database)
        """
        config = self.config

        # Parse connection URL if provided
        connection_url = config.get('connection_url')
        if connection_url:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(connection_url)
                params = {
                    'host': parsed.hostname or 'localhost',
                    'port': parsed.port or 3306,
                    'user': parsed.username or 'root',
                    'password': parsed.password or '',
                    'db': (parsed.path.lstrip('/') if parsed.path else 'mysql'),
                    'autocommit': True,
                    'connect_timeout': self._connection_timeout,
                }
                # Add SSL parameters if configured
                ssl_mode = config.get('ssl_mode', 'PREFERRED')
                if ssl_mode in ['REQUIRED', 'VERIFY_CA', 'VERIFY_IDENTITY']:
                    params['ssl'] = {
                        'ca': config.get('ssl_ca'),
                        'cert': config.get('ssl_cert'),
                        'key': config.get('ssl_key'),
                    }
                return params
            except Exception:
                logger.warning("Failed to parse MySQL connection URL, falling back to individual fields")

        params = {
            'host': config.get('host', 'localhost'),
            'port': config.get('port', 3306),
            'user': config.get('username', 'root'),
            'password': config.get('password', ''),
            'db': config.get('database', 'mysql'),
            'autocommit': True,
            'connect_timeout': self._connection_timeout,
        }

        # Add SSL parameters if configured
        ssl_mode = config.get('ssl_mode', 'PREFERRED')
        if ssl_mode in ['REQUIRED', 'VERIFY_CA', 'VERIFY_IDENTITY']:
            params['ssl'] = {
                'ca': config.get('ssl_ca'),
                'cert': config.get('ssl_cert'),
                'key': config.get('ssl_key'),
            }

        return params

    async def connect(self) -> bool:
        """Connect to MySQL database with connection pooling and retry logic"""
        start_time = self._log_operation_start("connect", {"host": self.config.get('host')})

        if self._pool is not None:
            return True

        self._connection_params = self._build_connection_params()
        last_error = None

        for attempt in range(self._max_retries):
            try:
                self._pool = await aiomysql.create_pool(
                    host=self._connection_params['host'],
                    port=self._connection_params['port'],
                    user=self._connection_params['user'],
                    password=self._connection_params['password'],
                    db=self._connection_params['db'],
                    autocommit=self._connection_params['autocommit'],
                    connect_timeout=self._connection_params['connect_timeout'],
                    minsize=1,
                    maxsize=self._pool_size,
                    pool_recycle=300,
                )

                async with self._pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT 1")
                        await cur.fetchone()

                self._connected_at = time.time()
                self._log_operation_end("connect", {"host": self.config.get('host')}, start_time, True)
                return True

            except (aiomysql.Error, ConnectionError, OSError) as e:
                last_error = e
                self._pool = None
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay_seconds * (2 ** attempt)
                    logger.warning(
                        f"MySQL connection attempt {attempt + 1}/{self._max_retries} "
                        f"failed: {e}. Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    error_msg = f"MySQL connection error after {self._max_retries} attempts: {last_error}"
                    logger.error(error_msg)
            except Exception as e:
                last_error = e
                self._pool = None
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay_seconds * (2 ** attempt)
                    logger.warning(
                        f"MySQL connection attempt {attempt + 1}/{self._max_retries} "
                        f"failed: {e}. Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    error_msg = f"Unexpected connection error after {self._max_retries} attempts: {last_error}"
                    logger.error(error_msg)

        self._log_operation_end("connect", {"host": self.config.get('host')}, start_time, False, str(last_error))
        return False

    async def disconnect(self) -> None:
        """Disconnect from MySQL database and close pool"""
        start_time = self._log_operation_start("disconnect", {"host": self.config.get('host')})

        try:
            if self._pool:
                self._pool.close()
                await self._pool.wait_closed()
                self._pool = None
                self._connection_params = None
                self._connected_at = None
                self._log_operation_end("disconnect", {"host": self.config.get('host')}, start_time, True)
        except Exception as e:
            error_msg = f"Error during disconnect: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("disconnect", {"host": self.config.get('host')}, start_time, False, error_msg)

    async def test_connection(self) -> Dict[str, Any]:
        """Test MySQL connection and get database version"""
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
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT VERSION()")
                    result = await cur.fetchone()
                    version = result.get('VERSION()') if result else None

                    await cur.execute("SELECT 1")
                    await cur.fetchone()

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
        """Get list of tables in MySQL database"""
        start_time = self._log_operation_start("get_tables", {"database": self.config.get('database')})

        try:
            if not self._pool:
                raise RuntimeError("Not connected to database")

            database = self.config.get('database', '')

            # Validate database name
            if not self.security_validator.validate_identifier(database, "database"):
                raise ValueError(f"Invalid database name: {database}")

            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    query = """
                        SELECT TABLE_NAME
                        FROM INFORMATION_SCHEMA.TABLES
                        WHERE TABLE_SCHEMA = %s
                        AND TABLE_TYPE = 'BASE TABLE'
                        ORDER BY TABLE_NAME
                    """
                    await cur.execute(query, (database,))
                    rows = await cur.fetchall()
                    tables = [row['TABLE_NAME'] for row in rows]

            self._log_operation_end("get_tables", {"database": database}, start_time, True)
            return tables

        except Exception as e:
            error_msg = f"Error getting tables: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("get_tables", {"database": self.config.get('database')}, start_time, False, error_msg)
            raise

    async def get_foreign_keys(self) -> List[Dict[str, Any]]:
        """
        Get all foreign key constraints in the MySQL database.

        Queries INFORMATION_SCHEMA.KEY_COLUMN_USAGE for the
        configured database.

        Returns:
            List of dicts with constraint_name, table_name, column_name,
            referenced_table, referenced_column
        """
        start_time = self._log_operation_start("get_foreign_keys", {"database": self.config.get('database')})

        try:
            if not self._pool:
                raise RuntimeError("Not connected to database")

            database = self.config.get('database', '')

            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    query = """
                        SELECT
                            tc.CONSTRAINT_NAME AS constraint_name,
                            kcu.TABLE_NAME AS table_name,
                            kcu.COLUMN_NAME AS column_name,
                            kcu.REFERENCED_TABLE_NAME AS referenced_table,
                            kcu.REFERENCED_COLUMN_NAME AS referenced_column
                        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                            ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                            AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
                            AND tc.TABLE_NAME = kcu.TABLE_NAME
                        WHERE tc.TABLE_SCHEMA = %s
                          AND tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
                        ORDER BY kcu.TABLE_NAME, kcu.CONSTRAINT_NAME, kcu.ORDINAL_POSITION
                    """
                    await cur.execute(query, (database,))
                    rows = await cur.fetchall()
                    result = [
                        {
                            "constraint_name": row['constraint_name'],
                            "table_name": row['table_name'],
                            "column_name": row['column_name'],
                            "referenced_table": row['referenced_table'],
                            "referenced_column": row['referenced_column'],
                        }
                        for row in rows
                    ]

            self._log_operation_end("get_foreign_keys", {"database": database, "count": len(result)}, start_time, True)
            return result

        except Exception as e:
            error_msg = f"Error getting foreign keys: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("get_foreign_keys", {"database": self.config.get('database')}, start_time, False, error_msg)
            return []

    async def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get schema for MySQL table"""
        start_time = self._log_operation_start("get_table_schema", {"table": table_name})

        try:
            if not self.security_validator.validate_identifier(table_name, "table"):
                raise ValueError(f"Invalid table name: {table_name}")

            if not self._pool:
                raise RuntimeError("Not connected to database")

            database = self.config.get('database', '')
            if not self.security_validator.validate_identifier(database, "database"):
                raise ValueError(f"Invalid database name: {database}")

            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    query = """
                        SELECT
                            COLUMN_NAME as name,
                            DATA_TYPE as type,
                            CASE WHEN IS_NULLABLE = 'YES' THEN 1 ELSE 0 END as nullable,
                            COLUMN_DEFAULT as default,
                            CHARACTER_MAXIMUM_LENGTH as max_length,
                            NUMERIC_PRECISION as precision,
                            NUMERIC_SCALE as scale
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                        ORDER BY ORDINAL_POSITION
                    """
                    await cur.execute(query, (database, table_name))
                    rows = await cur.fetchall()

                    result = []
                    for row in rows:
                        result.append({
                            "name": row['name'],
                            "type": row['type'],
                            "nullable": bool(row['nullable']),
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
        """Extract data from MySQL table with security validation"""
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

            # Build query safely using backtick-quoted identifiers
            column_clause = "*"
            if columns:
                # Quote identifiers with backticks to prevent SQL injection
                quoted_columns = [f"`{col}`" for col in columns]
                column_clause = ", ".join(quoted_columns)

            query = f"SELECT {column_clause} FROM `{table_name}` LIMIT %s OFFSET %s"

            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(query, (safe_limit, safe_offset))
                    rows = await cur.fetchall()
                    result = list(rows)

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
        """Extract incremental data from MySQL table"""
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
            query = f"""
                SELECT * FROM `{table_name}`
                WHERE `{increment_column}` > %s
                ORDER BY `{increment_column}` ASC
                LIMIT %s
            """

            safe_limit = self.security_validator.sanitize_limit(None, default=1000, max_limit=10000)

            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(query, (last_value, safe_limit))
                    rows = await cur.fetchall()
                    result = list(rows)

            self._log_operation_end("extract_incremental", {"table": table_name, "rows_returned": len(result)}, start_time, True)
            return result

        except Exception as e:
            error_msg = f"Error extracting incremental data: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("extract_incremental", {"table": table_name}, start_time, False, error_msg)
            raise
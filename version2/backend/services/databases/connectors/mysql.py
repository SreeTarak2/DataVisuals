"""
MySQL Database Connector
Implements DatabaseConnector for MySQL databases with full security
"""

from typing import Optional, Any, List, Dict
from .base import DatabaseConnector, SecurityValidator
import aiomysql
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
        """Build MySQL connection parameters from config"""
        config = self.config

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
        """Connect to MySQL database with connection pooling"""
        start_time = self._log_operation_start("connect", {"host": self.config.get('host')})

        try:
            if self._pool is not None:
                return True

            self._connection_params = self._build_connection_params()

            # Create connection pool with security settings
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

            # Test the pool by acquiring a connection
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    await cur.fetchone()

            self._connected_at = time.time()
            self._log_operation_end("connect", {"host": self.config.get('host')}, start_time, True)
            return True

        except aiomysql.Error as e:
            error_msg = f"MySQL connection error: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("connect", {"host": self.config.get('host')}, start_time, False, error_msg)
            return False
        except Exception as e:
            error_msg = f"Unexpected connection error: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("connect", {"host": self.config.get('host')}, start_time, False, error_msg)
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
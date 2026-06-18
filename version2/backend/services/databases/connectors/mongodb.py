"""
MongoDB Database Connector
Implements DatabaseConnector for MongoDB databases with full security
"""

from typing import Optional, Any, List, Dict
from .base import DatabaseConnector, SecurityValidator
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import time
import logging

logger = logging.getLogger(__name__)


class MongoDBConnector(DatabaseConnector):
    """MongoDB database connector implementation with security features"""

    def __init__(self, config: dict):
        super().__init__(config)
        self._client: Optional[AsyncIOMotorClient] = None
        self._database = None
        self._connection_string: Optional[str] = None

    def _build_connection_string(self) -> str:
        """Build MongoDB connection string from config

        Priority:
        1. Use ``connection_url`` directly if provided
        2. Build from individual fields (host, port, username, password, database)
        """
        config = self.config

        # Use full connection URL if provided (e.g., from Atlas connection string)
        connection_url = config.get('connection_url')
        if connection_url:
            return connection_url

        user = config.get('username', '')
        password = config.get('password', '')
        host = config.get('host', 'localhost')
        port = config.get('port', 27017)
        database = config.get('database', 'admin')
        auth_source = config.get('auth_source', database or 'admin')
        ssl_mode = config.get('ssl_mode', False)

        # URL encode username and password
        import urllib.parse
        encoded_user = urllib.parse.quote_plus(user) if user else ''
        encoded_password = urllib.parse.quote_plus(password) if password else ''

        # Build connection string
        if user and password:
            conn_string = f"mongodb://{encoded_user}:{encoded_password}@{host}:{port}/{database}"
        else:
            conn_string = f"mongodb://{host}:{port}/{database}"

        # Add query parameters
        params = []
        params.append(f"authSource={auth_source}")

        if ssl_mode:
            params.append("ssl=true")
            if config.get('ssl_ca'):
                params.append(f"sslCaFile={config.get('ssl_ca')}")
            if config.get('ssl_cert'):
                params.append(f"sslCertFile={config.get('ssl_cert')}")
            if config.get('ssl_key'):
                params.append(f"sslKeyFile={config.get('ssl_key')}")

        params.append(f"connectTimeoutMS={self._connection_timeout * 1000}")
        params.append(f"serverSelectionTimeoutMS={self._connection_timeout * 1000}")

        if params:
            conn_string += "?" + "&".join(params)

        return conn_string

    async def connect(self) -> bool:
        """Connect to MongoDB database with retry logic"""
        start_time = self._log_operation_start("connect", {"host": self.config.get('host')})

        if self._client is not None:
            # Test if client is still alive
            try:
                await self._client.admin.command('ping')
                return True
            except Exception:
                # Stale connection — reconnect below
                await self.disconnect()

        self._connection_string = self._build_connection_string()
        last_error = None

        for attempt in range(self._max_retries):
            try:
                self._client = AsyncIOMotorClient(
                    self._connection_string,
                    maxPoolSize=self._pool_size,
                    minPoolSize=1,
                    maxIdleTimeMS=300000,
                    serverSelectionTimeoutMS=self._connection_timeout * 1000,
                    connectTimeoutMS=self._connection_timeout * 1000,
                )

                database_name = self.config.get('database', 'admin')
                self._database = self._client[database_name]

                await self._client.admin.command('ping')

                self._connected_at = time.time()
                self._log_operation_end("connect", {"host": self.config.get('host')}, start_time, True)
                return True

            except Exception as e:
                last_error = e
                self._client = None
                self._database = None
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay_seconds * (2 ** attempt)
                    logger.warning(
                        f"MongoDB connection attempt {attempt + 1}/{self._max_retries} "
                        f"failed: {e}. Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    error_msg = f"MongoDB connection error after {self._max_retries} attempts: {last_error}"
                    logger.error(error_msg)

        self._log_operation_end("connect", {"host": self.config.get('host')}, start_time, False, str(last_error))
        return False

    async def disconnect(self) -> None:
        """Disconnect from MongoDB database"""
        start_time = self._log_operation_start("disconnect", {"host": self.config.get('host')})

        try:
            if self._client:
                self._client.close()
                self._client = None
                self._database = None
                self._connection_string = None
                self._connected_at = None
                self._log_operation_end("disconnect", {"host": self.config.get('host')}, start_time, True)
        except Exception as e:
            error_msg = f"Error during disconnect: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("disconnect", {"host": self.config.get('host')}, start_time, False, error_msg)

    async def test_connection(self) -> Dict[str, Any]:
        """Test MongoDB connection and get server version"""
        start_time = time.time()

        try:
            if not self._client:
                connected = await self.connect()
                if not connected:
                    return {
                        "success": False,
                        "message": "Failed to establish connection",
                        "response_time_ms": (time.time() - start_time) * 1000,
                        "database_version": None,
                    }

            # Ping the server
            await self._client.admin.command('ping')

            # Get server version
            build_info = await self._client.admin.command('buildInfo')
            version = build_info.get('version')

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
        """Get list of collections in MongoDB database"""
        start_time = self._log_operation_start("get_tables", {"database": self.config.get('database')})

        try:
            if not self._database:
                raise RuntimeError("Not connected to database")

            # Get collection names (excluding system collections)
            collections = await self._database.list_collection_names()

            # Filter out system collections
            tables = [c for c in collections if not c.startswith('system.')]

            self._log_operation_end("get_tables", {"database": self.config.get('database'), "count": len(tables)}, start_time, True)
            return tables

        except Exception as e:
            error_msg = f"Error getting collections: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("get_tables", {"database": self.config.get('database')}, start_time, False, error_msg)
            raise

    async def get_foreign_keys(self) -> List[Dict[str, Any]]:
        """
        Get foreign key constraints in MongoDB.

        MongoDB does not have native foreign key constraints.
        Relationships are typically embedded documents or manual
        references stored as fields. Returns an empty list.

        Returns:
            Empty list
        """
        # MongoDB has no native FK constraints, so return empty.
        # Cross-collection relationship discovery (Tier 2+ with value
        # overlap analysis) will detect these later from extracted data.
        return []

    async def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get schema for MongoDB collection by sampling documents"""
        start_time = self._log_operation_start("get_table_schema", {"collection": table_name})

        try:
            # Validate collection name
            if not self.security_validator.validate_identifier(table_name, "table"):
                raise ValueError(f"Invalid collection name: {table_name}")

            if not self._database:
                raise RuntimeError("Not connected to database")

            collection = self._database[table_name]

            # Sample documents to infer schema
            sample_docs = await collection.find().limit(10).to_list(length=10)

            if not sample_docs:
                self._log_operation_end("get_table_schema", {"collection": table_name}, start_time, True)
                return []

            # Infer schema from sampled documents
            schema = []
            field_types = {}

            for doc in sample_docs:
                for key, value in doc.items():
                    if key == '_id':
                        continue

                    if key not in field_types:
                        field_types[key] = set()

                    field_types[key].add(type(value).__name__)

            for field_name, types in field_types.items():
                # Determine primary type
                type_list = list(types)
                primary_type = type_list[0] if len(type_list) == 1 else f"mixed({','.join(type_list)})"

                schema.append({
                    "name": field_name,
                    "type": primary_type,
                    "nullable": len(sample_docs) != sum(1 for d in sample_docs if field_name in d),
                    "default": None,
                    "max_length": None,
                    "precision": None,
                    "scale": None,
                })

            self._log_operation_end("get_table_schema", {"collection": table_name, "fields": len(schema)}, start_time, True)
            return schema

        except Exception as e:
            error_msg = f"Error getting collection schema: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("get_table_schema", {"collection": table_name}, start_time, False, error_msg)
            raise

    async def extract_data(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Extract data from MongoDB collection with security validation"""
        start_time = self._log_operation_start("extract_data", {"collection": table_name, "columns": columns})

        try:
            # Validate collection name
            if not self.security_validator.validate_identifier(table_name, "table"):
                raise ValueError(f"Invalid collection name: {table_name}")

            # Sanitize limit and offset
            safe_limit = self.security_validator.sanitize_limit(limit, default=1000, max_limit=10000)
            safe_offset = self.security_validator.sanitize_limit(offset, default=0, max_limit=100000)

            if not self._database:
                raise RuntimeError("Not connected to database")

            collection = self._database[table_name]

            # Build projection if columns specified
            projection = None
            if columns:
                for col in columns:
                    if not self.security_validator.validate_identifier(col, "column"):
                        raise ValueError(f"Invalid field name: {col}")
                projection = {col: 1 for col in columns}
                projection['_id'] = 0  # Exclude _id unless explicitly requested

            # Query with limit and skip
            cursor = collection.find({}, projection).skip(safe_offset).limit(safe_limit)
            result = await cursor.to_list(length=safe_limit)

            # Convert ObjectId to string for JSON serialization
            for doc in result:
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])

            self._log_operation_end("extract_data", {"collection": table_name, "rows_returned": len(result)}, start_time, True)
            return result

        except Exception as e:
            error_msg = f"Error extracting data: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("extract_data", {"collection": table_name}, start_time, False, error_msg)
            raise

    async def extract_incremental(
        self, table_name: str, last_value: Any, increment_column: str
    ) -> List[Dict[str, Any]]:
        """Extract incremental data from MongoDB collection"""
        start_time = self._log_operation_start("extract_incremental", {"collection": table_name, "column": increment_column})

        try:
            # Validate identifiers
            if not self.security_validator.validate_identifier(table_name, "table"):
                raise ValueError(f"Invalid collection name: {table_name}")

            if not self.security_validator.validate_identifier(increment_column, "column"):
                raise ValueError(f"Invalid field name: {increment_column}")

            if not self._database:
                raise RuntimeError("Not connected to database")

            collection = self._database[table_name]

            # Build query for incremental extraction
            query = {increment_column: {"$gt": last_value}}

            # Sort by increment column and limit results
            safe_limit = self.security_validator.sanitize_limit(None, default=1000, max_limit=10000)

            cursor = collection.find(query).sort(increment_column, 1).limit(safe_limit)
            result = await cursor.to_list(length=safe_limit)

            # Convert ObjectId to string for JSON serialization
            for doc in result:
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])

            self._log_operation_end("extract_incremental", {"collection": table_name, "rows_returned": len(result)}, start_time, True)
            return result

        except Exception as e:
            error_msg = f"Error extracting incremental data: {str(e)}"
            logger.error(error_msg)
            self._log_operation_end("extract_incremental", {"collection": table_name}, start_time, False, error_msg)
            raise
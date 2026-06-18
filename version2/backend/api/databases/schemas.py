from pydantic import BaseModel, field_validator, model_validator
from typing import Literal, Optional
from datetime import datetime
from urllib.parse import urlparse


class TestConnectionRequest(BaseModel):
    db_type: Literal["postgresql", "mysql", "mongodb", "supabase"]
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssl_mode: str = "prefer"
    connection_url: Optional[str] = None

    @field_validator("host")
    @classmethod
    def validate_host(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v or len(v) > 253:
            raise ValueError("Invalid host")
        return v

    @field_validator("port")
    @classmethod
    def validate_port(cls, v):
        if v is None:
            return v
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    @model_validator(mode="before")
    @classmethod
    def validate_fields_by_type(cls, values):
        db_type = values.get("db_type")
        connection_url = values.get("connection_url")

        # For MongoDB and Supabase, allow connection_url as an alternative to individual fields
        if db_type in ("mongodb", "supabase") and connection_url:
            # Parse the URL to extract components, but keep the original URL
            parsed = urlparse(connection_url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid {db_type} connection URL")
            # Fill in individual fields from the URL so the rest of the pipeline works
            if not values.get("host"):
                values["host"] = parsed.hostname or ""
            if not values.get("port") and parsed.port:
                values["port"] = parsed.port
            if db_type == "mongodb":
                # MongoDB URLs have the database as the path (without leading /)
                db = parsed.path.lstrip("/") if parsed.path else "admin"
                values["database"] = db
            else:
                # Postgres/Supabase URLs have the database as the path
                db = parsed.path.lstrip("/") if parsed.path else "postgres"
                values["database"] = db
            if not values.get("username") and parsed.username:
                values["username"] = parsed.username
            if not values.get("password") and parsed.password:
                values["password"] = parsed.password
            return values

        # For non-MongoDB / non-Supabase, require individual fields
        if db_type not in ("mongodb", "supabase"):
            if not values.get("host"):
                raise ValueError("host is required")
            if not values.get("database"):
                raise ValueError("database is required")
            if not values.get("username"):
                raise ValueError("username is required")
            if not values.get("password"):
                raise ValueError("password is required")

        return values


class SaveConnectionRequest(TestConnectionRequest):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError("Name must be 1–100 characters")
        return v


class ConnectionResponse(BaseModel):
    connection_id: str
    name: str
    db_type: str
    host: str
    port: int
    database: str
    username: str
    status: str
    created_at: datetime
    last_used_at: Optional[datetime] = None


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    response_time_ms: float
    db_version: Optional[str] = None
    tables_count: Optional[int] = None


class ExtractTableRequest(BaseModel):
    table_name: Optional[str] = None
    custom_query: Optional[str] = None
    dataset_name: Optional[str] = None
    row_limit: int = 100_000

    @field_validator("row_limit")
    @classmethod
    def validate_limit(cls, v):
        if v < 1:
            raise ValueError("row_limit must be positive")
        if v > 1_000_000:
            raise ValueError("row_limit cannot exceed 1,000,000")
        return v

    @model_validator(mode="after")
    @classmethod
    def require_one_source(cls, data):
        # Ensure at least one of table_name or custom_query is provided
        if not data.table_name and not data.custom_query:
            raise ValueError("Either table_name or custom_query must be provided")
        return data


class ExtractTableResponse(BaseModel):
    dataset_id: str
    task_id: str
    rows_extracted: int
    name: str
    schema_hash: Optional[str] = None
    message: str


class SchemaDriftResponse(BaseModel):
    has_drift: bool
    stored_hash: Optional[str] = None
    current_hash: Optional[str] = None
    added_columns: list[str] = []
    removed_columns: list[str] = []
    changed_types: dict[str, dict[str, str]] = {}
    message: Optional[str] = None


class ReExtractResponse(BaseModel):
    dataset_id: str
    task_id: str
    rows_extracted: int
    name: str
    schema_hash: Optional[str] = None
    message: str


class ForeignKeyResponse(BaseModel):
    """A single foreign key constraint detected in the database."""

    constraint_name: str
    table_name: str
    column_name: str
    referenced_table: str
    referenced_column: str


class InferredRelationshipResponse(BaseModel):
    """A cross-table relationship detected by column name + type analysis or value overlap."""

    source_table: str
    source_column: str
    target_table: str
    target_column: str
    confidence: float = 0.0  # 0.0-1.0 based on name match + type compatibility
    method: str = "name_match"  # How it was detected: "name_match", "value_overlap"
    overlap_ratio: Optional[float] = None  # Only for value_overlap: fraction of FK values found in PK
    fk_sample_size: Optional[int] = None  # Number of FK unique values sampled


class ForeignKeysListResponse(BaseModel):
    """Response listing all foreign keys for a connection."""

    connection_id: str
    db_type: str
    foreign_keys: list[ForeignKeyResponse]
    count: int
    cached: bool = False
    inferred: list[InferredRelationshipResponse] = []
    inferred_count: int = 0

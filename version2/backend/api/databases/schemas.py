from pydantic import BaseModel, validator
from typing import Literal, Optional
from datetime import datetime


class TestConnectionRequest(BaseModel):
    db_type: Literal["postgresql", "mysql", "mongodb"]
    host: str
    port: int
    database: str
    username: str
    password: str
    ssl_mode: str = "prefer"

    @validator("host")
    def validate_host(cls, v):
        v = v.strip()
        if not v or len(v) > 253:
            raise ValueError("Invalid host")
        return v

    @validator("port")
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


class SaveConnectionRequest(TestConnectionRequest):
    name: str

    @validator("name")
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

    @validator("row_limit")
    def validate_limit(cls, v):
        if v < 1:
            raise ValueError("row_limit must be positive")
        if v > 1_000_000:
            raise ValueError("row_limit cannot exceed 1,000,000")
        return v

    @validator("table_name", "custom_query", always=True)
    def require_one_source(cls, v, values):
        # Pydantic validates fields in order — by the time we reach custom_query,
        # table_name is already in values. Ensure at least one is provided.
        if "table_name" in values and not values["table_name"] and not v:
            raise ValueError("Either table_name or custom_query must be provided")
        return v


class ExtractTableResponse(BaseModel):
    dataset_id: str
    task_id: str
    rows_extracted: int
    name: str
    message: str

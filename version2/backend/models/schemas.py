from pydantic import BaseModel, EmailStr
from typing import List, Dict, Any, Optional
from datetime import datetime

# Dataset Schemas
class DatasetInfo(BaseModel):
    id: str
    filename: str
    total_rows: int
    total_columns: int
    columns: List[str]
    uploaded_at: str

class DatasetMetadata(BaseModel):
    dataset_overview: Dict[str, Any]
    column_metadata: List[Dict[str, Any]]
    statistical_summaries: Dict[str, Any]
    data_quality: Dict[str, Any]
    chart_recommendations: List[Dict[str, Any]]
    hierarchies: List[Dict[str, Any]]

# Chart Schemas
class ChartRequest(BaseModel):
    chart_type: str
    fields: List[str]
    title: Optional[str] = None
    explanation: Optional[str] = None

class ChartResponse(BaseModel):
    id: str
    type: str
    title: str
    data: List[Dict[str, Any]]
    fields: List[str]
    explanation: str
    confidence: float

class ChartRecommendation(BaseModel):
    chart_type: str
    title: str
    description: str
    suitable_columns: List[str]
    confidence: str

# Chat Schemas
class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    chart: Optional[Dict[str, Any]] = None
    metadata_used: bool
    rag_used: bool

# Drill-down Schemas
class DrillDownRequest(BaseModel):
    hierarchy: Dict[str, Any]
    current_level: int
    filters: Optional[Dict[str, Any]] = None

class DrillDownResponse(BaseModel):
    data: List[Dict[str, Any]]
    level: int
    field: str
    aggregation_type: str
    total_records: int
    can_drill_down: bool
    can_drill_up: bool

# KPI Schemas
class KPICard(BaseModel):
    title: str
    value: str
    trend: str
    change: float
    description: str

# Upload Schemas
class UploadResponse(BaseModel):
    dataset_id: str
    message: str
    metadata: DatasetMetadata

# File-based Dataset Schemas
class DatasetFileInfo(BaseModel):
    file_id: str
    original_filename: str
    file_path: str
    file_size: int
    storage_type: str  # "database" or "file"
    upload_date: datetime

class DatasetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    file_id: str
    original_filename: str
    file_size: int
    storage_type: str

class DatasetFile(DatasetFileInfo):
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    columns: Optional[List[str]] = None
    data_types: Optional[Dict[str, str]] = None
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    preview_data: Optional[List[Dict[str, Any]]] = None
    sample_data: Optional[List[Dict[str, Any]]] = None
    last_accessed: Optional[datetime] = None
    is_processed: bool = False

    class Config:
        from_attributes = True

class DatasetData(BaseModel):
    data: List[Dict[str, Any]]
    total_rows: int
    current_page: int
    page_size: int
    has_more: bool

class DatasetSummary(BaseModel):
    total_rows: int
    total_columns: int
    numeric_columns: List[str]
    categorical_columns: List[str]
    missing_values: Dict[str, int]
    data_types: Dict[str, str]
    basic_stats: Optional[Dict[str, Any]] = None

# User Authentication Schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(UserBase):
    id: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

class TokenData(BaseModel):
    email: Optional[str] = None

class UserProfileUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

# Error Schemas
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: str


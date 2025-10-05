from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum


class DatasetUpload(BaseModel):
    filename: str
    size: int
    content_type: str


class DatasetInfo(BaseModel):
    id: str
    filename: str
    size: int
    row_count: int
    column_count: int
    upload_date: datetime
    columns: List[Dict[str, Any]]
    summary_stats: Dict[str, Any]


class ColumnInfo(BaseModel):
    name: str
    dtype: str
    null_count: int
    unique_count: int
    sample_values: List[Any]
    is_numeric: bool
    is_temporal: bool
    is_categorical: bool


class VisualizationRecommendation(BaseModel):
    chart_type: str
    title: str
    description: str
    fields: List[str]
    reasoning: str
    insights: str


class LLMRequest(BaseModel):
    dataset_id: str
    query: str
    context: Optional[str] = None


class LLMResponse(BaseModel):
    response: str
    confidence: float
    reasoning: str
    suggested_actions: List[str]


class DashboardTemplate(BaseModel):
    id: str
    name: str
    description: str
    template_type: str
    layout: List[Dict[str, Any]]
    recommended_datasets: List[str]
    features: Dict[str, Any]


class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    database: str
    llm_service: str
    version: str = "1.0.0"


# Authentication Models
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserInDB(UserBase):
    id: str
    hashed_password: str
    created_at: datetime
    last_login: Optional[datetime] = None


class UserResponse(UserBase):
    id: str
    created_at: datetime
    last_login: Optional[datetime] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    user_id: Optional[str] = None



from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class _Config:
    orm_mode = True
    extra = "forbid"
    arbitrary_types_allowed = True


class DatasetInfo(BaseModel):
    id: str
    filename: str
    total_rows: int
    total_columns: int
    columns: List[str]
    uploaded_at: str

    class Config(_Config):
        pass


class DatasetMetadata(BaseModel):
    dataset_overview: Dict[str, Any]
    column_metadata: List[Dict[str, Any]]
    statistical_summaries: Dict[str, Any]
    data_quality: Dict[str, Any]
    chart_recommendations: List[Dict[str, Any]]
    hierarchies: List[Dict[str, Any]]

    class Config(_Config):
        pass


class DatasetData(BaseModel):
    data: List[Dict[str, Any]]
    total_rows: int
    current_page: int
    page_size: int
    has_more: bool

    class Config(_Config):
        pass


class DatasetSummary(BaseModel):
    total_rows: int
    total_columns: int
    numeric_columns: List[str]
    categorical_columns: List[str]
    missing_values: Dict[str, int]
    data_types: Dict[str, str]
    basic_stats: Optional[Dict[str, Any]] = None

    class Config(_Config):
        pass


class DatasetFileInfo(BaseModel):
    file_id: str
    original_filename: str
    file_path: str
    file_size: int
    storage_type: str
    upload_date: datetime

    class Config(_Config):
        pass


class DatasetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    file_id: str
    original_filename: str
    file_size: int
    storage_type: str

    class Config(_Config):
        pass


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

    class Config(_Config):
        pass


class UploadResponse(BaseModel):
    dataset_id: str
    message: str
    metadata: DatasetMetadata

    class Config(_Config):
        pass


class DatasetAnalytics(BaseModel):
    dataset_id: str
    user_id: str
    chart_recommendations: Optional[List[Dict[str, Any]]] = []
    statistical_findings: Optional[List[Dict[str, Any]]] = []
    deep_analysis: Optional[Dict[str, Any]] = {}
    data_profile: Optional[Dict[str, Any]] = {}
    domain_intelligence: Optional[Dict[str, Any]] = {}
    data_quality: Optional[Dict[str, Any]] = {}
    computed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    pipeline_version: Optional[str] = None

    class Config(_Config):
        pass


class DatasetAnalyticsResponse(BaseModel):
    dataset_id: str
    chart_recommendations: List[Dict[str, Any]]
    statistical_findings: List[Dict[str, Any]]
    deep_analysis: Dict[str, Any]
    data_profile: Dict[str, Any]
    domain_intelligence: Dict[str, Any]
    data_quality: Dict[str, Any]
    computed_at: datetime

    class Config(_Config):
        pass


class ReportMetadata(BaseModel):
    dataset_id: str
    user_id: str
    title: Optional[str] = None
    generated_at: Optional[datetime] = None
    include_charts: bool = True
    status: str = "pending"
    findings_count: int = 0
    warnings_count: int = 0
    charts_included: Optional[List[str]] = []
    domain: Optional[str] = None
    file_size: Optional[int] = None
    analytics_version: Optional[str] = None
    analytics_computed_at: Optional[datetime] = None

    class Config(_Config):
        pass


class ReportMetadataResponse(BaseModel):
    id: str
    dataset_id: str
    title: Optional[str]
    generated_at: Optional[datetime]
    include_charts: bool
    status: str
    findings_count: int
    warnings_count: int
    domain: Optional[str]
    file_size: Optional[int]

    class Config(_Config):
        pass


__all__ = [
    "DatasetInfo",
    "DatasetMetadata",
    "DatasetData",
    "DatasetFileInfo",
    "DatasetCreate",
    "DatasetFile",
    "DatasetSummary",
    "UploadResponse",
    "DatasetAnalytics",
    "DatasetAnalyticsResponse",
    "ReportMetadata",
    "ReportMetadataResponse",
]

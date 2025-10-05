from fastapi import HTTPException, UploadFile, Depends
from typing import List, Dict, Any, Optional
import pandas as pd
import uuid
from datetime import datetime
import logging
import numpy as np
from database import get_database
from models.schemas import (
    DatasetCreate, DatasetFile, DatasetData, DatasetSummary,
    DatasetMetadata, ChartRequest, ChartResponse, KPICard, UploadResponse
)
from services.auth_service import get_current_user
from services.file_storage_service import file_storage_service
import io

logger = logging.getLogger(__name__)

class EnhancedDatasetService:
    def __init__(self):
        self.db = None
    
    def _get_db(self):
        """Get database connection"""
        if self.db is None:
            self.db = get_database()
        return self.db
    
    def _convert_numpy_types(self, obj):
        """Convert numpy types to Python native types recursively"""
        if isinstance(obj, dict):
            return {k: self._convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            val = float(obj)
            # Handle NaN and infinity values
            if np.isnan(val) or np.isinf(val):
                return None
            return val
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, float):
            # Handle regular Python floats that might be NaN
            if np.isnan(obj) or np.isinf(obj):
                return None
            return obj
        else:
            return obj
    
    async def upload_dataset(self, file: UploadFile, user_id: str, name: str = None, description: str = None) -> Dict[str, Any]:
        """Upload and process a dataset with file storage"""
        try:
            # Read file content
            file_content = await file.read()
            
            # Use file storage service
            file_metadata = await file_storage_service.save_file(
                file_content, 
                file.filename, 
                user_id
            )
            
            # Generate dataset ID
            dataset_id = str(uuid.uuid4())
            
            # Create dataset document
            dataset_doc = {
                "_id": dataset_id,
                "user_id": user_id,
                "name": name or file.filename.split('.')[0],
                "description": description or "",
                "file_id": file_metadata["file_id"],
                "original_filename": file_metadata["original_filename"],
                "file_path": file_metadata["file_path"],
                "file_size": file_metadata["file_size"],
                "storage_type": file_metadata["storage_type"],
                "file_extension": file_metadata["file_extension"],
                "upload_date": file_metadata["upload_date"],
                "last_accessed": None,
                "is_processed": False,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Add preview data if available
            if file_metadata.get("preview_data"):
                dataset_doc.update({
                    "columns": file_metadata["columns"],
                    "data_types": file_metadata["data_types"],
                    "row_count": file_metadata["row_count"],
                    "column_count": file_metadata["column_count"],
                    "preview_data": file_metadata["preview_data"],
                    "sample_data": file_metadata["sample_data"]
                })
            
            # Store dataset metadata in MongoDB
            db = self._get_db()
            result = await db.datasets.insert_one(dataset_doc)
            
            # Convert _id to id for response
            dataset_doc["id"] = str(result.inserted_id)
            dataset_doc.pop("_id", None)
            
            # Generate additional metadata for small datasets
            if file_metadata["storage_type"] == "database":
                metadata = await self._generate_metadata(file_metadata["file_path"])
                # Convert numpy types before storing
                metadata = self._convert_numpy_types(metadata)
                await db.datasets.update_one(
                    {"_id": result.inserted_id},
                    {"$set": {"metadata": metadata, "is_processed": True}}
                )
            
            logger.info(f"Dataset uploaded successfully: {dataset_id}")
            
            # Create metadata object
            metadata = DatasetMetadata(
                dataset_overview={
                    "total_rows": file_metadata.get("row_count", 0),
                    "total_columns": file_metadata.get("column_count", 0),
                    "numeric_columns": 0,
                    "categorical_columns": 0,
                    "missing_values": 0,
                    "duplicate_rows": 0
                },
                column_metadata=[
                    {"name": col, "type": "unknown", "null_count": 0, "null_percentage": 0.0, "unique_count": 0}
                    for col in file_metadata.get("columns", [])
                ],
                statistical_summaries={},
                data_quality={
                    "completeness": 100.0,
                    "uniqueness": 100.0,
                    "consistency": 85.0,
                    "accuracy": 90.0
                },
                chart_recommendations=[],
                hierarchies=[]
            )
            
            # Return simple dict response
            return {
                "dataset_id": dataset_id,
                "message": "Dataset uploaded successfully",
                "metadata": {
                    "dataset_overview": metadata.dataset_overview,
                    "column_metadata": metadata.column_metadata,
                    "statistical_summaries": metadata.statistical_summaries,
                    "data_quality": metadata.data_quality,
                    "chart_recommendations": metadata.chart_recommendations,
                    "hierarchies": metadata.hierarchies
                }
            }
            
        except Exception as e:
            logger.error(f"Error uploading dataset: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload dataset: {str(e)}"
            )
    
    async def _generate_metadata(self, file_path: str) -> Dict[str, Any]:
        """Generate metadata for small datasets stored in database"""
        try:
            # Read the file to generate metadata
            file_extension = file_path.split('.')[-1].lower()
            
            if file_extension == 'csv':
                df = pd.read_csv(file_path)
            elif file_extension in ['xlsx', 'xls']:
                # Try to read Excel file with different engines
                try:
                    df = pd.read_excel(file_path, engine='openpyxl')
                except Exception as e:
                    logger.warning(f"Failed to read Excel with openpyxl: {e}")
                    try:
                        df = pd.read_excel(file_path, engine='xlrd')
                    except Exception as e2:
                        logger.error(f"Failed to read Excel with xlrd: {e2}")
                        return {}
                
                # Handle NaT values in datetime columns
                for col in df.columns:
                    if df[col].dtype == 'datetime64[ns]':
                        # Replace NaT values with None to avoid utcoffset issues
                        df[col] = df[col].where(pd.notna(df[col]), None)
            elif file_extension == 'json':
                df = pd.read_json(file_path)
            else:
                return {}
            
            # Basic statistics
            numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
            categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
            
            # Dataset overview - ensure all values are Python native types
            dataset_overview = {
                "total_rows": int(len(df)),
                "total_columns": int(len(df.columns)),
                "numeric_columns": int(len(numeric_columns)),
                "categorical_columns": int(len(categorical_columns)),
                "missing_values": int(df.isnull().sum().sum()),
                "duplicate_rows": int(df.duplicated().sum())
            }
            
            # Column metadata
            column_metadata = []
            for col in df.columns:
                col_info = {
                    "name": col,
                    "type": str(df[col].dtype),
                    "null_count": int(df[col].isnull().sum()),
                    "null_percentage": float((df[col].isnull().sum() / len(df)) * 100),
                    "unique_count": int(df[col].nunique())
                }
                
                # Add type-specific statistics
                if col in numeric_columns:
                    col_info.update({
                        "min": float(df[col].min()) if not df[col].isnull().all() else None,
                        "max": float(df[col].max()) if not df[col].isnull().all() else None,
                        "mean": float(df[col].mean()) if not df[col].isnull().all() else None,
                        "std": float(df[col].std()) if not df[col].isnull().all() else None,
                        "median": float(df[col].median()) if not df[col].isnull().all() else None
                    })
                elif col in categorical_columns:
                    col_info.update({
                        "top_values": {k: int(v) for k, v in df[col].value_counts().head(5).to_dict().items()},
                        "most_common": str(df[col].mode().iloc[0]) if not df[col].mode().empty else None
                    })
                
                column_metadata.append(col_info)
            
            # Statistical summaries
            statistical_summaries = {}
            if numeric_columns:
                # Convert numpy types to Python native types
                desc = df[numeric_columns].describe()
                statistical_summaries["numeric_summary"] = {
                    col: {stat: float(val) for stat, val in stats.items()}
                    for col, stats in desc.to_dict().items()
                }
            
            # Data quality assessment
            data_quality = {
                "completeness": float((1 - df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100),
                "uniqueness": float((1 - df.duplicated().sum() / len(df)) * 100),
                "consistency": 85.0,  # Placeholder
                "accuracy": 90.0     # Placeholder
            }
            
            # Chart recommendations
            chart_recommendations = self._generate_chart_recommendations(df, numeric_columns, categorical_columns)
            
            # Hierarchy detection
            hierarchies = self._detect_hierarchies(df)
            
            metadata = {
                "dataset_overview": dataset_overview,
                "column_metadata": column_metadata,
                "statistical_summaries": statistical_summaries,
                "data_quality": data_quality,
                "chart_recommendations": chart_recommendations,
                "hierarchies": hierarchies
            }
            
            # Convert all numpy types to Python native types
            return self._convert_numpy_types(metadata)
            
        except Exception as e:
            logger.error(f"Error generating metadata: {e}")
            return {}
    
    def _generate_chart_recommendations(self, df: pd.DataFrame, numeric_cols: List[str], categorical_cols: List[str]) -> List[Dict[str, Any]]:
        """Generate chart recommendations based on data types"""
        recommendations = []
        
        # Bar chart for categorical data
        if categorical_cols:
            for col in categorical_cols[:3]:
                recommendations.append({
                    "chart_type": "bar",
                    "title": f"Distribution of {col}",
                    "description": f"Shows the frequency distribution of {col}",
                    "suitable_columns": [col],
                    "confidence": "high"
                })
        
        # Line chart for time series data
        date_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
        if date_cols and numeric_cols:
            for date_col in date_cols[:1]:
                for num_col in numeric_cols[:2]:
                    recommendations.append({
                        "chart_type": "line",
                        "title": f"{num_col} over {date_col}",
                        "description": f"Shows trend of {num_col} over time",
                        "suitable_columns": [date_col, num_col],
                        "confidence": "high"
                    })
        
        # Scatter plot for numeric relationships
        if len(numeric_cols) >= 2:
            recommendations.append({
                "chart_type": "scatter",
                "title": f"{numeric_cols[0]} vs {numeric_cols[1]}",
                "description": f"Shows relationship between {numeric_cols[0]} and {numeric_cols[1]}",
                "suitable_columns": numeric_cols[:2],
                "confidence": "high"
            })
        
        return recommendations
    
    def _detect_hierarchies(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect potential hierarchies in the data"""
        hierarchies = []
        
        # Date hierarchy detection
        date_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
        if date_cols:
            hierarchies.append({
                "type": "temporal",
                "field": date_cols[0],
                "levels": ["year", "month", "day"],
                "confidence": "high"
            })
        
        # Geographic hierarchy detection
        geo_keywords = ['country', 'state', 'city', 'region', 'area', 'location']
        for col in df.columns:
            if any(keyword in col.lower() for keyword in geo_keywords):
                hierarchies.append({
                    "type": "geographic",
                    "field": col,
                    "levels": ["country", "state", "city"],
                    "confidence": "medium"
                })
                break
        
        return hierarchies
    
    async def get_user_datasets(self, user_id: str, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Get datasets for a specific user"""
        try:
            db = self._get_db()
            cursor = db.datasets.find(
                {"user_id": user_id, "is_active": True}
            ).sort("created_at", -1).skip(skip).limit(limit)
            
            datasets = []
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                doc.pop("_id", None)
                # Convert numpy types before returning
                doc = self._convert_numpy_types(doc)
                datasets.append(doc)
            
            return datasets
            
        except Exception as e:
            logger.error(f"Error getting user datasets: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve datasets"
            )
    
    async def get_dataset(self, dataset_id: str, user_id: str) -> Dict[str, Any]:
        """Get a specific dataset"""
        try:
            db = self._get_db()
            dataset = await db.datasets.find_one({
                "_id": dataset_id,
                "user_id": user_id,
                "is_active": True
            })
            
            if not dataset:
                raise HTTPException(
                    status_code=404,
                    detail="Dataset not found"
                )
            
            # Update last accessed
            await db.datasets.update_one(
                {"_id": dataset_id},
                {"$set": {"last_accessed": datetime.utcnow()}}
            )
            
            dataset["id"] = str(dataset["_id"])
            dataset.pop("_id", None)
            return dataset
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting dataset: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve dataset"
            )
    
    async def get_dataset_data(self, dataset_id: str, user_id: str, page: int = 1, page_size: int = 100) -> DatasetData:
        """Get dataset data with pagination"""
        try:
            # Get dataset info
            dataset = await self.get_dataset(dataset_id, user_id)
            
            if dataset["storage_type"] == "database":
                # Data is stored in MongoDB
                db = self._get_db()
                data_collection = db[f"dataset_{dataset_id}_data"]
                
                skip = (page - 1) * page_size
                cursor = data_collection.find({}).skip(skip).limit(page_size)
                
                data = []
                async for doc in cursor:
                    doc.pop("_id", None)
                    data.append(doc)
                
                total_rows = await data_collection.count_documents({})
                
            else:
                # Data is stored as file
                data = await file_storage_service.get_file_data(
                    dataset["file_path"], 
                    limit=page_size
                )
                total_rows = dataset.get("row_count", len(data))
            
            has_more = (page * page_size) < total_rows
            
            return DatasetData(
                data=data,
                total_rows=total_rows,
                current_page=page,
                page_size=page_size,
                has_more=has_more
            )
            
        except Exception as e:
            logger.error(f"Error getting dataset data: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve dataset data"
            )
    
    async def get_dataset_summary(self, dataset_id: str, user_id: str) -> DatasetSummary:
        """Get dataset summary statistics"""
        try:
            dataset = await self.get_dataset(dataset_id, user_id)
            
            if dataset["storage_type"] == "database" and dataset.get("metadata"):
                # Use pre-computed metadata
                overview = dataset["metadata"]["dataset_overview"]
                column_metadata = dataset["metadata"]["column_metadata"]
                
                numeric_columns = [col["name"] for col in column_metadata if col["type"] in ["int64", "float64"]]
                categorical_columns = [col["name"] for col in column_metadata if col["type"] in ["object", "category"]]
                
                missing_values = {col["name"]: col["null_count"] for col in column_metadata}
                data_types = {col["name"]: col["type"] for col in column_metadata}
                
                return DatasetSummary(
                    total_rows=overview["total_rows"],
                    total_columns=overview["total_columns"],
                    numeric_columns=numeric_columns,
                    categorical_columns=categorical_columns,
                    missing_values=missing_values,
                    data_types=data_types,
                    basic_stats=dataset["metadata"].get("statistical_summaries", {})
                )
            else:
                # For file-based storage, we need to read the file
                # This is a simplified version - in production, you'd want to cache this
                return DatasetSummary(
                    total_rows=dataset.get("row_count", 0),
                    total_columns=dataset.get("column_count", 0),
                    numeric_columns=[],
                    categorical_columns=[],
                    missing_values={},
                    data_types={}
                )
                
        except Exception as e:
            logger.error(f"Error getting dataset summary: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve dataset summary"
            )
    
    async def delete_dataset(self, dataset_id: str, user_id: str) -> bool:
        """Permanently delete a dataset and its associated files"""
        try:
            # Get dataset info first
            dataset = await self.get_dataset(dataset_id, user_id)
            
            # Delete file from storage
            if dataset.get("file_id") and dataset.get("file_extension"):
                await file_storage_service.delete_file(
                    dataset["file_id"], user_id, dataset["file_extension"]
                )
            
            # Permanently delete from database
            db = self._get_db()
            result = await db.datasets.delete_one(
                {"_id": dataset_id, "user_id": user_id}
            )
            
            if result.deleted_count == 0:
                raise HTTPException(
                    status_code=404,
                    detail="Dataset not found or not owned by user"
                )
            
            # Delete related data collections if they exist
            if dataset.get("storage_type") == "database":
                try:
                    await db[f"dataset_{dataset_id}_data"].drop()
                except Exception as e:
                    logger.warning(f"Could not drop data collection for dataset {dataset_id}: {e}")
            
            logger.info(f"Dataset permanently deleted: {dataset_id}")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting dataset: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to delete dataset"
            )

# Create enhanced dataset service instance
enhanced_dataset_service = EnhancedDatasetService()

from fastapi import HTTPException, UploadFile, Depends
from typing import List, Dict, Any, Optional
import pandas as pd
import uuid
from datetime import datetime
import logging
from database import get_database
from models.schemas import DatasetInfo, DatasetMetadata
from services.auth_service import get_current_user
from services.file_upload_service import file_upload_service
import io

logger = logging.getLogger(__name__)

class DatasetService:
    def __init__(self):
        self.db = None
    
    def _get_db(self):
        """Get database connection"""
        if self.db is None:
            self.db = get_database()
        return self.db
    
    async def upload_dataset(self, file: UploadFile, user_id: str) -> Dict[str, Any]:
        """Upload and process a dataset"""
        try:
            # Use enhanced file upload service
            file_info = await file_upload_service.save_file(file, user_id)
            
            # Parse file based on extension
            if file_info["file_extension"] == 'csv':
                df = pd.read_csv(file_info["file_path"])
            elif file_info["file_extension"] in ['xlsx', 'xls']:
                df = pd.read_excel(file_info["file_path"])
                
                # Handle NaT values in datetime columns
                for col in df.columns:
                    if df[col].dtype == 'datetime64[ns]':
                        # Replace NaT values with None to avoid utcoffset issues
                        df[col] = df[col].where(pd.notna(df[col]), None)
            elif file_info["file_extension"] == 'json':
                df = pd.read_json(file_info["file_path"])
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported file format"
                )
            
            # Generate dataset ID
            dataset_id = str(uuid.uuid4())
            
            # Create dataset document
            dataset_doc = {
                "_id": dataset_id,
                "user_id": user_id,
                "filename": file_info["filename"],
                "original_filename": file_info["original_filename"],
                "file_path": file_info["file_path"],
                "file_size": file_info["file_size"],
                "mime_type": file_info["mime_type"],
                "file_extension": file_info["file_extension"],
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "columns": df.columns.tolist(),
                "column_types": df.dtypes.astype(str).to_dict(),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "is_active": True,
                "metadata": {}
            }
            
            # Store dataset metadata
            db = self._get_db()
            await db.datasets.insert_one(dataset_doc)
            
            # Generate metadata
            metadata = await self._generate_metadata(df, dataset_id)
            
            # Update dataset with metadata
            await db.datasets.update_one(
                {"_id": dataset_id},
                {"$set": {"metadata": metadata}}
            )
            
            logger.info(f"Dataset uploaded successfully: {dataset_id}")
            
            return {
                "dataset_id": dataset_id,
                "filename": file.filename,
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "columns": df.columns.tolist(),
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Error uploading dataset: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload dataset: {str(e)}"
            )
    
    async def _generate_metadata(self, df: pd.DataFrame, dataset_id: str) -> Dict[str, Any]:
        """Generate metadata for the dataset"""
        try:
            # Basic statistics
            numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
            categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
            
            # Dataset overview
            dataset_overview = {
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "numeric_columns": len(numeric_columns),
                "categorical_columns": len(categorical_columns),
                "missing_values": df.isnull().sum().sum(),
                "duplicate_rows": df.duplicated().sum()
            }
            
            # Column metadata
            column_metadata = []
            for col in df.columns:
                col_info = {
                    "name": col,
                    "type": str(df[col].dtype),
                    "null_count": df[col].isnull().sum(),
                    "null_percentage": (df[col].isnull().sum() / len(df)) * 100,
                    "unique_count": df[col].nunique()
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
                        "top_values": df[col].value_counts().head(5).to_dict(),
                        "most_common": df[col].mode().iloc[0] if not df[col].mode().empty else None
                    })
                
                column_metadata.append(col_info)
            
            # Statistical summaries
            statistical_summaries = {}
            if numeric_columns:
                statistical_summaries["numeric_summary"] = df[numeric_columns].describe().to_dict()
            
            # Data quality assessment
            data_quality = {
                "completeness": (1 - df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100,
                "uniqueness": (1 - df.duplicated().sum() / len(df)) * 100,
                "consistency": 85.0,  # Placeholder - would need domain-specific rules
                "accuracy": 90.0     # Placeholder - would need validation rules
            }
            
            # Chart recommendations
            chart_recommendations = self._generate_chart_recommendations(df, numeric_columns, categorical_columns)
            
            # Hierarchy detection
            hierarchies = self._detect_hierarchies(df)
            
            return {
                "dataset_overview": dataset_overview,
                "column_metadata": column_metadata,
                "statistical_summaries": statistical_summaries,
                "data_quality": data_quality,
                "chart_recommendations": chart_recommendations,
                "hierarchies": hierarchies
            }
            
        except Exception as e:
            logger.error(f"Error generating metadata: {e}")
            return {}
    
    def _generate_chart_recommendations(self, df: pd.DataFrame, numeric_cols: List[str], categorical_cols: List[str]) -> List[Dict[str, Any]]:
        """Generate chart recommendations based on data types"""
        recommendations = []
        
        # Bar chart for categorical data
        if categorical_cols:
            for col in categorical_cols[:3]:  # Limit to first 3 categorical columns
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
        
        # Pie chart for categorical data with few categories
        for col in categorical_cols:
            if df[col].nunique() <= 10:
                recommendations.append({
                    "chart_type": "pie",
                    "title": f"Proportion of {col}",
                    "description": f"Shows the proportion of different {col} values",
                    "suitable_columns": [col],
                    "confidence": "medium"
                })
                break
        
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
        
        # Geographic hierarchy detection (basic)
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
        
        # Categorical hierarchy detection
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        for col in categorical_cols:
            if df[col].nunique() > 5 and df[col].nunique() < 50:
                hierarchies.append({
                    "type": "categorical",
                    "field": col,
                    "levels": ["category", "subcategory"],
                    "confidence": "low"
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
    
    async def delete_dataset(self, dataset_id: str, user_id: str) -> bool:
        """Delete a dataset"""
        try:
            db = self._get_db()
            result = await db.datasets.update_one(
                {"_id": dataset_id, "user_id": user_id},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            
            if result.matched_count == 0:
                raise HTTPException(
                    status_code=404,
                    detail="Dataset not found"
                )
            
            # Also delete related charts and insights
            await db.charts.update_many(
                {"dataset_id": dataset_id, "user_id": user_id},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            
            await db.insights.update_many(
                {"dataset_id": dataset_id, "user_id": user_id},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            
            logger.info(f"Dataset deleted: {dataset_id}")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting dataset: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to delete dataset"
            )

# Create dataset service instance
dataset_service = DatasetService()



# services/rag/chunk_service.py
"""
Intelligent Chunking Service
============================
Creates semantic chunks from dataset metadata for vector retrieval.

Chunk Types:
1. Schema Chunk - High-level dataset overview
2. Column Chunks - Individual column metadata + statistics
3. Sample Chunks - Representative data rows
4. Relationship Chunks - Column correlations and patterns
"""

import logging
from typing import Dict, List, Any, Optional, TYPE_CHECKING
import json
import hashlib

# Polars is optional - only used for sample chunk extraction
if TYPE_CHECKING:
    import polars as pl

logger = logging.getLogger(__name__)


class ChunkService:
    """
    Creates intelligent, semantic chunks from dataset metadata and data.
    Designed for RAG retrieval to provide relevant context to LLMs.
    """
    
    # Chunk type identifiers
    CHUNK_SCHEMA = "schema"
    CHUNK_COLUMN = "column"
    CHUNK_SAMPLE = "sample"
    CHUNK_RELATIONSHIP = "relationship"
    CHUNK_STATISTICS = "statistics"
    
    def __init__(self):
        self.max_sample_rows = 10
        self.max_chunk_tokens = 500  # Approximate token limit per chunk
    
    def create_chunks_from_metadata(
        self, 
        dataset_id: str,
        metadata: Dict[str, Any],
        df: Optional[Any] = None  # pl.DataFrame at runtime
    ) -> List[Dict[str, Any]]:
        """
        Create all chunk types from dataset metadata.
        
        Args:
            dataset_id: Unique dataset identifier
            metadata: Dataset metadata dict (from enhanced_dataset_service)
            df: Optional DataFrame for sample extraction
            
        Returns:
            List of chunk dicts with 'content', 'chunk_type', 'metadata'
        """
        chunks = []
        
        # 1. Schema chunk - high-level overview
        schema_chunk = self._create_schema_chunk(dataset_id, metadata)
        if schema_chunk:
            chunks.append(schema_chunk)
        
        # 2. Column chunks - one per column
        column_chunks = self._create_column_chunks(dataset_id, metadata)
        chunks.extend(column_chunks)
        
        # 3. Statistics chunk - aggregated dataset statistics
        stats_chunk = self._create_statistics_chunk(dataset_id, metadata)
        if stats_chunk:
            chunks.append(stats_chunk)
        
        # 4. Sample chunks - representative data rows
        if df is not None:
            sample_chunks = self._create_sample_chunks(dataset_id, df, metadata)
            chunks.extend(sample_chunks)
        
        # 5. Relationship chunks - correlations and patterns
        relationship_chunks = self._create_relationship_chunks(dataset_id, metadata)
        chunks.extend(relationship_chunks)
        
        # Add chunk IDs
        for i, chunk in enumerate(chunks):
            chunk["chunk_id"] = self._generate_chunk_id(dataset_id, chunk["chunk_type"], i)
            chunk["dataset_id"] = dataset_id
        
        logger.info(f"Created {len(chunks)} chunks for dataset {dataset_id}")
        return chunks
    
    def _create_schema_chunk(
        self, 
        dataset_id: str, 
        metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create high-level schema overview chunk."""
        try:
            overview = metadata.get("dataset_overview", {})
            columns = metadata.get("column_metadata", [])
            
            # Build concise schema description
            content_parts = [
                f"Dataset: {overview.get('name', 'Unknown')}",
                f"Domain: {overview.get('domain', 'General')}",
                f"Rows: {overview.get('total_rows', 0):,}",
                f"Columns: {overview.get('total_columns', 0)}",
                "",
                "Column Overview:",
            ]
            
            for col in columns[:20]:  # Limit to prevent token explosion
                col_name = col.get("name", "unknown")
                col_type = col.get("type", "unknown")
                content_parts.append(f"  - {col_name} ({col_type})")
            
            if len(columns) > 20:
                content_parts.append(f"  ... and {len(columns) - 20} more columns")
            
            return {
                "content": "\n".join(content_parts),
                "chunk_type": self.CHUNK_SCHEMA,
                "metadata": {
                    "total_rows": overview.get("total_rows", 0),
                    "total_columns": overview.get("total_columns", 0),
                    "domain": overview.get("domain", "General")
                }
            }
        except Exception as e:
            logger.warning(f"Failed to create schema chunk: {e}")
            return None
    
    def _create_column_chunks(
        self, 
        dataset_id: str, 
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Create individual chunks for each column."""
        chunks = []
        columns = metadata.get("column_metadata", [])
        
        for col in columns:
            try:
                col_name = col.get("name", "unknown")
                col_type = col.get("type", "unknown")
                
                content_parts = [
                    f"Column: {col_name}",
                    f"Type: {col_type}",
                ]
                
                # Add statistics if available
                if "null_count" in col:
                    content_parts.append(f"Null Count: {col['null_count']}")
                if "unique_count" in col:
                    content_parts.append(f"Unique Values: {col['unique_count']}")
                if "min" in col:
                    content_parts.append(f"Min: {col['min']}")
                if "max" in col:
                    content_parts.append(f"Max: {col['max']}")
                if "mean" in col:
                    content_parts.append(f"Mean: {col['mean']:.2f}")
                if "std" in col:
                    content_parts.append(f"Std Dev: {col['std']:.2f}")
                if "sample_values" in col:
                    samples = col["sample_values"][:5]
                    content_parts.append(f"Sample Values: {samples}")
                if "top_values" in col:
                    top = col["top_values"][:5] if isinstance(col["top_values"], list) else []
                    content_parts.append(f"Top Values: {top}")
                
                chunks.append({
                    "content": "\n".join(content_parts),
                    "chunk_type": self.CHUNK_COLUMN,
                    "metadata": {
                        "column_name": col_name,
                        "column_type": col_type,
                        "is_numeric": col_type in ["Int64", "Float64", "Int32", "Float32"],
                        "is_categorical": col_type in ["Utf8", "Categorical", "String"]
                    }
                })
            except Exception as e:
                logger.warning(f"Failed to create column chunk for {col.get('name')}: {e}")
                continue
        
        return chunks
    
    def _create_statistics_chunk(
        self, 
        dataset_id: str, 
        metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create aggregated statistics chunk."""
        try:
            quality = metadata.get("data_quality", {})
            overview = metadata.get("dataset_overview", {})
            
            content_parts = [
                "Dataset Statistics:",
                f"Total Rows: {overview.get('total_rows', 0):,}",
                f"Total Columns: {overview.get('total_columns', 0)}",
            ]
            
            if quality:
                content_parts.extend([
                    f"Completeness: {quality.get('completeness', 0):.1%}",
                    f"Missing Values: {quality.get('missing_values', 0):,}",
                    f"Duplicate Rows: {quality.get('duplicate_rows', 0):,}",
                ])
            
            # Add column type breakdown
            columns = metadata.get("column_metadata", [])
            numeric_cols = [c for c in columns if c.get("type") in ["Int64", "Float64", "Int32", "Float32"]]
            categorical_cols = [c for c in columns if c.get("type") in ["Utf8", "Categorical", "String"]]
            
            content_parts.extend([
                "",
                "Column Type Breakdown:",
                f"  Numeric Columns: {len(numeric_cols)}",
                f"  Categorical Columns: {len(categorical_cols)}",
                f"  Other: {len(columns) - len(numeric_cols) - len(categorical_cols)}",
            ])
            
            return {
                "content": "\n".join(content_parts),
                "chunk_type": self.CHUNK_STATISTICS,
                "metadata": {
                    "numeric_columns": len(numeric_cols),
                    "categorical_columns": len(categorical_cols)
                }
            }
        except Exception as e:
            logger.warning(f"Failed to create statistics chunk: {e}")
            return None
    
    def _create_sample_chunks(
        self, 
        dataset_id: str, 
        df: Any,  # pl.DataFrame at runtime
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Create chunks with sample data rows."""
        chunks = []
        
        try:
            # Get stratified sample if possible
            sample_df = df.head(self.max_sample_rows)
            
            # Convert to readable format
            rows_content = []
            for i, row in enumerate(sample_df.iter_rows(named=True)):
                row_str = ", ".join([f"{k}={v}" for k, v in list(row.items())[:8]])
                rows_content.append(f"Row {i+1}: {row_str}")
            
            if rows_content:
                chunks.append({
                    "content": "Sample Data Rows:\n" + "\n".join(rows_content),
                    "chunk_type": self.CHUNK_SAMPLE,
                    "metadata": {
                        "sample_count": len(rows_content)
                    }
                })
        except Exception as e:
            logger.warning(f"Failed to create sample chunks: {e}")
        
        return chunks
    
    def _create_relationship_chunks(
        self, 
        dataset_id: str, 
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Create chunks for column relationships and correlations."""
        chunks = []
        
        try:
            correlations = metadata.get("correlations", [])
            
            if correlations:
                content_parts = ["Column Correlations:"]
                for corr in correlations[:10]:  # Limit to top correlations
                    if isinstance(corr, dict):
                        col1 = corr.get("column1", "?")
                        col2 = corr.get("column2", "?")
                        value = corr.get("correlation", 0)
                        content_parts.append(f"  {col1} ↔ {col2}: {value:.3f}")
                
                if content_parts:
                    chunks.append({
                        "content": "\n".join(content_parts),
                        "chunk_type": self.CHUNK_RELATIONSHIP,
                        "metadata": {
                            "correlation_count": len(correlations)
                        }
                    })
        except Exception as e:
            logger.warning(f"Failed to create relationship chunks: {e}")
        
        return chunks
    
    def _generate_chunk_id(
        self, 
        dataset_id: str, 
        chunk_type: str, 
        index: int
    ) -> str:
        """Generate unique chunk ID."""
        content = f"{dataset_id}:{chunk_type}:{index}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def get_chunk_for_embedding(self, chunk: Dict[str, Any]) -> str:
        """Get the text content to embed for a chunk."""
        return chunk.get("content", "")
    
    def filter_chunks_by_type(
        self, 
        chunks: List[Dict[str, Any]], 
        chunk_types: List[str]
    ) -> List[Dict[str, Any]]:
        """Filter chunks by type."""
        return [c for c in chunks if c.get("chunk_type") in chunk_types]


# Singleton instance
chunk_service = ChunkService()

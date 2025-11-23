"""
Data Profiling Service
======================
Comprehensive data profiling for intelligent analysis:
- Cardinality analysis (unique values, distribution)
- Pattern detection (email, phone, URL, ID patterns)
- Data quality metrics (nulls, completeness, consistency)
- Relationship inference (potential foreign keys, hierarchies)

Author: DataSage AI Team
Version: 1.0
"""

import logging
import re
from typing import Dict, List, Any
import polars as pl

logger = logging.getLogger(__name__)


class DataProfiler:
    """
    Advanced data profiling for intelligent dataset analysis.
    """
    
    # Pattern detection regex
    PATTERNS = {
        "email": r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        "phone": r'^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}$',
        "url": r'^https?://[^\s]+$',
        "zip_code": r'^\d{5}(-\d{4})?$',
        "uuid": r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        "ip_address": r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$',
        "credit_card": r'^\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}$',
        "ssn": r'^\d{3}-\d{2}-\d{4}$'
    }
    
    def profile_dataset(self, df: pl.DataFrame, column_metadata: List[Dict]) -> Dict[str, Any]:
        """
        Comprehensive dataset profiling.
        
        Args:
            df: Polars DataFrame
            column_metadata: Column metadata
        
        Returns:
            Dict with profiling results (cardinality, patterns, quality, relationships)
        """
        logger.info("Starting comprehensive data profiling...")
        
        profile = {
            "row_count": len(df),
            "column_count": len(column_metadata),
            "cardinality": {},
            "patterns": {},
            "quality_metrics": {},
            "relationships": {},
            "id_columns": [],
            "high_cardinality_dims": [],
            "low_cardinality_dims": []
        }
        
        # Profile each column
        for col_meta in column_metadata:
            col_name = col_meta["name"]
            col_type = col_meta["type"]
            
            try:
                # Get column data
                col_data = df.select(col_name).to_series()
                
                # Cardinality analysis
                profile["cardinality"][col_name] = self._analyze_cardinality(col_data, col_name)
                
                # Pattern detection (for string columns)
                if "str" in col_type.lower() or "utf8" in col_type.lower():
                    profile["patterns"][col_name] = self._detect_patterns(col_data, col_name)
                
                # Quality metrics
                profile["quality_metrics"][col_name] = self._calculate_quality_metrics(col_data)
                
            except Exception as e:
                logger.warning(f"Error profiling column {col_name}: {e}")
                continue
        
        # Identify special column types
        profile["id_columns"] = self._identify_id_columns(profile["cardinality"], profile["patterns"])
        profile["high_cardinality_dims"] = self._identify_high_cardinality_dims(profile["cardinality"], len(df))
        profile["low_cardinality_dims"] = self._identify_low_cardinality_dims(profile["cardinality"], len(df))
        
        # Infer relationships (potential foreign keys, hierarchies)
        profile["relationships"] = self._infer_relationships(df, column_metadata, profile["cardinality"])
        
        logger.info(f"Profiling complete: {profile['column_count']} columns, {profile['row_count']} rows")
        return profile
    
    def _analyze_cardinality(self, col_data: pl.Series, col_name: str) -> Dict[str, Any]:
        """Analyze column cardinality (unique values, distribution)."""
        total_count = len(col_data)
        unique_count = col_data.n_unique()
        null_count = col_data.null_count()
        
        # Calculate cardinality ratio
        cardinality_ratio = unique_count / max(total_count - null_count, 1)
        
        # Categorize cardinality
        if cardinality_ratio >= 0.95:
            cardinality_level = "very_high"  # Likely ID or unique identifier
        elif cardinality_ratio >= 0.5:
            cardinality_level = "high"  # Many unique values (e.g., names, addresses)
        elif cardinality_ratio >= 0.1:
            cardinality_level = "medium"  # Some repeating values (e.g., cities, products)
        else:
            cardinality_level = "low"  # Few unique values (e.g., categories, status)
        
        return {
            "unique_count": unique_count,
            "total_count": total_count,
            "null_count": null_count,
            "cardinality_ratio": round(cardinality_ratio, 4),
            "cardinality_level": cardinality_level
        }
    
    def _detect_patterns(self, col_data: pl.Series, col_name: str) -> Dict[str, Any]:
        """Detect common data patterns (email, phone, URL, etc.)."""
        # Sample up to 100 non-null values
        sample = col_data.drop_nulls().head(100).to_list()
        
        if not sample:
            return {"detected_patterns": [], "pattern_confidence": 0.0}
        
        detected_patterns = []
        
        for pattern_name, pattern_regex in self.PATTERNS.items():
            matches = sum(1 for val in sample if isinstance(val, str) and re.match(pattern_regex, val.strip(), re.IGNORECASE))
            match_ratio = matches / len(sample)
            
            if match_ratio >= 0.7:  # 70% match threshold
                detected_patterns.append({
                    "pattern": pattern_name,
                    "confidence": round(match_ratio, 2)
                })
        
        # Check for ID-like patterns
        if col_name.lower().endswith("_id") or col_name.lower() == "id":
            detected_patterns.append({"pattern": "id_column", "confidence": 0.9})
        
        return {
            "detected_patterns": detected_patterns,
            "pattern_confidence": max([p["confidence"] for p in detected_patterns], default=0.0)
        }
    
    def _calculate_quality_metrics(self, col_data: pl.Series) -> Dict[str, Any]:
        """Calculate data quality metrics."""
        total_count = len(col_data)
        null_count = col_data.null_count()
        
        # Completeness
        completeness = (total_count - null_count) / max(total_count, 1)
        
        # Empty string count (for string columns)
        empty_count = 0
        if col_data.dtype == pl.Utf8 or col_data.dtype == pl.String:
            try:
                empty_count = (col_data == "").sum() + (col_data == " ").sum()
            except:
                pass
        
        # Effective completeness (excluding nulls and empty strings)
        effective_completeness = (total_count - null_count - empty_count) / max(total_count, 1)
        
        quality_score = effective_completeness  # Simple quality score
        
        return {
            "completeness": round(completeness, 4),
            "effective_completeness": round(effective_completeness, 4),
            "null_count": null_count,
            "empty_count": empty_count,
            "quality_score": round(quality_score, 4)
        }
    
    def _identify_id_columns(self, cardinality: Dict, patterns: Dict) -> List[str]:
        """Identify potential ID columns (primary keys, unique identifiers)."""
        id_columns = []
        
        for col_name, card_info in cardinality.items():
            # Check cardinality (very high = likely ID)
            if card_info["cardinality_level"] == "very_high":
                id_columns.append(col_name)
            
            # Check pattern detection
            if col_name in patterns:
                pattern_types = [p["pattern"] for p in patterns[col_name].get("detected_patterns", [])]
                if "id_column" in pattern_types or "uuid" in pattern_types:
                    if col_name not in id_columns:
                        id_columns.append(col_name)
        
        return id_columns
    
    def _identify_high_cardinality_dims(self, cardinality: Dict, row_count: int) -> List[str]:
        """Identify high-cardinality dimensions (not good for grouping)."""
        threshold = 0.5  # > 50% unique values
        return [
            col for col, info in cardinality.items()
            if info["cardinality_ratio"] > threshold and info["cardinality_level"] in ["high", "very_high"]
        ]
    
    def _identify_low_cardinality_dims(self, cardinality: Dict, row_count: int) -> List[str]:
        """Identify low-cardinality dimensions (good for grouping)."""
        threshold = 0.1  # < 10% unique values
        return [
            col for col, info in cardinality.items()
            if info["cardinality_ratio"] < threshold and info["cardinality_level"] == "low"
        ]
    
    def _infer_relationships(
        self, 
        df: pl.DataFrame, 
        column_metadata: List[Dict], 
        cardinality: Dict
    ) -> Dict[str, Any]:
        """
        Infer potential relationships between columns:
        - Foreign key candidates (columns with matching value sets)
        - Hierarchies (e.g., Country -> State -> City)
        - Derived columns (e.g., Full Name = First Name + Last Name)
        """
        relationships = {
            "foreign_keys": [],
            "hierarchies": [],
            "derived_columns": []
        }
        
        # Identify potential foreign keys (columns ending with _id that reference other columns)
        id_suffix_cols = [col for col in df.columns if col.lower().endswith("_id")]
        
        for id_col in id_suffix_cols:
            # Try to find referenced column (e.g., customer_id -> customer)
            base_name = id_col[:-3]  # Remove "_id"
            
            # Look for columns with similar names
            potential_refs = [col for col in df.columns if base_name.lower() in col.lower() and col != id_col]
            
            if potential_refs:
                relationships["foreign_keys"].append({
                    "foreign_key": id_col,
                    "potential_references": potential_refs[:3]
                })
        
        # Identify potential hierarchies (columns with nested relationships)
        # Example: Country -> State -> City (State cardinality < Country cardinality)
        hierarchy_keywords = [
            ["country", "state", "city"],
            ["category", "subcategory", "product"],
            ["department", "team", "employee"],
            ["year", "quarter", "month", "day"]
        ]
        
        for hierarchy in hierarchy_keywords:
            hierarchy_cols = []
            for level in hierarchy:
                matching_cols = [col for col in df.columns if level in col.lower()]
                if matching_cols:
                    hierarchy_cols.append(matching_cols[0])
            
            if len(hierarchy_cols) >= 2:
                relationships["hierarchies"].append({
                    "hierarchy": hierarchy_cols,
                    "description": f"Potential hierarchy: {' -> '.join(hierarchy_cols)}"
                })
        
        return relationships


# Singleton instance
data_profiler = DataProfiler()

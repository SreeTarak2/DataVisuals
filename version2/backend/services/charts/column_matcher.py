"""
Column Matcher Service
======================
Provides intelligent column matching for chart generation.

Handles cases where LLM suggests column names that don't exactly match
the dataset columns (case variations, spaces vs underscores, synonyms).

Author: DataSage AI Team
"""

import logging
from typing import List, Tuple, Optional, Dict, Any
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class ColumnMatcher:
    """
    Match LLM-suggested columns to actual dataset columns using multiple strategies:
    
    1. Exact match
    2. Case-insensitive match
    3. Underscore/space normalization
    4. Fuzzy string matching (SequenceMatcher)
    5. Common synonym matching
    """
    
    # Common synonyms for column names
    SYNONYMS = {
        # Date/Time
        "date": ["timestamp", "datetime", "created_at", "updated_at", "time", "day", "month", "year"],
        "timestamp": ["date", "datetime", "created_at", "time"],
        
        # Financial
        "revenue": ["sales", "income", "amount", "total", "value", "gmv", "earnings"],
        "sales": ["revenue", "amount", "total", "gmv"],
        "price": ["cost", "amount", "value", "unit_price"],
        "profit": ["margin", "earnings", "net_income"],
        
        # Quantity
        "quantity": ["count", "qty", "num", "number", "units", "volume"],
        "count": ["quantity", "total", "num", "number"],
        
        # Categories
        "category": ["type", "group", "segment", "class", "kind"],
        "product": ["item", "sku", "name", "product_name"],
        "region": ["location", "area", "territory", "zone", "country", "state", "city"],
        "customer": ["user", "client", "buyer", "account"],
        
        # Identifiers
        "id": ["_id", "identifier", "key", "code"],
        "name": ["title", "label", "description"],
    }
    
    @classmethod
    def match(cls, suggested: str, available: List[str], threshold: float = 0.6) -> Tuple[Optional[str], float]:
        """
        Find the best matching column from available columns.
        
        Args:
            suggested: Column name suggested by LLM
            available: List of actual column names in dataset
            threshold: Minimum similarity threshold (0.0-1.0)
            
        Returns:
            Tuple of (matched_column, confidence_score)
            Returns (None, 0.0) if no match found above threshold
        """
        if not suggested or not available:
            return None, 0.0
        
        # 1. Exact match
        if suggested in available:
            logger.debug(f"Exact match found: {suggested}")
            return suggested, 1.0
        
        # 2. Case-insensitive match
        suggested_lower = suggested.lower()
        for col in available:
            if col.lower() == suggested_lower:
                logger.debug(f"Case-insensitive match: {suggested} → {col}")
                return col, 0.98
        
        # 3. Normalized match (spaces, underscores, hyphens)
        suggested_normalized = cls._normalize(suggested)
        for col in available:
            if cls._normalize(col) == suggested_normalized:
                logger.debug(f"Normalized match: {suggested} → {col}")
                return col, 0.95
        
        # 4. Synonym match
        for col in available:
            if cls._is_synonym(suggested, col):
                logger.debug(f"Synonym match: {suggested} → {col}")
                return col, 0.85
        
        # 5. Fuzzy string matching
        best_match = None
        best_score = 0.0
        
        for col in available:
            # Try both original and normalized versions
            scores = [
                SequenceMatcher(None, suggested_lower, col.lower()).ratio(),
                SequenceMatcher(None, suggested_normalized, cls._normalize(col)).ratio(),
            ]
            score = max(scores)
            
            if score > best_score:
                best_score = score
                best_match = col
        
        if best_score >= threshold:
            logger.debug(f"Fuzzy match: {suggested} → {best_match} (score: {best_score:.2f})")
            return best_match, best_score
        
        logger.warning(f"No match found for column: {suggested} (best: {best_match} @ {best_score:.2f})")
        return None, 0.0
    
    @classmethod
    def match_multiple(cls, suggested_columns: List[str], available: List[str], threshold: float = 0.6) -> Dict[str, Tuple[Optional[str], float]]:
        """
        Match multiple suggested columns to available columns.
        
        Returns:
            Dict mapping suggested → (matched, confidence)
        """
        results = {}
        for suggested in suggested_columns:
            results[suggested] = cls.match(suggested, available, threshold)
        return results
    
    @classmethod
    def validate_and_fix_chart_config(
        cls, 
        chart_config: Dict[str, Any], 
        available_columns: List[str],
        threshold: float = 0.6
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Validate and auto-correct column references in a chart config.
        
        Args:
            chart_config: Chart configuration from LLM
            available_columns: List of actual columns in dataset
            threshold: Minimum similarity for column matching
            
        Returns:
            Tuple of (fixed_config, list_of_corrections_made)
        """
        corrections = []
        fixed_config = chart_config.copy()
        
        # Column fields to check
        column_fields = ["x", "y", "labels", "values", "column", "group_by", "color", "size"]
        
        for field in column_fields:
            if field in fixed_config:
                original = fixed_config[field]
                
                # Skip if it's not a string (could be a list or dict)
                if not isinstance(original, str):
                    continue
                
                # Skip special values
                if original.lower() in ["count", "sum", "average", "mean", "max", "min"]:
                    continue
                
                # Try to match
                matched, confidence = cls.match(original, available_columns, threshold)
                
                if matched and matched != original:
                    fixed_config[field] = matched
                    corrections.append(f"{field}: '{original}' → '{matched}' (confidence: {confidence:.0%})")
                elif not matched and original not in available_columns:
                    corrections.append(f"{field}: '{original}' → NOT FOUND (below threshold)")
        
        if corrections:
            logger.info(f"Chart config corrections: {corrections}")
        
        return fixed_config, corrections
    
    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize column name for comparison."""
        return text.lower().replace(" ", "_").replace("-", "_").replace(".", "_").strip("_")
    
    @classmethod
    def _is_synonym(cls, word1: str, word2: str) -> bool:
        """Check if two words are synonyms based on our synonym table."""
        w1 = cls._normalize(word1)
        w2 = cls._normalize(word2)
        
        # Check both directions
        for base, synonyms in cls.SYNONYMS.items():
            all_related = [base] + synonyms
            all_related_normalized = [cls._normalize(s) for s in all_related]
            
            if w1 in all_related_normalized and w2 in all_related_normalized:
                return True
        
        return False


# Singleton instance
column_matcher = ColumnMatcher()

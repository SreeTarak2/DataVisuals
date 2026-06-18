"""
Schema Profiler - Extracts column metadata from any dataset
=============================================================

This is the foundation of entity extraction - it profiles columns to understand
their structure, types, and statistical properties.

Supports: CSV, Excel, SQL result sets, pandas DataFrames
"""

import logging
import math
import re
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

from .models import ColumnProfile, SchemaProfile

logger = logging.getLogger(__name__)


class SchemaProfilingError(Exception):
    """Raised when schema profiling fails"""

    pass


class SchemaProfiler:
    """
    Profiles dataset schemas to extract column metadata.

    This is the foundation for entity extraction - without understanding
    column structure, we cannot classify entities.
    """

    # Common date/time patterns for detection
    DATE_PATTERNS = [
        r"^\d{4}-\d{2}-\d{2}$",  # 2024-01-15
        r"^\d{2}/\d{2}/\d{4}$",  # 01/15/2024
        r"^\d{2}-\d{2}-\d{4}$",  # 15-01-2024
        r"^\d{4}/\d{2}/\d{2}$",  # 2024/01/15
    ]

    # UUID pattern
    UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

    def __init__(self, sample_size: int = 100):
        """
        Initialize schema profiler.

        Args:
            sample_size: Number of rows to sample for profiling
        """
        self.sample_size = sample_size

    async def profile_columns(
        self,
        columns: List[Dict[str, Any]],
        rows: List[Dict[str, Any]],
        table_name: str = "unknown",
    ) -> SchemaProfile:
        """
        Profile all columns from a dataset.

        Args:
            columns: List of column definitions with 'name' and optionally 'type'
            rows: List of row data (dictionaries)
            table_name: Name of the table/file

        Returns:
            SchemaProfile with all column profiles
        """
        try:
            row_count = len(rows)

            # Sample rows for large datasets
            sampled_rows = self._sample_rows(rows)

            # Build column profiles
            column_profiles = []
            for col_def in columns:
                col_name = col_def.get("name", "")
                inferred_type = col_def.get("type", "unknown")

                # Get column values from rows
                values = [row.get(col_name) for row in sampled_rows if col_name in row]

                # Profile the column
                profile = self._profile_column(
                    column_name=col_name,
                    values=values,
                    inferred_type=inferred_type,
                    total_rows=row_count,
                )
                column_profiles.append(profile)

            return SchemaProfile(
                table_name=table_name, columns=column_profiles, row_count=row_count
            )

        except Exception as e:
            logger.error(f"Schema profiling failed for {table_name}: {e}")
            raise SchemaProfilingError(f"Failed to profile schema: {e}") from e

    def _sample_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sample rows if dataset is large"""
        if len(rows) <= self.sample_size:
            return rows

        # Stratified sampling - take from start, middle, end
        n = self.sample_size
        total = len(rows)

        if total <= n:
            return rows

        # Take every nth row for均匀 distribution
        step = total // n
        indices = list(range(0, total, step))[:n]

        return [rows[i] for i in indices]

    def _profile_column(
        self, column_name: str, values: List[Any], inferred_type: str, total_rows: int
    ) -> ColumnProfile:
        """Profile a single column"""

        # Filter out None values for analysis
        non_null_values = [v for v in values if v is not None]

        # Calculate null ratio
        null_count = len(values) - len(non_null_values)
        null_ratio = null_count / len(values) if values else 1.0

        # Get distinct values
        distinct_values = set(non_null_values)
        distinct_count = len(distinct_values)
        distinct_ratio = (
            distinct_count / len(non_null_values) if non_null_values else 0.0
        )

        # Detect data type from values if not provided
        detected_type = self._detect_data_type(non_null_values, inferred_type)

        # Check if unique (likely primary key)
        is_unique = (
            distinct_ratio == 1.0 and null_ratio == 0.0 and len(non_null_values) > 1
        )
        is_primary_key = is_unique and self._looks_like_id(column_name, non_null_values)

        # Get sample values (up to 5 diverse samples)
        sample_values = self._get_samples(non_null_values, 5)

        # Calculate numeric stats if applicable
        min_value, max_value = None, None
        if detected_type in ("integer", "decimal"):
            numeric_values = [v for v in non_null_values if isinstance(v, (int, float))]
            if numeric_values:
                min_value = min(numeric_values)
                max_value = max(numeric_values)

        # Calculate average string length
        avg_length = None
        if detected_type == "string":
            str_lengths = [len(str(v)) for v in non_null_values if v]
            if str_lengths:
                avg_length = sum(str_lengths) / len(str_lengths)

        return ColumnProfile(
            name=column_name,
            data_type=detected_type,
            null_ratio=null_ratio,
            distinct_count=distinct_count,
            distinct_ratio=distinct_ratio,
            sample_values=sample_values,
            is_unique=is_unique,
            is_primary_key=is_primary_key,
            min_value=min_value,
            max_value=max_value,
            avg_length=avg_length,
        )

    def _detect_data_type(self, values: List[Any], inferred_type: str) -> str:
        """Detect data type from values"""

        if not values:
            return "unknown"

        # If already specified and valid, use it
        if inferred_type and inferred_type != "unknown":
            return inferred_type

        # Analyze first non-null values
        sample = values[: min(100, len(values))]

        # Check for boolean
        bool_values = {"true", "false", "yes", "no", "1", "0", "y", "n"}
        if all(str(v).lower() in bool_values or v is None for v in sample):
            return "boolean"

        # Check for numeric
        numeric_count = 0
        for v in sample:
            if isinstance(v, (int, float)):
                numeric_count += 1
            elif isinstance(v, str):
                try:
                    float(v.replace(",", ""))
                    numeric_count += 1
                except (ValueError, AttributeError):
                    pass

        if numeric_count / len(sample) > 0.8:
            # Check if decimal or integer
            has_decimal = any("." in str(v) for v in sample)
            return "decimal" if has_decimal else "integer"

        # Check for date
        date_like_count = 0
        for v in sample:
            if isinstance(v, str):
                if any(re.match(p, v) for p in self.DATE_PATTERNS):
                    date_like_count += 1
                elif self._looks_like_date(v):
                    date_like_count += 1
            elif isinstance(v, datetime):
                date_like_count += 1

        if date_like_count / len(sample) > 0.8:
            return "timestamp"

        # Check for UUID
        uuid_count = 0
        for v in sample:
            if isinstance(v, str) and re.match(self.UUID_PATTERN, v.lower()):
                uuid_count += 1

        if uuid_count / len(sample) > 0.8:
            return "uuid"

        return "string"

    def _looks_like_id(self, column_name: str, values: List[Any]) -> bool:
        """Check if column name suggests an ID"""
        name_lower = column_name.lower()
        id_patterns = ["_id", "key", "pk", "code", "uuid", "no", "number"]

        # Check name patterns
        if any(p in name_lower for p in id_patterns):
            return True

        # Check if values look like IDs (short strings with pattern)
        if values:
            sample = str(values[0])
            # IDs typically are alphanumeric, not too long
            if len(sample) < 50 and re.match(r"^[a-zA-Z0-9_-]+$", sample):
                return True

        return False

    def _looks_like_date(self, value: str) -> bool:
        """Check if string looks like a date"""
        if not isinstance(value, str):
            return False

        # Common date formats
        date_formats = [
            r"\d{4}-\d{2}-\d{2}",  # 2024-01-15
            r"\d{2}/\d{2}/\d{4}",  # 01/15/2024
            r"\d{2}-\d{2}-\d{4}",  # 15-01-2024
            r"\d{4}/\d{2}/\d{2}",  # 2024/01/15
            r"\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
        ]

        return any(re.match(p, value.lower()) for p in date_formats)

    def _get_samples(self, values: List[Any], count: int) -> List[str]:
        """Get diverse sample values"""
        if not values:
            return []

        # Convert to strings and limit length
        samples = []
        for v in values[: count * 2]:
            s = str(v)[:100]  # Truncate long values
            if s not in samples:
                samples.append(s)
            if len(samples) >= count:
                break

        return samples

    async def profile_from_dataframe(
        self, df: Any, table_name: str = "dataframe"
    ) -> SchemaProfile:
        """
        Profile from a pandas DataFrame.

        Args:
            df: pandas DataFrame
            table_name: Name for the profile

        Returns:
            SchemaProfile
        """
        try:
            import pandas as pd

            # Get column definitions
            columns = [
                {"name": col, "type": str(dtype)} for col, dtype in df.dtypes.items()
            ]

            # Get row data (limited sample)
            rows = df.head(self.sample_size).to_dict("records")

            return await self.profile_columns(columns, rows, table_name)

        except ImportError:
            raise SchemaProfilingError("pandas required for DataFrame profiling")
        except Exception as e:
            raise SchemaProfilingError(f"DataFrame profiling failed: {e}") from e

    async def profile_from_csv(
        self, csv_path: str, table_name: Optional[str] = None
    ) -> SchemaProfile:
        """
        Profile from a CSV file.

        Args:
            csv_path: Path to CSV file
            table_name: Optional table name (defaults to filename)

        Returns:
            SchemaProfile
        """
        try:
            import pandas as pd

            df = pd.read_csv(csv_path, nrows=self.sample_size)

            if table_name is None:
                import os

                table_name = os.path.splitext(os.path.basename(csv_path))[0]

            return await self.profile_from_dataframe(df, table_name)

        except Exception as e:
            raise SchemaProfilingError(f"CSV profiling failed: {e}") from e


# Singleton instance
schema_profiler = SchemaProfiler()

__all__ = ["SchemaProfiler", "SchemaProfilingError", "schema_profiler"]

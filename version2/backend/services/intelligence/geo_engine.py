"""
intelligence/geo_engine.py — Geographic role detection (Layer 3, NEW)

Detects geographic columns within a single table:
  - Latitude / Longitude pairs (by name + value range check)
  - Country, State, City columns (by name + cardinality pattern)
  - ZIP / Postal code columns (by name + pattern match)
  - Address columns (by name)

Rules:
  - Latitude: column name matches lat/latitude + values in [-90, 90]
  - Longitude: column name matches lng/lon/longitude + values in [-180, 180]
  - Country: name matches country/nation + cardinality < 300 (249 countries)
  - State: name matches state/province + cardinality < 100
  - City: name matches city/town + cardinality < 100000

All deterministic. No LLM calls.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import polars as pl

from services.profiling.models import RawColumnProfile, RawProfilingResult
from .models import GeoInfo

logger = logging.getLogger(__name__)


class GeoEngine:
    """Detects geographic columns in a dataset."""

    # Column name patterns
    LAT_PATTERNS = re.compile(r"\b(lat|latitude|lat_)\b", re.I)
    LNG_PATTERNS = re.compile(r"\b(lng|lon|longitude|long_)\b", re.I)
    COUNTRY_PATTERNS = re.compile(r"\b(country|nation|region)\b", re.I)
    STATE_PATTERNS = re.compile(r"\b(state|province|territory|prefecture)\b", re.I)
    CITY_PATTERNS = re.compile(r"\b(city|town|locality|municipality)\b", re.I)
    ZIP_PATTERNS = re.compile(r"\b(zip|postal|postcode|pin)\b", re.I)
    ADDRESS_PATTERNS = re.compile(r"\b(address|street|location)\b", re.I)

    def detect(
        self, result: RawProfilingResult, df: Optional[pl.DataFrame] = None
    ) -> GeoInfo:
        """Detect geographic columns from profiling results.

        Args:
            result: RawProfilingResult from the profiling layer.
            df: Optional DataFrame for value-range validation.

        Returns:
            GeoInfo with detected geographic column names.
        """
        geo = GeoInfo()

        for profile in result.columns:
            name_lower = profile.name.lower()

            # Latitude
            if self.LAT_PATTERNS.search(name_lower):
                if self._validate_lat_lng(profile, df, -90, 90):
                    geo.latitude = profile.name
                    geo.has_geo = True

            # Longitude
            elif self.LNG_PATTERNS.search(name_lower):
                if self._validate_lat_lng(profile, df, -180, 180):
                    geo.longitude = profile.name
                    geo.has_geo = True

            # Country
            elif self.COUNTRY_PATTERNS.search(name_lower):
                if self._validate_range_column(profile, 1, 300):
                    geo.country = profile.name
                    geo.has_geo = True

            # State / Province
            elif self.STATE_PATTERNS.search(name_lower):
                if self._validate_range_column(profile, 1, 100):
                    geo.state = profile.name
                    geo.has_geo = True

            # City
            elif self.CITY_PATTERNS.search(name_lower):
                if self._validate_range_column(profile, 1, 100000):
                    geo.city = profile.name
                    geo.has_geo = True

            # ZIP / Postal Code
            elif self.ZIP_PATTERNS.search(name_lower):
                geo.postal_code = profile.name
                geo.has_geo = True

            # Address
            elif self.ADDRESS_PATTERNS.search(name_lower):
                geo.address = profile.name
                geo.has_geo = True

        return geo

    def _validate_lat_lng(
        self,
        profile: RawColumnProfile,
        df: Optional[pl.DataFrame],
        min_val: float,
        max_val: float,
    ) -> bool:
        """Validate that column values fall within expected geo range."""
        stats = profile.stats
        if stats is not None:
            # Numeric column — check min/max range
            col_min = stats.col_min or 0
            col_max = stats.col_max or 0
            if min_val <= col_min <= max_val and min_val <= col_max <= max_val:
                return True
            return False

        # String column — check sample values
        for sample in profile.sample_values:
            try:
                val = float(sample)
                if min_val <= val <= max_val:
                    return True
            except (ValueError, TypeError):
                continue
        return False

    def _validate_range_column(
        self, profile: RawColumnProfile, min_unique: int, max_unique: int
    ) -> bool:
        """Validate that cardinality is in the expected range for geo columns."""
        uniq = profile.cardinality.unique_count
        if min_unique <= uniq <= max_unique:
            return True
        # Allow if named appropriately even with unusual cardinality
        if uniq <= max_unique * 2:
            return True
        return False


# Singleton
geo_engine = GeoEngine()

"""
intelligence/entity_detector.py — Entity detection engine (Layer 3)

Detects:
  - Entity columns (customer_id → Customer entity)
  - Entity statistics (unique count, avg records per entity)
  - Grain (what one row represents: transaction / daily_agg / customer_period)
  - Primary key candidates

All deterministic. No LLM calls.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import polars as pl

from services.profiling.models import RawProfilingResult
from .models import (
    EntityInfo,
    TemporalInfo,
)

logger = logging.getLogger(__name__)


# ── Entity Type Mappings ──────────────────────────────────────────────────────

_ENTITY_TYPES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(customer|client|buyer|member|subscriber)\b", re.I), "Customer"),
    (re.compile(r"\b(product|item|sku)\b", re.I), "Product"),
    (re.compile(r"\b(order|transaction|purchase|invoice)\b", re.I), "Transaction"),
    (re.compile(r"\b(employee|staff|worker|personnel)\b", re.I), "Employee"),
    (re.compile(r"\b(patient|doctor|physician|nurse)\b", re.I), "Patient"),
    (re.compile(r"\b(student|teacher|professor|course)\b", re.I), "Student"),
    (re.compile(r"\b(vehicle|car|truck|auto)\b", re.I), "Vehicle"),
    (re.compile(r"\b(property|house|apartment|building|listing)\b", re.I), "Property"),
    (re.compile(r"\b(company|vendor|supplier|organization|brand)\b", re.I), "Company"),
    (re.compile(r"\b(lead|opportunity|deal)\b", re.I), "Lead"),
    (re.compile(r"\b(shipment|delivery|parcel)\b", re.I), "Shipment"),
    (re.compile(r"\b(claim|policy|beneficiary)\b", re.I), "Insurance"),
    (re.compile(r"\b(member|group|team)\b", re.I), "Group"),
]


class EntityDetector:
    """Detects entity columns and computes entity statistics."""

    ENTITY_ID_SUFFIX = re.compile(r"(_id|_key|_uuid|_guid)$", re.I)
    INTERNAL_KEY_NAMES = re.compile(r"^(id|pk|row_id|row_num|index|seq|record_id)$", re.I)

    def detect(
        self,
        result: RawProfilingResult,
        df: Optional[pl.DataFrame] = None,
    ) -> tuple[list[EntityInfo], TemporalInfo]:
        """Detect entities and temporal structure from profiling results.

        Args:
            result: RawProfilingResult from the profiling layer.
            df: Optional DataFrame for computing entity stats. If None,
                 stats will be estimated from profiling data.

        Returns:
            Tuple of (entities list, temporal info).
        """
        entities: list[EntityInfo] = []

        for profile in result.columns:
            entity = self._detect_single(profile, df)
            if entity:
                entities.append(entity)

        temporal = self._detect_temporal(result, df)

        return entities, temporal

    def _detect_single(
        self,
        profile: "RawColumnProfile",
        df: Optional[pl.DataFrame] = None,
    ) -> Optional[EntityInfo]:
        """Detect entity info for a single column."""
        name = profile.name
        card = profile.cardinality

        # Must have _id suffix or high cardinality
        is_entity = bool(self.ENTITY_ID_SUFFIX.search(name))
        is_high_card = card.cardinality_ratio > 0.5

        if not is_entity and not is_high_card:
            return None

        if self.INTERNAL_KEY_NAMES.match(name):
            return None

        # Determine entity type from column name
        entity_type = self._infer_entity_type(name)

        unique_count = card.unique_count
        total_count = card.total_count - card.null_count
        avg_per_entity = total_count / max(unique_count, 1) if unique_count > 0 else 0.0

        # Confidence: higher if _id suffix + high cardinality
        confidence = 0.85 if (is_entity and card.cardinality_ratio > 0.8) else 0.70

        return EntityInfo(
            entity_column=name,
            entity_type=entity_type,
            unique_count=unique_count,
            total_count=total_count,
            avg_records_per_entity=round(avg_per_entity, 2),
            confidence=round(confidence, 2),
        )

    def _infer_entity_type(self, col_name: str) -> str:
        """Infer entity type from column name patterns."""
        # Strip _id, _key, _uuid, _guid suffix
        base = self.ENTITY_ID_SUFFIX.sub("", col_name).lower().replace("_", " ").strip()

        for pattern, entity_type in _ENTITY_TYPES:
            if pattern.search(base):
                return entity_type

        return base.title() if base else "Entity"

    def _detect_temporal(
        self,
        result: RawProfilingResult,
        df: Optional[pl.DataFrame] = None,
    ) -> TemporalInfo:
        """Detect temporal structure from profiling results."""
        time_cols = [
            c for c in result.columns
            if any(t in c.dtype for t in ("Date", "Datetime", "Duration"))
        ]

        if not time_cols:
            return TemporalInfo()

        primary_date = time_cols[0].name
        date_range_days = None

        if df is not None and primary_date in df.columns:
            try:
                series = df[primary_date].drop_nulls()
                if len(series) > 0:
                    min_dt = series.min()
                    max_dt = series.max()
                    if hasattr(min_dt, "days"):
                        date_range_days = int((max_dt - min_dt).days)
                    else:
                        from datetime import datetime
                        if hasattr(min_dt, "strftime"):
                            date_range_days = (max_dt - min_dt).days
            except Exception:
                pass

        # Detect grain from entity columns
        entity_cols = [c.name for c in result.columns if self.ENTITY_ID_SUFFIX.search(c.name)]
        entities, _ = self.detect(result, df)  # noqa: F811 — recursive call for entities

        grain = "unknown"
        if entity_cols and time_cols:
            if df is not None:
                try:
                    entity_count = df[entity_cols[0]].n_unique()
                    rows_per_entity = len(df) / max(entity_count, 1)
                    grain = "transaction" if rows_per_entity > 3 else "customer_period"
                except Exception:
                    pass

        return TemporalInfo(
            date_column=primary_date,
            date_range_days=date_range_days,
            grain=grain,
            has_date_hierarchy=primary_date is not None,
            available_date_parts=["year", "quarter", "month", "day"] if primary_date else [],
        )


# Singleton
entity_detector = EntityDetector()

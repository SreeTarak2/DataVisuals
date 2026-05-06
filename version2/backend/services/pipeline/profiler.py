import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Optional

import polars as pl

from db.schemas_pipeline import (
    ColumnProfile,
    DatasetProfile,
    SemanticRole,
    StructureFlags,
)

logger = logging.getLogger(__name__)

_MARGIN_KEYWORDS = re.compile(r"discount|margin|markup|rebate", re.I)
_STAGE_KEYWORDS = re.compile(r"stage|funnel|step|phase", re.I)
_INTERNAL_KEY_NAMES = re.compile(r"^(id|pk|row_id|row_num|index|seq|record_id)$", re.I)
_ENTITY_ID_SUFFIX = re.compile(r"(_id|_key|_uuid|_guid)$", re.I)
_TIME_KEYWORDS = re.compile(r"date|time|timestamp|period|month|year|created|updated", re.I)
_MEASURE_EXCLUDE = re.compile(r"(_id|_key|_uuid|count$|rank$|index$|_num$|_no$)", re.I)

_NUMERIC_DTYPES: tuple = ()
_STRING_DTYPES: tuple = ()
_TEMPORAL_DTYPES: tuple = ()


def _dtype_sets() -> None:
    global _NUMERIC_DTYPES, _STRING_DTYPES, _TEMPORAL_DTYPES
    _NUMERIC_DTYPES = tuple(pl.NUMERIC_DTYPES)
    _STRING_DTYPES = (pl.Utf8, pl.String) if hasattr(pl, "String") else (pl.Utf8,)
    _TEMPORAL_DTYPES = (pl.Date,)


_dtype_sets()


def _is_numeric(dtype: pl.DataType) -> bool:
    return dtype in pl.NUMERIC_DTYPES


def _is_string(dtype: pl.DataType) -> bool:
    base = (pl.Utf8,)
    if hasattr(pl, "String"):
        base = (pl.Utf8, pl.String)
    return dtype in base or str(dtype) in ("Utf8", "String", "Categorical")


def _is_temporal(dtype: pl.DataType) -> bool:
    return dtype == pl.Date or str(dtype).startswith(("Datetime", "Duration", "Time"))


def _looks_like_timestamp(sample_values: list[str]) -> bool:
    if not sample_values:
        return False
    try:
        datetime.fromisoformat(sample_values[0].replace("Z", "+00:00"))
        return True
    except (ValueError, TypeError):
        return False


def _detect_semantic(
    col_name: str,
    dtype: pl.DataType,
    cardinality: int,
    row_count: int,
    null_rate: float,
    sample_values: list[str],
) -> SemanticRole:
    effective_rows = max(row_count - round(null_rate * row_count), 1)
    cardinality_ratio = cardinality / effective_rows

    if _is_temporal(dtype):
        return SemanticRole.time

    if _is_string(dtype) and _TIME_KEYWORDS.search(col_name) and _looks_like_timestamp(sample_values):
        return SemanticRole.time

    if _is_numeric(dtype):
        if _INTERNAL_KEY_NAMES.match(col_name):
            return SemanticRole.internal_key
        if _MEASURE_EXCLUDE.search(col_name):
            return SemanticRole.internal_key
        return SemanticRole.measure

    if _is_string(dtype):
        if _INTERNAL_KEY_NAMES.match(col_name) and cardinality_ratio > 0.95:
            return SemanticRole.internal_key
        if _ENTITY_ID_SUFFIX.search(col_name) and cardinality_ratio > 0.5:
            return SemanticRole.entity_id
        if cardinality_ratio < 0.1 and cardinality <= 100:
            return SemanticRole.dimension
        if cardinality_ratio > 0.5:
            return SemanticRole.entity_id

    return SemanticRole.unknown


def _detect_grain(
    df: pl.DataFrame,
    time_cols: list[str],
    entity_cols: list[str],
) -> str:
    if not time_cols or not entity_cols:
        return "unknown"
    try:
        entity_count = df[entity_cols[0]].n_unique()
        rows_per_entity = len(df) / max(entity_count, 1)
        return "transaction" if rows_per_entity > 3 else "customer_period"
    except Exception:
        return "unknown"


def _date_range_days(df: pl.DataFrame, time_cols: list[str]) -> Optional[int]:
    if not time_cols:
        return None
    col = time_cols[0]
    try:
        series = df[col].drop_nulls()
        if len(series) == 0:
            return None
        min_val = series.min()
        max_val = series.max()
        if hasattr(min_val, "days"):
            return int((max_val - min_val).days)
        min_dt = datetime.fromisoformat(str(min_val).replace("Z", "+00:00").split(".")[0])
        max_dt = datetime.fromisoformat(str(max_val).replace("Z", "+00:00").split(".")[0])
        return (max_dt - min_dt).days
    except Exception:
        return None


async def profile_dataframe(
    df: pl.DataFrame,
    domain_signal: str = "general",
    domain_confidence: float = 0.5,
    source_type: str = "file",
) -> DatasetProfile:
    row_count = len(df)
    columns: list[ColumnProfile] = []

    for col_name in df.columns:
        series = df[col_name]
        dtype = series.dtype
        null_count = series.null_count()
        null_rate = null_count / max(row_count, 1)
        cardinality = series.n_unique()
        effective_rows = max(row_count - null_count, 1)
        sample = [str(v) for v in series.drop_nulls().head(5).to_list()]

        semantic = _detect_semantic(
            col_name=col_name,
            dtype=dtype,
            cardinality=cardinality,
            row_count=row_count,
            null_rate=null_rate,
            sample_values=sample,
        )

        columns.append(ColumnProfile(
            name=col_name,
            dtype=str(dtype),
            semantic=semantic,
            null_rate=round(null_rate, 4),
            cardinality=cardinality,
            cardinality_ratio=round(cardinality / effective_rows, 4),
            sample_values=sample,
        ))

    entity_cols = [c.name for c in columns if c.semantic == SemanticRole.entity_id]
    time_cols = [c.name for c in columns if c.semantic == SemanticRole.time]
    measure_cols = [c.name for c in columns if c.semantic == SemanticRole.measure]
    dimension_cols = [c.name for c in columns if c.semantic == SemanticRole.dimension]
    margin_cols = [c.name for c in columns if _MARGIN_KEYWORDS.search(c.name)]
    stage_cols = [c.name for c in columns if _STAGE_KEYWORDS.search(c.name)]

    structures = StructureFlags(
        has_entity_id=bool(entity_cols),
        has_time=bool(time_cols),
        has_measure=bool(measure_cols),
        has_dimension=bool(dimension_cols),
        has_margin_col=bool(margin_cols),
        has_stage_col=bool(stage_cols),
        entity_cols=entity_cols,
        time_cols=time_cols,
        measure_cols=measure_cols,
        dimension_cols=dimension_cols,
    )

    grain = _detect_grain(df, time_cols, entity_cols)
    date_range = _date_range_days(df, time_cols)
    schema_hash = hashlib.sha256(
        json.dumps([(c.name, c.dtype) for c in columns]).encode()
    ).hexdigest()[:16]

    return DatasetProfile(
        source_type=source_type,  # type: ignore[arg-type]
        row_count=row_count,
        columns=columns,
        structures=structures,
        grain=grain,
        date_range_days=date_range,
        domain_signal=domain_signal,
        domain_confidence=domain_confidence,
        schema_hash=schema_hash,
    )

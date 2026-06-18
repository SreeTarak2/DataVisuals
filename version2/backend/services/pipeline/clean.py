import logging

import polars as pl

logger = logging.getLogger(__name__)


def clean_dataframe(df: pl.LazyFrame, schema: dict) -> tuple[pl.DataFrame, int, int]:
    string_columns = [
        name for name, dtype in schema.items() if dtype in (pl.Utf8, pl.String)
    ]
    numeric_columns = [
        name
        for name, dtype in schema.items()
        if dtype
        in (
            pl.Float64,
            pl.Int64,
            pl.Float32,
            pl.Int32,
            pl.Int16,
            pl.Int8,
            pl.UInt64,
            pl.UInt32,
            pl.UInt16,
            pl.UInt8,
        )
    ]

    if string_columns:
        df = df.with_columns(
            [pl.col(col).str.strip_chars().alias(col) for col in string_columns]
        )
        for col in string_columns:
            df = df.with_columns(
                [
                    pl.when(
                        pl.col(col).str.contains(r"(?i)(N/A|null|NULL|none|NONE|^$)")
                    )
                    .then(None)
                    .otherwise(pl.col(col))
                    .alias(col)
                ]
            )

    if numeric_columns:
        for col in numeric_columns:
            df = df.with_columns(
                [
                    pl.when(pl.col(col).is_infinite() | pl.col(col).is_nan())
                    .then(None)
                    .otherwise(pl.col(col))
                    .alias(col)
                ]
            )

    df_columns = list(schema.keys())
    seen_columns = {}
    rename_dict = {}
    for col in df_columns:
        if col in seen_columns:
            seen_columns[col] += 1
            rename_dict[col] = f"{col}_{seen_columns[col]}"
        else:
            seen_columns[col] = 0

    if rename_dict:
        df = df.rename(rename_dict)
        logger.info(f"✓ Renamed {len(rename_dict)} duplicate columns")

    df = df.unique()

    try:
        df_eager = df.collect(streaming=True)
    except Exception:
        df_eager = df.collect()

    return df_eager


def calculate_quality_metrics(
    column_metadata: list, original_rows: int, duplicates_removed: int
) -> dict:
    total_nulls = sum(col.get("null_count", 0) for col in column_metadata)
    total_cells = original_rows * len(column_metadata) if column_metadata else 0

    return {
        "completeness": round(100.0 - (total_nulls / total_cells * 100), 2)
        if total_cells > 0
        else 100.0,
        "uniqueness": round(100.0 - (duplicates_removed / original_rows * 100), 2)
        if original_rows > 0
        else 100.0,
        "duplicates_removed": duplicates_removed,
        "original_rows": original_rows,
        "cleaned_rows": original_rows - duplicates_removed,
        "data_cleaning_applied": True,
        "null_cells": total_nulls,
        "total_cells": total_cells,
    }


__all__ = ["clean_dataframe", "calculate_quality_metrics"]

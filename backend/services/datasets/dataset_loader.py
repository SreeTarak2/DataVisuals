"""
Dataset Loader
--------------
Handles dataset loading (CSV/XLSX/JSON) using Polars
+ dataset context generation for LLM prompts.
"""

import polars as pl
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

SUPPORTED_ENCODINGS = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]


# -----------------------------------------------------------
# LOAD DATASET
# -----------------------------------------------------------

async def load_dataset(path: str) -> pl.DataFrame:
    ext = path.split(".")[-1].lower()

    try:
        if ext in ("xls", "xlsx"):
            return pl.read_excel(path)

        if ext == "json":
            return pl.read_json(path)

        if ext == "csv":
            last_err = None
            for enc in SUPPORTED_ENCODINGS:
                try:
                    return pl.read_csv(
                        path,
                        encoding=enc,
                        truncate_ragged_lines=True,
                        ignore_errors=True
                    )
                except Exception as e:
                    last_err = e
                    continue
            raise last_err

    except Exception as e:
        logger.error(f"Dataset load failed for {path}: {e}")
        raise

    raise ValueError(f"Unsupported file format: {ext}")


# -----------------------------------------------------------
# CONTEXT STRING FOR LLM
# -----------------------------------------------------------

def create_context_string(metadata: Dict, sample_df: Optional[pl.DataFrame] = None) -> str:
    overview = metadata.get("dataset_overview", {})
    columns = metadata.get("column_metadata", [])

    context = [
        f"Dataset Overview: {overview.get('total_rows')} rows, {overview.get('total_columns')} columns.",
        "Columns:"
    ]

    for c in columns[:10]:
        context.append(f"- {c.get('name')} ({c.get('type')})")

    # include sample data
    if sample_df is not None and len(sample_df) > 0:
        try:
            rows = sample_df.head(3).to_pandas().to_dict(orient="records")
            context.append("\nSample Rows:")
            for r in rows:
                context.append(str(r))
        except Exception:
            pass

    return "\n".join(context)

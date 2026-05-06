"""
Agent 2 — Data Understanding
Builds the "Data Passport" from pre-computed Celery metadata.
No LLM call needed — structures what already exists.
"""

import logging
from services.agents.eda.context import AgentContext

logger = logging.getLogger(__name__)


async def run(ctx: AgentContext) -> AgentContext:
    meta = ctx.column_metadata
    quality = ctx.data_quality

    numeric_cols = [c for c in meta if "int" in c.get("type","").lower() or "float" in c.get("type","").lower()]
    categorical_cols = [c for c in meta if "utf8" in c.get("type","").lower() or "str" in c.get("type","").lower() or "categorical" in c.get("type","").lower()]
    date_cols = [c for c in meta if "date" in c.get("type","").lower() or "time" in c.get("type","").lower()]

    high_null_cols = [c["name"] for c in meta if c.get("null_percentage", 0) > 20]
    high_cardinality_cols = [c["name"] for c in meta if c.get("unique_count", 0) > 100 and "utf8" in c.get("type","").lower()]

    ctx.data_passport = {
        "summary": {
            "total_rows": ctx.row_count,
            "total_columns": ctx.column_count,
            "completeness_pct": quality.get("completeness", 100),
            "duplicate_rows_removed": quality.get("duplicates_removed", 0),
            "domain": ctx.domain,
        },
        "column_breakdown": {
            "numeric": [c["name"] for c in numeric_cols],
            "categorical": [c["name"] for c in categorical_cols],
            "datetime": [c["name"] for c in date_cols],
        },
        "quality_flags": {
            "high_null_columns": high_null_cols,
            "high_cardinality_columns": high_cardinality_cols,
            "has_temporal_data": len(date_cols) > 0,
        },
        "numeric_stats": {
            c["name"]: c["numeric_summary"]
            for c in numeric_cols
            if "numeric_summary" in c
        },
    }

    logger.info(
        f"[DataUnderstanding] {len(numeric_cols)} numeric, {len(categorical_cols)} categorical, "
        f"{len(date_cols)} datetime | flags: nulls={high_null_cols}"
    )
    return ctx

import logging
from typing import Optional

import duckdb
import pandas as pd
import polars as pl

from db.schemas_pipeline import ComputeResult, PrimitiveSpec, PrimitiveType

logger = logging.getLogger(__name__)


# ── SQL builders ────────────────────────────────────────────────────────────

def _sql_coverage_quality(spec: PrimitiveSpec) -> str:
    t = spec.time_col
    m = spec.measure_col
    return f"""
SELECT
    COUNT(*) AS total_rows,
    COUNT(CASE WHEN "{t}" IS NOT NULL THEN 1 END) AS rows_with_time,
    COUNT(CASE WHEN "{m}" IS NOT NULL THEN 1 END) AS rows_with_measure,
    COUNT(CASE WHEN "{t}" IS NOT NULL THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS time_coverage,
    COUNT(CASE WHEN "{m}" IS NOT NULL THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS measure_coverage
FROM data
"""


def _sql_entity_concentration(spec: PrimitiveSpec) -> str:
    e = spec.entity_col
    m = spec.measure_col
    n = spec.top_n
    return f"""
WITH entity_totals AS (
    SELECT "{e}" AS entity, SUM("{m}") AS entity_total
    FROM data
    WHERE "{m}" IS NOT NULL AND "{e}" IS NOT NULL
    GROUP BY "{e}"
    ORDER BY entity_total DESC
),
top_n AS (
    SELECT SUM(entity_total) AS top_n_total, COUNT(*) AS top_n_count
    FROM (SELECT entity_total FROM entity_totals LIMIT {n})
),
grand AS (
    SELECT SUM("{m}") AS grand_total, COUNT(DISTINCT "{e}") AS total_entities
    FROM data
    WHERE "{m}" IS NOT NULL AND "{e}" IS NOT NULL
)
SELECT
    top_n.top_n_total,
    grand.grand_total,
    top_n.top_n_total / NULLIF(grand.grand_total, 0) AS concentration_ratio,
    top_n.top_n_count,
    grand.total_entities
FROM top_n, grand
"""


def _sql_period_delta(spec: PrimitiveSpec) -> str:
    m = spec.measure_col
    t = spec.time_col
    grain = spec.grain.value if spec.grain else "month"
    return f"""
WITH periods AS (
    SELECT
        DATE_TRUNC('{grain}', TRY_CAST("{t}" AS TIMESTAMP)) AS period,
        SUM("{m}") AS period_total,
        COUNT(*) AS row_count
    FROM data
    WHERE "{m}" IS NOT NULL AND "{t}" IS NOT NULL
    GROUP BY period
    ORDER BY period DESC NULLS LAST
    LIMIT 3
)
SELECT period, period_total, row_count FROM periods ORDER BY period DESC
"""


def _sql_segment_mix(spec: PrimitiveSpec) -> str:
    d = spec.dimension_col
    m = spec.measure_col
    return f"""
WITH segment_totals AS (
    SELECT
        CAST("{d}" AS VARCHAR) AS segment,
        SUM("{m}") AS segment_total,
        COUNT(*) AS row_count
    FROM data
    WHERE "{m}" IS NOT NULL AND "{d}" IS NOT NULL
    GROUP BY "{d}"
    ORDER BY segment_total DESC
    LIMIT 20
),
grand AS (
    SELECT SUM("{m}") AS grand_total
    FROM data
    WHERE "{m}" IS NOT NULL AND "{d}" IS NOT NULL
)
SELECT
    st.segment,
    st.segment_total,
    st.row_count,
    st.segment_total / NULLIF(grand.grand_total, 0) AS segment_share
FROM segment_totals st, grand
ORDER BY st.segment_total DESC
"""


def _sql_trend_stability(spec: PrimitiveSpec) -> str:
    m = spec.measure_col
    t = spec.time_col
    grain = spec.grain.value if spec.grain else "month"
    return f"""
WITH period_totals AS (
    SELECT
        DATE_TRUNC('{grain}', TRY_CAST("{t}" AS TIMESTAMP)) AS period,
        SUM("{m}") AS period_total
    FROM data
    WHERE "{m}" IS NOT NULL AND "{t}" IS NOT NULL
    GROUP BY period
    ORDER BY period
)
SELECT
    AVG(period_total)                                           AS mean_val,
    STDDEV(period_total)                                        AS std_val,
    STDDEV(period_total) / NULLIF(ABS(AVG(period_total)), 0)   AS cov,
    MIN(period_total)                                           AS min_val,
    MAX(period_total)                                           AS max_val,
    COUNT(*)                                                    AS period_count
FROM period_totals
"""


def _sql_cohort_behavior(spec: PrimitiveSpec) -> str:
    e = spec.entity_col
    t = spec.time_col
    return f"""
WITH entity_first AS (
    SELECT
        "{e}" AS entity,
        MIN(DATE_TRUNC('month', TRY_CAST("{t}" AS TIMESTAMP))) AS first_month
    FROM data
    WHERE "{e}" IS NOT NULL AND "{t}" IS NOT NULL
    GROUP BY "{e}"
),
entity_activity AS (
    SELECT
        d."{e}"                                                          AS entity,
        ef.first_month,
        DATE_TRUNC('month', TRY_CAST(d."{t}" AS TIMESTAMP))             AS activity_month
    FROM data d
    JOIN entity_first ef ON CAST(d."{e}" AS VARCHAR) = CAST(ef.entity AS VARCHAR)
    WHERE d."{e}" IS NOT NULL AND d."{t}" IS NOT NULL
)
SELECT
    COUNT(DISTINCT entity)                                                       AS total_entities,
    COUNT(DISTINCT CASE WHEN activity_month > first_month THEN entity END)       AS repeat_entities,
    COUNT(DISTINCT CASE WHEN activity_month > first_month THEN entity END) * 1.0
        / NULLIF(COUNT(DISTINCT entity), 0)                                      AS repeat_rate
FROM entity_activity
"""


def _sql_anomaly_detection(spec: PrimitiveSpec) -> str:
    m = spec.measure_col
    t = spec.time_col
    grain = spec.grain.value if spec.grain else "month"
    return f"""
WITH period_totals AS (
    SELECT
        DATE_TRUNC('{grain}', TRY_CAST("{t}" AS TIMESTAMP)) AS period,
        SUM("{m}") AS period_total
    FROM data
    WHERE "{m}" IS NOT NULL AND "{t}" IS NOT NULL
    GROUP BY period
    ORDER BY period
),
stats AS (
    SELECT AVG(period_total) AS mean_val, STDDEV(period_total) AS std_val
    FROM period_totals
)
SELECT
    pt.period,
    pt.period_total,
    s.mean_val,
    s.std_val,
    ABS(pt.period_total - s.mean_val) / NULLIF(s.std_val, 0) AS z_score
FROM period_totals pt, stats s
ORDER BY pt.period DESC
LIMIT 24
"""


# ── Execution ────────────────────────────────────────────────────────────────

def _run_sql(df: pl.DataFrame, sql: str) -> tuple[list[dict], Optional[str]]:
    try:
        try:
            pandas_df = df.to_pandas()
        except ModuleNotFoundError:
            pandas_df = pd.DataFrame(df.to_dicts())
        conn = duckdb.connect(":memory:")
        conn.register("data", pandas_df)
        cursor = conn.execute(sql.strip())
        cols = [d[0] for d in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        conn.close()
        return rows, None
    except Exception as exc:
        return [], str(exc)


def _coverage_pct(df: pl.DataFrame, *col_names: Optional[str]) -> float:
    valid = [c for c in col_names if c and c in df.columns]
    if not valid:
        return 1.0
    null_rates = [df[c].null_count() / max(len(df), 1) for c in valid]
    return round(1.0 - (sum(null_rates) / len(null_rates)), 4)


# ── Result parsers ───────────────────────────────────────────────────────────

def _parse_coverage_quality(
    rows: list[dict], spec: PrimitiveSpec, df: pl.DataFrame
) -> ComputeResult:
    if not rows:
        return ComputeResult(
            kpi_id=spec.kpi_id, primitive=spec.primitive,
            compute_error="No rows returned", row_count=len(df),
        )
    r = rows[0]
    time_cov = r.get("time_coverage") or 0.0
    measure_cov = r.get("measure_coverage") or 0.0
    combined = min(float(time_cov), float(measure_cov))
    return ComputeResult(
        kpi_id=spec.kpi_id,
        primitive=spec.primitive,
        current_value=combined,
        coverage_pct=combined,
        row_count=int(r.get("total_rows") or len(df)),
    )


def _parse_entity_concentration(
    rows: list[dict], spec: PrimitiveSpec, df: pl.DataFrame
) -> ComputeResult:
    if not rows:
        return ComputeResult(
            kpi_id=spec.kpi_id, primitive=spec.primitive,
            compute_error="No rows returned", row_count=len(df),
        )
    r = rows[0]
    ratio = r.get("concentration_ratio")
    return ComputeResult(
        kpi_id=spec.kpi_id,
        primitive=spec.primitive,
        current_value=float(ratio) if ratio is not None else None,
        coverage_pct=_coverage_pct(df, spec.entity_col, spec.measure_col),
        row_count=len(df),
        segment_breakdown={
            "top_n": spec.top_n,
            "top_n_total": float(r.get("top_n_total") or 0),
            "grand_total": float(r.get("grand_total") or 0),
            "total_entities": int(r.get("total_entities") or 0),
        },
    )


def _parse_period_delta(
    rows: list[dict], spec: PrimitiveSpec, df: pl.DataFrame
) -> ComputeResult:
    if not rows:
        return ComputeResult(
            kpi_id=spec.kpi_id, primitive=spec.primitive,
            compute_error="No period data found", row_count=len(df),
        )
    current = float(rows[0].get("period_total") or 0)
    comparison: Optional[float] = float(rows[1].get("period_total") or 0) if len(rows) > 1 else None
    delta: Optional[float] = (current - comparison) if comparison is not None else None
    delta_pct: Optional[float] = None
    if delta is not None and comparison and comparison != 0:
        delta_pct = round(delta / abs(comparison), 4)
    return ComputeResult(
        kpi_id=spec.kpi_id,
        primitive=spec.primitive,
        current_value=current,
        comparison_value=comparison,
        delta=delta,
        delta_pct=delta_pct,
        coverage_pct=_coverage_pct(df, spec.time_col, spec.measure_col),
        row_count=int(rows[0].get("row_count") or 0),
    )


def _parse_segment_mix(
    rows: list[dict], spec: PrimitiveSpec, df: pl.DataFrame
) -> ComputeResult:
    if not rows:
        return ComputeResult(
            kpi_id=spec.kpi_id, primitive=spec.primitive,
            compute_error="No segments found", row_count=len(df),
        )
    breakdown = {
        str(r.get("segment", i)): round(float(r.get("segment_share") or 0), 4)
        for i, r in enumerate(rows)
    }
    top_share = float(rows[0].get("segment_share") or 0)
    return ComputeResult(
        kpi_id=spec.kpi_id,
        primitive=spec.primitive,
        current_value=top_share,
        coverage_pct=_coverage_pct(df, spec.dimension_col, spec.measure_col),
        row_count=len(df),
        segment_breakdown=breakdown,
    )


def _parse_trend_stability(
    rows: list[dict], spec: PrimitiveSpec, df: pl.DataFrame
) -> ComputeResult:
    if not rows:
        return ComputeResult(
            kpi_id=spec.kpi_id, primitive=spec.primitive,
            compute_error="No period data", row_count=len(df),
        )
    r = rows[0]
    cov = r.get("cov")
    return ComputeResult(
        kpi_id=spec.kpi_id,
        primitive=spec.primitive,
        current_value=float(cov) if cov is not None else None,
        cov=float(cov) if cov is not None else None,
        coverage_pct=_coverage_pct(df, spec.time_col, spec.measure_col),
        row_count=len(df),
        segment_breakdown={
            "mean": float(r.get("mean_val") or 0),
            "std": float(r.get("std_val") or 0),
            "period_count": int(r.get("period_count") or 0),
        },
    )


def _parse_cohort_behavior(
    rows: list[dict], spec: PrimitiveSpec, df: pl.DataFrame
) -> ComputeResult:
    if not rows:
        return ComputeResult(
            kpi_id=spec.kpi_id, primitive=spec.primitive,
            compute_error="No cohort data", row_count=len(df),
        )
    r = rows[0]
    repeat_rate = r.get("repeat_rate")
    return ComputeResult(
        kpi_id=spec.kpi_id,
        primitive=spec.primitive,
        current_value=float(repeat_rate) if repeat_rate is not None else None,
        coverage_pct=_coverage_pct(df, spec.entity_col, spec.time_col),
        row_count=int(r.get("total_entities") or 0),
        segment_breakdown={
            "total_entities": int(r.get("total_entities") or 0),
            "repeat_entities": int(r.get("repeat_entities") or 0),
        },
    )


def _parse_anomaly_detection(
    rows: list[dict], spec: PrimitiveSpec, df: pl.DataFrame
) -> ComputeResult:
    if not rows:
        return ComputeResult(
            kpi_id=spec.kpi_id, primitive=spec.primitive,
            compute_error="No anomaly data", row_count=len(df),
        )
    breakdown = {
        str(r.get("period", i)): round(float(r.get("z_score") or 0), 3)
        for i, r in enumerate(rows[:6])
    }
    recent_z = [float(r.get("z_score") or 0) for r in rows[:3]]
    return ComputeResult(
        kpi_id=spec.kpi_id,
        primitive=spec.primitive,
        current_value=max(recent_z) if recent_z else 0.0,
        coverage_pct=_coverage_pct(df, spec.time_col, spec.measure_col),
        row_count=len(df),
        segment_breakdown=breakdown,
    )


# ── Dispatch tables ──────────────────────────────────────────────────────────

_SQL_BUILDERS = {
    PrimitiveType.coverage_quality: _sql_coverage_quality,
    PrimitiveType.entity_concentration: _sql_entity_concentration,
    PrimitiveType.period_delta: _sql_period_delta,
    PrimitiveType.segment_mix: _sql_segment_mix,
    PrimitiveType.trend_stability: _sql_trend_stability,
    PrimitiveType.cohort_behavior: _sql_cohort_behavior,
    PrimitiveType.anomaly_detection: _sql_anomaly_detection,
}

_PARSERS = {
    PrimitiveType.coverage_quality: _parse_coverage_quality,
    PrimitiveType.entity_concentration: _parse_entity_concentration,
    PrimitiveType.period_delta: _parse_period_delta,
    PrimitiveType.segment_mix: _parse_segment_mix,
    PrimitiveType.trend_stability: _parse_trend_stability,
    PrimitiveType.cohort_behavior: _parse_cohort_behavior,
    PrimitiveType.anomaly_detection: _parse_anomaly_detection,
}


# ── Public API ───────────────────────────────────────────────────────────────

def compute(spec: PrimitiveSpec, df: pl.DataFrame) -> ComputeResult:
    sql_builder = _SQL_BUILDERS.get(spec.primitive)
    parser = _PARSERS.get(spec.primitive)

    if not sql_builder or not parser:
        return ComputeResult(
            kpi_id=spec.kpi_id, primitive=spec.primitive,
            compute_error=f"No handler for primitive: {spec.primitive}",
            row_count=len(df),
        )

    sql = sql_builder(spec)
    rows, error = _run_sql(df, sql)

    if error:
        logger.warning("compute error [%s]: %s", spec.kpi_id, error)
        return ComputeResult(
            kpi_id=spec.kpi_id, primitive=spec.primitive,
            compute_error=error, row_count=len(df),
        )

    return parser(rows, spec, df)


async def compute_all(specs: list[PrimitiveSpec], df: pl.DataFrame) -> list[ComputeResult]:
    results = []
    for spec in specs:
        results.append(compute(spec, df))
    return results

"""
Agent 3 — Univariate Explorer
Interprets per-column distributions using pre-computed stats + LLM.
Uses stepfun_flash (free) — fast, good at structured analysis.
"""

import logging
from agents.eda.context import AgentContext
from llm import llm_router

logger = logging.getLogger(__name__)

PROMPT = """You are a data analyst. Interpret the univariate statistics below and produce a JSON report.

DATASET: {name} ({domain} domain) — {rows:,} rows

NUMERIC COLUMNS:
{numeric_stats}

CATEGORICAL COLUMNS:
{categorical_stats}

DATA QUALITY FLAGS:
{quality_flags}

USER FOCUS: "{focus}"

Respond with ONLY valid JSON:
{{
  "key_findings": [
    {{"column": "col_name", "finding": "brief insight", "severity": "info"|"warning"|"critical"}}
  ],
  "skewed_columns": ["list of right/left-skewed numeric columns"],
  "outlier_columns": ["columns with notable outliers"],
  "recommended_transformations": ["e.g. log-transform revenue, encode region as dummy"]
}}"""


async def run(ctx: AgentContext) -> AgentContext:
    passport = ctx.data_passport
    numeric_names = passport.get("column_breakdown", {}).get("numeric", [])
    categorical_names = passport.get("column_breakdown", {}).get("categorical", [])

    # Build concise stat strings
    numeric_stats_lines = []
    for name in numeric_names[:15]:
        stats = passport.get("numeric_stats", {}).get(name, {})
        if stats:
            numeric_stats_lines.append(
                f"  {name}: min={stats.get('min')}, max={stats.get('max')}, mean={stats.get('mean')}"
            )

    categorical_stats_lines = []
    for col in ctx.column_metadata:
        if col["name"] in categorical_names[:10] and "top_values" in col:
            top = col["top_values"][:3]
            vals = ", ".join(f"{v['value']}({v['count']})" for v in top)
            categorical_stats_lines.append(f"  {col['name']}: top values → {vals}")

    quality_flags = passport.get("quality_flags", {})

    prompt = PROMPT.format(
        name=ctx.dataset_name,
        domain=ctx.domain,
        rows=ctx.row_count,
        numeric_stats="\n".join(numeric_stats_lines) or "  (none)",
        categorical_stats="\n".join(categorical_stats_lines) or "  (none)",
        quality_flags=str(quality_flags),
        focus=f"<user_question>{ctx.planner_output.get('analysis_focus', 'general EDA')}</user_question>",
    )

    try:
        result = await llm_router.call(
            prompt=prompt,
            model_role="insight_generation",
            expect_json=True,
            temperature=0.3,
            max_tokens=1024,
        )
        ctx.univariate_report = result if isinstance(result, dict) else {}
    except Exception as e:
        logger.warning(f"[Univariate] LLM failed: {e}")
        ctx.univariate_report = {"key_findings": [], "skewed_columns": [], "outlier_columns": []}

    findings_count = len(ctx.univariate_report.get("key_findings", []))
    logger.info(f"[Univariate] {findings_count} findings generated")
    return ctx

"""
Agent 5 — Visualization Specialist
Selects the 3 most insightful charts and produces Plotly-compatible configs.
Uses mistral_small_32 — reliable for structured JSON output.
"""

import logging
from services.agents.eda.context import AgentContext
from services.llm import llm_router

logger = logging.getLogger(__name__)

PROMPT = """You are a data visualization expert. Select the 3 most insightful charts for this dataset.

DATASET: {name} ({domain}) — {rows:,} rows

AVAILABLE CHART RECOMMENDATIONS:
{chart_recs}

KEY RELATIONSHIPS FOUND:
{relationships}

PRIMARY DRIVERS: {drivers}

COLUMN TYPES:
- Numeric: {numeric_cols}
- Categorical: {categorical_cols}
- Datetime: {date_cols}

USER QUESTION: "{question}"

Select/generate the 3 best charts. Respond with ONLY valid JSON:
{{
  "charts": [
    {{
      "chart_type": "bar"|"line"|"scatter"|"histogram"|"box"|"heatmap"|"pie",
      "title": "descriptive chart title",
      "x": "column_name",
      "y": "column_name",
      "color": "column_name or null",
      "aggregation": "sum"|"mean"|"count"|"max"|"min"|"none",
      "rationale": "why this chart answers the user's question"
    }}
  ]
}}"""


async def run(ctx: AgentContext) -> AgentContext:
    passport = ctx.data_passport
    breakdown = passport.get("column_breakdown", {})

    # Format existing chart recommendations
    chart_rec_lines = []
    for i, rec in enumerate(ctx.chart_recommendations[:6], 1):
        ctype = rec.get("chart_type", rec.get("type", "?"))
        cols = rec.get("columns", rec.get("config", {}).get("columns", []))
        chart_rec_lines.append(f"  {i}. {ctype} — columns: {cols}")

    # Format relationships
    rel_lines = []
    for rel in ctx.bivariate_report.get("key_relationships", [])[:4]:
        rel_lines.append(f"  • {rel.get('columns', [])} — {rel.get('relationship', '')}")

    prompt = PROMPT.format(
        name=ctx.dataset_name,
        domain=ctx.domain,
        rows=ctx.row_count,
        chart_recs="\n".join(chart_rec_lines) or "  None pre-computed",
        relationships="\n".join(rel_lines) or "  None found",
        drivers=", ".join(ctx.bivariate_report.get("primary_drivers", [])) or "unknown",
        numeric_cols=", ".join(breakdown.get("numeric", [])[:10]),
        categorical_cols=", ".join(breakdown.get("categorical", [])[:10]),
        date_cols=", ".join(breakdown.get("datetime", [])[:5]),
        question=f"<user_question>{ctx.user_question}</user_question>",
    )

    try:
        result = await llm_router.call(
            prompt=prompt,
            model_role="visualization_engine",  # mistral_small_32
            expect_json=True,
            temperature=0.2,
            max_tokens=1024,
        )
        ctx.chart_configs = result.get("charts", []) if isinstance(result, dict) else []
    except Exception as e:
        logger.warning(f"[Visualization] LLM failed: {e}")
        ctx.chart_configs = []

    logger.info(f"[Visualization] {len(ctx.chart_configs)} chart configs generated")
    return ctx

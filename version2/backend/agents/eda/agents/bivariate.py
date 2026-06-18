"""
Agent 4 — Bivariate / Multivariate Analyst
Identifies relationships between columns using correlations + QUIS insights.
Uses deepseek_v32 — best for pattern detection and mathematical reasoning.
"""

import logging
from agents.eda.context import AgentContext
from llm import llm_router

logger = logging.getLogger(__name__)

PROMPT = """You are a senior data analyst finding relationships in data.

DATASET: {name} ({domain}) — {rows:,} rows

TOP STATISTICAL CORRELATIONS:
{correlations}

QUIS DEEP INSIGHTS (statistically significant):
{quis_insights}

UNIVARIATE FINDINGS SUMMARY:
{univariate_summary}

USER QUESTION: "{question}"

Find the most important relationships and patterns. Respond with ONLY valid JSON:
{{
  "key_relationships": [
    {{
      "columns": ["col_a", "col_b"],
      "relationship": "description of the relationship",
      "strength": "weak"|"moderate"|"strong",
      "direction": "positive"|"negative"|"non-linear"|"categorical",
      "business_implication": "what this means for the user"
    }}
  ],
  "primary_drivers": ["top 2-3 columns that most explain variation in the data"],
  "anomalies": ["any surprising or counter-intuitive patterns found"],
  "segmentation_opportunities": ["columns worth grouping/segmenting by"]
}}"""


async def run(ctx: AgentContext) -> AgentContext:
    # Format correlations — schema is normalized in _load_context: {column_a, column_b, correlation}
    corr_lines = []
    for c in ctx.top_correlations(8):
        col_a = c["column_a"]
        col_b = c["column_b"]
        r     = c["correlation"]
        corr_lines.append(f"  {col_a} ↔ {col_b}: r={r}")

    # Format QUIS insights
    quis_lines = []
    for ins in ctx.top_quis_insights(6):
        desc = ins.get("description") or ins.get("insight", "")
        sig = ins.get("p_value") or ins.get("significance", "")
        quis_lines.append(f"  • {desc}" + (f" (p={sig})" if sig else ""))

    # Summarise univariate findings
    uni_findings = ctx.univariate_report.get("key_findings", [])
    uni_summary = "; ".join(
        f["column"] + ": " + f["finding"]
        for f in uni_findings[:5]
    ) or "No univariate flags"

    prompt = PROMPT.format(
        name=ctx.dataset_name,
        domain=ctx.domain,
        rows=ctx.row_count,
        correlations="\n".join(corr_lines) or "  No correlations pre-computed",
        quis_insights="\n".join(quis_lines) or "  No QUIS insights available",
        univariate_summary=uni_summary,
        question=f"<user_question>{ctx.user_question}</user_question>",
    )

    try:
        result = await llm_router.call(
            prompt=prompt,
            model_role="insight_generation",   # deepseek_v32
            expect_json=True,
            temperature=0.4,
            max_tokens=1500,
        )
        ctx.bivariate_report = result if isinstance(result, dict) else {}
    except Exception as e:
        logger.warning(f"[Bivariate] LLM failed: {e}")
        ctx.bivariate_report = {"key_relationships": [], "primary_drivers": [], "anomalies": []}

    rel_count = len(ctx.bivariate_report.get("key_relationships", []))
    logger.info(f"[Bivariate] {rel_count} relationships identified")
    return ctx

"""
Agent 1 — Planner / Coordinator
Classifies user intent and decides which agents to run.
Fast + free model: gemini_flash_lite_intent
"""

import json
import logging
from services.agents.eda.context import AgentContext
from services.llm import llm_router

logger = logging.getLogger(__name__)

PROMPT = """You are a data analysis planner. Given a user's question and dataset info, produce a JSON plan.

DATASET:
- Name: {name}
- Domain: {domain}
- Rows: {rows:,} | Columns: {cols}
- Quality: {quality}% complete

COLUMNS:
{schema}

USER QUESTION: "{question}"

Respond with ONLY valid JSON:
{{
  "intent": "full_eda" | "trend_analysis" | "correlation_analysis" | "distribution_analysis" | "anomaly_detection" | "comparison",
  "key_columns": ["list of most relevant column names for this question"],
  "analysis_focus": "one sentence describing what to focus on",
  "run_advanced_modeling": false,
  "complexity": "simple" | "moderate" | "complex"
}}"""


async def run(ctx: AgentContext) -> AgentContext:
    prompt = PROMPT.format(
        name=ctx.dataset_name,
        domain=ctx.domain,
        rows=ctx.row_count,
        cols=ctx.column_count,
        quality=ctx.data_quality.get("completeness", 100),
        schema=ctx.schema_summary(),
        question=f"<user_question>{ctx.user_question}</user_question>",
    )

    try:
        result = await llm_router.call(
            prompt=prompt,
            model_role="intent_engine",
            expect_json=True,
            temperature=0.3,
            max_tokens=512,
        )
        ctx.planner_output = result if isinstance(result, dict) else {}
    except Exception as e:
        logger.warning(f"[Planner] LLM failed, using fallback: {e}")
        ctx.planner_output = {
            "intent": "full_eda",
            "key_columns": [c["name"] for c in ctx.column_metadata[:5]],
            "analysis_focus": "General exploratory analysis",
            "run_advanced_modeling": False,
            "complexity": "moderate",
        }

    logger.info(f"[Planner] intent={ctx.planner_output.get('intent')} complexity={ctx.planner_output.get('complexity')}")
    return ctx

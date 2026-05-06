"""
Measure prompt template sizes at startup.

This runs once when the app boots, logs baseline token counts for every prompt,
and identifies models that are too small for entire template + completion reserve.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def measure_all_templates() -> dict[str, dict]:
    """
    Call at app startup. Measures token sizes for every prompt template
    with empty context so you always know the bare minimum cost.

    Returns a dict mapping role → {template_tokens, completion_reserve, min_window, unsafe_models}
    """
    try:
        from services.prompts.prompt_templates import PromptRegistry
        from services.prompts.token_budget import (
            count_tokens,
            COMPLETION_RESERVES,
            MODEL_CONTEXT_WINDOWS,
        )
    except ImportError as e:
        logger.error(f"[template_baseline] Failed to import: {e}")
        return {}

    baselines: dict[str, dict] = {}

    # Define what to measure
    checks = [
        (
            "sql_generator",
            lambda: PromptRegistry.get_sql_generation_prompt(
                column_schema="",
                sample_data="",
                data_stats="",
                user_query="",
                allowed_columns=[],
                include_context=False,
            ),
        ),
        (
            "chart_engine",
            lambda: PromptRegistry.get_chart_recommendation_prompt(
                dataset_context="", include_context=False
            ),
        ),
        (
            "chart_explanation",
            lambda: PromptRegistry.get_chart_explanation_prompt(
                chart_summary="", dataset_context="", include_context=False
            ),
        ),
        (
            "insight_generator",
            lambda: PromptRegistry.get_insight_generation_prompt(
                dataset_context="",
                charts_text="",
                kpis_text="",
                include_context=False,
            ),
        ),
        (
            "memory_extraction",
            lambda: PromptRegistry.get_memory_extraction_prompt(""),
        ),
        (
            "narrative_engine",
            lambda: PromptRegistry.get_narrative_prompt(
                dataset_name="",
                key_metrics="",
                anomalies="",
                correlations="",
                include_context=False,
            ),
        ),
    ]

    for role, fn in checks:
        try:
            template_tokens = count_tokens(fn())
            reserve = COMPLETION_RESERVES.get(role, 1_000)
            min_window = template_tokens + reserve

            # Flag models that are already too small for just the template
            unsafe_models = [
                m
                for m, limit in MODEL_CONTEXT_WINDOWS.items()
                if template_tokens + reserve > limit
            ]

            baselines[role] = {
                "template_tokens": template_tokens,
                "completion_reserve": reserve,
                "minimum_model_window": min_window,
                "unsafe_for_models": unsafe_models,
            }

            status = "⚠️  UNSAFE" if unsafe_models else "✅ OK"
            logger.info(
                f"[template_baseline] {role}: {template_tokens} tokens "
                f"(+{reserve} reserve = {min_window} min window) {status}"
            )
            if unsafe_models:
                logger.warning(
                    f"[template_baseline] '{role}' template too large for: {unsafe_models}"
                )

        except Exception as e:
            logger.error(f"[template_baseline] Failed to measure '{role}': {e}")
            baselines[role] = {"error": str(e)}

    return baselines


# ── Startup hook ───────────────────────────────────────────────────────────────
TEMPLATE_BASELINES: dict[str, dict] = {}


def init_token_budgets():
    """
    Initialize token budget system at app startup.
    Measures all templates and logs their baseline sizes.
    """
    global TEMPLATE_BASELINES
    TEMPLATE_BASELINES = measure_all_templates()

    if TEMPLATE_BASELINES:
        logger.info(
            f"[token_budget] Template baselines ready:\n"
            + json.dumps(TEMPLATE_BASELINES, indent=2)
        )
    else:
        logger.warning("[token_budget] No templates measured — check import paths")

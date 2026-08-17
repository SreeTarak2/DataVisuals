"""
prompts — Central Prompt Registry
=====================================

Single source of truth for ALL LLM prompts across the application.

Modules:
  _identity.py   → Shared platform identity, tone, safety rules
  chat.py         → Chat synthesis prompt builder
  sql.py          → SQL generation prompts
  chart.py        → Chart recommendation prompts
  kpi.py          → KPI generation prompt
  dashboard.py    → Dashboard designer prompt
  narrative.py    → 3-stage narrative pipeline
  guards.py       → Off-topic detection
  output_format.py → JSON/markdown formatting rules

Utility (legacy, kept in place):
  token_budget.py     → Token counting and context window management
  schema_scoper.py    → Schema context trimming
  measure_templates.py → Startup prompt measurement
"""

from prompts._identity import (
    ARCHETYPE_INSTRUCTIONS,
    IDENTITY,
    PERSONA,
    RULES,
    SAFETY_RULES,
    SYSTEM_JSON_RULES,
    TONE_RULES,
)

from prompts.builder import PromptBuilder
from prompts.chart import (
    build_chart_recommendation_prompt,
    get_chart_explanation_prompt,
    get_chart_recommendation_prompt,
    get_streaming_chart_prompt,
)
from prompts.chat import (
    build_synthesis_prompt,
    check_response_quality,
    humanize_text,
    normalize_response_style,
)
from prompts.dashboard import get_dashboard_designer_prompt
from prompts.guards import GuardResult, check_off_topic, check_scope
from prompts.kpi import KPI_GENERATOR_SYSTEM_PROMPT
from prompts.narrative import (
    FALLBACK_STORY_TEMPLATES,
    JARGON_BAN,
    PLAIN_ENGLISH_GLOSSARY,
    get_stage1_computation_prompt,
    get_stage2_prioritization_prompt,
    get_stage3_narration_prompt,
    get_story_resolution_prompt,
    get_story_theme_detection_prompt,
    get_story_weaver_prompt,
    validate_narration_quality,
)
from prompts.output_format import (
    COMPLEXITY_HINTS,
    CONVERSATIONAL_SYSTEM_PROMPT,
)
from prompts.sql import (
    REWRITE_SYSTEM_PROMPT,
    get_analytical_question_prompt,
    get_conversation_summary_prompt,
    get_deep_reasoning_prompt,
    get_direct_sql_prompt,
    get_domain_detection_prompt,
    get_follow_up_prompt,
    get_insight_generation_prompt,
    get_kpi_suggestion_prompt,
    get_memory_extraction_prompt,
    get_quis_answer_prompt,
    get_refinement_retry_prompt,
    get_result_interpretation_prompt,
    get_self_critique_prompt,
    get_sql_generation_prompt,
    get_insight_generation_prompt,
    validate_insight_response,
    MECE_CATEGORIES,
)

__all__ = [
    # identity
    "IDENTITY",
    "PERSONA",
    "SAFETY_RULES",
    "RULES",
    "SYSTEM_JSON_RULES",
    "TONE_RULES",
    "ARCHETYPE_INSTRUCTIONS",
    # builder
    "PromptBuilder",
    # chat
    "build_synthesis_prompt",
    "check_response_quality",
    "normalize_response_style",
    "humanize_text",
    # sql
    "REWRITE_SYSTEM_PROMPT",
    "get_sql_generation_prompt",
    "get_direct_sql_prompt",
    "get_kpi_suggestion_prompt",
    "get_insight_generation_prompt",
    "get_domain_detection_prompt",
    "get_conversation_summary_prompt",
    "get_memory_extraction_prompt",
    "get_analytical_question_prompt",
    "get_follow_up_prompt",
    "get_quis_answer_prompt",
    "get_result_interpretation_prompt",
    "get_refinement_retry_prompt",
    "get_deep_reasoning_prompt",
    "get_self_critique_prompt",
    "get_insight_generation_prompt",
    "validate_insight_response",
    "MECE_CATEGORIES",
    # chart
    "get_chart_recommendation_prompt",
    "build_chart_recommendation_prompt",
    "get_chart_explanation_prompt",
    "get_streaming_chart_prompt",
    # kpi
    "KPI_GENERATOR_SYSTEM_PROMPT",
    # dashboard
    "get_dashboard_designer_prompt",
    # narrative
    "FALLBACK_STORY_TEMPLATES",
    "JARGON_BAN",
    "PLAIN_ENGLISH_GLOSSARY",
    "get_stage1_computation_prompt",
    "get_stage2_prioritization_prompt",
    "get_stage3_narration_prompt",
    "get_story_weaver_prompt",
    "get_story_theme_detection_prompt",
    "get_story_resolution_prompt",
    "validate_narration_quality",
    # guards
    "check_off_topic",
    "check_scope",
    "GuardResult",
    # output_format
    "COMPLEXITY_HINTS",
    "CONVERSATIONAL_SYSTEM_PROMPT",
]

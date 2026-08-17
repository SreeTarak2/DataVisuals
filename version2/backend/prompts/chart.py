"""
chart — Chart Recommendation & Explanation Prompts
=====================================================

Extracted from core/prompt_templates.py.
Functions: get_chart_recommendation_prompt(), get_chart_explanation_prompt(),
           get_streaming_chart_prompt()
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

# =============================================================================
# CONSTANTS
# =============================================================================

MAX_CONTEXT_CHARS = 6000


# =============================================================================
# CHART RECOMMENDATION PROMPT
# =============================================================================


def _domain_neutral_examples() -> dict:
    return {
        "title_good_1": "West Region Drives 68% of Revenue Despite Only 30% of Orders",
        "title_good_2": "Retention Drops 42% After the First Three Months",
        "title_good_3": "Discount Rate Above 20% Triples Average Order Value",
        "title_bad_1": "Average Sales by Region",
        "title_bad_2": "Distribution of Values",
        "annotation_good_1": "The top 10% of accounts generate 73% of total revenue.",
        "annotation_good_2": "Conversion rate peaks at 18% on Tuesdays and falls to 6% on Sundays.",
        "annotation_bad": "This chart shows the distribution of sales across regions.",
    }


def _persona_block() -> str:
    return (
        "You are the Chart Intelligence Engine for Signal — "
        "a Fortune-500-grade analytics platform used by non-technical executives "
        "and senior data scientists alike.\n\n"
        "Your ONLY job: return a JSON array of charts that are INDISTINGUISHABLE "
        "from what a senior Tableau consultant or Power BI Premium expert would "
        "design — charts that surface surprises and drive decisions in under "
        "3 seconds of viewing."
    )


def _context_block(dataset_context: str) -> str:
    return f"""
================================================================================
DATASET CONTEXT (columns you MAY use - NO others)
================================================================================
{dataset_context.strip()}
"""


def _query_block(user_query: str) -> str:
    return f"\nUSER REQUEST: {user_query.strip()}\n"


def _column_rules_block() -> str:
    return """
================================================================================
COLUMN SELECTION RULES (enforced strictly)
================================================================================
[R1] ONLY use column names listed in DATASET CONTEXT.
     Invented column names will crash the renderer.

[R2] CARDINALITY LIMITS
     - pie x <= 8 unique values
     - bar x <= 20 unique values
     - box_plot groups <= 15
     - group_by column(s) <= 12 unique values total (use list for multi-level)

[R3] TEMPORAL COLUMNS
     Columns with dtype date, datetime, or name ending in _date, _at, _year, _month
     MUST use LINE or AREA chart type. NEVER use BAR.

[R4] BINARY/BOOLEAN COLUMNS
     Columns with exactly 2 unique values MUST appear as group_by in at least one chart.

[R5] SKIP ALWAYS
     - ID columns (_id, _key, _uuid, _pk)
     - Columns with exactly 1 unique value
     - Free-text columns

[R6] TOOLTIP & DRILL-DOWN SAFETY
     - tooltip_fields: only exact column names from context
     - drill_down_column: cardinality <= 20, never an ID column
"""


def _aggregation_rules_block() -> str:
    return """
================================================================================
AGGREGATION CONTRACT
================================================================================
Allowed: sum | mean | median | count | count_unique | min | max | none

Rules:
1. Use MEDIAN for right-skewed: revenue, income, cost, salary, age
2. Use COUNT when y is null (histogram, frequency bar)
3. Use SUM for additive columns (units, dollars)
4. aggregation="none" ONLY valid for: scatter, histogram
5. NEVER use aggregation="none" on bar, grouped_bar, or line
"""


def _anatomy_block() -> str:
    ex = _domain_neutral_examples()
    return f"""
================================================================================
ENTERPRISE CHART ANATOMY (7 mandatory layers)
================================================================================

Layer 1 - IDENTITY
  title_insight: Headline with finding, <=12 words.
    BAD: "{ex["title_bad_1"]}"
    GOOD: "{ex["title_good_1"]}"
  subtitle_scope: "[x] vs [y] - aggregation - filter"
  badge_type: KEY FINDING | ANOMALY | STREND | RELATIONSHIP | DISTRIBUTION | COMPOSITION | COMPARISON
  diversity_role: TREND | COMPARISON | DISTRIBUTION | COMPOSITION | RELATIONSHIP | ANOMALY | RANKING
    NO two charts may share the same role.

Layer 2 - DATA MAPPING
  type: bar | line | scatter | pie | histogram | box_plot | area | grouped_bar | stacked_bar | multi_line | stacked_area | heatmap | treemap
  x: EXACT column name
  y: EXACT numeric column name. Null ONLY for pie/histogram.
  group_by: null if no segment, col_name if comparing segments (<=5 unique values)
  aggregation: See AGGREGATION CONTRACT
  sort_by: value_desc (default) | value_asc | x_natural | none
  limit: pie <=8, bar <=20, grouped_bar <=6 groups

Layer 3 - VISUAL
  show_reference_line: true/false
  reference_type: mean | median | none
  color_strategy: brand_single | brand_sequential | categorical

Layer 3b - SEMANTIC TYPES (optional, improves formatting)
  semantic_types: {{column_name: one of currency | percentage | ratio | temperature |
    duration | date | datetime | year_month | rank | score | quantity | identifier |
    dimension | boolean | number}}
  If omitted, the renderer infers these automatically — declaring them only
  helps when the column name is ambiguous (e.g. "total" that holds currency).

Layer 4 - NARRATIVE
  insight_annotation: 1 sentence <=25 words with >=1 number
  key_numbers: 2-3 label-value callouts
  reading_guide: 1 sentence action

Layer 5 - INTERACTION
  action_chips: Exactly 2 questions, MUST end with "?"
  tooltip_fields: exact column names
  drill_down_column: low-card column <=20

Layer 6 - QUALITY
  cardinality_check: ok | warning | blocked
  reasoning: 1-2 sentences on chart type choice

Layer 7 - POSITION
  position: hero | primary | supporting
  span: hero=4, primary=2, supporting=1-2
"""


def _multi_series_scan_block() -> str:
    return """
================================================================================
STEP 0 — GROUP_BY CANDIDATE SCAN
================================================================================

Before selecting any chart, scan the DATASET CONTEXT for GROUP_BY CANDIDATES:
  A GROUP_BY CANDIDATE is any categorical column with 2-5 unique values.

MANDATE — if ANY group_by candidates exist in the dataset:
  ✓ At least 2 of your 6-8 charts MUST use a group_by candidate.
  ✓ One of these MUST be on the hero or primary chart.
  ✓ When group_by is set → color_strategy MUST be "categorical".
  ✓ When group_by is null → color_strategy MUST be "brand_single".

BINARY/BOOLEAN COLUMNS:
  ✓ MUST appear as group_by in at least one chart — no exceptions.
"""


def _selection_framework_block() -> str:
    return """
================================================================================
CHART SELECTION FRAMEWORK
================================================================================

  ── TREND ──
  Temporal x + one numeric y                    → line
  Temporal x + numeric y + segment col          → multi_line

  ── COMPARISON ──
  Categories <=20 + numeric y                   → bar, sort=value_desc
  Categories + segment col                      → grouped_bar

  ── COMPOSITION ──
  Proportion <=8 categories                     → pie
  Part-of-whole over time                       → stacked_area
  Part-of-whole across categories               → stacked_bar

  ── DISTRIBUTION ──
  One numeric col                               → histogram
  Split across groups                           → box_plot

  ── RELATIONSHIP ──
  Two numeric columns                           → scatter

TRIGGER CONDITIONS FOR MULTI-SERIES:
  IF temporal col AND categorical col <=5 uniques → MUST include multi_line
  IF categorical x AND segment col <=5 uniques   → MUST include grouped_bar or stacked_bar
  IF temporal col AND part-of-whole col          → MUST include stacked_area
  IF binary/boolean column exists                → MUST appear as group_by
"""


def get_chart_recommendation_prompt(
    dataset_context: str,
    user_query: Optional[str] = None,
    include_context: bool = True,
    max_context_chars: int = MAX_CONTEXT_CHARS,
    logger: logging.Logger | None = None,
) -> str:
    """Production-grade chart recommendation prompt."""
    log = logger or logging.getLogger(__name__)

    ctx_text = dataset_context
    if include_context and len(dataset_context) > max_context_chars:
        log.warning(f"[chart_recommendation] context truncated: {len(dataset_context)} -> {max_context_chars}")
        ctx_text = dataset_context[:max_context_chars] + "\n...[truncated]"

    sections = [_persona_block()]

    if include_context:
        sections.append(_context_block(ctx_text))

    if user_query:
        sections.append(_query_block(user_query))

    sections.append(_column_rules_block())
    sections.append(_multi_series_scan_block())
    sections.append(_aggregation_rules_block())
    sections.append(_anatomy_block())
    sections.append(_selection_framework_block())

    return "\n".join(sections)


# Alias for backward compatibility
build_chart_recommendation_prompt = get_chart_recommendation_prompt


# =============================================================================
# CHART EXPLANATION PROMPT
# =============================================================================


def get_chart_explanation_prompt(
    chart_summary: str,
    dataset_context: str,
    data_stats: str,
    include_context: bool = True,
    max_context_chars: int = 2000,
    logger: logging.Logger | None = None,
) -> str:
    """Generate prompt for chart explanation agent."""
    log = logger or logging.getLogger(__name__)

    sections = [
        "You are an Elite Data Analyst specializing in data visualization interpretation.",
        "Your task: Analyze the recommended chart and provide a business-ready explanation.",
        "",
        "CHART DETAILS:",
        f"{chart_summary}",
        "",
    ]

    if data_stats.strip():
        sections.extend(["DATA STATISTICS:", f"{data_stats}", ""])

    if include_context and dataset_context.strip():
        ctx_text = dataset_context
        if len(dataset_context) > max_context_chars:
            log.warning(f"[chart_explanation] context truncated: {len(dataset_context)} -> {max_context_chars}")
            ctx_text = dataset_context[:max_context_chars] + "\n[...truncated...]"
        sections.extend(["DATASET CONTEXT:", f"{ctx_text}", ""])

    sections.extend([
        "INSTRUCTIONS:",
        "Generate a JSON response with EXACTLY these fields:",
        "  1. 'explanation': 2-3 sentence business interpretation",
        "  2. 'key_patterns': List of 2-4 discovered patterns",
        "  3. 'business_value': 1-2 sentence actionable insight for a stakeholder",
        "  4. 'confidence': Confidence level (0.0 to 1.0)",
        "",
        "OUTPUT: Return ONLY valid JSON. No markdown, no prose, no extra text.",
    ])

    return "\n".join(sections)


# =============================================================================
# STREAMING CHART PROMPT
# =============================================================================


def get_streaming_chart_prompt(
    full_response: str,
    columns: List[str],
    column_metadata: Optional[List[dict]] = None,
    max_response_chars: int = 3000,
    logger: logging.Logger | None = None,
) -> str:
    """Build prompt for chart config extraction with full response context."""
    log = logger or logging.getLogger(__name__)

    MAX_COLUMNS = 40
    display_columns = columns[:MAX_COLUMNS] if columns else []
    display_metadata = column_metadata[:MAX_COLUMNS] if column_metadata else None

    if column_metadata and len(column_metadata) > MAX_COLUMNS:
        log.warning(f"[streaming_chart] Dataset has {len(column_metadata)} columns, truncating to {MAX_COLUMNS}")

    if display_metadata:
        col_lines = []
        for cm in display_metadata:
            name = cm.get("name", "?")
            dtype = cm.get("type", "unknown")
            samples = cm.get("sample_values", [])
            sample_str = f" - e.g. {samples[0]}" if samples else ""
            col_lines.append(f"  - {name} ({dtype}){sample_str}")
        cols_section = "\n".join(col_lines)
    else:
        cols_section = "\n".join(f"  - {c}" for c in display_columns)

    col_names = [cm.get("name") for cm in display_metadata] if display_metadata else display_columns
    whitelist = f"COLUMN WHITELIST: {', '.join(col_names[:MAX_COLUMNS])}\nUse ONLY these exact names."

    if len(full_response) > max_response_chars:
        log.warning(f"[streaming_chart] Response truncated from {len(full_response)} to {max_response_chars} chars")
        response_snippet = full_response[:max_response_chars] + "\n...[truncated]"
    else:
        response_snippet = full_response

    return f"""You are a chart config extraction engine.
Extract chart config from the assistant's response.

ASSISTANT RESPONSE:
{response_snippet}

AVAILABLE COLUMNS:
{cols_section}

{whitelist}

Return ONLY a valid JSON object with: {{
    "chart_config": {{ ... }},
    "reasoning": "Why this chart type was chosen"
}} or {{
    "chart_config": null,
    "reasoning": "No chart needed for this response"
}}

Rules:
- Use ONLY columns from the whitelist above
- Never invent columns
- Return null chart_config if no visualization value
- Valid JSON only, no markdown fences
"""


__all__ = [
    "get_chart_recommendation_prompt",
    "build_chart_recommendation_prompt",
    "get_chart_explanation_prompt",
    "get_streaming_chart_prompt",
]

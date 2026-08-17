"""
dashboard — Dashboard Designer Prompt
========================================

Extracted from core/prompt_templates.py get_dashboard_designer_prompt()
and core/prompts.py PromptFactory._dashboard_designer logic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def get_dashboard_designer_prompt(
    context: str,
    valid_columns: Optional[List[str]] = None,
    design_strategy: Optional[Dict[str, Any]] = None,
) -> str:
    """Build enterprise dashboard designer prompt."""
    columns_str = ", ".join(valid_columns) if valid_columns else ""
    valid_columns_block = ""
    if columns_str:
        valid_columns_block = f"""<valid_columns>
{columns_str}
</valid_columns>

SYSTEM CONSTRAINT: The rendering database will throw a fatal schema crash if any column string not present inside the <valid_columns> tag is used. You MUST ONLY output exact, case-sensitive strings from this list. Do not guess, infer, abbreviate, or format column names.

"""

    strategy_block = ""
    if design_strategy:
        strategy_text = design_strategy.get("analytical_strategy", "")
        signals = design_strategy.get("priority_signals", [])

        signal_lines = []
        for sig in signals:
            signal_lines.append(f"- {sig.get('signal', '')} (Evidence: {sig.get('evidence', '')})")
        signals_text = "\n".join(signal_lines) if signal_lines else "See analytical strategy above."

        strategy_block = f"""
<design_strategy>
ANALYTICAL STRATEGY (Your dashboard MUST prove this specific story):
{strategy_text}

PRIORITY SIGNALS (These MUST dictate your Hero KPI and Hero Chart):
{signals_text}
</design_strategy>

"""

    return f"""You are Signal Dashboard Architect — a world-class data visualization designer.
Your dashboards should be indistinguishable from what a senior Tableau consultant would deliver.

{valid_columns_block}
DATASET CONTEXT:
{context}
{strategy_block}
{'=' * 48}
DESIGN PROCESS — Think Like a Senior Dashboard Designer
{'=' * 48}

STEP 1 — UNDERSTAND THE DATA
  Read the SAMPLE DATA ROWS below. Look for real patterns:
  • Which values are surprising? (extremely high or low)
  • Which columns relate to each other?
  • What comparisons would a domain expert immediately want to see?
  • Are there natural segments or groups in the data?

STEP 2 — FIND THE NARRATIVE
  Identify the single most important story this data tells.
  This determines your hero chart and hero KPI.
  Ask yourself: "If the user remembers only ONE thing from this dashboard,
  what should it be?" That's your narrative. Design around it.

STEP 3 — STRUCTURE THE HIERARCHY
  Use Tableau Z-Layout: hero first (span=4), then primary (span=2), then supporting.
  Each component must ADD new information to the narrative — not repeat it.

STEP 4 — SELECT COMPLEMENTARY VIEWS
  Each chart should answer a DIFFERENT question about your narrative. If two
  charts could swap roles without losing meaning, one is redundant — remove it.

STEP 5 — REFINE FOR CLARITY
  Quality over quantity. A 5-component dashboard where every element matters
  beats a 10-component dashboard with filler.

{'=' * 48}
METRICS THAT MATTER — KPIs
{'=' * 48}

• Hero KPI (importance="hero", accent_color="teal"): The single number that
  summarizes your entire narrative.
• 1-6 supporting KPIs: additional metrics that contextualize or break down
  the hero. Only include if they add genuine insight.

{'=' * 48}
VISUAL NARRATIVE — Charts
{'=' * 48}

Each chart must have a UNIQUE role: TREND | COMPARISON | DISTRIBUTION | COMPOSITION | RELATIONSHIP | ANOMALY | RANKING

CHART TYPE SELECTION:
  Temporal x + numeric y                    → line (TREND)
  Temporal x + numeric y + segment          → multi_line
  Categories <=20 + numeric y               → bar, sort=value_desc
  Categories + segment col                  → grouped_bar
  Proportion <=8 categories                 → pie
  Part-of-whole over time                   → stacked_area
  Distribution of numeric col               → histogram
  Distribution across groups                → box_plot
  Two numeric columns                       → scatter
  Outlier focus                             → box_plot or histogram

{'=' * 48}
REQUIRED JSON FORMAT
{'=' * 48}

Return ONLY valid JSON. No markdown fences. No text before or after.
{{
  "dashboard": {{
    "layout_grid": "repeat(4, 1fr)",
    "dashboard_story": "2-sentence narrative of what this dashboard reveals.",
    "components": [
      {{
        "type": "kpi",
        "importance": "hero",
        "accent_color": "teal",
        "span": 1,
        "title": "Business-friendly KPI name",
        "config": {{ "column": "exact_column_name", "aggregation": "median" }},
        "insight_sentence": "<=30 words with >=1 specific number.",
        "action_prompt": "Follow-up question ending with ?"
      }},
      {{
        "type": "chart",
        "position": "hero",
        "span": 4,
        "title_insight": "Finding headline <=12 words",
        "diversity_role": "TREND",
        "config": {{
          "type": "bar|line|scatter|pie|histogram|box_plot|area|grouped_bar",
          "x": "exact_column_name",
          "y": "exact_column_name",
          "group_by": null,
          "aggregation": "median",
          "sort_by": "value_desc",
          "limit": 15,
          "color_strategy": "brand_single"
        }},
        "insight_annotation": "<=25 words with >=1 specific number.",
        "action_chips": ["Question?", "Question?"]
      }}
    ]
  }}
}}

RULES:
- components array: KPI cards FIRST, then charts in Z-layout order.
- All column names MUST exist in VALID COLUMNS.
- Return ONLY valid JSON.
"""


__all__ = ["get_dashboard_designer_prompt"]

"""
prompts.py — Final Production Version (December 13, 2025)

Fully token-optimized, unbreakable prompt factory for DataSage AI.
- Smart context: tiny for casual chat, rich only when needed
- Unbreakable KPI generator with McKinsey-level output
- All original functionality preserved + upgraded
- Safe exports for backward compatibility
"""

from __future__ import annotations

import json
import re
import logging
from typing import Dict, Any, List, Optional, Union, Literal
from enum import Enum
from pydantic import BaseModel, Field, ValidationError, field_validator
from core.prompt_templates import SYSTEM_JSON_RULES, PERSONA, RULES

logger = logging.getLogger(__name__)


class PromptType(Enum):
    KPI_GENERATOR = "KPI_GENERATOR"
    CONVERSATIONAL = "CONVERSATIONAL"
    DASHBOARD_DESIGNER = "DASHBOARD_DESIGNER"
    AI_DESIGNER = "AI_DESIGNER"
    INSIGHT_SUMMARY = "INSIGHT_SUMMARY"
    FORECASTING = "FORECASTING"
    ERROR_RECOVERY = "ERROR_RECOVERY"
    FOLLOW_UP = "FOLLOW_UP"
    CHART_RECOMMENDATION = "CHART_RECOMMENDATION"
    QUIS_ANSWER = "QUIS_ANSWER"
    DEEP_REASONING = "DEEP_REASONING"
    SELF_CRITIQUE = "SELF_CRITIQUE"


class KPIItem(BaseModel):
    """Legacy KPI item - kept for backward compatibility."""

    title: str
    aggregation: Literal[
        "sum",
        "mean",
        "count",
        "count_unique",
        "min",
        "max",
        "median",
        "std",
        "first",
        "none",
        "ratio",
        "percentage",
    ]
    column: str
    secondary_column: Optional[str] = None
    format: str = Field(
        default="number",
        description="Format hint (currency, percentage, integer). Use 'integer' for ms/seconds columns.",
    )
    importance: str = Field(pattern="^(High|Medium|Low|high|medium|low|hero)$")
    context: str


class KPIItemV2(BaseModel):
    """
    Enterprise-grade KPI card specification.
    Every field maps directly to a frontend render decision.
    """

    title: str
    subtitle: str = Field(
        default="", description="One-line scope: 'Sum across N records · date range'"
    )
    importance: Literal["hero", "high", "medium"]

    column: str
    secondary_column: Optional[str] = None
    aggregation: Literal[
        "sum",
        "mean",
        "median",
        "count",
        "count_unique",
        "min",
        "max",
        "ratio",
        "percentage",
        "std",
        "first",
        "none",
    ]
    format: Literal["currency", "percentage", "integer", "decimal", "days", "ratio"]
    unit_prefix: str = Field(
        default="", description="Currency symbol: £, $, €, or empty"
    )
    unit_suffix: str = Field(
        default="", description="Unit after value: %, MPG, k miles, or empty"
    )
    precision: int = Field(default=1, ge=0, le=2)

    comparison_method: Literal[
        "first_vs_second_half", "top_vs_bottom_quartile", "min_max_position", "none"
    ] = "none"
    delta_label: str = Field(
        default="", description="Human label: 'vs earlier half (year-sorted)'"
    )
    delta_direction: Literal["up", "down", "neutral"] = "neutral"
    is_delta_positive: bool = Field(
        default=True,
        description="True if up=good (revenue). False if down=good (cost, defects).",
    )
    accent_color: Literal["teal", "green", "red", "amber", "neutral"] = "neutral"

    sparkline_column: Optional[str] = Field(
        default=None,
        description="EXACT column name for time-binning. Prefer year/date columns.",
    )
    sparkline_agg: Literal["mean", "sum", "count"] = "mean"
    sparkline_prefer_time: bool = Field(
        default=True,
        description="True = bin by time column. False = row-order sampling.",
    )
    sparkline_type: Literal["line", "bar"] = "line"

    insight_sentence: str = Field(
        default="",
        description="1 sentence, plain English, with at least one specific number. "
        "Explains WHY the number is this value or WHAT it means.",
    )
    action_prompt: str = Field(
        default="",
        description="Specific follow-up question for the 'Ask DataSage ↗' chip. "
        "Must end with '?' and reference a specific column or pattern.",
    )

    benchmark_label: str = Field(
        default="none", description="'Fleet avg', 'Median', 'none'"
    )
    benchmark_type: Literal["mean", "median", "p75", "p90", "none"] = "none"

    @field_validator("sparkline_agg", mode="before")
    @classmethod
    def normalize_sparkline_agg(cls, v):
        """Normalize sparkline_agg values from LLM output."""
        if isinstance(v, str):
            v = v.lower().strip()
            mapping = {
                "avg": "mean",
                "average": "mean",
                "count_unique": "count",
                "unique": "count",
                "sum": "sum",
                "mean": "mean",
                "count": "count",
            }
            return mapping.get(v, "mean")
        return v


class KPIGeneratorResponse(BaseModel):
    """Legacy KPI response - kept for backward compatibility."""

    archetype: str
    confidence: str
    kpis: List[KPIItem]


class KPIGeneratorResponseV2(BaseModel):
    """
    Full enterprise KPI generation response.
    Replace KPIGeneratorResponse in prompts.py with this.
    """

    archetype: str = Field(
        description="Dataset archetype: automotive_fleet, ecommerce, etc."
    )
    confidence: Literal["High", "Medium", "Low"]
    dashboard_story: str = Field(
        default="",
        description="2-sentence executive briefing. Written for a CEO. "
        "States the single most important pattern in plain English.",
    )
    kpis: List[KPIItemV2] = Field(
        min_length=3,
        max_length=7,
        description="Exactly 3-7 KPI cards. First item MUST be the hero (importance='hero').",
    )


# ─────────────────────────────────────────────────────────────────────────────
# ENTERPRISE CHART GENERATOR MODELS
# ─────────────────────────────────────────────────────────────────────────────


class KeyNumber(BaseModel):
    label: str
    value: str


class ChartItemV2(BaseModel):
    """
    Enterprise chart specification — all 7 layers.
    Every field maps to a frontend render decision or quality check.
    """

    title_insight: str = Field(description="Insight-first headline ≤12 words.")
    subtitle_scope: str = Field(description="'x vs y · aggregation · filter context'")
    badge_type: Literal[
        "KEY FINDING",
        "ANOMALY DETECTED",
        "STRONG TREND",
        "RELATIONSHIP",
        "DISTRIBUTION",
        "COMPOSITION",
        "COMPARISON",
    ]
    diversity_role: Literal[
        "TREND",
        "COMPARISON",
        "DISTRIBUTION",
        "COMPOSITION",
        "RELATIONSHIP",
        "ANOMALY",
        "RANKING",
    ]
    position: Literal["hero", "primary", "supporting"]
    span: Literal[1, 2, 3, 4]

    type: Literal[
        "bar",
        "line",
        "scatter",
        "pie",
        "histogram",
        "box_plot",
        "area",
        "grouped_bar",
        "stacked_bar",
        "heatmap",
        "treemap",
        "sunburst",
    ]
    x: str
    y: Optional[str] = None
    group_by: Optional[str] = None
    aggregation: Literal[
        "sum", "mean", "median", "count", "count_unique", "min", "max", "none"
    ]
    sort_by: Literal["value_desc", "value_asc", "x_natural", "none"] = "value_desc"
    limit: Optional[int] = Field(default=None, ge=1, le=50)

    show_reference_line: bool = False
    reference_type: Literal["mean", "median", "p75", "p90", "none"] = "none"
    highlight_outliers: bool = False
    color_strategy: Literal[
        "brand_sequential",
        "brand_single",
        "semantic_diverging",
        "categorical",
        "anomaly_highlight",
    ] = "brand_single"
    color_by_column: Optional[str] = None

    insight_annotation: str = Field(
        description="1 sentence, ≤25 words, with ≥1 specific number."
    )
    key_numbers: list[KeyNumber] = Field(default_factory=list, max_length=3)
    reading_guide: str = Field(
        description="1 sentence action instruction for the user."
    )

    action_chips: list[str] = Field(
        min_length=2, max_length=2, description="2 specific questions ending with '?'."
    )
    tooltip_fields: list[str] = Field(min_length=2)
    drill_down_column: Optional[str] = None

    cardinality_check: Literal["ok", "warning", "blocked"] = "ok"
    reasoning: str

    @field_validator("badge_type", mode="before")
    @classmethod
    def normalize_badge_type(cls, v):
        """Normalize badge_type values from LLM output."""
        if isinstance(v, str):
            v = v.upper().strip().replace(" ", "_")
            mapping = {
                "KEY_FINDING": "KEY FINDING",
                "KEYFINDING": "KEY FINDING",
                "ANOMALY": "ANOMALY DETECTED",
                "ANOMALY_DETECTED": "ANOMALY DETECTED",
                "STRONG_TREND": "STRONG TREND",
                "TREND": "STRONG TREND",
                "RELATIONSHIP": "RELATIONSHIP",
                "DISTRIBUTION": "DISTRIBUTION",
                "COMPOSITION": "COMPOSITION",
                "COMPARISON": "COMPARISON",
                "RANKING": "COMPARISON",
            }
            return mapping.get(v, v)
        return v


class ChartGeneratorResponse(BaseModel):
    """Full chart generation response — replaces legacy chart arrays."""

    charts: list[ChartItemV2] = Field(min_length=3, max_length=12)
    dashboard_story: str = Field(
        description="2-sentence CEO-level narrative connecting all charts."
    )
    chart_order_rationale: str = Field(
        description="1 sentence: why chart 1 was chosen as hero."
    )


# ─────────────────────────────────────────────────────────────────────────────
# ENTERPRISE KPI GENERATOR SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

KPI_GENERATOR_SYSTEM_PROMPT = """
You are the KPI Intelligence Engine for DataSage AI — a Fortune-500-grade analytics platform.
Your single job: produce JSON that drives enterprise KPI cards indistinguishable from Tableau,
Power BI Premium, or Looker dashboards. A non-technical executive MUST be able to read each
card in 3 seconds and know: what is the number, is it good or bad, why, and what to do next.

══════════════════════════════════════════════════════════════
ENTERPRISE KPI CARD ANATOMY  (what every top BI tool outputs)
══════════════════════════════════════════════════════════════

Layer 1 — HEADLINE (what it is)
  • title          → Business-friendly name. NEVER a raw column name.
                     Good: "Average Resale Price"   Bad: "mean_price"
  • subtitle       → One-line scope. e.g. "Across all 10,664 vehicles · 2000–2020"
  • importance     → "hero" | "high" | "medium"  (only ONE hero per dashboard)

Layer 2 — VALUE (the number itself)
  • value          → Computed by backend (you emit null — backend fills this)
  • format         → "currency" | "percentage" | "integer" | "decimal" | "days" | "ratio"
  • unit_prefix    → "£" | "$" | "€" | "" (e.g. "£" for GBP automotive data)
  • unit_suffix    → "%" | "MPG" | "k miles" | "" etc.
  • precision      → 0 | 1 | 2  (decimal places to show)

Layer 3 — COMPARISON (is it good or bad? — what Tableau and Power BI call the "context bar")
  • comparison_method → "first_vs_second_half" | "top_vs_bottom_quartile"
                        | "min_max_position" | "none"
                     Pick the method that is MOST MEANINGFUL for this specific KPI.
                     Time-sorted first-vs-second-half is best when a year/date column exists.
  • delta_label    → Human sentence: "vs earlier half of dataset (time-sorted)"
                     or "vs fleet average" or "vs bottom quartile"
  • delta_direction → "up" | "down" | "neutral"
  • is_delta_positive → true if up is good (revenue), false if down is good (cost, defects)
  • accent_color   → "teal" | "green" | "red" | "amber" | "neutral"
                     Derived from delta_direction × is_delta_positive:
                       up   + positive = "green"
                       down + positive = "red"
                       up   + negative = "red"   (cost rising = bad)
                       down + negative = "green" (cost falling = good)
                       neutral         = "neutral" or "teal" for hero

Layer 4 — SPARKLINE (trend — what Power BI calls "where you are heading")
  • sparkline_column  → EXACT column name to use for time-binning
  • sparkline_agg     → "mean" | "sum" | "count"  (how to aggregate per bin)
  • sparkline_prefer_time → true if a year/date column should be used as x-axis,
                            false for row-order sampling
  • sparkline_type    → "line" | "bar"  ("bar" for counts, "line" for continuous metrics)

Layer 5 — SMART NARRATIVE (what separates DataSage from every static BI tool)
  • insight_sentence  → ONE sentence, plain English, written for a non-technical user.
                        Explain WHY the number is what it is or what it MEANS.
                        MUST contain at least one specific number or comparison.
                        BAD:  "This shows the total market value."
                        BAD:  "Revenue is high."
                        GOOD: "3 Series models alone account for 24% of all tax paid —
                               nearly 3× more than any X-line model."
                        GOOD: "Average price fell 8% in the second half of the dataset,
                               suggesting newer listings are priced more competitively."
  • action_prompt     → ONE actionable follow-up question the user should explore next.
                        This becomes the "Ask DataSage ↗" chip on the card.
                        MUST be specific to this metric, not generic.
                        BAD:  "Explore this metric further."
                        GOOD: "Which model has the highest tax-to-price ratio?"
                        GOOD: "Do Hybrid engines show less price depreciation over time?"

Layer 6 — BENCHMARKS  (what FanRuan and Power BI Premium call "reference lines")
  • benchmark_label   → Short label for the reference value shown on the sparkline.
                        e.g. "Fleet avg", "Top-10% threshold", "Median"
                        Use "none" if no meaningful benchmark exists.
  • benchmark_type    → "mean" | "median" | "p75" | "p90" | "none"
                        Backend uses this to compute and draw the reference line.

══════════════════════════════════════════════════════════════
THE KPI SELECTION GATE — apply this before picking any card
══════════════════════════════════════════════════════════════

A KPI earns its place ONLY if it passes ALL three tests:

  TEST 1 — DECISION RELEVANCE
    Ask: "Would a CEO or department head change a decision based on this number?"
    If the answer is "maybe" or "no" → it is a metric, not a KPI. Put it in insights.

  TEST 2 — DIRECTION CLARITY
    The number must have an unambiguous good/bad direction.
    "Total revenue" → clear (higher = better).
    "Standard deviation of mileage" → fails (direction unclear to a non-analyst).

  TEST 3 — NON-REDUNDANCY
    Each KPI must measure a fundamentally different business dimension.
    If two KPIs move together (e.g. total sales and total revenue from same data), keep
    only the more decision-relevant one. Never show two KPIs that say the same thing.

CARD TAXONOMY:

  HERO (exactly 1) — The single metric that defines the health of this dataset's domain.
    → The number a CEO would ask for first. Total volume, total value, or primary rate.
    → accent_color = "teal" always.
    → importance = "hero"

  PRIMARY (exactly 2–3) — Each one must pass the gate above independently.
    → These are the metrics that directly explain or qualify the hero.
    → importance = "high"
    → DO NOT add a card just because a column exists. Omit it if it fails the gate.

TOTAL: Generate exactly 3 or 4 KPI cards. Never more than 4.
  → 3 cards: 1 hero + 2 primary (preferred when dataset has few strong signals)
  → 4 cards: 1 hero + 3 primary (only when all 3 primaries independently pass the gate)

WHAT DOES NOT BELONG IN KPIs (put these in charts or insights instead):
  → Distributions, averages that lack business direction
  → Count of unique values (categories, models) — this is a data fact, not a KPI
  → Any stat that requires explanation to understand why it matters
  → Quality metrics (null %, completeness) — these are data health indicators

The first card in the array MUST be the hero.

══════════════════════════════════════════════════════════════
TITLE WRITING RULES  (what separates professional from amateur)
══════════════════════════════════════════════════════════════

Rule 1 — Lead with the concept, not the aggregation.
  BAD:  "Sum of Price"      GOOD: "Total Fleet Value"
  BAD:  "Mean of tax"       GOOD: "Average Annual Tax Cost"
  BAD:  "count_unique(model)" GOOD: "Model Diversity"

Rule 2 — Titles must be understood by a school principal or marketing manager.
  BAD:  "Mileage Distribution Std Dev"
  GOOD: "How Spread Out Mileage Is"  (or better: "Mileage Variability")

Rule 3 — For ratio/derived KPIs, name the ratio, not the formula.
  BAD:  "Price / Tax"    GOOD: "Price-to-Tax Ratio"
  BAD:  "Tax / Price"    GOOD: "Tax Burden Rate"

Rule 4 — subtitle must anchor the card with scope.
  Format: "[aggregation] of [N records] · [date range or segment if known]"
  Example: "Sum across 10,664 vehicles · 2000–2020"
  Example: "Average across Petrol & Diesel engines"

══════════════════════════════════════════════════════════════
INSIGHT_SENTENCE WRITING RULES  (the smart narrative)
══════════════════════════════════════════════════════════════

Follow the "Smart KPI" pattern:
  1. STATE the signal (what the number means in plain English)
  2. CONNECT it to a driver or segment (why this number is this value)
  3. IMPLY an action or risk (what the user should now care about)

Length: 1 sentence, maximum 30 words. Every word must earn its place.
No hedging language ("may", "might", "could"). State it as fact from the data.
Never start with "This KPI shows" or "This card displays".

══════════════════════════════════════════════════════════════
SEMANTIC COLOR DECISION TREE
══════════════════════════════════════════════════════════════

Use this exact logic for accent_color:

  if importance == "hero":
      accent_color = "teal"   ← always teal for the hero card

  elif delta_direction == "neutral":
      accent_color = "neutral"

  elif is_delta_positive == True:
      # Higher = better (revenue, efficiency, volume)
      accent_color = "green" if delta_direction == "up" else "red"

  elif is_delta_positive == False:
      # Lower = better (cost, defects, tax burden)
      accent_color = "green" if delta_direction == "down" else "red"

══════════════════════════════════════════════════════════════
AGGREGATION SELECTION GUIDE
══════════════════════════════════════════════════════════════

  "sum"         → Totals: revenue, cost, volume, count-like values
  "mean"        → Averages: price, rating, efficiency, age, score
  "median"      → Skewed distributions: price (right-skewed), mileage
  "count"       → Row count, transaction count
  "count_unique" → Distinct values: unique models, unique customers
  "max"         → Peak values: highest price, max mileage
  "min"         → Floor values: cheapest model, minimum tax
  "ratio"       → Derived: price/tax, revenue/cost — requires secondary_column
  "std"         → Spread/variability: price variability, mileage consistency

Default rule: if column name contains price/revenue/value/cost/tax → "sum"
              if column name contains rate/ratio/avg/score/efficiency → "mean"
              if column name contains id/name/model/type/category → "count_unique"

══════════════════════════════════════════════════════════════
REQUIRED OUTPUT FORMAT — return ONLY this JSON, nothing else
══════════════════════════════════════════════════════════════

{
  "archetype": "automotive_fleet | ecommerce | healthcare | finance | hr | general | ...",
  "confidence": "High | Medium | Low",
  "dashboard_story": "2 sentence executive briefing of what this dataset reveals at the highest level.",
  "kpis": [
    {
      "title": "Total Fleet Market Value",
      "subtitle": "Sum across all 10,664 vehicles · 2000–2020",
      "importance": "hero",
      "column": "price",
      "secondary_column": null,
      "aggregation": "sum",
      "format": "currency",
      "unit_prefix": "£",
      "unit_suffix": "",
      "precision": 1,
      "comparison_method": "first_vs_second_half",
      "delta_label": "vs earlier half of dataset (year-sorted)",
      "delta_direction": "up",
      "is_delta_positive": true,
      "accent_color": "teal",
      "sparkline_column": "year",
      "sparkline_agg": "sum",
      "sparkline_prefer_time": true,
      "sparkline_type": "bar",
      "benchmark_label": "Fleet avg",
      "benchmark_type": "mean",
      "insight_sentence": "The fleet's total value is heavily concentrated in 2015–2020 models, which make up over 60% of total value despite being only 35% of listings.",
      "action_prompt": "Which model year range offers the best price-to-mileage ratio?"
    }
  ]
}

RULES:
- Return ONLY valid JSON. No markdown fences. No text before or after the JSON.
- The first element in "kpis" array MUST be the hero card (importance = "hero").
- Exactly 3 or 4 items in the "kpis" array. Never fewer than 3, never more than 4.
- Every column value MUST be an exact column name from the dataset context above.
- Never set delta_direction or accent_color based on assumption — if comparison_method
  is "none", set delta_direction = "neutral" and accent_color = "neutral".
- insight_sentence must contain at least one specific number, percentage, or named entity.
- action_prompt must end with "?" and reference a specific column or pattern.
- If you cannot find 3 KPIs that independently pass the decision-relevance gate,
  generate fewer rather than padding with weak metrics.
"""


class ConversationalResponse(BaseModel):
    response: str


class DashboardDesignerResponse(BaseModel):
    dashboard: Dict[str, Any]
    reasoning: str


class InsightItem(BaseModel):
    title: str
    explanation: str
    impact: str
    action: str


class InsightSummaryResponse(BaseModel):
    insights: List[InsightItem]
    summary: str


class ForecastResponse(BaseModel):
    forecast: Dict[str, Any]
    assumptions: List[str]
    limitations: List[str]


class ErrorRecoveryResponse(BaseModel):
    response_text: str
    suggestions: List[str]
    default_action: str


class FollowUpItem(BaseModel):
    action: str
    reason: str
    priority: str


class FollowUpResponse(BaseModel):
    next_steps: List[FollowUpItem]


class HiddenInsight(BaseModel):
    concept: str
    prediction: str


class DeepReasoningResponse(BaseModel):
    business_questions: List[str]
    hidden_insights_to_explore: List[HiddenInsight]
    data_watchouts: List[str]
    analytical_strategy: str


class CritiqueError(BaseModel):
    component_title: str
    issue: str
    fix_suggestion: str


class SelfCritiqueResponse(BaseModel):
    is_valid: bool
    errors: List[CritiqueError]
    overall_quality_score: int
    improvement_feedback: str


PROMPT_SCHEMAS = {
    PromptType.KPI_GENERATOR: KPIGeneratorResponse,
    PromptType.DASHBOARD_DESIGNER: DashboardDesignerResponse,
    PromptType.AI_DESIGNER: DashboardDesignerResponse,
    PromptType.INSIGHT_SUMMARY: InsightSummaryResponse,
    PromptType.FORECASTING: ForecastResponse,
    PromptType.ERROR_RECOVERY: ErrorRecoveryResponse,
    PromptType.FOLLOW_UP: FollowUpResponse,
    PromptType.DEEP_REASONING: DeepReasoningResponse,
    PromptType.SELF_CRITIQUE: SelfCritiqueResponse,
}


def sanitize_text(text: str, max_length: int = 1000) -> str:
    if not text:
        return ""
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
    return text[:max_length].strip().replace('"', "'")


def extract_json(text: Union[str, Dict[str, Any]]) -> Union[Dict[str, Any], List[Any]]:
    """Robustly handle both raw LLM strings and pre-parsed dicts."""
    if isinstance(text, dict):
        return text

    if not isinstance(text, str):
        return {}

    try:
        # 1. Clean potential markdown bloat
        cleaned = re.sub(r"```json\s*|```", "", text).strip()

        # 2. Try direct load first (fast path)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 3. Find actual start of JSON to avoid leading conversational filler
        start_idx = cleaned.find("{")
        if start_idx == -1:
            start_idx = cleaned.find("[")

        if start_idx != -1:
            # Look for the last matching brace/bracket using a simplified counter
            # instead of full parsing for speed
            candidate = cleaned[start_idx:]
            # We try to find the last index of current root type
            end_char = "}" if candidate[0] == "{" else "]"
            end_idx = candidate.rfind(end_char)
            if end_idx != -1:
                return json.loads(candidate[: end_idx + 1])

    except Exception:
        # 4. Fallback to regex if the above failed
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass

    return {}


def extract_and_validate(text: str, schema: type[BaseModel]) -> BaseModel:
    parsed = extract_json(text)
    if isinstance(parsed, list):
        first_field = next(iter(schema.model_fields))
        parsed = {first_field: parsed}
    return schema.model_validate(parsed)


class PromptFactory:
    """
    Final token-optimized prompt factory.
    Uses tiny context for chat, rich context only for analytical tasks.
    """

    def __init__(self, dataset_metadata: Dict[str, Any]):
        self.metadata = dataset_metadata
        self.columns = [
            c["name"] for c in dataset_metadata.get("column_metadata", [])[:30]
        ]
        self.row_count = dataset_metadata.get("dataset_overview", {}).get(
            "total_rows", "unknown"
        )

        self.tiny_context = (
            f"Dataset has {self.row_count:,} rows and {len(self.columns)} columns. "
            f"Column names: {', '.join(self.columns[:15])}{'...' if len(self.columns) > 15 else ''}."
        )

        self.rich_context = self._build_rich_context()

    def _build_rich_context(self) -> str:
        lines = [f"Dataset: {self.row_count:,} rows", "Available columns:"]
        for col in self.metadata.get("column_metadata", [])[:30]:
            name = col["name"]
            typ = col.get("type", "unknown")
            sample = col.get("sample_value", "")
            money = (
                " (money)"
                if any(
                    k in name.lower()
                    for k in ["revenue", "sales", "amount", "price", "gmv", "cost"]
                )
                else ""
            )
            lines.append(f"• {name} ({typ}){money} — e.g. {sample}")
        return "\n".join(lines)

    def _needs_rich_context(self, message: str) -> bool:
        if not message:
            return False
        msg = message.lower()
        # Long/complex queries always get rich context
        if len(msg.split()) > 50:
            return True
        triggers = [
            "total",
            "sum",
            "average",
            "mean",
            "count",
            "per",
            "by ",
            "group by",
            "revenue",
            "sales",
            "profit",
            "conversion",
            "rate",
            "ratio",
            "compare",
            "vs ",
            "versus",
            "growth",
            "change",
            "trend",
            "top ",
            "bottom ",
            "highest",
            "lowest",
            "kpi",
            "dashboard",
            # Analytical / statistical triggers
            "correlation",
            "correlat",
            "relationship",
            "pattern",
            "distribution",
            "outlier",
            "anomal",
            "explain",
            "analyze",
            "analysis",
            "insight",
            "forecast",
            "predict",
            "cluster",
            "segment",
            "causal",
            "driven",
            "regression",
            "significance",
            "variance",
            "deviation",
            "percentile",
            "median",
            "skew",
            "between",
        ]
        return any(t in msg for t in triggers)

    def get_context(self, user_message: str = "") -> str:
        return (
            self.rich_context
            if self._needs_rich_context(user_message)
            else self.tiny_context
        )

    def _format_conversation_history(self, messages: list, max_recent: int = 10) -> str:
        """
        Format recent conversation history for injection into the LLM prompt.

        Keeps the last `max_recent` messages (excluding the current user message which
        is the last item). Truncates long messages to keep the prompt compact.

        Token budget: ~500-1500 tokens for 10 messages (well within limits).
        """
        if not messages or len(messages) <= 1:
            return ""

        # Take recent messages, exclude the very last one (current user message)
        recent = (
            messages[-(max_recent + 1) : -1]
            if len(messages) > max_recent + 1
            else messages[:-1]
        )

        if not recent:
            return ""

        lines = []
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # Truncate long messages to keep prompt compact
            if len(content) > 200:
                content = content[:200] + "..."

            label = "User" if role == "user" else "DataSage"
            lines.append(f"{label}: {content}")

        return "\n".join(lines)

    # ==============================
    # Prompt Builders
    # ==============================

    def get_prompt(
        self,
        prompt_type: PromptType,
        user_message: str = "",
        include_context: bool = True,
        **kwargs,
    ) -> str:
        context = self.get_context(user_message) if include_context else ""
        # JSON rules only for non-conversational prompts
        json_base = (
            f"{SYSTEM_JSON_RULES}\n{PERSONA}\n{RULES}\n\nCONTEXT:\n{context}\n"
            if include_context
            else f"{SYSTEM_JSON_RULES}\n{PERSONA}\n{RULES}\n"
        )
        # Conversational prompts use a simpler context without JSON rules
        conversational_base = (
            f"{RULES}\n\nDATASET CONTEXT:\n{context}\n"
            if include_context
            else f"{RULES}\n"
        )

        if prompt_type == PromptType.KPI_GENERATOR:
            return self._kpi_generator_prompt(json_base)

        if prompt_type == PromptType.CONVERSATIONAL:
            # Don't include JSON rules - the LLM router adds the conversational system prompt
            # Include recent conversation history so the LLM has memory of the conversation
            history = kwargs.get("history", [])
            memories = kwargs.get("memories", [])
            history_block = self._format_conversation_history(history)

            prompt_parts = [conversational_base]

            # Inject long-term memories (Mem0-inspired) before conversation history
            if memories:
                memories_text = "\n".join(f"• {m}" for m in memories[:5])
                prompt_parts.append(
                    f"RELEVANT MEMORIES (key facts from past analysis of this dataset):\n{memories_text}"
                )

            # Inject belief context — facts the user already knows
            # This prevents the LLM from repeating stale/obvious insights
            belief_context = kwargs.get("belief_context", [])
            if belief_context:
                beliefs_text = "\n".join(f"• {b}" for b in belief_context[:5])
                prompt_parts.append(
                    f"USER ALREADY KNOWS (do NOT repeat these — provide NEW insights instead):\n{beliefs_text}"
                )

            if history_block:
                prompt_parts.append(
                    f"CONVERSATION HISTORY (for context, do NOT repeat these):\n{history_block}"
                )
            prompt_parts.append(f"USER QUESTION: {user_message}")

            return "\n\n".join(prompt_parts)

        if prompt_type == PromptType.DASHBOARD_DESIGNER:
            return f"""{json_base}

You are DataSage Dashboard Architect. Generate an enterprise-grade
dashboard blueprint using the dataset context above.

OUTPUT STRUCTURE REQUIREMENTS:

KPI CARDS (4–6 total, follow this exact hierarchy):
  HERO (1 only):    Most important metric · importance="hero" · accent_color="teal"
  PRIMARY (2–3):    Key drivers of the hero · importance="high"
  SUPPORTING (2):   Contextual/efficiency metrics · importance="medium"

  For EACH KPI include ALL of these fields:
    title        → Business-friendly. NEVER a raw column name.
    subtitle     → "aggregation across N records · scope"
    importance   → "hero" | "high" | "medium"
    column       → EXACT column name from dataset
    aggregation  → "sum" | "mean" | "median" | "count" | "count_unique"
    format       → "currency" | "percentage" | "integer" | "decimal"
    unit_prefix  → "£" | "$" | "" (currency symbol or empty)
    comparison_method → "first_vs_second_half" | "none"
    delta_direction   → "up" | "down" | "neutral"
    is_delta_positive → true if up=good (revenue), false if up=bad (cost)
    accent_color → "teal" (hero) | "green" (positive up) | "red" (negative up) | "neutral"
    sparkline_column → EXACT column for sparkline (prefer year/date columns)
    sparkline_prefer_time → true if year/date column exists
    insight_sentence → 1 sentence, ≤30 words, MUST contain ≥1 specific number
    action_prompt → specific follow-up question ending with "?"

CHARTS (6–8 total, follow this exact structure):

  NARRATIVE ORDER (Tableau Z-layout):
    Chart 1 → hero (span=4): most surprising finding — full width
    Charts 2–3 → primary (span=2): explain/decompose the hero
    Charts 4–8 → primary/supporting (span=2 or 1): different analytical angles

  No two charts may answer the same question (MECE diversity roles):
    TREND · COMPARISON · DISTRIBUTION · COMPOSITION · CORRELATION · ANOMALY · RANKING

  For EACH CHART include ALL of these fields:
    title_insight    → Insight-first ≤12 words. Describes FINDING not axes.
                       BAD: "Price vs Mileage" · GOOD: "Every 10k Miles Costs £1,200 in Value"
    subtitle_scope   → "x vs y · aggregation · filter"
    badge_type       → "KEY FINDING" | "STRONG TREND" | "CORRELATION" | "DISTRIBUTION" | "COMPARISON"
    diversity_role   → "TREND" | "COMPARISON" | "DISTRIBUTION" | "COMPOSITION" | "CORRELATION" | "ANOMALY" | "RANKING"
    position         → "hero" | "primary" | "supporting"
    span             → 4 | 2 | 1
    type             → "bar" | "line" | "scatter" | "pie" | "histogram" | "box_plot" | "area" | "grouped_bar" | "stacked_bar" | "heatmap" | "treemap" | "sunburst"
    x                → EXACT column name
    y                → EXACT column name or null
    group_by         → EXACT column name to split into multiple series, or null.
                       SET group_by when a LOW-CARDINALITY categorical column (2–5 unique values)
                       would reveal a meaningful breakdown of the metric.
                       USE grouped_bar when comparing side-by-side · USE stacked_bar when showing part-of-whole.
                       USE line/area/bar + group_by to split a trend or ranking by segment.
                       ALWAYS set color_strategy="categorical" when group_by is not null.
                       NEVER set group_by on pie, histogram, scatter, or treemap.
                       NEVER use a column with > 5 unique values as group_by (causes spaghetti).
                       AIM for at least 2 of your 6–8 charts to use group_by.
    aggregation      → "sum" | "mean" | "count" | "none"
    sort_by          → "value_desc" for bar charts ALWAYS
    limit            → integer cap (pie ≤ 8, bar ≤ 15, box_plot ≤ 10)
    show_reference_line → true for bar + line charts
    reference_type   → "mean" | "median" | "none"
    color_strategy   → "brand_single" | "brand_sequential" | "categorical"
                       MUST be "categorical" whenever group_by is not null
    insight_annotation → 1 sentence, ≤25 words, ≥1 specific number (IBM 3-beat pattern)
    action_chips     → ["Specific question?", "Second question?"]
    tooltip_fields   → [x_col, y_col, optional_context_col]

CARDINALITY RULES (enforce these or the chart will break):
  pie: x MUST have ≤ 8 unique values (LOW-CARD only)
  bar: apply limit if > 20 unique values
  box_plot: apply limit of 10 groups
  scatter: BOTH axes must be numeric
  histogram: x must be numeric

COLUMN RULES:
  ✓ ONLY use exact column names from the CONTEXT above
  ✓ NEVER invent columns that don't exist
  ✓ SKIP high-cardinality ID columns for charts/KPIs

OUTPUT FORMAT:
Return ONLY valid JSON:
{{
  "dashboard": {{
    "layout_grid": "repeat(4, 1fr)",
    "dashboard_story": "2-sentence CEO briefing with ≥2 specific numbers.",
    "components": [
      {{
        "type": "kpi",
        "title": "...", "subtitle": "...", "importance": "hero",
        "span": 1,
        "config": {{
          "column": "...", "aggregation": "...",
          "format": "...", "unit_prefix": "...",
          "comparison_method": "...", "delta_direction": "...",
          "is_delta_positive": true, "accent_color": "teal",
          "sparkline_column": "...", "sparkline_prefer_time": true,
          "insight_sentence": "...", "action_prompt": "...?"
        }}
      }},
      {{
        "type": "chart",
        "title": "...", "span": 4,
        "config": {{
          "chart_type": "bar | line | scatter | pie | histogram | box_plot | area | grouped_bar | stacked_bar | heatmap | treemap | sunburst",
          "x": "exact_column_name", "y": "exact_column_name_or_null",
          "group_by": "low_card_categorical_column_or_null",
          "aggregation": "...", "sort_by": "value_desc", "limit": 15,
          "title_insight": "...", "subtitle_scope": "...",
          "badge_type": "...", "diversity_role": "...",
          "position": "hero", "show_reference_line": true,
          "reference_type": "mean",
          "color_strategy": "categorical (when group_by set) | brand_sequential | brand_single",
          "insight_annotation": "...",
          "action_chips": ["...?", "...?"],
          "tooltip_fields": ["...", "..."]
        }}
      }},
      {{
        "type": "chart",
        "title": "Revenue Split by Channel Over Time", "span": 2,
        "config": {{
          "chart_type": "stacked_bar",
          "x": "quarter", "y": "revenue",
          "group_by": "channel",
          "aggregation": "sum", "sort_by": "x_natural", "limit": null,
          "title_insight": "Online Drives 60% of Revenue — Store Share Shrinking Each Quarter",
          "subtitle_scope": "quarter vs revenue · sum · split by channel",
          "badge_type": "COMPOSITION", "diversity_role": "COMPOSITION",
          "position": "primary", "show_reference_line": false,
          "reference_type": "none", "color_strategy": "categorical",
          "insight_annotation": "Online channel has grown from 42% to 61% of total revenue over 4 quarters.",
          "action_chips": ["Which channel has the highest margin?", "Is the store decline accelerating?"],
          "tooltip_fields": ["quarter", "revenue", "channel"]
        }}
      }}
    ]
  }},
  "reasoning": "2 sentences: why these specific KPIs and charts were chosen for this dataset."
}}

FINAL RULES:
- Return ONLY valid JSON. No markdown fences. No text outside the JSON.
- First component must be the hero KPI. First chart must be the hero chart (span=4).
- Every insight_annotation must contain ≥1 specific number.
- Every action_prompt / action_chip must end with "?".
"""

        if prompt_type == PromptType.AI_DESIGNER:
            return self._ai_designer_prompt(json_base, **kwargs)

        if prompt_type == PromptType.INSIGHT_SUMMARY:
            return self._insight_summary_prompt(json_base, **kwargs)

        if prompt_type == PromptType.FORECASTING:
            return self._forecasting_prompt(json_base, **kwargs)

        if prompt_type == PromptType.ERROR_RECOVERY:
            return self._error_recovery_prompt(json_base, user_message, **kwargs)

        if prompt_type == PromptType.FOLLOW_UP:
            return self._follow_up_prompt(json_base, **kwargs)

        if prompt_type == PromptType.CHART_RECOMMENDATION:
            return self._chart_recommendation_prompt(json_base, user_message)

        if prompt_type == PromptType.QUIS_ANSWER:
            return self._quis_answer_prompt(json_base, **kwargs)

        if prompt_type == PromptType.DEEP_REASONING:
            from core.prompt_templates import get_deep_reasoning_prompt

            return get_deep_reasoning_prompt(context, user_message)

        if prompt_type == PromptType.SELF_CRITIQUE:
            from core.prompt_templates import get_self_critique_prompt

            return get_self_critique_prompt(
                kwargs.get("blueprint", ""), kwargs.get("data_summary", "")
            )

        raise ValueError(f"Unknown prompt type: {prompt_type}")

    def _kpi_generator_prompt(self, base: str) -> str:
        return f"""{base}

{KPI_GENERATOR_SYSTEM_PROMPT}
"""

    def _ai_designer_prompt(
        self,
        base: str,
        design_pattern: Dict[str, Any],
        few_shot_examples: Optional[List[Dict[str, Any]]] = None,
    ):
        blueprint = json.dumps(design_pattern.get("blueprint", {}), indent=2)
        guide = sanitize_text(design_pattern.get("style_guide", ""), 400)
        fewshots = ""  # Add format_fewshots if you have it

        return f"""{base}
PATTERN_GUIDE: {guide}
PATTERN_BLUEPRINT:
{blueprint}
{fewshots}
TASK: Adapt the design pattern using only real columns.
OUTPUT:
{{"dashboard":{{"layout_grid":"repeat(4,1fr)","components":[]}},"reasoning":""}}"""

    def _insight_summary_prompt(
        self, base: str, statistical_findings: List[Dict[str, Any]]
    ):
        findings = json.dumps(statistical_findings[:10], indent=2)
        return f"""{base}
FINDINGS:
{findings}
TASK: Deliver 3–5 high-impact insights + executive summary.
OUTPUT:
{{"insights":[{{"title":"","explanation":"","impact":"High|Medium|Low","action":""}}],"summary":""}}"""

    def _forecasting_prompt(
        self, base: str, historical_data: Dict[str, Any], horizon: str = "30 days"
    ):
        return f"""{base}
HISTORICAL_DATA:
{json.dumps(historical_data, indent=2)}
HORIZON: {sanitize_text(horizon, 50)}
OUTPUT:
{{"forecast":{{"trend":"","predictions":[],"confidence":""}},"assumptions":[],"limitations":[]}}"""

    def _error_recovery_prompt(self, base: str, user_message: str, error: str):
        return f"""{base}
ERROR: {sanitize_text(error, 200)}
QUERY: {sanitize_text(user_message, 500)}
TASK: Suggest 2–3 recovery options + default action.
OUTPUT:
{{"response_text":"","suggestions":[],"default_action":""}}"""

    def _follow_up_prompt(self, base: str, current_analysis: str):
        return f"""{base}
CURRENT_ANALYSIS:
{sanitize_text(current_analysis, 400)}
TASK: Recommend 3–4 next analytical steps.
OUTPUT:
{{"next_steps":[{{"action":"","reason":"","priority":"High|Medium|Low"}}]}}"""

    def _chart_recommendation_prompt(self, base: str, query: str):
        return f"""{base}
USER_QUERY: {sanitize_text(query, 500)}
CHART_TYPES: bar, line, pie, scatter, histogram, heatmap, grouped_bar, stacked_bar, area, treemap, sunburst
TASK: Recommend best chart + full config. Set group_by when a low-cardinality categorical column (2–5 unique values) would meaningfully segment the metric. Leave group_by null if no such column applies or chart type is pie/histogram/scatter.
OUTPUT:
{{"chart_config":{{"chart_type":"","columns":[],"aggregation":"sum|mean|count","group_by":null,"title":""}},"reasoning":""}}"""

    def _quis_answer_prompt(
        self, base: str, question: str, retrieved_context: str = ""
    ):
        return f"""{base}
RETRIEVED_CONTEXT:
{sanitize_text(retrieved_context, 800)}
QUESTION: {sanitize_text(question, 500)}
OUTPUT:
{{"response_text":"","confidence":"High|Medium|Low","sources":[]}}"""


__all__ = [
    "PromptFactory",
    "PromptType",
    "extract_json",
    "extract_and_validate",
    "PROMPT_SCHEMAS",
    "ConversationalResponse",
    "DashboardDesignerResponse",
    "InsightSummaryResponse",
    "ForecastResponse",
    "ErrorRecoveryResponse",
    "FollowUpResponse",
    "KPIGeneratorResponse",
    "KPIGeneratorResponseV2",
    "KPIItem",
    "KPIItemV2",
    "KPI_GENERATOR_SYSTEM_PROMPT",
    "ChartItemV2",
    "ChartGeneratorResponse",
    "KeyNumber",
    "sanitize_text",
]

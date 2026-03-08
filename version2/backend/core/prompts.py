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
from typing import Dict, Any, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, ValidationError
from core.prompt_templates import SYSTEM_JSON_RULES, PERSONA, RULES

logger = logging.getLogger(__name__)


# ==============================
# Enums & Models
# ==============================

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

class KPIItem(BaseModel):
    title: str
    aggregation: str
    column: str
    secondary_column: Optional[str] = None
    format: str
    importance: str
    context: str

class KPIGeneratorResponse(BaseModel):
    archetype: str
    confidence: str
    kpis: List[KPIItem]

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

PROMPT_SCHEMAS = {
    PromptType.KPI_GENERATOR: KPIGeneratorResponse,
    PromptType.DASHBOARD_DESIGNER: DashboardDesignerResponse,
    PromptType.AI_DESIGNER: DashboardDesignerResponse,
    PromptType.INSIGHT_SUMMARY: InsightSummaryResponse,
    PromptType.FORECASTING: ForecastResponse,
    PromptType.ERROR_RECOVERY: ErrorRecoveryResponse,
    PromptType.FOLLOW_UP: FollowUpResponse
}


# ==============================
# Utilities
# ==============================

def sanitize_text(text: str, max_length: int = 1000) -> str:
    if not text:
        return ""
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    return text[:max_length].strip().replace('"', "'")

def extract_json(text: str) -> Union[Dict[str, Any], List[Any]]:
    start = text.find("{")
    if start == -1:
        start = text.find("[")
    if start == -1:
        raise ValueError("No JSON found")

    depth = 0
    in_string = False
    escape = False

    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if not in_string:
            if ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i+1])
    raise ValueError("Unbalanced JSON")


def extract_and_validate(text: str, schema: type[BaseModel]) -> BaseModel:
    parsed = extract_json(text)
    if isinstance(parsed, list):
        first_field = next(iter(schema.model_fields))
        parsed = {first_field: parsed}
    return schema.model_validate(parsed)


# ==============================
# Smart Context Manager
# ==============================

class PromptFactory:
    """
    Final token-optimized prompt factory.
    Uses tiny context for chat, rich context only for analytical tasks.
    """

    def __init__(self, dataset_metadata: Dict[str, Any]):
        self.metadata = dataset_metadata
        self.columns = [c["name"] for c in dataset_metadata.get("column_metadata", [])[:30]]
        self.row_count = dataset_metadata.get("dataset_overview", {}).get("total_rows", "unknown")

        self.tiny_context = (
            f"Dataset has {self.row_count:,} rows and {len(self.columns)} columns. "
            f"Column names: {', '.join(self.columns[:15])}{'...' if len(self.columns)>15 else ''}."
        )

        self.rich_context = self._build_rich_context()

    def _build_rich_context(self) -> str:
        lines = [f"Dataset: {self.row_count:,} rows", "Available columns:"]
        for col in self.metadata.get("column_metadata", [])[:30]:
            name = col["name"]
            typ = col.get("type", "unknown")
            sample = col.get("sample_value", "")
            money = " (money)" if any(k in name.lower() for k in ["revenue","sales","amount","price","gmv","cost"]) else ""
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
            "total", "sum", "average", "mean", "count", "per", "by ", "group by",
            "revenue", "sales", "profit", "conversion", "rate", "ratio",
            "compare", "vs ", "versus", "growth", "change", "trend",
            "top ", "bottom ", "highest", "lowest", "kpi", "dashboard",
            # Analytical / statistical triggers
            "correlation", "correlat", "relationship", "pattern", "distribution",
            "outlier", "anomal", "explain", "analyze", "analysis", "insight",
            "forecast", "predict", "cluster", "segment", "causal", "driven",
            "regression", "significance", "variance", "deviation", "percentile",
            "median", "skew", "between",
        ]
        return any(t in msg for t in triggers)

    def get_context(self, user_message: str = "") -> str:
        return self.rich_context if self._needs_rich_context(user_message) else self.tiny_context

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
        recent = messages[-(max_recent + 1):-1] if len(messages) > max_recent + 1 else messages[:-1]
        
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

    def get_prompt(self, prompt_type: PromptType, user_message: str = "", **kwargs) -> str:
        context = self.get_context(user_message)
        # JSON rules only for non-conversational prompts
        json_base = f"{SYSTEM_JSON_RULES}\n{PERSONA}\n{RULES}\n\nCONTEXT:\n{context}\n"
        # Conversational prompts use a simpler context without JSON rules
        conversational_base = f"{RULES}\n\nDATASET CONTEXT:\n{context}\n"

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
            
            if history_block:
                prompt_parts.append(f"CONVERSATION HISTORY (for context, do NOT repeat these):\n{history_block}")
            prompt_parts.append(f"USER QUESTION: {user_message}")
            
            return "\n\n".join(prompt_parts)

        if prompt_type == PromptType.DASHBOARD_DESIGNER:
            return f"""{json_base}
TASK: Build an executive dashboard with 3–4 KPIs, 4–6 charts, 1 table.
Use only real columns.
OUTPUT:
{{"dashboard":{{"layout_grid":"repeat(4,1fr)","components":[]}},"reasoning":""}}"""

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

        raise ValueError(f"Unknown prompt type: {prompt_type}")

    def _kpi_generator_prompt(self, base: str) -> str:
        return f"""{base}

You are a McKinsey partner presenting to a Fortune 10 CEO tomorrow.
One mistake and you're fired.

TASK: Generate exactly 6–8 perfect executive KPI cards.
Detect archetype first.
Never use raw column names in titles.
Always add context (% change, % of total, concentration, benchmark).

OUTPUT:
{{
  "archetype": "ecommerce_sales|cricket|healthcare|...",
  "confidence": "High|Medium|Low",
  "kpis": [
    {{
      "title": "Total Revenue",
      "aggregation": "sum|mean|count|ratio|percentage",
      "column": "exact_column_name",
      "secondary_column": "optional_divisor",
      "format": "currency|percent|integer|decimal|days",
      "importance": "hero|high|medium",
      "context": "↑12% YoY / Top 3 = 38% / vs target 94%"
    }}
  ]
}}
Exactly 6–8 items.
"""

    def _ai_designer_prompt(self, base: str, design_pattern: Dict[str, Any], few_shot_examples: Optional[List[Dict[str, Any]]] = None):
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

    def _insight_summary_prompt(self, base: str, statistical_findings: List[Dict[str, Any]]):
        findings = json.dumps(statistical_findings[:10], indent=2)
        return f"""{base}
FINDINGS:
{findings}
TASK: Deliver 3–5 high-impact insights + executive summary.
OUTPUT:
{{"insights":[{{"title":"","explanation":"","impact":"High|Medium|Low","action":""}}],"summary":""}}"""

    def _forecasting_prompt(self, base: str, historical_data: Dict[str, Any], horizon: str = "30 days"):
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
CHART_TYPES: bar, line, pie, scatter, histogram, heatmap, grouped_bar, area, treemap
TASK: Recommend best chart + full config.
OUTPUT:
{{"chart_config":{{"chart_type":"","columns":[],"aggregation":"sum|mean|count","title":""}},"reasoning":""}}"""

    def _quis_answer_prompt(self, base: str, question: str, retrieved_context: str = ""):
        return f"""{base}
RETRIEVED_CONTEXT:
{sanitize_text(retrieved_context, 800)}
QUESTION: {sanitize_text(question, 500)}
OUTPUT:
{{"response_text":"","confidence":"High|Medium|Low","sources":[]}}"""


# ==============================
# Safe Exports
# ==============================

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
    "sanitize_text",
]
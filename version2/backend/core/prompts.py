from __future__ import annotations
import json
import re
import hashlib
import logging
from typing import Dict, Any, List, Optional, Union
from enum import Enum
from functools import lru_cache
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

class ConversationalResponse(BaseModel):
    response_text: str = Field(..., min_length=1, max_length=5000)
    chart_config: Optional[Dict[str, Any]] = None
    confidence: str = Field(default="High", pattern="^(High|Medium|Low)$")

class DashboardDesignerResponse(BaseModel):
    dashboard: Dict[str, Any]
    reasoning: Optional[str] = Field(default="", max_length=1000)

class InsightSummaryResponse(BaseModel):
    insights: List[Dict[str, Any]] = Field(..., min_length=1, max_length=10)
    summary: str = Field(..., max_length=2000)

class ForecastResponse(BaseModel):
    forecast: Dict[str, Any]
    assumptions: List[str] = Field(default_factory=list, max_length=5)
    limitations: List[str] = Field(default_factory=list, max_length=5)

class ErrorRecoveryResponse(BaseModel):
    response_text: str = Field(..., min_length=1, max_length=2000)
    suggestions: List[str] = Field(..., min_length=1, max_length=5)
    default_action: str = Field(..., max_length=500)

class FollowUpResponse(BaseModel):
    next_steps: List[Dict[str, str]] = Field(..., min_length=1, max_length=5)

class PromptType(str, Enum):
    CONVERSATIONAL = "conversational"
    DASHBOARD_DESIGNER = "dashboard_designer"
    AI_DESIGNER = "ai_designer"
    INSIGHT_SUMMARY = "insight_summary"
    FORECASTING = "forecasting"
    ERROR_RECOVERY = "error_recovery"
    FOLLOW_UP = "follow_up"
    CHART_RECOMMENDATION = "chart_recommendation"
    QUIS_ANSWER = "quis_answer"

PROMPT_SCHEMAS = {
    PromptType.CONVERSATIONAL: ConversationalResponse,
    PromptType.DASHBOARD_DESIGNER: DashboardDesignerResponse,
    PromptType.AI_DESIGNER: DashboardDesignerResponse,
    PromptType.INSIGHT_SUMMARY: InsightSummaryResponse,
    PromptType.FORECASTING: ForecastResponse,
    PromptType.ERROR_RECOVERY: ErrorRecoveryResponse,
    PromptType.FOLLOW_UP: FollowUpResponse,
}

SYSTEM_JSON_RULES = "OUTPUT: Valid JSON only. No code fences. No text outside JSON."
GLOBAL_BEHAVIOR_RULES = "RULES: Use ONLY columns in DATASET_CONTEXT. Do NOT invent columns or placeholders."
PERSONA_ANALYTICAL = "ROLE: Analytical data expert. Style: concise, factual."

def sanitize_text(text: str, max_length: int = 1000) -> str:
    if not text:
        return ""
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    text = text[:max_length]
    text = text.replace('"', "'")
    return text.strip()

def sanitize_error(error: str, max_length: int = 200) -> str:
    if not error:
        return "Unknown error"
    last_line = error.strip().split("\n")[-1]
    return sanitize_text(last_line, max_length)

def extract_json(text: str) -> Union[Dict[str, Any], List[Any]]:
    start_obj = text.find("{")
    start_arr = text.find("[")
    if start_obj == -1 and start_arr == -1:
        raise ValueError("No JSON found")
    if start_obj == -1:
        return _extract_array(text, start_arr)
    if start_arr == -1 or start_obj < start_arr:
        return _extract_object(text, start_obj)
    return _extract_array(text, start_arr)

def _extract_object(text: str, start: int) -> Dict[str, Any]:
    depth = 0
    in_string = False
    escape = False
    for idx, ch in enumerate(text[start:], start=start):
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
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    block = text[start:idx+1]
                    return json.loads(block)
    raise ValueError("Unbalanced JSON object")

def _extract_array(text: str, start: int) -> List[Any]:
    depth = 0
    in_string = False
    escape = False
    for idx, ch in enumerate(text[start:], start=start):
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
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    block = text[start:idx+1]
                    return json.loads(block)
    raise ValueError("Unbalanced JSON array")

def extract_and_validate(text: str, schema: type[BaseModel]) -> BaseModel:
    parsed = extract_json(text)
    if isinstance(parsed, list):
        first_field = list(schema.model_fields.keys())[0]
        parsed = {first_field: parsed}
    try:
        return schema.model_validate(parsed)
    except ValidationError as e:
        raise ValueError(f"Schema validation failed: {e}") from e

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

@lru_cache(maxsize=100)
def build_context_cached(key: str, metadata_json: str, max_cols: int) -> str:
    return _build_context_internal(json.loads(metadata_json), max_cols)

def _build_context_internal(metadata: Dict[str, Any], max_cols: int) -> str:
    cols = metadata.get("column_metadata", [])[:max_cols]
    col_list = []
    for c in cols:
        name = c.get("name", "unknown")
        ctype = c.get("type", "unknown")
        sample = c.get("sample_value", "")
        col_list.append(f"{name} ({ctype})" + (f" e.g. {sample}" if sample else ""))
    overview = metadata.get("dataset_overview", {})
    ctx = {"total_rows": overview.get("total_rows", "N/A"), "total_columns": overview.get("total_columns", "N/A"), "columns": col_list}
    if len(metadata.get("column_metadata", [])) > max_cols:
        ctx["note"] = f"Showing first {max_cols} of {len(metadata.get('column_metadata', []))} columns"
    return json.dumps(ctx, indent=2)

def build_context(metadata: Dict[str, Any], max_cols: int = 12) -> str:
    metadata_json = json.dumps(metadata, sort_keys=True)
    key = hashlib.md5(metadata_json.encode()).hexdigest()
    return build_context_cached(key, metadata_json, max_cols)

def format_fewshots(examples: Optional[List[Dict[str, Any]]], max_examples: int = 3) -> str:
    if not examples:
        return ""
    out = []
    total_tokens = 0
    max_tokens = 2000
    for i, ex in enumerate(examples[:max_examples], 1):
        if not isinstance(ex, dict) or "input" not in ex or "output" not in ex:
            logger.warning("Skipping malformed few-shot example")
            continue
        block = f"BEGIN_EXAMPLE_{i}\nINPUT: {json.dumps(ex['input'])}\nOUTPUT: {json.dumps(ex['output'])}\nEND_EXAMPLE_{i}"
        tokens = estimate_tokens(block)
        if total_tokens + tokens > max_tokens:
            break
        out.append(block)
        total_tokens += tokens
    return "\n\n".join(out)

class PromptFactory:
    def __init__(self, dataset_metadata: Optional[Dict[str, Any]] = None, dataset_context: str = "", user_preferences: Optional[Dict[str, Any]] = None, schema: Optional[Dict[str, Any]] = None, rag_service=None, max_cols: int = 12):
        if dataset_metadata:
            self.dataset_context = build_context(dataset_metadata, max_cols)
        else:
            self.dataset_context = dataset_context
        self.user_prefs = user_preferences or {}
        self.schema = schema or {}
        self.rag_service = rag_service

    def get_prompt(self, task: PromptType, **params) -> str:
        if task == PromptType.CONVERSATIONAL:
            prompt = self._conversational_prompt(**params)
        elif task == PromptType.DASHBOARD_DESIGNER:
            prompt = self._dashboard_designer_prompt(**params)
        elif task == PromptType.AI_DESIGNER:
            prompt = self._ai_designer_prompt(**params)
        elif task == PromptType.INSIGHT_SUMMARY:
            prompt = self._insight_summary_prompt(**params)
        elif task == PromptType.FORECASTING:
            prompt = self._forecast_prompt(**params)
        elif task == PromptType.ERROR_RECOVERY:
            prompt = self._error_recovery_prompt(**params)
        elif task == PromptType.FOLLOW_UP:
            prompt = self._follow_up_prompt(**params)
        elif task == PromptType.CHART_RECOMMENDATION:
            prompt = self._chart_recommendation_prompt(**params)
        elif task == PromptType.QUIS_ANSWER:
            prompt = self._quis_prompt(**params)
        else:
            raise ValueError(f"Unknown task: {task}")
        tokens = estimate_tokens(prompt)
        logger.info(f"Built prompt ~{tokens} tokens for task={task.value}")
        return prompt

    def get_schema(self, task: PromptType):
        return PROMPT_SCHEMAS.get(task)

    def _conversational_prompt(self, query: str = "", history: Optional[List[Dict[str, str]]] = None, allow_markdown: bool = True):
        safe_query = sanitize_text(query, 500)
        hist = ""
        if history:
            hist_lines = []
            for m in history[-3:]:
                role = m.get("role", "user")
                content = sanitize_text(m.get("content", ""), 150)
                hist_lines.append(f"{role}: {content}")
            hist = "\nCONVERSATION_HISTORY:\n" + "\n".join(hist_lines)
        
        persona = PERSONA_ANALYTICAL
        markdown_note = "Use markdown formatting (bold, lists, code blocks) in response_text for better readability" if allow_markdown else "Use plain text only in response_text"
        
        # CRITICAL FIX: Don't show empty string in example format!
        return f"""{SYSTEM_JSON_RULES}
{persona}
{GLOBAL_BEHAVIOR_RULES}

DATASET_CONTEXT:
{self.dataset_context}

{hist}

USER_QUESTION: {safe_query}

INSTRUCTIONS:
1. Analyze the user's question in context of the dataset
2. Provide a detailed, helpful answer in the "response_text" field
3. If user asks to "show", "draw", "create", "visualize", or "plot" a chart, include "chart_config" with proper Plotly configuration
4. For chart requests, specify: type (bar/line/pie/scatter/histogram), x column, y column, and any aggregation needed
5. Set "confidence" to High/Medium/Low based on data quality
6. {markdown_note}

CHART TYPES AVAILABLE: bar, line, pie, scatter, histogram, heatmap, box, violin

IMPORTANT: 
- The response_text field MUST contain your actual answer. Do NOT leave it empty!
- When user asks for a chart, you MUST include chart_config with real column names from the dataset
- Use ONLY columns that exist in DATASET_CONTEXT above

OUTPUT_FORMAT (example with chart):
{{
  "response_text": "Here's a bar chart showing total runs by batsman. The visualization reveals that Virat Kohli leads with 12,000 runs.",
  "chart_config": {{
    "type": "bar",
    "x": "batsman",
    "y": "total_runs",
    "title": "Total Runs by Batsman",
    "xaxis": {{"title": "Batsman"}},
    "yaxis": {{"title": "Total Runs"}}
  }},
  "confidence": "High"
}}

OUTPUT_FORMAT (example without chart):
{{
  "response_text": "The dataset contains 6 columns including batsman, total_runs, average, and strikerate. You can create various visualizations from this data.",
  "chart_config": null,
  "confidence": "High"
}}

Now respond to the user's question:""".strip()

    def _dashboard_designer_prompt(self, fewshots: Optional[List[Dict[str, Any]]] = None):
        return f"{SYSTEM_JSON_RULES}\n{PERSONA_ANALYTICAL}\n{GLOBAL_BEHAVIOR_RULES}\nTASK: Build a dashboard with 3-4 KPIs, 3-6 charts, 1 table. Use only real columns.\nCHART_TYPES: bar,line,pie,scatter,histogram,heatmap,grouped_bar,area,treemap\nDATASET_CONTEXT:\n{self.dataset_context}\n{format_fewshots(fewshots)}\nFORMAT:\n{{\"dashboard\":{{\"layout_grid\":\"repeat(4,1fr)\",\"components\":[]}},\"reasoning\":\"\"}}".strip()

    def _ai_designer_prompt(self, design_pattern: Dict[str, Any], few_shot_examples: Optional[List[Dict[str, Any]]] = None):
        blueprint = json.dumps(design_pattern.get("blueprint", {}))
        guide = sanitize_text(design_pattern.get("style_guide", ""), 400)
        fewshots = format_fewshots(few_shot_examples)
        return f"{SYSTEM_JSON_RULES}\n{PERSONA_ANALYTICAL}\n{GLOBAL_BEHAVIOR_RULES}\nPATTERN_GUIDE: {guide}\nPATTERN_BLUEPRINT: {blueprint}\n{fewshots}\nDATASET_CONTEXT:\n{self.dataset_context}\nTASK: Adapt pattern using only real dataset columns.\nFORMAT:\n{{\"dashboard\":{{\"layout_grid\":\"repeat(4,1fr)\",\"components\":[]}},\"reasoning\":\"\"}}".strip()

    def _insight_summary_prompt(self, statistical_findings: List[Dict[str, Any]]):
        safe_findings = json.dumps(statistical_findings[:10], indent=2)
        return f"{SYSTEM_JSON_RULES}\n{PERSONA_ANALYTICAL}\nDATASET_CONTEXT:\n{self.dataset_context}\nFINDINGS: {safe_findings}\nTASK: Produce 3-5 actionable insights + summary.\nFORMAT:\n{{\"insights\":[{{\"title\":\"\",\"explanation\":\"\",\"impact\":\"High\",\"action\":\"\"}}],\"summary\":\"\"}}".strip()

    def _forecast_prompt(self, historical_data: Dict[str, Any], horizon: str = "30 days"):
        return f"{SYSTEM_JSON_RULES}\n{PERSONA_ANALYTICAL}\nDATASET_CONTEXT:\n{self.dataset_context}\nHISTORY: {json.dumps(historical_data)}\nHORIZON: {sanitize_text(horizon,50)}\nFORMAT:\n{{\"forecast\":{{\"trend\":\"\",\"predictions\":[],\"confidence\":\"High\"}},\"assumptions\":[],\"limitations\":[]}}".strip()

    def _error_recovery_prompt(self, error: str, user_query: str):
        return f"{SYSTEM_JSON_RULES}\n{PERSONA_ANALYTICAL}\nERROR: {sanitize_error(error)}\nQUERY: {sanitize_text(user_query)}\nDATASET_CONTEXT:\n{self.dataset_context}\nTASK: Provide 2-3 clarifying options + default recommendation.\nFORMAT:\n{{\"response_text\":\"\",\"suggestions\":[],\"default_action\":\"\"}}".strip()

    def _follow_up_prompt(self, current_analysis: str):
        return f"{SYSTEM_JSON_RULES}\n{PERSONA_ANALYTICAL}\nCURRENT_ANALYSIS: {sanitize_text(current_analysis,400)}\nDATASET_CONTEXT:\n{self.dataset_context}\nTASK: Provide 3-4 next analytical steps.\nFORMAT:\n{{\"next_steps\":[{{\"action\":\"\",\"reason\":\"\",\"priority\":\"High\"}}]}}".strip()

    def _chart_recommendation_prompt(self, query: str = ""):
        return f"{SYSTEM_JSON_RULES}\n{PERSONA_ANALYTICAL}\nQUERY: {sanitize_text(query,500)}\nDATASET_CONTEXT:\n{self.dataset_context}\nCHART_TYPES: bar,line,pie,scatter,histogram,heatmap,grouped_bar,area\nTASK: Recommend best chart + config.\nFORMAT:\n{{\"chart_config\":{{\"chart_type\":\"\",\"columns\":[],\"aggregation\":\"sum\",\"title\":\"\"}},\"reasoning\":\"\"}}".strip()

    def _quis_prompt(self, question: str, retrieved_context: str = ""):
        return f"{SYSTEM_JSON_RULES}\n{PERSONA_ANALYTICAL}\nQUESTION: {sanitize_text(question,500)}\nRETRIEVED_CONTEXT: {sanitize_text(retrieved_context,800)}\nDATASET_CONTEXT:\n{self.dataset_context}\nFORMAT:\n{{\"response_text\":\"\",\"confidence\":\"High\",\"sources\":[]}}".strip()

__all__ = [
    "PromptFactory",
    "PromptType",
    "extract_json",
    "extract_and_validate",
    "build_context",
    "sanitize_text",
    "sanitize_error",
    "estimate_tokens",
    "PROMPT_SCHEMAS",
    "ConversationalResponse",
    "DashboardDesignerResponse",
    "InsightSummaryResponse",
    "ForecastResponse",
    "ErrorRecoveryResponse",
    "FollowUpResponse",
]

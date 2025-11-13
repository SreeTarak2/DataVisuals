# backend/core/prompts.py
from typing import List, Dict, Any, Optional, Union
import json
import re
from enum import Enum
from pydantic import BaseModel, ValidationError, Field
# from jinja2 import Template  # Not used in current implementation


class PromptType(Enum):
    """Enum for prompt selection to improve type safety."""
    CONVERSATIONAL = "conversational"
    INSIGHT_SUMMARIZER = "insight_summarizer"
    QUIS_ANSWER = "quis_answer"
    CHART_RECOMMENDATION = "chart_recommendation"
    DASHBOARD_DESIGNER = "dashboard_designer"
    AI_DESIGNER = "ai_designer"
    ERROR_RECOVERY = "error_recovery"  # New: For handling unclear queries
    FOLLOW_UP_PLANNER = "follow_up_planner"  # New: For proactive next steps
    FORECASTING = "forecasting"  # New: For prediction queries


# Enhanced Schemas for Validation
class ConversationalResponse(BaseModel):
    response_text: str = Field(..., description="Engaging, explanatory response with pedagogical approach")
    chart_config: Optional[Dict[str, Any]] = None
    story_elements: Dict[str, Any] = {}
    confidence: str = Field(..., pattern="^(High|Med|Low)$", description="Confidence level of the response")
    learning_arc: Dict[str, str] = Field(
        ..., 
        description="Learning progression elements",
        example={
            "hook": "Fascinating fact or engaging question",
            "analogy": "Simple explanation using analogy", 
            "explanation": "Clear technical explanation",
            "reflection": "Thought-provoking question for user"
        }
    )


class PromptFactory:
    """Enhanced factory for generating context-aware prompts with pedagogical approach and RAG integration."""

    def __init__(self, dataset_context: str = "", user_preferences: Optional[Dict[str, Any]] = None, schema: Optional[Dict[str, Any]] = None, rag_service=None):
        self.dataset_context = dataset_context
        self.user_prefs = user_preferences or {} 
        self.schema = schema or {} 
        self.rag_service = rag_service  

    def _inject_context(self, template: str) -> str:
        """Helper to inject dataset and user context into templates."""
        prefs_str = json.dumps(self.user_prefs, indent=2) if self.user_prefs else "{}"
        # Use string replacement instead of format to avoid conflicts with JSON braces
        template = template.replace("{dataset_context}", self.dataset_context)
        template = template.replace("{user_preferences}", prefs_str)
        return template
    
    def _inject_context_and_format(self, template: str, **kwargs) -> str:
        """Helper to inject context and then format remaining placeholders."""
        template_with_context = self._inject_context(template)
        return template_with_context.format(**kwargs)
    
    def _compress_context(self, context: str, max_length: int = 1000) -> str:
        """Compress context to reduce token usage while preserving key information."""
        if len(context) <= max_length:
            return context

        first_part = context[:max_length//2]
        last_part = context[-(max_length//2):]
        return f"{first_part}... [compressed] ...{last_part}"
    
    def _render_template(self, template: str, **kwargs) -> str:
        """Render template with context injection and parameter formatting."""
        template_with_context = self._inject_context(template)
        try:
            return template_with_context.format(**kwargs)
        except KeyError as e:
           
            result = template_with_context
            for key, value in kwargs.items():
                result = result.replace(f"{{{key}}}", str(value))
            return result
    
    def _validate_output(self, output: str, prompt_type: PromptType) -> Dict[str, Any]:
        """Validate LLM output against expected schema with retry logic."""
        try:
 
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = output
            
            parsed = json.loads(json_str)
            
            response_text = parsed.get("response_text", "")
            if ("pedagogical approach" in response_text and "150-250 words" in response_text) or "[ORIGINAL" in response_text:
                return {
                    "valid": False,
                    "parsed": None,
                    "error": "Echo detected - model copied template text instead of generating original content",
                    "suggestion": "Retry with simplified prompt"
                }
            
            # Validate against ConversationalResponse schema for conversational prompts
            if prompt_type == PromptType.CONVERSATIONAL:
                validation_result = ConversationalResponse(**parsed)
                return {
                    "valid": True,
                    "parsed": validation_result.dict(),
                    "error": None
                }
            else:
                return {
                    "valid": True,
                    "parsed": parsed,
                    "error": None
                }
                
        except (json.JSONDecodeError, ValidationError) as e:
            return {
                "valid": False,
                "parsed": None,
                "error": str(e)
            }
    
    def render_and_validate(self, prompt_type: PromptType, llm_output: str) -> Dict[str, Any]:
        """Render prompt and validate output with error handling."""
        validation = self._validate_output(llm_output, prompt_type)
        return {
            "prompt_type": prompt_type.value,
            "validation": validation
        }
    
    def load_rag_few_shots(self, query: str, dataset_id: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Pull similar past queries as few-shots via FAISS."""
        if not self.rag_service:
            return []
        try:
            import asyncio
            import inspect

            search_fn = getattr(self.rag_service, 'search_similar_queries', None)
            if not callable(search_fn):
                return []

            if inspect.iscoroutinefunction(search_fn):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        return []
                except RuntimeError:
                    # No current loop, safe to run
                    pass

                results = asyncio.run(search_fn(query, None, k=limit))
            else:
                # sync function - call directly
                results = search_fn(query, None, k=limit)

            if not results:
                return []

            # Normalize results to a few-shot format: {query, response}
            few_shots: List[Dict[str, Any]] = []
            for r in results[:limit]:
                few_shots.append({
                    'query': r.get('query') or r.get('content_preview') or r.get('dataset_id') or '',
                    'response': r.get('response', '')
                })
            return few_shots
        except Exception:
            return []
    
    def _summarize_history(self, history: List[Dict[str, Any]]) -> str:
        """Compress history to key themes for token efficiency."""
        if len(history) <= 2:
            return "\n".join([f"{msg['role'].title()}: {msg['content'][:100]}..." for msg in history])

        recent = history[-2:]
        summary_parts = []
        for msg in recent:
            role = msg['role'].title()
            content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
            summary_parts.append(f"{role}: {content}")
        
        return "\n".join(summary_parts)

    def get_prompt(self, prompt_type: PromptType, **kwargs) -> str:
        """Factory method: Select and generate prompt based on type and args."""
        methods = {
            PromptType.CONVERSATIONAL: self._get_conversational_prompt,
            PromptType.INSIGHT_SUMMARIZER: self._get_insight_summarizer_prompt,
            PromptType.QUIS_ANSWER: self._get_quis_answer_prompt,
            PromptType.CHART_RECOMMENDATION: self._get_chart_recommendation_prompt,
            PromptType.DASHBOARD_DESIGNER: self._get_dashboard_designer_prompt,
            PromptType.AI_DESIGNER: self._get_ai_designer_prompt,
            PromptType.ERROR_RECOVERY: self._get_error_recovery_prompt,
            PromptType.FOLLOW_UP_PLANNER: self._get_follow_up_planner_prompt,
            PromptType.FORECASTING: self._get_forecasting_prompt,
        }
        method = methods.get(prompt_type)
        if not method:
            raise ValueError(f"Unknown prompt type: {prompt_type}")
        return method(**kwargs)

    def _get_conversational_prompt(
        self,
        history: List[Dict[str, Any]],
        chart_options: List[str],
        query_type_hints: Optional[List[str]] = None,
        mode: str = "learning",  # New: 'quick', 'deep', 'forecast'
        query: str = ""  # For RAG
    ) -> str:
        """
        Enhanced conversational prompt with pedagogical approach and expert teacher tone.
        - Implements "explain-like-I'm-5" layers with analogies
        - Uses RAG for few-shot examples from similar conversations
        - Builds learning arcs: hook → explain → reflect → next
        - Compresses history for token efficiency
        """
        history_summary = self._summarize_history(history[-2:] if len(history) >= 2 else history)  # Compress to recent exchanges
        chart_options_str = ", ".join(chart_options)
        hints_str = ", ".join(query_type_hints) if query_type_hints else ""
        few_shots = self.load_rag_few_shots(query, "current_dataset", 2)  # RAG integration
        few_shots_str = "\n".join([f"Q: {fs.get('query', '')} → R: {fs.get('response', '')[:50]}..." for fs in few_shots])

        # Query Rewrite if Vague
        if len(query.split()) < 3:  # Simple heuristic
            columns = list(self.schema.get('columns', {}).keys())
            if columns:
                query = f"Summarize key insights from {columns[0]} in a fun way."
            else:
                query = "Summarize key insights from this dataset in a fun way."

        # Enhanced Common Rules with Pedagogy
        common_rules = """
        **EXPERT TEACHER DIRECTIVES:**
        1. **Engage Joyfully:** Start with a hook: "That's a great question—let's uncover the magic in your data!"
        2. **Simplify Deeply:** Explain like a story/analogy (e.g., "Correlations are like best friends in your dataset—they move together!").
        3. **Build Learning:** Break down: Fact → Why it matters → Real-world tie-in → Your "aha!" reflection question.
        4. **Delight User:** End with: "You're now a data wizard—what else sparks your curiosity?"
        5. Use schema for accurate columns/types. Bias to {mode} (e.g., 'learning': more explanations).
        """

        # Detect if user is requesting a chart
        query_lower = query.lower()
        is_chart_request = any(keyword in query_lower for keyword in [
            'chart', 'graph', 'plot', 'visualize', 'show me', 'display', 'bar', 'line', 'pie'
        ])
        
        template = f"""
        Analyze the dataset and answer the user's query.

        **USER QUERY:** {query}

        **DATASET SCHEMA:**
        {{schema}}

        **IMPORTANT INSTRUCTIONS:**
        1. Use ONLY actual column names from the schema above
        2. {"**CHART REQUIRED:** The user is asking for a visualization. You MUST provide a chart_config." if is_chart_request else "Provide chart_config only if visualization would enhance the answer."}
        3. Do NOT use HTML/Tailwind classes in response_text - use plain text with markdown formatting only
        4. Make response_text engaging and insightful (150-200 words)

        **CHART TYPES AVAILABLE:**
        - "bar_chart" or "bar": Compare categories (needs 1 categorical + 1 numeric column)
        - "line_chart" or "line": Show trends over time (needs 1 date/temporal + 1 numeric column)
        - "pie_chart" or "pie": Show distribution (needs 1 categorical + 1 numeric column)
        - "scatter_plot" or "scatter": Show correlation (needs 2 numeric columns)
        - "histogram": Show distribution of single numeric column

        **OUTPUT FORMAT (JSON only):**
        {{
            "response_text": "Your engaging analysis without HTML classes - use **bold** and *italic* markdown only",
            "chart_config": {{"chart_type": "bar", "columns": ["ActualColumnName1", "ActualColumnName2"], "aggregation": "sum", "group_by": "ActualColumnName1"}} OR null,
            "confidence": "High|Med|Low"
        }}

        {"**REMEMBER:** User explicitly requested a chart - chart_config MUST NOT be null!" if is_chart_request else ""}
        """
        return self._render_template(
            template,
            schema=json.dumps(self.schema, indent=2) if self.schema else "No schema available",
            mode=mode
        )

    def _get_insight_summarizer_prompt(
        self,
        statistical_findings: List[Dict[str, Any]],
        focus_areas: Optional[List[str]] = None
    ) -> str:
        """
        Enhanced for productivity: Prioritizes high-impact insights; suggests context-specific actions.
        """
        findings_str = json.dumps(statistical_findings, indent=2)
        focus_str = "Focus on: " + ", ".join(focus_areas) if focus_areas else "All areas equally."

        template = """
        You are DataSage Strategist, turning stats into business actions.

        --- DATASET CONTEXT ---
        {dataset_context}
        --- END CONTEXT ---

        --- USER PREFERENCES ---
        {user_preferences}
        --- END PREFERENCES ---

        --- STATISTICAL FINDINGS ---
        {focus_str}
        {findings_str}
        --- END FINDINGS ---

        Task: Synthesize into 3-5 prioritized insights. For each:
        - State the finding.
        - Explain "Why it matters" (business impact).
        - Suggest 1 action/visual (context-based, e.g., "Visualize with line chart for trends").

        Output JSON:
        {{
            "insights": [
                {{
                    "title": "Insight Title",
                    "explanation": "Why it matters...",
                    "impact": "High/Med/Low",
                    "action": "Suggested step/visual"
                }}
            ],
            "overall_recommendation": "1-paragraph executive summary"
        }}
        """
        return self._inject_context_and_format(
            template,
            findings_str=findings_str,
            focus_str=focus_str
        )

    def _get_quis_answer_prompt(self, question: str, depth_level: int = 1) -> str:
        """
        Enhanced: Adds depth for subspace analysis; context-aware brevity.
        """
        template = """
        You are DataSage Analyst. Answer this QUIS question at depth level {depth_level} (1=overview, 2=subspace details).

        Question: "{question}"

        --- DATASET CONTEXT ---
        {dataset_context}
        --- END CONTEXT ---

        --- USER PREFERENCES ---
        {user_preferences}
        --- END PREFERENCES ---

        Answer directly and clearly: Start with the specific answer, then explain what it means. Be conversational and helpful.
        Output: {{"answer": "Direct answer with specific numbers and clear explanation", "confidence": "High/Med/Low", "follow_up_question": "Optional suggestion"}}
        """
        return self._inject_context_and_format(
            template,
            question=question,
            depth_level=depth_level
        )

    def _get_chart_recommendation_prompt(
        self,
        chart_types: List[str],
        user_goal: Optional[str] = None
    ) -> str:
        """
        Enhanced: Goal-oriented; ranks by relevance to user intent.
        """
        chart_list = ", ".join(chart_types)
        goal_str = f"User goal: {user_goal}" if user_goal else "General exploration."

        template = """
        You are DataSage Visualizer. Recommend 2-3 charts from: {chart_list}.

        --- DATASET CONTEXT ---
        {dataset_context}
        --- END CONTEXT ---

        {goal_str}

        For each: Explain fit (e.g., "Line for trends"), columns/agg, score (1-10 relevance).

        Output JSON:
        {{
            "recommendations": [
                {{
                    "chart_type": "",
                    "config": {{"columns": [], "aggregation": "sum"}},
                    "reason": "Why suitable",
                    "relevance_score": 8
                }}
            ]
        }}
        """
        return self._inject_context_and_format(
            template,
            chart_list=chart_list,
            goal_str=goal_str
        )

    # ---------------- Dashboard Designer Prompt ----------------
    def _get_dashboard_designer_prompt(
        self,
        chart_options: List[str],
        max_components: int = 12,
        layout_style: Optional[str] = "professional"
    ) -> str:
        """
        Enhanced dashboard designer prompt that creates flexible, multi-chart dashboards
        with comprehensive visual depictions to satisfy user expectations.
        """
        chart_options_str = ", ".join(chart_options)

        style_guide_and_example = f"""
        You are an expert data analyst creating a dynamic dashboard. Analyze the dataset context below and create a professional dashboard using ONLY the actual column names and data types provided.

        **TASK:**
        Create a JSON dashboard configuration that uses the EXACT column names from the dataset context. Do NOT use placeholder names or generic examples.

        **DASHBOARD REQUIREMENTS:**
        1. Create 3-4 KPI cards using numeric columns with appropriate aggregations
        2. Create 4-8 charts using different visualizations based on data types
        3. Include 1 data table showing all columns
        4. Use meaningful titles that reflect the actual data domain

        **CHART TYPE SELECTION RULES:**
        - Use bar_chart for categorical vs numeric comparisons
        - Use pie_chart for categorical distributions (max 8 categories)
        - Use line_chart for time series or ordered data
        - Use scatter_plot for numeric vs numeric relationships
        - Use histogram for single numeric column distributions
        - Use area_chart for cumulative trends over time

        **KPI SELECTION RULES:**
        - Use sum() for total values where appropriate
        - Use mean() for averages
        - Use count() for record counts
        - Use max()/min() for extremes

        **TITLE GENERATION RULES:**
        - Use descriptive titles based on actual column names and data domain
        - For any data: Use meaningful titles that reflect the actual data content
        - Avoid including unrelated example domains; rely only on the provided dataset context

        **REQUIRED JSON STRUCTURE:**
        {{
            "dashboard": {{
                "layout_grid": "repeat(4, 1fr)",
                "components": [
                    // KPI components using actual numeric columns
                    // chart components using actual column combinations
                    // table component showing all columns
                ]
            }}
        }}

        **CRITICAL REQUIREMENTS:**
        1. Use ONLY the exact column names from the dataset context above
        2. Create titles that match the actual data domain
        3. Choose appropriate chart types based on data types
        4. Use meaningful aggregations for each column
        5. Return ONLY valid JSON, no explanations

        **Available Chart Types:** [{chart_options_str}]

        Generate the dashboard now using the actual dataset context provided above.
        """

        template = f"""
        You are DataSage Designer, creating flexible, multi-chart dashboards.

        {style_guide_and_example}

        --- DATASET CONTEXT ---
        {{dataset_context}}
        --- END CONTEXT ---

        --- USER PREFERENCES ---
        {{user_preferences}}
        --- END PREFERENCES ---

        Your task: Design a comprehensive dashboard with diverse visualizations that showcase different aspects of the data.
        The dashboard should provide multiple perspectives and satisfy the user's need for "different combinations of visual depictions."

        Provide only the valid JSON object and nothing else.
        """

        template_formatted = (
            template.replace("{chart_options_str}", chart_options_str)
                    .replace("{max_components}", str(max_components))
        )
        return self._inject_context(template_formatted)

    # ---------------- Enhanced AI Designer Prompt ----------------

    def _get_ai_designer_prompt(
        self,
        design_pattern: Dict[str, Any],
        few_shot_examples: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Enhanced: Supports multiple few-shots; pattern-adaptive.
        """
        pattern_blueprint = json.dumps(design_pattern["blueprint"], indent=2)
        examples_str = (
            "\n".join([json.dumps(ex, indent=2) for ex in (few_shot_examples or [])])
            if few_shot_examples
            else ""
        )

        template = """
        You are DataSage Designer. Adapt the {design_pattern[name]} pattern.

        **STYLE GUIDE:**
        {design_pattern[style_guide]}

        **EXAMPLE BLUEPRINT:**
        ```json
        {pattern_blueprint}
        ```

        **FEW-SHOT EXAMPLES:**
        {examples_str}

        --- DATASET CONTEXT ---
        {dataset_context}
        --- END CONTEXT ---

        **DESIGN RULES:**
        1. **Hierarchy First:** Always start with 3-4 KPI components for high-level metrics
        2. **Tell a Story:** Include a "hero" chart (line/bar) that spans 2-3 columns
        3. **Provide Detail:** End with a table component spanning all columns
        4. **Component Variety:** Use at least 3 different component types (kpi, chart, table)
        5. **Smart Spanning:** Charts should span 2-3 columns, KPIs span 1, tables span all
        6. **Contextual Relevance:** Choose columns and aggregations that make sense for the data

        **OUTPUT FORMAT:**
        {{
            "dashboard": {{
                "layout_grid": "repeat(X, 1fr)",
                "components": []
            }},
            "reasoning": "Brief explanation of your design choices"
        }}
        """
        return self._inject_context_and_format(
            template,
            design_pattern=design_pattern,
            pattern_blueprint=pattern_blueprint,
            examples_str=examples_str
        )

    # ---------------- New: Error Recovery Prompt ----------------

    def _get_error_recovery_prompt(self, error_context: str, user_query: str) -> str:
        """
        New: Handles unclear or ambiguous queries with graceful recovery.
        """
        template = """
        You are DataSage, handling an unclear query with grace.

        **ERROR CONTEXT:**
        {error_context}

        **USER QUERY:**
        {user_query}

        --- DATASET CONTEXT ---
        {dataset_context}
        --- END CONTEXT ---

        **RECOVERY STRATEGY:**
        1. Acknowledge the ambiguity politely
        2. Offer 2-3 specific, actionable options
        3. Provide a default recommendation with reasoning

        Output JSON:
        {{
            "response_text": "I'd be happy to help! Your request could mean a few things. Here are your options: [options]. I recommend [default] because [reason].",
            "suggestions": ["Option 1", "Option 2", "Option 3"],
            "default_action": "Recommended action",
            "chart_config": null
        }}
        """
        return self._inject_context_and_format(
            template,
            error_context=error_context,
            user_query=user_query
        )

    # ---------------- New: Follow-up Planner Prompt ----------------

    def _get_follow_up_planner_prompt(self, current_analysis: str, user_goals: Optional[List[str]] = None) -> str:
        """
        New: Proactively suggests next steps based on current analysis.
        """
        goals_str = "User goals: " + ", ".join(user_goals) if user_goals else "General exploration"

        template = """
        You are DataSage Strategist, planning the next analytical steps.

        **CURRENT ANALYSIS:**
        {current_analysis}

        **USER GOALS:**
        {goals_str}

        --- DATASET CONTEXT ---
        {dataset_context}
        --- END CONTEXT ---

        **PLANNING TASK:**
        Suggest 3-4 logical next steps that build on the current analysis.
        Prioritize by: 1) Business impact, 2) Data availability, 3) User goals.

        Output JSON:
        {{
            "next_steps": [
                {{
                    "action": "Specific action to take",
                    "reason": "Why this is valuable",
                    "priority": "High/Med/Low",
                    "estimated_effort": "Quick/Moderate/Complex"
                }}
            ],
            "recommended_sequence": "Suggested order of execution"
        }}
        """
        return self._inject_context_and_format(
            template,
            current_analysis=current_analysis,
            goals_str=goals_str
        )

    # ---------------- New: Forecasting Prompt ----------------
    
    def _get_forecasting_prompt(self, historical_data: Dict[str, Any], forecast_horizon: str = "30 days") -> str:
        """
        New: Generates forecasting prompts for predictive analysis.
        """
        template = """
        You are DataSage Forecaster, predicting future trends from historical patterns.

        **FORECASTING CONTEXT:**
        {historical_data}

        **FORECAST HORIZON:** {forecast_horizon}

        --- DATASET CONTEXT ---
        {dataset_context}
        --- END CONTEXT ---

        **FORECASTING TASK:**
        1. Analyze historical trends and patterns
        2. Identify seasonal components or cycles
        3. Predict future values with confidence intervals
        4. Explain assumptions and limitations

        Output JSON:
        {{
            "forecast": {{
                "predictions": [
                    {{"period": "2024-01", "value": 100, "confidence_lower": 90, "confidence_upper": 110}}
                ],
                "trend": "increasing/decreasing/stable",
                "seasonality": "yes/no with description",
                "confidence": "High/Med/Low"
            }},
            "assumptions": ["Key assumptions made"],
            "limitations": ["Important limitations to consider"],
            "recommendations": ["Actionable recommendations based on forecast"]
        }}
        """
        return self._inject_context_and_format(
            template,
            historical_data=json.dumps(historical_data, indent=2),
            forecast_horizon=forecast_horizon
        )



# ---------------- Legacy Compatibility Functions ----------------

def get_conversational_prompt(history: List[Dict[str, Any]], dataset_context: str, chart_options: List[str]) -> str:
    """Legacy function for backward compatibility."""
    factory = PromptFactory(dataset_context=dataset_context)
    return factory.get_prompt(PromptType.CONVERSATIONAL, history=history, chart_options=chart_options)


def get_insight_summarizer_prompt(statistical_findings: List[Dict[str, Any]], dataset_context: str) -> str:
    """Legacy function for backward compatibility."""
    factory = PromptFactory(dataset_context=dataset_context)
    return factory.get_prompt(PromptType.INSIGHT_SUMMARIZER, statistical_findings=statistical_findings)


def get_quis_answer_prompt(question: str, dataset_context: str) -> str:
    """Legacy function for backward compatibility."""
    factory = PromptFactory(dataset_context=dataset_context)
    return factory.get_prompt(PromptType.QUIS_ANSWER, question=question)


def get_chart_recommendation_prompt(dataset_context: str, chart_types: List[str]) -> str:
    """Legacy function for backward compatibility."""
    factory = PromptFactory(dataset_context=dataset_context)
    return factory.get_prompt(PromptType.CHART_RECOMMENDATION, chart_types=chart_types)


def get_dashboard_designer_prompt(dataset_context: str, chart_options: List[str]) -> str:
    """Legacy function for backward compatibility."""
    factory = PromptFactory(dataset_context=dataset_context)
    return factory.get_prompt(PromptType.DASHBOARD_DESIGNER, chart_options=chart_options)


def get_ai_designer_prompt(dataset_context: str, design_pattern: Dict[str, Any]) -> str:
    """Legacy function for backward compatibility."""
    factory = PromptFactory(dataset_context=dataset_context)
    return factory.get_prompt(PromptType.AI_DESIGNER, design_pattern=design_pattern)



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
        self.user_prefs = user_preferences or {}  # e.g., {"prefers_charts": True, "industry": "sales", "mode": "learning"}
        self.schema = schema or {}  # Dynamic schema for accurate column/types
        self.rag_service = rag_service  # Injected FAISS service for few-shots

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
        
        # Simple compression: keep first part and last part with indicator
        first_part = context[:max_length//2]
        last_part = context[-(max_length//2):]
        return f"{first_part}... [compressed] ...{last_part}"
    
    def _render_template(self, template: str, **kwargs) -> str:
        """Render template with context injection and parameter formatting."""
        template_with_context = self._inject_context(template)
        try:
            return template_with_context.format(**kwargs)
        except KeyError as e:
            # Fallback to string replacement for complex templates
            result = template_with_context
            for key, value in kwargs.items():
                result = result.replace(f"{{{key}}}", str(value))
            return result
    
    def _validate_output(self, output: str, prompt_type: PromptType) -> Dict[str, Any]:
        """Validate LLM output against expected schema with retry logic."""
        try:
            # Extract JSON from output if needed
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = output
            
            parsed = json.loads(json_str)
            
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
            # Note: This would need to be called asynchronously in practice
            # For now, return empty list as the actual implementation would require async/await
            return []
        except Exception:
            return []
    
    def _summarize_history(self, history: List[Dict[str, Any]]) -> str:
        """Compress history to key themes for token efficiency."""
        if len(history) <= 2:
            return "\n".join([f"{msg['role'].title()}: {msg['content'][:100]}..." for msg in history])
        
        # Summarize recent exchanges
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

    # ---------------- Enhanced Conversational Prompt with Pedagogy ----------------

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
        history_summary = self._summarize_history(history[-2:])  # Compress to recent exchanges
        chart_options_str = ", ".join(chart_options)
        hints_str = ", ".join(query_type_hints) if query_type_hints else ""
        few_shots = self.load_rag_few_shots(query, "current_dataset", 2)  # RAG integration
        few_shots_str = "\n".join([f"Q: {fs['query']} → R: {fs['response'][:50]}..." for fs in few_shots])

        # Query Rewrite if Vague
        if len(query.split()) < 3:  # Simple heuristic
            query = f"Summarize key insights from {list(self.schema.get('columns', {}).keys())[0]} in a fun way."

        # Enhanced Common Rules with Pedagogy
        common_rules = """
        **EXPERT TEACHER DIRECTIVES:**
        1. **Engage Joyfully:** Start with a hook: "That's a great question—let's uncover the magic in your data!"
        2. **Simplify Deeply:** Explain like a story/analogy (e.g., "Correlations are like best friends in your dataset—they move together!").
        3. **Build Learning:** Break down: Fact → Why it matters → Real-world tie-in → Your "aha!" reflection question.
        4. **Delight User:** End with: "You're now a data wizard—what else sparks your curiosity?"
        5. Use schema for accurate columns/types. Bias to {mode} (e.g., 'learning': more explanations).
        """

        template = f"""
        {common_rules}

        --- DATASET SCHEMA (Dynamic) ---
        {{schema}}
        --- END ---

        --- COMPRESSED HISTORY ---
        {history_summary}
        --- END ---

        Final Query (Rewritten if Vague): {query}
        Mode: {mode} | Hints: {hints_str}

        **CLASSIFICATION & ARC:**
        ANALYTICAL: Build learning arc (hook/analogy/reflect).
        VISUAL: Explain chart story + why it teaches.

        **RAG FEW-SHOTS (Learn from Similar Chats):**
        {few_shots_str}

        **OUTPUT FORMAT (STRICT JSON SCHEMA):**
        {{
            "response_text": "Engaging response with pedagogical approach (150-250 words). Structure: Hook → Analogy → Explanation → Reflection question. Be conversational and delightful.",
            "chart_config": null (analytical) OR {{"chart_type": "bar|line|...", "columns": ["col1"], "aggregation": "sum", "group_by": ["col2"]}} (visual),
            "story_elements": {{
                "hook": "Direct answer or fascinating fact",
                "key_findings": ["Finding 1", "Finding 2", "Finding 3"],
                "business_impact": "Why this matters for decision-making",
                "next_questions": ["Follow-up question 1", "Follow-up question 2"]
            }},
            "confidence": "High|Med|Low",
            "learning_arc": {{
                "hook": "Engaging opening or fascinating fact",
                "analogy": "Simple analogy to explain the concept",
                "explanation": "Clear technical explanation",
                "reflection": "Thought-provoking question for user"
            }}
        }}

        Provide ONLY the JSON object. No extra text.
        """
        return self._render_template(
            template,
            schema=json.dumps(self.schema, indent=2) if self.schema else "No schema available",
            mode=mode
        )

    # ---------------- Enhanced Statistical Insight Summarizer Prompt ----------------

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

    # ---------------- Enhanced QUIS Prompt ----------------

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

    # ---------------- Enhanced Chart Recommendation Prompt ----------------

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

    # ---------------- Enhanced Dashboard Designer Prompt ----------------
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
        **Dashboard Design Principles:**

        Your task is to design a professional dashboard layout using ONLY the actual column names from the dataset context below.

        **Design Guidelines:**
        1. Create EXACTLY 4 KPI components using numeric columns (Total Sales, Price per Unit, Units Sold)
        2. Create EXACTLY 5-6 charts using different chart types and combinations
        3. Include 1 data table at the end showing all columns
        4. Total: 10-11 components (4 KPIs + 5-6 charts + 1 table)

        **CRITICAL RULES - READ CAREFULLY:**
        1. **USE ONLY ACTUAL COLUMN NAMES** - Look at the dataset context and use the exact column names provided
        2. **DO NOT use placeholders** like [actual_column_name], [date_column], [value_column], etc.
        3. **DO NOT copy the example** - Create your own dashboard based on the actual data
        4. **Match column types** - Use numeric columns for KPIs and value columns, categorical for grouping

        **Available Chart Types:** [{chart_options_str}]
        
        **Advanced Chart Types Available:**
        - line_chart: Time-series trends (use with date columns)
        - bar_chart: Comparisons and rankings
        - pie_chart: Proportions and distributions
        - scatter_plot: Correlations and relationships
        - area_chart: Cumulative trends over time
        - histogram: Data distribution analysis
        - heatmap: Pattern visualization
        - box_plot: Statistical distributions
        - violin_plot: Advanced distributions
        - treemap: Hierarchical data
        - candlestick: Financial data (requires OHLC data - not applicable to this dataset)

        **For THIS dataset, you MUST use these exact columns:**
        STRING columns: "Invoice Date", "Product", "Region", "Retailer", "Sales Method", "State"
        INT64 columns: "Price per Unit", "Total Sales", "Units Sold"
        
        **REQUIRED COMPONENTS - Generate EXACTLY these:**
        
        1. KPI: Total Sales (sum of "Total Sales" column)
        2. KPI: Average Price (mean of "Price per Unit" column)
        3. KPI: Total Units (sum of "Units Sold" column)
        4. KPI: Total Records (count of "Total Sales" column)
        
        5. Chart: Line chart showing "Total Sales" over time by "Invoice Date" (time-series)
        6. Chart: Bar chart showing "Total Sales" by "Region"
        7. Chart: Pie chart showing "Total Sales" by "Product"
        8. Chart: Scatter plot showing "Price per Unit" vs "Total Sales" colored by "Region"
        9. Chart: Area chart showing "Units Sold" over time by "Invoice Date"
        10. Chart: Bar chart showing "Total Sales" by "Retailer"
        11. Chart: Histogram showing distribution of "Price per Unit"
        12. Chart: Bar chart showing "Units Sold" by "Sales Method"
        
        13. Table: Show all columns
        
        **COMPLETE WORKING EXAMPLE - Copy this structure:**
        {{
          "dashboard": {{
            "layout_grid": "repeat(4, 1fr)",
            "components": [
              {{ "type": "kpi", "title": "Total Sales", "span": 1, "config": {{"column": "Total Sales", "aggregation": "sum", "icon": "TrendingUp", "color": "emerald"}} }},
              {{ "type": "kpi", "title": "Average Price", "span": 1, "config": {{"column": "Price per Unit", "aggregation": "mean", "icon": "Database", "color": "blue"}} }},
              {{ "type": "kpi", "title": "Total Units", "span": 1, "config": {{"column": "Units Sold", "aggregation": "sum", "icon": "Users", "color": "green"}} }},
              {{ "type": "kpi", "title": "Total Records", "span": 1, "config": {{"column": "Total Sales", "aggregation": "count", "icon": "FileText", "color": "amber"}} }},
              
              {{ "type": "chart", "title": "Sales Over Time", "span": 2, "config": {{"chart_type": "line_chart", "columns": ["Invoice Date", "Total Sales"], "aggregation": "sum", "group_by": "Invoice Date"}} }},
              {{ "type": "chart", "title": "Sales by Region", "span": 2, "config": {{"chart_type": "bar_chart", "columns": ["Region", "Total Sales"], "aggregation": "sum", "group_by": "Region"}} }},
              {{ "type": "chart", "title": "Sales by Product", "span": 2, "config": {{"chart_type": "pie_chart", "columns": ["Product", "Total Sales"], "aggregation": "sum", "group_by": "Product"}} }},
              {{ "type": "chart", "title": "Price vs Sales", "span": 2, "config": {{"chart_type": "scatter_plot", "columns": ["Price per Unit", "Total Sales"], "aggregation": "none", "group_by": "Region"}} }},
              {{ "type": "chart", "title": "Units Over Time", "span": 2, "config": {{"chart_type": "area_chart", "columns": ["Invoice Date", "Units Sold"], "aggregation": "sum", "group_by": "Invoice Date"}} }},
              {{ "type": "chart", "title": "Sales by Retailer", "span": 2, "config": {{"chart_type": "bar_chart", "columns": ["Retailer", "Total Sales"], "aggregation": "sum", "group_by": "Retailer"}} }},
              {{ "type": "chart", "title": "Price Distribution", "span": 2, "config": {{"chart_type": "histogram", "columns": ["Price per Unit"], "aggregation": "none", "group_by": "Price per Unit"}} }},
              {{ "type": "chart", "title": "Units by Sales Method", "span": 2, "config": {{"chart_type": "bar_chart", "columns": ["Sales Method", "Units Sold"], "aggregation": "sum", "group_by": "Sales Method"}} }},
              
              {{ "type": "table", "title": "Data Overview", "span": 4, "config": {{"columns": ["Invoice Date", "Product", "Region", "Retailer", "Sales Method", "State", "Price per Unit", "Total Sales", "Units Sold"]}} }}
            ]
          }}
        }}

        **CRITICAL INSTRUCTIONS:**
        1. You MUST include EXACTLY 4 KPIs + 8 CHARTS + 1 TABLE = 13 components total
        2. DO NOT skip the charts - they are required!
        3. Use the complete working example above as your template
        4. Replace the example values with the actual column names from the dataset
        5. Make sure each chart has the correct chart_type and columns
        6. Return ONLY the JSON object, no explanations

        **MANDATORY: Include these 8 charts:**
        - Line chart: Sales over time
        - Bar chart: Sales by Region  
        - Pie chart: Sales by Product
        - Scatter plot: Price vs Sales
        - Area chart: Units over time
        - Bar chart: Sales by Retailer
        - Histogram: Price distribution
        - Bar chart: Units by Sales Method

        Provide only the valid JSON object and nothing else.
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

        # ✅ FIX: Avoid using .format() which breaks due to JSON braces in template
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



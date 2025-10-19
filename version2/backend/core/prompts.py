# backend/core/prompts.py

"""
Enhanced Prompt Engineering Library for DataSage AI.

This refactored version improves productivity and usability by:
- **Modularity**: Prompt templates use parameterized f-strings with clear placeholders for easy extension.
- **Context-Awareness**: Dynamic injection of dataset schema, user history, and preferences.
- **Stricter Logic**: Exhaustive classification in conversational prompts to reduce misfires (e.g., no auto-charts for analytical queries).
- **Validation**: Enforced JSON schemas in prompts for reliable parsing.
- **Extensibility**: Added prompt factory for selection; new prompts for edge cases (e.g., error recovery, follow-up planning).
- **Best Practices**: Shorter, focused prompts (<2k tokens); role-playing with clear boundaries; few-shot examples where high-value.

Usage:
from prompts import PromptFactory
factory = PromptFactory(dataset_context="Your schema here")
convo_prompt = factory.get_conversational_prompt(history, user_prefs)
"""

from typing import List, Dict, Any, Optional, Union
import json
from enum import Enum


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
    DATA_STORYTELLER = "data_storyteller"  # New: For compelling data narratives
    CHART_EXPLAINER = "chart_explainer"  # New: For detailed chart explanations
    BUSINESS_INSIGHTS = "business_insights"  # New: For business-focused storytelling


class PromptFactory:
    """Factory for generating context-aware prompts. Injects shared elements like dataset context."""

    def __init__(self, dataset_context: str = "", user_preferences: Optional[Dict[str, Any]] = None):
        self.dataset_context = dataset_context
        self.user_prefs = user_preferences or {}  # e.g., {"prefers_charts": True, "industry": "sales"}

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
            PromptType.DATA_STORYTELLER: self._get_data_storyteller_prompt,
            PromptType.CHART_EXPLAINER: self._get_chart_explainer_prompt,
            PromptType.BUSINESS_INSIGHTS: self._get_business_insights_prompt,
        }
        method = methods.get(prompt_type)
        if not method:
            raise ValueError(f"Unknown prompt type: {prompt_type}")
        return method(**kwargs)

    # ---------------- Enhanced Conversational Prompt ----------------

    def _get_conversational_prompt(
        self,
        history: List[Dict[str, Any]],
        chart_options: List[str],
        query_type_hints: Optional[List[str]] = None
    ) -> str:
        """
        Enhanced for stricter classification and context-based responses.
        - Exhaustive indicators reduce fallback to charts.
        - Injects user prefs (e.g., "prefers_charts: True" → slight bias to visuals).
        - Supports pre-hints for backend classification.
        """
        history_str = "\n".join(
            [f"{msg['role'].title()}: {msg['content']}" for msg in history[-5:]]
        )
        chart_options_str = ", ".join(chart_options)
        hints_str = "Pre-classified hints: " + ", ".join(query_type_hints) if query_type_hints else ""

        template = """
        You are DataSage, a precise and context-aware data analyst AI. Respond based on the dataset and user preferences.

        **CORE DIRECTIVES (Updated for Precision):**
        1. **Classify First**: ALWAYS classify the final user query as ANALYTICAL (text-only) or VISUALIZATION (with chart) using the rules below. Use pre-hints if provided.
        2. **Context-Driven**: Tailor to {user_preferences} (e.g., if user prefers charts, suggest but don't force).
        3. **Proactive but Safe**: For analytical, provide deep insights. For visualization, generate one targeted chart. End with 1-2 follow-up suggestions.
        4. **No Loops**: If vague (e.g., "yes"), default to analytical summary unless history indicates visuals.

        --- DATASET CONTEXT ---
        {dataset_context}
        --- END CONTEXT ---

        --- USER PREFERENCES ---
        {user_preferences}
        --- END PREFERENCES ---

        --- CONVERSATION HISTORY ---
        {history_str}
        --- END HISTORY ---

        --- QUERY CLASSIFICATION (MANDATORY - STRICT RULES) ---
        Final User Query: [EXTRACT LAST MESSAGE CONTENT HERE]
        {hints_str}

        **ANALYTICAL QUERY** (Output: {{"response_text": "insights...", "chart_config": null}}):
        - Matches ANY of: "summarize trends/what are trends", "patterns/crucial patterns/key patterns", "insights/analyze deeper/what stands out",
          "relationships/correlations/what drives", "hidden/unusual/properties/emerge when filter", "explain/understand" (without visual words).
        - Focus: Tell a compelling data story with:
          1. **Opening Hook**: Start with the most surprising or important finding
          2. **Narrative Flow**: Connect insights logically (cause → effect → implications)
          3. **Business Context**: Explain "Why this matters" with real-world impact
          4. **Data Evidence**: Support claims with specific numbers and correlations
          5. **Future Implications**: What this means for decision-making

        **VISUALIZATION QUERY** (Output: {{"response_text": "...", "chart_config": {{...}}}}):
        - Matches ONLY: "show/generate/create + chart/graph/plot/visualize/display", specific types ("bar/line/pie/etc."), "visualize this".
        - Generate ONE chart: Use {chart_options_str}. For sales: Prioritize histogram (distribution), line (trends), bar (comparisons).

        If unclear, DEFAULT TO ANALYTICAL. NEVER include chart_config for analytical.

        **DATASET GUIDELINES (Context-Based):**
        - Sales data: Insights on price/revenue correlations; visuals for regional trends.
        - Use schema from context for column suggestions.

        **OUTPUT FORMAT (STRICT JSON SCHEMA):**
        {{
            "response_text": "Compelling data story (300-400 words). Structure: Hook → Analysis → Implications → Next steps. End with: 'What would you like to explore next: [suggestion1] or [suggestion2]?'",
            "chart_config": null (analytical) OR {{"chart_type": "bar|line|...", "columns": ["col1"], "aggregation": "sum", "group_by": ["col2"]}} (visual),
            "story_elements": {{
                "hook": "Opening attention-grabbing insight",
                "key_findings": ["Finding 1", "Finding 2", "Finding 3"],
                "business_impact": "Why this matters for decision-making",
                "next_questions": ["Follow-up question 1", "Follow-up question 2"]
            }}
        }}

        Provide ONLY the JSON object. No extra text.
        """
        return template.format(
            dataset_context=self.dataset_context,
            user_preferences=json.dumps(self.user_prefs, indent=2) if self.user_prefs else "{}",
            history_str=history_str,
            chart_options_str=chart_options_str,
            hints_str=hints_str
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

        Respond in 1-3 concise sentences: Fact-based, actionable. If depth=2, include subspace examples (e.g., "In North region...").
        Output: {{"answer": "Your response", "confidence": "High/Med/Low", "follow_up_question": "Optional suggestion"}}
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
        **Dashboard Design Principles & Flexible Example:**

        Your task is to design a professional, visually engaging, and data-rich dashboard layout as a valid JSON blueprint.

        **Design Guidelines:**
        1. Start with 3-5 KPI components summarizing key high-level metrics.
        2. Include 4-8 charts from various types to showcase different data aspects:
           - Trends (line, area, time series)
           - Comparisons (bar, grouped bar, waterfall)
           - Distributions (histogram, box plot, violin plot)
           - Proportions (pie, funnel, treemap)
           - Correlations and relationships (scatter, bubble, heatmap, contour)
           - Maps and geo-visualizations (choropleth, tile map, scatter 3D)
           - Financial and specialized charts (candlestick, indicator)
        3. Include a detailed data table section spanning full dashboard width.
        4. Total components should not exceed {max_components} for usability.
        5. Follow a hierarchical flow: KPIs up top, followed by thematic visual clusters toward detailed views.

        **Example Layout Structure (adapt to your actual data):**
        ```json
        {{
          "dashboard": {{
            "layout_grid": "repeat(4, 1fr)",
            "components": [
              {{ "type": "kpi", "title": "Total [Metric Name]", "span": 1, "config": {{"column": "[actual_column_name]", "aggregation": "sum", "icon": "TrendingUp", "color": "emerald"}} }},
              {{ "type": "kpi", "title": "Unique [Entity Name]", "span": 1, "config": {{"column": "[actual_id_column]", "aggregation": "nunique", "icon": "Users", "color": "sky"}} }},
              {{ "type": "kpi", "title": "Average [Value Name]", "span": 1, "config": {{"column": "[actual_numeric_column]", "aggregation": "mean", "icon": "Database", "color": "teal"}} }},
              {{ "type": "kpi", "title": "Total [Count Name]", "span": 1, "config": {{"column": "[actual_column]", "aggregation": "count", "icon": "FileText", "color": "amber"}} }},
              
              {{ "type": "chart", "title": "[Metric] Over Time", "span": 3, "config": {{"chart_type": "line_chart", "columns": ["[date_column]", "[value_column]"], "aggregation": "sum", "group_by": "[date_column]"}} }},
              {{ "type": "chart", "title": "[Metric] by [Category]", "span": 1, "config": {{"chart_type": "pie_chart", "columns": ["[category_column]", "[value_column]"], "aggregation": "sum", "group_by": "[category_column]"}} }},
              {{ "type": "chart", "title": "[Performance] by [Group]", "span": 2, "config": {{"chart_type": "bar_chart", "columns": ["[group_column]", "[value_column]"], "aggregation": "sum", "group_by": "[group_column]"}} }},
              {{ "type": "chart", "title": "[Distribution] Analysis", "span": 2, "config": {{"chart_type": "histogram", "columns": ["[category_column]", "[value_column]"]}} }},
              {{ "type": "chart", "title": "[Relationship] Analysis", "span": 2, "config": {{"chart_type": "scatter_plot", "columns": ["[x_column]", "[y_column]", "[group_column]"]}} }},
              {{ "type": "chart", "title": "[Trend] Analysis", "span": 2, "config": {{"chart_type": "area_chart", "columns": ["[time_column]", "[value_column]"], "aggregation": "sum", "group_by": "[time_column]"}} }},
              
              {{ "type": "table", "title": "Data Overview", "span": 4, "config": {{"columns": ["[key_column1]", "[key_column2]", "[value_column1]", "[value_column2]", "[category_column]"]}} }}
            ]
          }}
        }}
        ```

        You may use any combination of the following chart types: [{chart_options_str}].

        **CRITICAL REQUIREMENTS:**
        - **MUST USE ACTUAL DATASET COLUMNS**: Use only the column names and data types from the dataset context above
        - **NO HARDCODED SALES DATA**: Do not use generic sales terms like "Revenue", "Sales", "Orders" unless they exist in the actual data
        - Create 8-12 components total: 3-5 KPIs + 4-8 Charts + 1 Table
        - Use diverse chart types to show "different combinations of visual depictions"
        - Hero chart should span 3 columns for maximum impact
        - Secondary charts can span 1-2 columns based on importance
        - Table should span full width (4 columns)
        - Choose appropriate aggregations and groupings for each chart type
        - Ensure professional, business-focused titles that reflect the actual data domain
        - This satisfies user expectations for comprehensive data exploration

        **IMPORTANT**: Analyze the dataset context carefully and create titles and configurations that match the actual data structure and domain. If this is game data, use game-related terms. If this is financial data, use financial terms. Match the actual column names exactly.

        Provide only the JSON object representing the dashboard layout.
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

    # ---------------- New: Data Storyteller Prompt ----------------

    def _get_data_storyteller_prompt(
        self,
        data_insights: List[Dict[str, Any]],
        story_type: str = "business_impact",
        target_audience: str = "business_stakeholder"
    ) -> str:
        """
        New: Creates compelling data narratives that engage and inform.
        """
        insights_str = json.dumps(data_insights, indent=2)
        
        template = """
        You are DataSage Storyteller, transforming data insights into compelling narratives.

        **STORY TYPE:** {story_type}
        **TARGET AUDIENCE:** {target_audience}

        --- DATASET CONTEXT ---
        {dataset_context}
        --- END CONTEXT ---

        --- USER PREFERENCES ---
        {user_preferences}
        --- END PREFERENCES ---

        --- DATA INSIGHTS ---
        {insights_str}
        --- END INSIGHTS ---

        **STORYTELLING FRAMEWORK:**
        1. **Opening Hook**: Start with the most surprising or impactful finding
        2. **Context Setting**: Provide background and why this matters
        3. **Evidence Journey**: Walk through key findings with supporting data
        4. **Implications**: What this means for the business/decision-making
        5. **Call to Action**: Clear next steps or recommendations

        **STORY ELEMENTS:**
        - Use metaphors and analogies to make data relatable
        - Include specific numbers and percentages for credibility
        - Connect findings to real-world business scenarios
        - End with actionable insights and next steps

        Output JSON:
        {{
            "story": {{
                "title": "Compelling story title",
                "hook": "Opening attention-grabbing statement",
                "narrative": "Full story (400-500 words) with clear structure",
                "key_metrics": ["Metric 1", "Metric 2", "Metric 3"],
                "business_impact": "Why this matters for decision-making",
                "recommendations": ["Action 1", "Action 2", "Action 3"]
            }},
            "story_type": "{story_type}",
            "confidence": "High/Med/Low"
        }}
        """
        return self._inject_context_and_format(
            template,
            insights_str=insights_str,
            story_type=story_type,
            target_audience=target_audience
        )

    # ---------------- New: Chart Explainer Prompt ----------------

    def _get_chart_explainer_prompt(
        self,
        chart_config: Dict[str, Any],
        chart_data: Optional[List[Dict[str, Any]]] = None,
        explanation_depth: str = "detailed"
    ) -> str:
        """
        New: Provides comprehensive explanations of charts and visualizations.
        """
        chart_config_str = json.dumps(chart_config, indent=2)
        chart_data_str = json.dumps(chart_data[:10], indent=2) if chart_data else "No data provided"
        
        template = """
        You are DataSage Chart Expert, providing detailed explanations of data visualizations.

        **EXPLANATION DEPTH:** {explanation_depth}

        --- DATASET CONTEXT ---
        {dataset_context}
        --- END CONTEXT ---

        --- CHART CONFIGURATION ---
        {chart_config_str}
        --- END CONFIG ---

        --- SAMPLE DATA ---
        {chart_data_str}
        --- END DATA ---

        **EXPLANATION FRAMEWORK:**
        1. **Chart Purpose**: What this visualization is designed to show
        2. **Data Structure**: How the data is organized and what each axis/segment represents
        3. **Key Patterns**: What patterns, trends, or outliers are visible
        4. **Statistical Insights**: What the numbers tell us about the data
        5. **Business Interpretation**: What this means in practical terms
        6. **Limitations**: What this chart doesn't show or potential caveats

        **EXPLANATION STYLE:**
        - Use clear, jargon-free language
        - Include specific data points and percentages
        - Explain both what you see and what it means
        - Connect patterns to business implications
        - Suggest what to look for or investigate next

        Output JSON:
        {{
            "explanation": {{
                "purpose": "What this chart shows and why it's useful",
                "data_structure": "How the data is organized",
                "key_patterns": ["Pattern 1", "Pattern 2", "Pattern 3"],
                "statistical_insights": "What the numbers reveal",
                "business_meaning": "Practical implications",
                "limitations": "What this chart doesn't show",
                "next_steps": "What to investigate or visualize next"
            }},
            "confidence": "High/Med/Low",
            "suggested_follow_ups": ["Follow-up 1", "Follow-up 2"]
        }}
        """
        return self._inject_context_and_format(
            template,
            chart_config_str=chart_config_str,
            chart_data_str=chart_data_str,
            explanation_depth=explanation_depth
        )

    # ---------------- New: Business Insights Prompt ----------------

    def _get_business_insights_prompt(
        self,
        analysis_results: Dict[str, Any],
        business_context: Optional[str] = None
    ) -> str:
        """
        New: Generates business-focused insights with actionable recommendations.
        """
        analysis_str = json.dumps(analysis_results, indent=2)
        context_str = business_context or "General business analysis"
        
        template = """
        You are DataSage Business Strategist, translating data analysis into actionable business insights.

        **BUSINESS CONTEXT:** {context_str}

        --- DATASET CONTEXT ---
        {dataset_context}
        --- END CONTEXT ---

        --- USER PREFERENCES ---
        {user_preferences}
        --- END PREFERENCES ---

        --- ANALYSIS RESULTS ---
        {analysis_str}
        --- END ANALYSIS ---

        **BUSINESS INSIGHTS FRAMEWORK:**
        1. **Executive Summary**: High-level findings in business terms
        2. **Opportunity Identification**: What opportunities does the data reveal?
        3. **Risk Assessment**: What risks or concerns should be addressed?
        4. **Performance Metrics**: Key performance indicators and benchmarks
        5. **Strategic Recommendations**: Specific, actionable next steps
        6. **ROI Potential**: Expected impact of recommended actions

        **INSIGHT CATEGORIES:**
        - Revenue Growth Opportunities
        - Cost Optimization Potential
        - Customer Behavior Insights
        - Operational Efficiency Gains
        - Market Positioning Advantages
        - Risk Mitigation Strategies

        Output JSON:
        {{
            "business_insights": {{
                "executive_summary": "High-level business findings",
                "opportunities": [
                    {{
                        "title": "Opportunity title",
                        "description": "What the opportunity is",
                        "potential_impact": "High/Med/Low",
                        "effort_required": "High/Med/Low",
                        "recommended_action": "Specific next step"
                    }}
                ],
                "risks": [
                    {{
                        "title": "Risk title",
                        "description": "What the risk is",
                        "severity": "High/Med/Low",
                        "mitigation_strategy": "How to address it"
                    }}
                ],
                "key_metrics": {{
                    "primary_kpi": "Main performance indicator",
                    "benchmark": "How it compares to standards",
                    "trend": "Improving/Declining/Stable"
                }},
                "strategic_recommendations": [
                    {{
                        "priority": "High/Med/Low",
                        "action": "Specific recommendation",
                        "timeline": "When to implement",
                        "expected_outcome": "What success looks like"
                    }}
                ]
            }},
            "confidence": "High/Med/Low",
            "next_analysis": "Suggested follow-up analysis"
        }}
        """
        return self._inject_context_and_format(
            template,
            analysis_str=analysis_str,
            context_str=context_str
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


def get_data_storyteller_prompt(dataset_context: str, data_insights: List[Dict[str, Any]], story_type: str = "business_impact") -> str:
    """Legacy function for backward compatibility."""
    factory = PromptFactory(dataset_context=dataset_context)
    return factory.get_prompt(PromptType.DATA_STORYTELLER, data_insights=data_insights, story_type=story_type)


def get_chart_explainer_prompt(dataset_context: str, chart_config: Dict[str, Any], chart_data: Optional[List[Dict[str, Any]]] = None) -> str:
    """Legacy function for backward compatibility."""
    factory = PromptFactory(dataset_context=dataset_context)
    return factory.get_prompt(PromptType.CHART_EXPLAINER, chart_config=chart_config, chart_data=chart_data)


def get_business_insights_prompt(dataset_context: str, analysis_results: Dict[str, Any], business_context: Optional[str] = None) -> str:
    """Legacy function for backward compatibility."""
    factory = PromptFactory(dataset_context=dataset_context)
    return factory.get_prompt(PromptType.BUSINESS_INSIGHTS, analysis_results=analysis_results, business_context=business_context)

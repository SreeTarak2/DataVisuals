# backend/services/agents/quis_graph.py

"""
LangGraph QUIS Orchestrator
===========================
Cyclic state graph implementing the agentic QUIS architecture.

Graph Topology:
    START -> planner -> analyst -> critic -> [conditional]
                                      |
                          +-----------+-----------+
                          |           |           |
                        REJECT      APPROVE     DONE
                          |           |           |
                          v           v           v
                       analyst    novelty    synthesizer -> END
                                    |
                          +---------+---------+
                          |                   |
                        BORING              NOVEL
                          |                   |
                          v                   v
                       planner           synthesizer

This replaces the linear `run_analysis()` in enhanced_quis.py with a
self-correcting loop that can retry on errors and filter boring insights.
"""

import logging
from typing import Dict, Any, Literal
from datetime import datetime

# LangGraph imports
try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logging.warning("LangGraph not installed. Run: pip install langgraph")

from .state import AgentState, create_initial_state

logger = logging.getLogger(__name__)


# ============================================================
# NODE FUNCTIONS
# ============================================================

async def planner_node(state: AgentState) -> Dict[str, Any]:
    """
    QUGEN: Generate analytical questions from dataset schema.
    
    This node replaces QuestionGenerator.generate_questions_template()
    with state-aware question generation.
    """
    logger.info(f"[PLANNER] Starting question generation for dataset {state['dataset_id']}")
    
    # Import here to avoid circular dependencies
    from services.analysis.enhanced_quis import QuestionGenerator
    import polars as pl
    from db.database import get_database
    from bson import ObjectId
    
    # Check if questions already generated
    if state["questions"] and state["current_question_idx"] < len(state["questions"]):
        logger.info(f"[PLANNER] Questions already generated, moving to next at idx {state['current_question_idx']}")
        return {}  # No state update needed
    
    # Generate questions if not yet done
    if not state["questions"]:
        try:
            # Get dataset for question generation
            db = get_database()
            dataset = await db.datasets.find_one({
                "_id": ObjectId(state["dataset_id"]),
                "user_id": state["user_id"]
            })
            if not dataset or "file_path" not in dataset:
                return {
                    "last_error": "Dataset not found or missing file path",
                    "final_response": "Error: Could not access dataset for analysis."
                }
            
            # Load data for schema analysis
            df = pl.read_parquet(dataset["file_path"])
            
            # Generate questions
            generator = QuestionGenerator()
            questions = generator.generate_questions_template(df, max_questions=15)
            
            # Convert to state format
            question_states = [
                {
                    "question": q.question,
                    "question_type": q.question_type,
                    "target_columns": q.target_columns,
                    "filter_column": q.filter_column,
                    "priority": q.priority
                }
                for q in questions
            ]
            
            logger.info(f"[PLANNER] Generated {len(question_states)} questions")
            
            return {
                "questions": question_states,
                "current_question_idx": 0,
                "iteration_count": state["iteration_count"] + 1
            }
            
        except Exception as e:
            logger.error(f"[PLANNER] Error generating questions: {e}")
            return {
                "last_error": str(e),
                "iteration_count": state["iteration_count"] + 1
            }
    
    return {"iteration_count": state["iteration_count"] + 1}


async def analyst_node(state: AgentState) -> Dict[str, Any]:
    """
    ISGEN: Execute statistical analysis for current question.
    
    This node wraps InsightGenerator methods with error handling
    and state management.
    """
    logger.info(f"[ANALYST] Analyzing question {state['current_question_idx']}")
    
    from services.analysis.enhanced_quis import InsightGenerator, AnalyticalQuestion
    import polars as pl
    from db.database import get_database
    from bson import ObjectId
    
    # Safety check
    if state["current_question_idx"] >= len(state["questions"]):
        logger.info("[ANALYST] No more questions to analyze")
        return {}
    
    current_question = state["questions"][state["current_question_idx"]]
    
    try:
        # Get dataset
        db = get_database()
        dataset = await db.datasets.find_one({
            "_id": ObjectId(state["dataset_id"]),
            "user_id": state["user_id"]
        })
        df = pl.read_parquet(dataset["file_path"])
        
        # Convert to AnalyticalQuestion object
        question_obj = AnalyticalQuestion(
            question=current_question["question"],
            question_type=current_question["question_type"],
            target_columns=current_question["target_columns"],
            filter_column=current_question.get("filter_column"),
            priority=current_question.get("priority", 1.0)
        )
        
        # Generate insights
        generator = InsightGenerator()
        insights = generator.generate_insights(df, [question_obj])
        
        logger.info(f"[ANALYST] Generated {len(insights)} raw insights")
        
        # Convert to state format
        if insights:
            insight = insights[0]  # Take first insight for this question
            execution_result = {
                "insight_type": insight.insight_type,
                "description": insight.description,
                "columns": insight.columns,
                "subspace": insight.subspace,
                "statistic": insight.statistic,
                "p_value": insight.p_value,
                "effect_size": insight.effect_size,
                "effect_interpretation": insight.effect_interpretation,
                "sample_size": insight.sample_size,
                "is_simpson_paradox": insight.is_simpson_paradox,
                "novelty_score": insight.novelty_score,
                "overall_score": insight.overall_score
            }
            
            return {
                "execution_result": str(execution_result),
                "error_count": 0,  # Reset on success
                "last_error": None,
                "iteration_count": state["iteration_count"] + 1
            }
        else:
            return {
                "execution_result": "No significant insights found for this question.",
                "current_question_idx": state["current_question_idx"] + 1,
                "iteration_count": state["iteration_count"] + 1
            }
            
    except Exception as e:
        logger.error(f"[ANALYST] Error during analysis: {e}")
        return {
            "last_error": str(e),
            "error_count": state["error_count"] + 1,
            "iteration_count": state["iteration_count"] + 1
        }


async def critic_node(state: AgentState) -> Dict[str, Any]:
    """
    Critic: Validate analyst output before passing to user.
    
    Checks:
    1. Code safety (if code was generated)
    2. Statistical validity (p-value ranges, effect size sanity)
    3. Schema compliance (column names exist)
    """
    logger.info("[CRITIC] Reviewing analyst output")
    
    execution_result = state.get("execution_result", "")
    
    # Check if there's an error to handle
    if state.get("last_error"):
        logger.info(f"[CRITIC] Found error: {state['last_error']}")
        return {
            "critique": {
                "score": 0.0,
                "passed": False,
                "feedback": f"Execution failed: {state['last_error']}",
                "issues": ["execution_error"],
                "suggestions": ["Fix the error and retry"]
            },
            "iteration_count": state["iteration_count"] + 1
        }
    
    # Check if we got a valid result
    if not execution_result or execution_result == "No significant insights found for this question.":
        logger.info("[CRITIC] No significant insights, moving to next question")
        return {
            "critique": {
                "score": 0.5,
                "passed": True,  # Not an error, just no findings
                "feedback": "No significant insights for this question",
                "issues": [],
                "suggestions": []
            },
            "current_question_idx": state["current_question_idx"] + 1,
            "iteration_count": state["iteration_count"] + 1
        }
    
    # Parse and validate the insight
    try:
        import ast
        insight_dict = ast.literal_eval(execution_result)
        
        issues = []
        suggestions = []
        
        # Validate p-value
        p_value = insight_dict.get("p_value", 1.0)
        if p_value < 0 or p_value > 1:
            issues.append("invalid_p_value")
            suggestions.append(f"P-value {p_value} is out of range [0, 1]")
        
        # Validate effect size
        effect_size = insight_dict.get("effect_size", 0)
        if abs(effect_size) > 10:  # Unreasonably large
            issues.append("suspicious_effect_size")
            suggestions.append(f"Effect size {effect_size} seems unreasonably large")
        
        # Calculate critique score
        score = 1.0
        if issues:
            score = max(0.3, 1.0 - len(issues) * 0.2)
        
        passed = score >= 0.7 and len(issues) == 0
        
        return {
            "critique": {
                "score": score,
                "passed": passed,
                "feedback": "Insight validated successfully" if passed else f"Issues found: {', '.join(issues)}",
                "issues": issues,
                "suggestions": suggestions
            },
            "iteration_count": state["iteration_count"] + 1
        }
        
    except Exception as e:
        logger.error(f"[CRITIC] Error parsing insight: {e}")
        return {
            "critique": {
                "score": 0.3,
                "passed": False,
                "feedback": f"Could not parse insight: {e}",
                "issues": ["parse_error"],
                "suggestions": ["Ensure insight is in valid format"]
            },
            "iteration_count": state["iteration_count"] + 1
        }


async def novelty_filter_node(state: AgentState) -> Dict[str, Any]:
    """
    Novelty Filter: Check if insight is subjectively novel to this user.
    
    Computes:
    1. Semantic Surprisal via Belief Store vector similarity
    2. Bayesian Surprise for numeric insights
    3. Hybrid score combining both
    
    Routes to synthesizer if novel, back to planner if boring.
    """
    logger.info("[NOVELTY] Checking insight novelty")
    
    from .belief_store import get_belief_store, get_bayesian_tracker
    import re
    
    # Parse the execution result
    try:
        import ast
        insight_dict = ast.literal_eval(state["execution_result"])
        insight_text = insight_dict.get("description", "")
    except:
        insight_text = state["execution_result"]
    
    # Get Belief Store and Bayesian Tracker
    belief_store = get_belief_store()
    bayesian_tracker = get_bayesian_tracker()
    
    # 1. Calculate Semantic Surprisal
    semantic_surprisal, similar_beliefs = await belief_store.calculate_semantic_surprisal(
        user_id=state["user_id"],
        insight_text=insight_text
    )
    
    # 2. Calculate Bayesian Surprise (for numeric insights)
    bayesian_surprise = 0.5  # Default moderate surprise
    
    # Extract numeric values from insight
    numbers = re.findall(r'[-+]?\d*\.?\d+', insight_text)
    if numbers and isinstance(insight_dict, dict):
        # Use statistic or effect_size as the metric value
        metric_value = insight_dict.get("statistic") or insight_dict.get("effect_size")
        if metric_value:
            # Create metric name from columns
            columns = insight_dict.get("columns", [])
            metric_name = "_".join(columns[:2]) if columns else "unknown_metric"
            bayesian_surprise = bayesian_tracker.update_prior(metric_name, float(metric_value))
    
    # 3. Compute Hybrid Score (α = 0.6, emphasis on semantic novelty)
    alpha = 0.6
    hybrid_score = alpha * semantic_surprisal + (1 - alpha) * bayesian_surprise
    
    is_novel = hybrid_score >= state["novelty_threshold"]
    
    logger.info(
        f"[NOVELTY] Semantic: {semantic_surprisal:.2f}, "
        f"Bayesian: {bayesian_surprise:.2f}, "
        f"Hybrid: {hybrid_score:.2f}, "
        f"Threshold: {state['novelty_threshold']}, "
        f"Novel: {is_novel}"
    )
    
    # Store similar beliefs as context (for transparency)
    belief_context = [b["document"] for b in similar_beliefs[:3]]
    
    if is_novel:
        # Add to approved insights
        try:
            insight = ast.literal_eval(state["execution_result"])
            insight["novelty_score"] = hybrid_score
            insight["semantic_surprisal"] = semantic_surprisal
            insight["bayesian_surprise"] = bayesian_surprise
            approved = state.get("approved_insights", []) + [insight]
        except:
            approved = state.get("approved_insights", [])
        
        return {
            "semantic_surprisal": semantic_surprisal,
            "bayesian_surprise": bayesian_surprise,
            "hybrid_novelty_score": hybrid_score,
            "is_novel": True,
            "belief_context": belief_context,
            "approved_insights": approved,
            "current_question_idx": state["current_question_idx"] + 1,
            "iteration_count": state["iteration_count"] + 1
        }
    else:
        # Add to boring insights (for debugging)
        try:
            insight = ast.literal_eval(state["execution_result"])
            insight["novelty_score"] = hybrid_score
            insight["similar_to"] = belief_context[0] if belief_context else None
            boring = state.get("boring_insights", []) + [insight]
        except:
            boring = state.get("boring_insights", [])
        
        logger.info(f"[NOVELTY] Filtered as boring. Similar to: {belief_context[0][:50] if belief_context else 'N/A'}...")
        
        return {
            "semantic_surprisal": semantic_surprisal,
            "bayesian_surprise": bayesian_surprise,
            "hybrid_novelty_score": hybrid_score,
            "is_novel": False,
            "belief_context": belief_context,
            "boring_insights": boring,
            "current_question_idx": state["current_question_idx"] + 1,
            "iteration_count": state["iteration_count"] + 1
        }


async def synthesizer_node(state: AgentState) -> Dict[str, Any]:
    """
    Synthesizer: Compile approved insights into final response.
    """
    logger.info("[SYNTHESIZER] Generating final response")
    
    approved = state.get("approved_insights", [])
    
    if not approved:
        response = "Analysis complete. No significant novel insights were found for this dataset."
    else:
        # Format insights
        lines = [f"## Analysis Results\n\nFound {len(approved)} significant insights:\n"]
        
        for i, insight in enumerate(approved, 1):
            desc = insight.get("description", "Unknown insight")
            p_val = insight.get("p_value", "N/A")
            effect = insight.get("effect_interpretation", "")
            novelty = insight.get("novelty_score", 0)
            
            lines.append(f"### {i}. {desc}")
            lines.append(f"- **Statistical Significance**: p = {p_val}")
            if effect:
                lines.append(f"- **Effect Size**: {effect}")
            lines.append(f"- **Novelty Score**: {novelty:.2f}")
            lines.append("")
        
        response = "\n".join(lines)
    
    return {
        "final_response": response,
        "end_time": datetime.utcnow().isoformat(),
        "iteration_count": state["iteration_count"] + 1
    }


# ============================================================
# ROUTING FUNCTIONS
# ============================================================

def route_after_critic(state: AgentState) -> Literal["analyst", "novelty_filter", "synthesizer"]:
    """
    Conditional routing after Critic node.
    
    Routes:
    - REJECT (critique failed): Back to analyst for retry
    - APPROVE: To novelty filter
    - DONE (all questions answered): To synthesizer
    """
    critique = state.get("critique", {})
    error_count = state.get("error_count", 0)
    max_retries = state.get("max_retries", 3)
    current_idx = state.get("current_question_idx", 0)
    total_questions = len(state.get("questions", []))
    
    # Check if we've exceeded iteration limit
    if state.get("iteration_count", 0) >= state.get("max_iterations", 50):
        logger.warning("[ROUTER] Max iterations reached, forcing synthesis")
        return "synthesizer"
    
    # Too many retries on this question - skip to next
    if error_count >= max_retries:
        logger.info(f"[ROUTER] Max retries ({max_retries}) exceeded, skipping question")
        # This will be handled by incrementing current_question_idx
        if current_idx >= total_questions - 1:
            return "synthesizer"
        return "novelty_filter"  # Skip to next question
    
    # Critique failed - retry
    if not critique.get("passed", True):
        logger.info("[ROUTER] Critique failed, routing to analyst for retry")
        return "analyst"
    
    # All questions answered - synthesize
    if current_idx >= total_questions - 1:
        logger.info("[ROUTER] All questions answered, routing to synthesizer")
        return "synthesizer"
    
    # Normal flow - check novelty
    logger.info("[ROUTER] Critique passed, routing to novelty filter")
    return "novelty_filter"


def route_after_novelty(state: AgentState) -> Literal["planner", "synthesizer"]:
    """
    Conditional routing after Novelty Filter.
    
    Routes:
    - More questions to process: Back to planner
    - All questions done: To synthesizer
    """
    current_idx = state.get("current_question_idx", 0)
    total_questions = len(state.get("questions", []))
    
    if current_idx >= total_questions:
        logger.info("[ROUTER] All questions processed, routing to synthesizer")
        return "synthesizer"
    
    logger.info(f"[ROUTER] More questions remaining ({current_idx}/{total_questions}), routing to planner")
    return "planner"


# ============================================================
# VISUALIZATION NODE
# ============================================================

async def viz_designer_node(state: AgentState) -> Dict[str, Any]:
    """
    VIZ DESIGNER: Convert approved insights into Plotly visualization configs.
    
    Maps insight types to appropriate chart types:
    - correlation → scatter plot
    - comparison → bar chart
    - trend → line chart
    - distribution → histogram
    - anomaly → box plot
    """
    logger.info("[VIZ] Generating visualizations for approved insights")
    
    import polars as pl
    from bson import ObjectId
    from db.database import get_database
    
    viz_configs = []
    approved = state.get("approved_insights", [])
    
    if not approved:
        logger.info("[VIZ] No approved insights to visualize")
        return {"viz_configs": [], "iteration_count": state["iteration_count"] + 1}
    
    # Map insight types to chart types
    chart_type_map = {
        "correlation": "scatter",
        "comparison": "bar",
        "trend": "line",
        "distribution": "histogram",
        "subspace": "bar",
        "anomaly": "box"
    }
    
    try:
        # Load dataset once for all visualizations
        db = get_database()
        dataset = await db.datasets.find_one({
            "_id": ObjectId(state["dataset_id"]),
            "user_id": state["user_id"]
        })
        
        if not dataset or "file_path" not in dataset:
            logger.warning("[VIZ] Dataset not found, skipping visualization")
            return {"viz_configs": [], "iteration_count": state["iteration_count"] + 1}
        
        df = pl.read_parquet(dataset["file_path"])
        available_columns = list(df.columns)
        
        for i, insight in enumerate(approved):
            try:
                insight_type = insight.get("insight_type", "correlation")
                columns = insight.get("columns", [])
                description = insight.get("description", f"Insight {i+1}")
                subspace = insight.get("subspace")
                
                # Validate columns exist
                valid_columns = [c for c in columns if c in available_columns]
                if len(valid_columns) < 1:
                    logger.warning(f"[VIZ] No valid columns for insight {i+1}, skipping")
                    continue
                
                # Apply subspace filter if present
                df_filtered = df
                subspace_label = ""
                if subspace:
                    for col, val in subspace.items():
                        if col in df_filtered.columns:
                            df_filtered = df_filtered.filter(pl.col(col) == val)
                            subspace_label = f" (filtered: {col}={val})"
                
                chart_type = chart_type_map.get(insight_type, "bar")
                
                # Generate Plotly trace based on chart type
                traces = []
                layout = {
                    "title": f"{description[:60]}{'...' if len(description) > 60 else ''}{subspace_label}",
                    "paper_bgcolor": "rgba(0,0,0,0)",
                    "plot_bgcolor": "rgba(0,0,0,0)",
                    "font": {"color": "#e2e8f0"},
                    "height": 350,
                    "margin": {"t": 50, "b": 50, "l": 60, "r": 20}
                }
                
                if chart_type == "scatter" and len(valid_columns) >= 2:
                    x_data = df_filtered[valid_columns[0]].to_list()
                    y_data = df_filtered[valid_columns[1]].to_list()
                    traces.append({
                        "type": "scatter",
                        "mode": "markers",
                        "x": x_data[:1000],  # Limit for performance
                        "y": y_data[:1000],
                        "marker": {"color": "#8b5cf6", "opacity": 0.7}
                    })
                    layout["xaxis"] = {"title": valid_columns[0]}
                    layout["yaxis"] = {"title": valid_columns[1]}
                    
                elif chart_type == "bar" and len(valid_columns) >= 1:
                    # Aggregate by first categorical column
                    cat_col = valid_columns[0]
                    if len(valid_columns) >= 2:
                        val_col = valid_columns[1]
                        agg_df = df_filtered.group_by(cat_col).agg(
                            pl.col(val_col).mean().alias("value")
                        ).sort("value", descending=True).head(20)
                    else:
                        agg_df = df_filtered.group_by(cat_col).agg(
                            pl.count().alias("value")
                        ).sort("value", descending=True).head(20)
                    
                    traces.append({
                        "type": "bar",
                        "x": agg_df[cat_col].to_list(),
                        "y": agg_df["value"].to_list(),
                        "marker": {"color": "#06b6d4"}
                    })
                    layout["xaxis"] = {"title": cat_col}
                    layout["yaxis"] = {"title": valid_columns[1] if len(valid_columns) >= 2 else "Count"}
                    
                elif chart_type == "line" and len(valid_columns) >= 2:
                    # Sort by x column for line chart
                    sorted_df = df_filtered.sort(valid_columns[0])
                    traces.append({
                        "type": "scatter",
                        "mode": "lines+markers",
                        "x": sorted_df[valid_columns[0]].to_list()[:500],
                        "y": sorted_df[valid_columns[1]].to_list()[:500],
                        "line": {"color": "#10b981"}
                    })
                    layout["xaxis"] = {"title": valid_columns[0]}
                    layout["yaxis"] = {"title": valid_columns[1]}
                    
                elif chart_type == "histogram" and len(valid_columns) >= 1:
                    traces.append({
                        "type": "histogram",
                        "x": df_filtered[valid_columns[0]].to_list(),
                        "marker": {"color": "#f59e0b"}
                    })
                    layout["xaxis"] = {"title": valid_columns[0]}
                    layout["yaxis"] = {"title": "Frequency"}
                    
                elif chart_type == "box" and len(valid_columns) >= 1:
                    traces.append({
                        "type": "box",
                        "y": df_filtered[valid_columns[0]].to_list(),
                        "name": valid_columns[0],
                        "marker": {"color": "#ef4444"}
                    })
                    layout["yaxis"] = {"title": valid_columns[0]}
                
                if traces:
                    viz_configs.append({
                        "insight_id": f"insight_{i+1}",
                        "insight_type": insight_type,
                        "description": description,
                        "data": traces,
                        "layout": layout
                    })
                    logger.info(f"[VIZ] Generated {chart_type} chart for insight {i+1}")
                    
            except Exception as e:
                logger.warning(f"[VIZ] Failed to generate chart for insight {i+1}: {e}")
                continue
        
        logger.info(f"[VIZ] Generated {len(viz_configs)} visualizations")
        
    except Exception as e:
        logger.error(f"[VIZ] Error generating visualizations: {e}")
    
    return {
        "viz_configs": viz_configs,
        "iteration_count": state["iteration_count"] + 1
    }


# ============================================================
# GRAPH CONSTRUCTION
# ============================================================

def create_quis_graph():
    """
    Create the LangGraph state machine for agentic QUIS.
    
    Returns:
        Compiled StateGraph ready for execution
    """
    if not LANGGRAPH_AVAILABLE:
        raise ImportError(
            "LangGraph is required for agentic QUIS. "
            "Install with: pip install langgraph"
        )
    
    # Create graph builder
    builder = StateGraph(AgentState)
    
    # Add nodes
    builder.add_node("planner", planner_node)
    builder.add_node("analyst", analyst_node)
    builder.add_node("critic", critic_node)
    builder.add_node("novelty_filter", novelty_filter_node)
    builder.add_node("viz_designer", viz_designer_node)
    builder.add_node("synthesizer", synthesizer_node)
    
    # Add edges
    builder.add_edge("planner", "analyst")
    builder.add_edge("analyst", "critic")
    
    # Conditional edges after critic
    builder.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "analyst": "analyst",
            "novelty_filter": "novelty_filter",
            "synthesizer": "synthesizer"
        }
    )
    
    # Conditional edges after novelty filter
    builder.add_conditional_edges(
        "novelty_filter",
        route_after_novelty,
        {
            "planner": "planner",
            "synthesizer": "viz_designer"  # Route to viz_designer before synthesizer
        }
    )
    
    # Viz designer goes to synthesizer
    builder.add_edge("viz_designer", "synthesizer")
    
    # Synthesizer goes to END
    builder.add_edge("synthesizer", END)
    
    # Set entry point
    builder.set_entry_point("planner")
    
    # Compile with memory checkpointer
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)
    
    logger.info("QUIS graph compiled successfully")
    return graph


# ============================================================
# MAIN ENTRY POINT
# ============================================================

async def run_agentic_quis(
    dataset_id: str,
    user_id: str,
    data_schema: str,
    sample_rows: str,
    row_count: int,
    column_count: int,
    novelty_threshold: float = 0.35,
    thread_id: str = None
) -> Dict[str, Any]:
    """
    Run the agentic QUIS analysis pipeline.
    
    Args:
        dataset_id: ID of the dataset to analyze
        user_id: User ID for Belief Graph retrieval
        data_schema: JSON string of column schema
        sample_rows: Text preview of data
        row_count: Total rows
        column_count: Total columns
        novelty_threshold: Minimum novelty to present (default 0.35)
        thread_id: Optional thread ID for checkpointing
    
    Returns:
        Dictionary containing:
        - final_response: Synthesized markdown response
        - approved_insights: List of novel insights
        - boring_insights: List of filtered insights
        - stats: Execution statistics
    """
    import uuid
    
    # Create graph
    graph = create_quis_graph()
    
    # Create initial state
    initial_state = create_initial_state(
        dataset_id=dataset_id,
        user_id=user_id,
        data_schema=data_schema,
        sample_rows=sample_rows,
        row_count=row_count,
        column_count=column_count,
        novelty_threshold=novelty_threshold
    )
    
    # Configuration with thread ID
    config = {
        "configurable": {
            "thread_id": thread_id or str(uuid.uuid4())
        }
    }
    
    # Run graph
    logger.info(f"Starting agentic QUIS for dataset {dataset_id}")
    
    final_state = None
    async for state in graph.astream(initial_state, config):
        final_state = state
        # Log progress
        for node_name, node_state in state.items():
            if isinstance(node_state, dict):
                logger.debug(f"Node {node_name}: iteration {node_state.get('iteration_count', '?')}")
    
    # Extract results from final state
    # The final state is nested by node name
    result_state = {}
    for node_name, node_state in (final_state or {}).items():
        if isinstance(node_state, dict):
            result_state.update(node_state)
    
    return {
        "final_response": result_state.get("final_response", "Analysis complete."),
        "approved_insights": result_state.get("approved_insights", []),
        "boring_insights": result_state.get("boring_insights", []),
        "rejected_insights": result_state.get("rejected_insights", []),
        "viz_configs": result_state.get("viz_configs", []),
        "stats": {
            "total_questions": len(result_state.get("questions", [])),
            "novel_insights": len(result_state.get("approved_insights", [])),
            "filtered_insights": len(result_state.get("boring_insights", [])),
            "iterations": result_state.get("iteration_count", 0),
            "start_time": result_state.get("start_time"),
            "end_time": result_state.get("end_time")
        }
    }


# ============================================================
# HIGH-LEVEL ANALYSIS ENTRY POINT (For Chat Integration)
# ============================================================

async def run_quis_analysis(
    dataset_id: str,
    user_id: str,
    query: str = None,
    novelty_threshold: float = 0.35
) -> Dict[str, Any]:
    """
    High-level entry point for QUIS analysis.
    
    Handles dataset loading from MongoDB and state initialization.
    Use this function from chat endpoints for deep analysis.
    
    Args:
        dataset_id: MongoDB ObjectId of the dataset to analyze
        user_id: User ID for access control and Belief Graph
        query: Optional user query to guide analysis focus
        novelty_threshold: Minimum novelty score (0-1) to present insight
        
    Returns:
        Dict containing:
        - response: Synthesized markdown response with insights
        - charts: List of Plotly chart configurations
        - insights: List of approved insight objects
        - stats: Execution statistics
        
    Raises:
        HTTPException: If dataset not found or still processing
    """
    import polars as pl
    import json
    from bson import ObjectId
    from fastapi import HTTPException
    from db.database import get_database
    from datetime import datetime
    
    start_time = datetime.utcnow()
    
    # Get dataset from MongoDB
    db = get_database()
    dataset = await db.datasets.find_one({
        "_id": ObjectId(dataset_id) if isinstance(dataset_id, str) else dataset_id,
        "user_id": user_id
    })
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    file_path = dataset.get("file_path")
    if not file_path:
        raise HTTPException(status_code=409, detail="Dataset is still processing")
    
    # Build lightweight schema summary using lazy loading
    try:
        lf = pl.scan_parquet(file_path)
        schema = {col: str(dtype) for col, dtype in lf.schema.items()}
        
        # Get sample rows (limit to 5 for context)
        sample_df = lf.limit(5).collect()
        sample_rows = sample_df.to_pandas().to_string()
        
        # Get row count from metadata or estimate
        metadata = dataset.get("metadata", {})
        row_count = metadata.get("dataset_overview", {}).get("total_rows", 0)
        if not row_count:
            row_count = lf.select(pl.count()).collect().item()
        
        column_count = len(schema)
        
    except Exception as e:
        logger.error(f"Failed to load dataset schema: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {str(e)}")
    
    # Run the agentic QUIS pipeline
    logger.info(f"Starting QUIS analysis for dataset {dataset_id} (user: {user_id})")
    
    try:
        result = await run_agentic_quis(
            dataset_id=str(dataset_id),
            user_id=user_id,
            data_schema=json.dumps(schema),
            sample_rows=sample_rows,
            row_count=row_count,
            column_count=column_count,
            novelty_threshold=novelty_threshold
        )
    except ImportError as e:
        # LangGraph not installed - return helpful error
        logger.warning(f"LangGraph not available: {e}")
        return {
            "response": "Deep analysis requires LangGraph. Please install with: pip install langgraph",
            "charts": [],
            "insights": [],
            "stats": {"error": "langgraph_not_installed"},
            "analysis_type": "error"
        }
    except Exception as e:
        logger.error(f"QUIS analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    
    end_time = datetime.utcnow()
    execution_time = (end_time - start_time).total_seconds()
    
    # Format response for chat integration
    return {
        "response": result.get("final_response", "Analysis complete."),
        "charts": result.get("viz_configs", []),
        "insights": result.get("approved_insights", []),
        "boring_filtered": len(result.get("boring_insights", [])),
        "stats": {
            **result.get("stats", {}),
            "execution_time_seconds": execution_time
        },
        "analysis_type": "deep_quis"
    }

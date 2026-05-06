import logging
from typing import Dict, Any, Optional, List, Literal, TypedDict
from datetime import datetime
import json

import polars as pl

from services.query.executor import query_executor
from services.datasets.faiss_vector_service import faiss_vector_service
from services.agents.belief_store import get_belief_store
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from services.agents.agent_utils import build_observation_summary, build_synthesis_snippets
from services.analysis.advanced_stats import (
    hypothesis_tester,
    correlation_analyzer,
    anomaly_detector,
    effect_size_calculator,
)
from db.database import get_database
from services.llm_router import llm_router

logger = logging.getLogger(__name__)


class ReActContext(TypedDict):
    """Context for a single ReAct execution — request-scoped, never shared."""
    query: str
    dataset_id: str
    user_id: str
    df: Optional[Any]  # Polars DataFrame, loaded on demand


class ChatAgent:
    """
    ReAct Agent: Reason → Act → Observe → Loop
    
    Orchestrates 4 composable tools to answer data questions:
    1. SQL Tool — Execute queries against real data (returns actual numbers)
    2. Stats Tool — Test statistical significance (returns p-value, effect size)
    3. RAG Tool — Retrieve business context (returns historical patterns)
    4. Memory Tool — Check if finding is novel to user (returns novelty score)
    
    All state is request-scoped (passed via function args), never stored on self.
    This prevents multi-tenancy data leaks between concurrent users.
    """
    
    def __init__(self):
        """Initialize the agent with access to all 4 tools (singletons)."""
        # Tool 1: SQL — executes queries against data
        self.sql_tool = query_executor
        
        # Tool 2: Stats — lightweight, composable statistical primitives
        #         (not enhanced_quis, which is a full pipeline)
        self.stats_tool = {
            "hypothesis_tester": hypothesis_tester,
            "correlation_analyzer": correlation_analyzer,
            "anomaly_detector": anomaly_detector,
            "effect_size_calculator": effect_size_calculator,
        }
        
        # Tool 3: RAG — vector search for historical context
        self.rag_tool = faiss_vector_service
        
        # Tool 4: Memory — user belief store for novelty detection
        self.memory_tool = get_belief_store()
        
        # Database access (for dataset loading, conversation management)
        self.db = get_database()
        self.llm_router = llm_router
        
        logger.info("✓ ChatAgent initialized with 4 tools (no instance state)")

    # NOTE: dataset loading and schema summarization are infrastructure concerns.
    # The ChatAgent expects `df` and an optional compact `schema` to be passed
    # into `run()` by the caller. This keeps ChatAgent minimal: run, _reason,
    # _act, _synthesize only.
        
    
    async def run(
        self,
        query: str,
        dataset_id: str,
        user_id: str,
        df: Optional[Any] = None,
        dataset_schema: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        ReAct Loop: Reason → Act → Observe → Repeat
        
        Runs up to 5 iterations. Each iteration:
        1. _reason() decides which tool to call next (or "DONE")
        2. _act() calls the tool and captures result
        3. Append observation to local list
        4. Loop or synthesize
        
        All state is LOCAL (request-scoped), never touches self.
        Exceptions from tools are caught and logged as failed observations.
        
        Args:
            query: User's natural language question
            dataset_id: Which dataset to analyze
            user_id: Which user is asking (for memory context)
        
        Returns:
            {
                "response": str,            # Final answer to user
                "tools_used": list[str],    # Tools that ran successfully
                "iterations": int,          # Number of ReAct loops
                "observations": list,       # Full trace for debugging
            }
        """
        # Request-scoped context — dies when run() returns
        context: ReActContext = {
            "query": query,
            "dataset_id": dataset_id,
            "user_id": user_id,
            "df": df,
        }
        if dataset_schema:
            context["schema"] = dataset_schema

        # Agent must not load dataset itself — caller must pass a DataFrame.
        if context.get("df") is None:
            raise ValueError("ChatAgent.run() requires a Polars DataFrame 'df' passed by the caller")

        # If no compact schema was provided, build one for planner prompts
        if not context.get("schema"):
            try:
                schema_ctx = await enhanced_dataset_service.build_compact_schema_context(
                    dataset_id=dataset_id, user_id=user_id, sample_rows=3
                )
                context["schema"] = schema_ctx
            except Exception:
                context["schema"] = "Schema not available"

        observations: List[Dict[str, Any]] = []
        tools_used = set()

        max_iters = 5
        for i in range(max_iters):
            try:
                decision = await self._reason(observations, context)
            except Exception as e:
                logger.error(f"[RUN] _reason failed: {e}", exc_info=True)
                break

            if decision == "DONE":
                logger.debug("[RUN] Reasoner returned DONE — finishing loop")
                break

            obs = await self._act(decision, observations, context)
            observations.append(obs)
            if obs.get("success"):
                tools_used.add(obs.get("tool"))

            # If a tool indicates finality, stop early
            if obs.get("tool") == "memory" and obs.get("success"):
                logger.debug("[RUN] Memory tool ran and returned success — ending loop")
                break

        # Final synthesis via narrative LLM
        try:
            final_answer = await self._synthesize(query, observations, context)
        except Exception as e:
            logger.error(f"[RUN] _synthesize failed: {e}", exc_info=True)
            final_answer = "I couldn't synthesize a final answer due to an internal error."

        return {
            "response": final_answer,
            "tools_used": list(tools_used),
            "iterations": len(observations),
            "observations": observations,
        }
    
    async def _reason(self, observations: List[Dict[str, Any]], context: ReActContext) -> str:
        """Decide which tool to call next using role-mapped LLMs.

        - First turn: use `intent_engine` (expects JSON with tools list)
        - Subsequent turns: use `complex_analysis` (returns one token)
        """
        query = context["query"]
        schema_context = context.get("schema", "Schema not provided")

        if not observations:
            prompt = (
                "You are a planning model for a ReAct data agent.\n\n"
                f"User question:\n{query}\n\n"
                f"Dataset schema:\n{schema_context}\n\n"
                "Task: choose the minimal set of tools needed for the first step.\n"
                "Available tools: sql, stats, rag, memory.\n"
                "Return ONLY valid JSON in this format:\n"
                '{"tools": ["sql", "stats"], "reason": "short explanation"}\n\n'
                "Rules:\n"
                "- Use sql when the question needs data from the dataset.\n"
                "- Use rag when the question needs historical/business context.\n"
                "- Use stats when significance, correlation, anomaly, or effect size is needed.\n"
                "- Use memory when novelty to the user matters.\n"
                "- Return an empty tools array only if the question is clearly unanswerable from data."
            )

            try:
                response = await self.llm_router.call(
                    prompt=prompt,
                    model_role="intent_engine",
                    expect_json=True,
                    temperature=0.1,
                    max_tokens=256,
                )
            except Exception as exc:
                logger.warning("[REASON] Intent planner failed (%s); defaulting to SQL.", exc)
                return "sql"

            tools = []
            if isinstance(response, dict):
                tools = response.get("tools") or response.get("tool") or []
            elif isinstance(response, list):
                tools = response

            if isinstance(tools, str):
                tools = [tools]

            for tool_name in tools:
                if tool_name in {"sql", "stats", "rag", "memory"}:
                    logger.debug("[REASON] First-turn planner selected → %s", tool_name)
                    return tool_name

            logger.debug("[REASON] First-turn planner returned no usable tools → DONE")
            return "DONE"

        # Subsequent turns: summarize observations and ask the reasoning model
        observation_summary = build_observation_summary(observations, max_items=5)

        prompt = (
            "You are a reasoning model for a ReAct data agent.\n\n"
            f"User question:\n{query}\n\n"
            f"Dataset schema:\n{schema_context}\n\n"
            f"Observations so far:\n{observation_summary}\n\n"
            "Task: decide the next single tool to call, or DONE if enough evidence exists.\n"
            "Available tools: sql, stats, rag, memory, DONE.\n"
            "Return ONLY one token: sql, stats, rag, memory, or DONE.\n"
            "Rules:\n"
            "- Use sql if we still need direct data.\n"
            "- Use stats if the data exists but needs deeper analysis.\n"
            "- Use rag if we need business or historical context.\n"
            "- Use memory if we need novelty assessment.\n"
            "- Use DONE if the chain already has enough evidence to answer well."
        )

        try:
            response = await self.llm_router.call(
                prompt=prompt,
                model_role="complex_analysis",
                expect_json=False,
                temperature=0.1,
                max_tokens=32,
            )
        except Exception as exc:
            logger.warning("[REASON] Reasoning model failed (%s); defaulting to DONE.", exc)
            return "DONE"

        choice = str(response).strip().upper()
        if choice in {"SQL", "STATS", "RAG", "MEMORY", "DONE"}:
            logger.debug("[REASON] Reasoning model selected → %s", choice)
            return choice if choice == "DONE" else choice.lower()

        logger.debug("[REASON] Unrecognized reasoning response '%s' → DONE", choice)
        return "DONE"
    
    async def _act(
        self, tool_name: str, observations: List[Dict[str, Any]], context: ReActContext
    ) -> Dict[str, Any]:
        """
        Act: Call a single tool and return its observation.
        
        Routes to correct tool and extracts the right input:
        - SQL: uses context["query"] (original question)
        - Stats: uses observations[-1]["result"] (SQL output data)
        - RAG: uses observations[-1]["result"]["summary"] (SQL findings)
        - Memory: uses observations[-1]["result"]["key_finding"] (stats insight)
        
        Calls one of: sql | stats | rag | memory
        Returns observation dict with success, result, reasoning_summary.
        """
        timestamp = datetime.utcnow().isoformat()
        
        try:
            if tool_name == "sql":
                # SQL Tool: Query the database for actual data
                logger.debug(f"[ACT] Calling SQL with query: {context['query'][:80]}...")

                df = context.get("df")
                if df is None:
                    return {
                        "tool": "sql",
                        "success": False,
                        "timestamp": timestamp,
                        "error": "No DataFrame provided to agent; caller must pass df",
                        "result": {},
                        "reasoning_summary": "SQL tool could not access dataset data",
                    }

                result = await self.sql_tool.execute_query(
                    query=context["query"],
                    df=df,
                    dataset_id=context["dataset_id"],
                )
                
                # Cache the DataFrame for downstream tools
                context["df"] = df
                
                return {
                    "tool": "sql",
                    "success": True,
                    "timestamp": timestamp,
                    "error": None,
                    "result": result,
                    "reasoning_summary": f"Executed SQL query, returned {result.get('row_count', 0)} rows",
                }
            
            elif tool_name == "stats":
                # Stats Tool: Analyze SQL results for patterns, correlations, anomalies
                if not observations or observations[-1]["tool"] != "sql":
                    return {
                        "tool": "stats",
                        "success": False,
                        "timestamp": timestamp,
                        "error": "Stats requires SQL data as input",
                        "result": {},
                        "reasoning_summary": "Stats tool called without SQL result",
                    }
                
                sql_result = observations[-1]["result"]
                df = pl.from_dicts(sql_result.get("data") or [])
                
                if df.is_empty():
                    logger.debug("[ACT] SQL returned no data — stats tool skipped")
                    return {
                        "tool": "stats",
                        "success": False,
                        "timestamp": timestamp,
                        "error": "No data to analyze",
                        "result": {},
                        "reasoning_summary": "SQL returned empty result",
                    }
                
                # Apply multiple statistical tests
                logger.debug("[ACT] Running stats analysis (hypothesis test, correlation, anomaly, effect size)...")
                stats_results = {}
                
                try:
                    stats_results["hypothesis_test"] = hypothesis_tester(df)
                    stats_results["correlations"] = correlation_analyzer(df)
                    stats_results["anomalies"] = anomaly_detector(df)
                    stats_results["effect_sizes"] = effect_size_calculator(df)
                except Exception as e:
                    logger.error(f"[ACT] Stats analysis error: {e}", exc_info=True)
                    return {
                        "tool": "stats",
                        "success": False,
                        "timestamp": timestamp,
                        "error": f"Stats analysis failed: {str(e)}",
                        "result": {},
                        "reasoning_summary": f"Stats tool failed on data analysis",
                    }
                
                return {
                    "tool": "stats",
                    "success": True,
                    "timestamp": timestamp,
                    "error": None,
                    "result": stats_results,
                    "reasoning_summary": f"Stats analysis complete: found {len(stats_results)} analysis types",
                }
            
            elif tool_name == "rag":
                # RAG Tool: Retrieve historical context/patterns from vector DB
                if not observations:
                    return {
                        "tool": "rag",
                        "success": False,
                        "timestamp": timestamp,
                        "error": "RAG requires prior query results",
                        "result": {},
                        "reasoning_summary": "RAG tool called without context",
                    }
                
                # Extract search query from latest observation (could be SQL summary or user query)
                search_text = context["query"]  # Default: original user query
                if observations:
                    # Prefer summary from stats/sql if available
                    latest = observations[-1]
                    if latest["tool"] == "stats" and latest["result"]:
                        search_text = latest["reasoning_summary"]
                    elif latest["tool"] == "sql" and latest["result"].get("summary"):
                        search_text = latest["result"].get("summary", context["query"])
                
                logger.debug(f"[ACT] RAG search for: {search_text[:80]}...")
                
                rag_results = await self.rag_tool.search_similar_queries(
                    query=search_text,
                    user_id=context["user_id"],
                    k=5,
                )
                
                return {
                    "tool": "rag",
                    "success": True,
                    "timestamp": timestamp,
                    "error": None,
                    "result": {
                        "documents": rag_results,
                        "search_query": search_text,
                    },
                    "reasoning_summary": f"Retrieved {len(rag_results)} similar documents from historical context",
                }
            
            elif tool_name == "memory":
                # Memory Tool: Check if finding is novel to this user
                if not observations:
                    return {
                        "tool": "memory",
                        "success": False,
                        "timestamp": timestamp,
                        "error": "Memory requires prior analysis",
                        "result": {},
                        "reasoning_summary": "Memory tool called without findings",
                    }
                
                # Extract the key finding from latest observation (usually stats or RAG)
                latest_result = observations[-1]["result"]
                finding_text = observations[-1]["reasoning_summary"]
                
                logger.debug(f"[ACT] Checking novelty for user {context['user_id']}: {finding_text[:80]}...")
                
                # Get user's belief store and check novelty
                belief_store = self.memory_tool
                user_surprisal, _similar_beliefs = await belief_store.calculate_semantic_surprisal(
                    context["user_id"],
                    finding_text,
                )
                
                # Store the new finding in user's memory
                await belief_store.add_belief(
                    user_id=context["user_id"],
                    belief_text=finding_text,
                    dataset_id=context["dataset_id"],
                )
                
                return {
                    "tool": "memory",
                    "success": True,
                    "timestamp": timestamp,
                    "error": None,
                    "result": {
                        "surprisal_score": user_surprisal,
                        "is_novel": user_surprisal > 0.7,  # Threshold: 0.7 = novel
                        "finding": finding_text,
                    },
                    "reasoning_summary": f"Novelty check complete: surprisal={user_surprisal:.2f} ({'novel' if user_surprisal > 0.7 else 'familiar'})",
                }
            
            else:
                # Unknown tool
                return {
                    "tool": tool_name,
                    "success": False,
                    "timestamp": timestamp,
                    "error": f"Unknown tool: {tool_name}",
                    "result": {},
                    "reasoning_summary": f"Tool '{tool_name}' not recognized",
                }
        
        except Exception as e:
            # Catch any unexpected exception from tool execution
            logger.error(f"[ACT] Unexpected exception in {tool_name}: {e}", exc_info=True)
            return {
                "tool": tool_name,
                "success": False,
                "timestamp": timestamp,
                "error": f"Unexpected error: {str(e)}",
                "result": {},
                "reasoning_summary": f"Tool execution exception: {str(e)[:100]}",
            }
    
    async def _synthesize(
        self, query: str, observations: List[Dict[str, Any]], context: ReActContext
    ) -> str:
        """
        Synthesize: Build final answer from observation chain.
        
        Assembles findings from each tool into a coherent narrative:
        - SQL findings (actual data + row counts)
        - Stats findings (significance, correlations, anomalies)
        - RAG findings (historical context, similar patterns)
        - Memory findings (novelty assessment)
        
        Returns: Natural language response to user.
        """
        if not observations:
            return "No data available to answer your question. Please check your dataset and try again."
        
        # Build a compact prompt from observations for the narrative model
        snippets = build_synthesis_snippets(observations, max_chars=300)
        prompt = (
            f"You are a narrative assistant. The user asked: {query}\n\n"
            "Below are concise reasoning snippets and brief results from the agent's tools:\n"
            + "\n".join(snippets)
            + "\n\nProvide a concise, human-facing summary of findings and recommended next steps."
        )

        try:
            resp = await self.llm_router.call(
                prompt=prompt,
                model_role="narrative_story",
                user_id=context.get("user_id"),
                expect_json=False,
                max_tokens=512,
            )
        except Exception as e:
            logger.error(f"[SYNTHESIZE] Narrative model call failed: {e}", exc_info=True)
            return "Failed to produce a narrative summary."

        return resp.get("text") if isinstance(resp, dict) else str(resp)
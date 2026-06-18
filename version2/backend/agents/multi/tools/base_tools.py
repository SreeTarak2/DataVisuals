"""
Tool wrappers — thin adapters that expose existing services as ReAct tools.

Each wrapper wraps one service method with a consistent interface:
    async def call(context, observations) -> tuple[dict, str]

The tuple is (result_dict, reasoning_summary) — matching _call_tool expectations.
"""

from typing import Any

import polars as pl

from services.query.executor import query_executor


async def sql_tool(
    context: dict[str, Any], observations: list[dict]
) -> tuple[dict[str, Any], str]:
    """
    Execute a natural-language query against the dataset via SQL.

    Input:  context["query"], context["df"], context["dataset_id"]
    Output: query result dict (same shape as query_executor.execute_query)
    """
    df = context.get("df")
    if df is None:
        return {
            "success": False,
            "error": "No DataFrame provided",
        }, "SQL tool requires df in context"

    result = await query_executor.execute_query(
        query=context["query"],
        df=df,
        dataset_id=context["dataset_id"],
    )
    row_count = result.get("row_count", 0)
    return result, f"Executed SQL query, returned {row_count} rows"


async def stats_tool(
    context: dict[str, Any], observations: list[dict]
) -> tuple[dict[str, Any], str]:
    """
    Run statistical analysis on the most recent SQL result.

    Input:  context["df"] (from last SQL observation)
    Output: dict with hypothesis_test, correlations, anomalies, effect_sizes
    """
    from services.analysis.advanced_stats import (
        anomaly_detector,
        correlation_analyzer,
        effect_size_calculator,
        hypothesis_tester,
    )

    sql_obs = None
    for obs in reversed(observations):
        if obs.get("tool") == "sql" and obs.get("success"):
            sql_obs = obs
            break

    if sql_obs is None:
        return {
            "error": "Stats requires a prior SQL observation"
        }, "Stats called without SQL result"

    data = sql_obs.get("result", {}).get("data", [])
    df = pl.from_dicts(data) if data else pl.DataFrame()

    if df.is_empty():
        return {"error": "No data to analyze"}, "SQL returned empty result"

    stats_results = {
        "hypothesis_test": hypothesis_tester(df),
        "correlations": correlation_analyzer(df),
        "anomalies": anomaly_detector(df),
        "effect_sizes": effect_size_calculator(df),
    }

    return (
        stats_results,
        f"Stats analysis complete: {len(stats_results)} analysis types",
    )


async def rag_tool(
    context: dict[str, Any], observations: list[dict]
) -> tuple[dict[str, Any], str]:
    """
    Retrieve historical context from the vector database.

    Input:  context["user_id"], context["query"]
    Output: similar documents list
    """
    from services.datasets.faiss_vector_service import faiss_vector_service

    search_text = context["query"]
    for obs in reversed(observations):
        if obs.get("success"):
            summary = obs.get("reasoning_summary") or ""
            if summary:
                search_text = summary
                break

    rag_results = await faiss_vector_service.search_similar_queries(
        query=search_text,
        user_id=context["user_id"],
        k=5,
    )

    return {"documents": rag_results}, f"Retrieved {len(rag_results)} similar documents"


async def memory_tool(
    context: dict[str, Any], observations: list[dict]
) -> tuple[dict[str, Any], str]:
    """
    Check novelty of the latest finding and store it in the user's belief store.

    Input:  context["user_id"], context["dataset_id"]
    Output: {surprisal_score, is_novel, finding}
    """
    from agents.belief.belief_store import get_belief_store

    belief_store = get_belief_store()
    finding_text = ""
    for obs in reversed(observations):
        if obs.get("success"):
            finding_text = obs.get("reasoning_summary") or ""
            if finding_text:
                break

    if not finding_text:
        return {"error": "No finding to check"}, "Memory tool called without findings"

    user_surprisal, _similar_beliefs = await belief_store.calculate_semantic_surprisal(
        context["user_id"],
        finding_text,
    )

    await belief_store.add_belief(
        user_id=context["user_id"],
        belief_text=finding_text,
        dataset_id=context.get("dataset_id"),
    )

    is_novel = user_surprisal > 0.7
    return (
        {
            "surprisal_score": user_surprisal,
            "is_novel": is_novel,
            "finding": finding_text,
        },
        f"Novelty: surprisal={user_surprisal:.2f} ({'novel' if is_novel else 'familiar'})",
    )

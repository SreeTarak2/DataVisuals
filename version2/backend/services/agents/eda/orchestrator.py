"""
EDA Orchestrator
Loads pre-computed Celery data, runs 6 agents, and yields Server-Sent Events.

Pipeline order:
  1. Planner          (sequential)
  2. Data Understanding (sequential)
  3. Univariate  ─┐  (parallel, deepcopy so writes never race)
  4. Bivariate   ─┘
  5. Visualization    (sequential)
  6. Critic           (sequential)

SSE event shapes:
  {"type": "agent_start",  "agent": "planner",   "label": "Planning analysis…"}
  {"type": "agent_done",   "agent": "planner",   "data": {...}}
  {"type": "agent_error",  "agent": "planner",   "error": "…"}
  {"type": "pipeline_done","data": {full result, timings, partial_failure}}
  {"type": "pipeline_error","error": "…"}
"""

import asyncio
import json
import logging
import re
import time
from typing import AsyncGenerator

from db.database import get_database
from services.agents.eda.context import AgentContext
from services.agents.eda.agents import (
    planner, data_understanding, univariate, bivariate, visualization, critic,
)

logger = logging.getLogger(__name__)

AGENT_LABELS = {
    "planner":            "Planning analysis…",
    "data_understanding": "Understanding your data…",
    "univariate":         "Exploring each column…",
    "bivariate":          "Finding relationships…",
    "visualization":      "Selecting best charts…",
    "critic":             "Validating results…",
}

# Per-agent timeouts (seconds) — bivariate uses DeepSeek which reasons slowly
AGENT_TIMEOUTS = {
    "planner":            30.0,
    "data_understanding": 10.0,
    "univariate":         45.0,
    "bivariate":          60.0,
    "visualization":      45.0,
    "critic":             45.0,
}


def _sse(type_: str, **kwargs) -> str:
    return f"data: {json.dumps({'type': type_, **kwargs})}\n\n"


def _sanitize_question(q: str) -> str:
    """
    Strip and cap user question to prevent prompt injection.
    Removing control characters; the orchestrator wraps it in delimiters at call sites.
    """
    q = re.sub(r"[\x00-\x1f\x7f]", " ", q).strip()
    return q[:500]


def _normalize_correlations(raw: list) -> list:
    """
    Upstream Celery can emit correlations with different key names.
    Normalise once here so every downstream agent uses {column_a, column_b, correlation}.
    """
    out = []
    for c in raw:
        col_a = c.get("column_a") or c.get("col_a") or (c.get("columns") or ["?", "?"])[0]
        col_b = c.get("column_b") or c.get("col_b") or (c.get("columns") or ["?", "?"])[-1]
        r = c.get("correlation") or c.get("r") or c.get("coefficient", 0)
        out.append({"column_a": col_a, "column_b": col_b, "correlation": r})
    return out


async def _load_context(dataset_id: str, user_id: str, question: str) -> AgentContext:
    db = get_database()
    doc = await db.uploads.find_one({"_id": dataset_id, "user_id": user_id})
    if not doc:
        raise ValueError(f"Dataset '{dataset_id}' not found")
    if not doc.get("is_processed"):
        raise ValueError("Dataset is still processing — please wait for it to complete")

    meta = doc.get("metadata", {})
    col_meta = meta.get("column_metadata", [])

    if not col_meta:
        raise ValueError("Dataset has no column metadata — re-upload or re-process the dataset")

    # Normalise correlation schema once so all agents get consistent keys
    stat_findings = meta.get("statistical_findings", {})
    if "correlations" in stat_findings:
        stat_findings = {
            **stat_findings,
            "correlations": _normalize_correlations(stat_findings["correlations"]),
        }

    return AgentContext(
        dataset_id=dataset_id,
        user_id=user_id,
        user_question=_sanitize_question(question),
        dataset_name=doc.get("name", "Untitled"),
        domain=doc.get("domain", "general"),
        row_count=doc.get("row_count", 0),
        column_count=doc.get("column_count", 0),
        column_metadata=col_meta,
        data_quality=meta.get("data_quality", {}),
        statistical_findings=stat_findings,
        deep_analysis=meta.get("deep_analysis", {}),
        chart_recommendations=meta.get("chart_recommendations", []),
        sample_data=meta.get("sample_data", [])[:5],
        domain_intelligence=meta.get("domain_intelligence", {}),
    )


async def _run_agent(name: str, fn, ctx: AgentContext) -> tuple[AgentContext, str | None]:
    """
    Run one agent with a timeout. Returns (updated_ctx, error_msg | None).
    The caller is responsible for yielding agent_start BEFORE calling this,
    and for yielding agent_done / agent_error based on the returned error.
    """
    timeout = AGENT_TIMEOUTS.get(name, 45.0)
    try:
        result = await asyncio.wait_for(fn(ctx), timeout=timeout)
        return result, None
    except asyncio.TimeoutError:
        logger.error(f"[{name}] timed out after {timeout:.0f}s")
        return ctx, f"Timed out after {timeout:.0f}s"
    except Exception as e:
        logger.error(f"[{name}] failed: {e}", exc_info=True)
        return ctx, str(e)


async def run_eda_pipeline(
    dataset_id: str,
    user_id: str,
    user_question: str,
) -> AsyncGenerator[str, None]:
    """Yields SSE strings. Call with `async for event in run_eda_pipeline(...)`."""

    try:
        ctx = await _load_context(dataset_id, user_id, user_question)
    except ValueError as e:
        yield _sse("pipeline_error", error=str(e))
        return

    # ── 1. Planner ───────────────────────────────────────────────────────────
    yield _sse("agent_start", agent="planner", label=AGENT_LABELS["planner"])
    t0 = time.monotonic()
    ctx, err = await _run_agent("planner", planner.run, ctx)
    if err:
        ctx.errors.append(f"planner: {err}")
        ctx.partial_failure = True
        yield _sse("agent_error", agent="planner", error=err)
    else:
        ctx.timings["planner"] = time.monotonic() - t0
        yield _sse("agent_done", agent="planner", data=_summary("planner", ctx))

    # ── 2. Data Understanding ────────────────────────────────────────────────
    yield _sse("agent_start", agent="data_understanding", label=AGENT_LABELS["data_understanding"])
    t0 = time.monotonic()
    ctx, err = await _run_agent("data_understanding", data_understanding.run, ctx)
    if err:
        ctx.errors.append(f"data_understanding: {err}")
        ctx.partial_failure = True
        yield _sse("agent_error", agent="data_understanding", error=err)
    else:
        ctx.timings["data_understanding"] = time.monotonic() - t0
        yield _sse("agent_done", agent="data_understanding", data=_summary("data_understanding", ctx))

    # ── 3. Univariate ────────────────────────────────────────────────────────
    yield _sse("agent_start", agent="univariate", label=AGENT_LABELS["univariate"])
    t0 = time.monotonic()
    ctx, err = await _run_agent("univariate", univariate.run, ctx)
    if err:
        ctx.errors.append(f"univariate: {err}")
        ctx.partial_failure = True
        yield _sse("agent_error", agent="univariate", error=err)
    else:
        ctx.timings["univariate"] = time.monotonic() - t0
        yield _sse("agent_done", agent="univariate", data=_summary("univariate", ctx))

    # ── 4. Bivariate (sequential after univariate so it sees univariate_report) ──
    yield _sse("agent_start", agent="bivariate", label=AGENT_LABELS["bivariate"])
    t0 = time.monotonic()
    ctx, err = await _run_agent("bivariate", bivariate.run, ctx)
    if err:
        ctx.errors.append(f"bivariate: {err}")
        ctx.partial_failure = True
        yield _sse("agent_error", agent="bivariate", error=err)
    else:
        ctx.timings["bivariate"] = time.monotonic() - t0
        yield _sse("agent_done", agent="bivariate", data=_summary("bivariate", ctx))

    # ── 5. Visualization ─────────────────────────────────────────────────────
    yield _sse("agent_start", agent="visualization", label=AGENT_LABELS["visualization"])
    t0 = time.monotonic()
    ctx, err = await _run_agent("visualization", visualization.run, ctx)
    if err:
        ctx.errors.append(f"visualization: {err}")
        ctx.partial_failure = True
        yield _sse("agent_error", agent="visualization", error=err)
    else:
        ctx.timings["visualization"] = time.monotonic() - t0
        yield _sse("agent_done", agent="visualization", data=_summary("visualization", ctx))

    # ── 6. Critic ────────────────────────────────────────────────────────────
    yield _sse("agent_start", agent="critic", label=AGENT_LABELS["critic"])
    t0 = time.monotonic()
    ctx, err = await _run_agent("critic", critic.run, ctx)
    if err:
        ctx.errors.append(f"critic: {err}")
        ctx.partial_failure = True
        yield _sse("agent_error", agent="critic", error=err)
    else:
        ctx.timings["critic"] = time.monotonic() - t0
        yield _sse("agent_done", agent="critic", data=_summary("critic", ctx))

    # ── Final result ──────────────────────────────────────────────────────────
    yield _sse("pipeline_done", data=_final(ctx))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _summary(name: str, ctx: AgentContext) -> dict:
    if name == "planner":
        return ctx.planner_output
    if name == "data_understanding":
        return {
            "columns": ctx.data_passport.get("column_breakdown", {}),
            "quality_flags": ctx.data_passport.get("quality_flags", {}),
        }
    if name == "univariate":
        return {
            "findings_count": len(ctx.univariate_report.get("key_findings", [])),
            "key_findings": ctx.univariate_report.get("key_findings", [])[:3],
        }
    if name == "bivariate":
        return {
            "relationships_count": len(ctx.bivariate_report.get("key_relationships", [])),
            "primary_drivers": ctx.bivariate_report.get("primary_drivers", []),
            "top_relationship": (ctx.bivariate_report.get("key_relationships") or [{}])[0],
        }
    if name == "visualization":
        return {"charts_count": len(ctx.chart_configs), "charts": ctx.chart_configs}
    if name == "critic":
        return {
            "passed": ctx.validation_result.get("passed", True),
            "confidence_score": ctx.validation_result.get("confidence_score", 0.8),
            "issues": ctx.validation_result.get("issues", []),
        }
    return {}


def _final(ctx: AgentContext) -> dict:
    return {
        "dataset_id":   ctx.dataset_id,
        "dataset_name": ctx.dataset_name,
        "planner":      ctx.planner_output,
        "data_passport": ctx.data_passport,
        "univariate":   ctx.univariate_report,
        "bivariate":    ctx.bivariate_report,
        "charts":       ctx.chart_configs,
        "validation":   ctx.validation_result,
        "errors":       ctx.errors,
        "partial_failure": ctx.partial_failure,
        "timings":      ctx.timings,
    }

"""
Pipeline types and helpers extracted from PipelineOrchestrator.

Contains:
- PipelineAgent protocol
- PipelineContext dataclass
- AGENT_TIMEOUTS / AGENT_LABELS / PIPELINE_CONFIG
- _sse() and _run_agent() helpers

These are shared between orchestrator implementations and external
pipeline runners (e.g. Celery workers).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


def _sse(type_: str, **kwargs) -> str:
    return f"data: {json.dumps({'type': type_, **kwargs})}\n\n"


@runtime_checkable
class PipelineAgent(Protocol):
    """Protocol for agents that can run within the pipeline orchestrator."""

    async def run_pipeline(self, ctx: PipelineContext) -> PipelineContext: ...


@dataclass
class PipelineContext:
    """Blackboard shared across all agents in a pipeline run."""

    dataset_id: str
    user_id: str
    df: Any = None
    domain_signal: str = "general"
    domain_confidence: float = 0.5
    source_type: str = "file"

    profile: Any = None
    specs: list[Any] = field(default_factory=list)
    compute_results: list[Any] = field(default_factory=list)
    cards: list[Any] = field(default_factory=list)
    kpi_results: list[Any] = field(default_factory=list)
    charts: list[dict] = field(default_factory=list)
    intelligent_kpis: list[Any] = field(default_factory=list)

    errors: list[str] = field(default_factory=list)
    partial_failure: bool = False
    timings: dict[str, float] = field(default_factory=dict)


AGENT_TIMEOUTS = {
    "profile": 30.0,
    "kpi": 45.0,
    "chart": 45.0,
    "table": 30.0,
    "narrative": 30.0,
}

AGENT_LABELS = {
    "profile": "Profiling data…",
    "kpi": "Computing KPIs…",
    "chart": "Generating charts…",
    "table": "Building tables…",
    "narrative": "Writing narrative…",
}

PIPELINE_CONFIG: dict[str, dict[str, Any]] = {
    "profile": {
        "agents": ["profile"],
        "depends_on": {},
    },
    "kpi": {
        "agents": ["profile", "kpi"],
        "depends_on": {"kpi": ["profile"]},
    },
    "chart": {
        "agents": ["profile", "chart"],
        "depends_on": {"chart": ["profile"]},
    },
    "full": {
        "agents": ["profile", "kpi", "chart"],
        "depends_on": {
            "kpi": ["profile"],
            "chart": ["profile"],
        },
    },
}


async def _run_agent(
    name: str,
    fn: Any,
    ctx: PipelineContext,
    timeout: float = 45.0,
) -> tuple[PipelineContext, str | None]:
    """Run one agent with a timeout. Returns (updated_ctx, error_msg | None)."""
    t0 = time.monotonic()
    try:
        result = await asyncio.wait_for(fn(ctx), timeout=timeout)
        if isinstance(result, PipelineContext):
            ctx = result
        ctx.timings[name] = time.monotonic() - t0
        return ctx, None
    except TimeoutError:
        logger.error(f"[{name}] timed out after {timeout:.0f}s")
        ctx.errors.append(f"{name}: Timed out after {timeout:.0f}s")
        ctx.partial_failure = True
        return ctx, f"Timed out after {timeout:.0f}s"
    except Exception as e:
        logger.error(f"[{name}] failed: {e}", exc_info=True)
        ctx.errors.append(f"{name}: {e}")
        ctx.partial_failure = True
        return ctx, str(e)

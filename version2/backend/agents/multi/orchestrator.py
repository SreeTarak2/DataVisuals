"""
PipelineOrchestrator — event-driven pipeline manager.

Routes queries to the appropriate agents, manages state, and assembles
multi-modal responses. Pattern from services/agents/eda/orchestrator.py.

Uses PipelineContext, PIPELINE_CONFIG, and helpers from agents.multi.pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from agents.multi.pipeline import (
    AGENT_LABELS,
    AGENT_TIMEOUTS,
    PIPELINE_CONFIG,
    PipelineAgent,
    PipelineContext,
    _run_agent,
    _sse,
)

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Event-driven pipeline manager for multi-agent execution.

    Manages agent lifecycle, dependency resolution, and result assembly.
    Supports both PipelineAgent (run_pipeline) and BaseAgent (run) protocols.
    Backward compatible with the Celery pipeline — same stage API.
    """

    def __init__(self) -> None:
        self.agents: dict[str, Any] = {}

    def register_agent(self, name: str, agent: Any) -> None:
        self.agents[name] = agent
        logger.debug(f"PipelineOrchestrator registered agent: {name}")

    async def run(
        self,
        pipeline_type: str,
        context: PipelineContext,
    ) -> dict[str, Any]:
        """
        Run a named pipeline, returning a result dict.
        """
        config = PIPELINE_CONFIG.get(pipeline_type, PIPELINE_CONFIG["profile"])
        agents = config["agents"]
        depends_on = config.get("depends_on", {})
        completed: set[str] = set()

        for agent_name in agents:
            agent = self.agents.get(agent_name)
            if agent is None:
                logger.warning(
                    f"PipelineOrchestrator: agent '{agent_name}' not registered, skipping"
                )
                continue

            deps = depends_on.get(agent_name, [])
            if not all(d in completed for d in deps):
                logger.debug(f"[Orchestrator] Skipping {agent_name} — deps {deps} not met")
                continue

            timeout = AGENT_TIMEOUTS.get(agent_name, 45.0)
            logger.info(f"[PipelineOrchestrator] Starting agent: {agent_name}")

            ctx, err = await _run_agent(
                agent_name,
                lambda c=context: self._run_agent_fn(agent, c),
                context,
                timeout,
            )

            if err:
                logger.warning(f"[PipelineOrchestrator] Agent {agent_name} failed: {err}")
            else:
                completed.add(agent_name)
                timing = ctx.timings.get(agent_name, 0)
                logger.info(f"[PipelineOrchestrator] Agent {agent_name} completed in {timing:.1f}s")

        return {
            "profile": context.profile,
            "specs": context.specs,
            "compute_results": context.compute_results,
            "cards": context.cards,
            "kpi_results": context.kpi_results,
            "charts": context.charts,
            "intelligent_kpis": context.intelligent_kpis,
            "errors": context.errors,
            "partial_failure": context.partial_failure,
            "timings": context.timings,
        }

    async def run_streaming(
        self,
        pipeline_type: str,
        context: PipelineContext,
    ) -> AsyncGenerator[str, None]:
        """Yields SSE strings for the pipeline run."""
        config = PIPELINE_CONFIG.get(pipeline_type, PIPELINE_CONFIG["profile"])
        agents = config["agents"]
        depends_on = config.get("depends_on", {})
        completed: set[str] = set()

        for agent_name in agents:
            yield _sse(
                "agent_start",
                agent=agent_name,
                label=AGENT_LABELS.get(agent_name, f"Running {agent_name}…"),
            )

            agent = self.agents.get(agent_name)
            if agent is None:
                yield _sse(
                    "agent_error", agent=agent_name, error=f"Agent '{agent_name}' not registered"
                )
                continue

            deps = depends_on.get(agent_name, [])
            if not all(d in completed for d in deps):
                logger.debug(f"[Orchestrator] Skipping {agent_name} — deps {deps} not met")
                continue

            timeout = AGENT_TIMEOUTS.get(agent_name, 45.0)
            ctx, err = await _run_agent(
                agent_name, lambda c=context: self._run_agent_fn(agent, c), context, timeout
            )

            if err:
                yield _sse("agent_error", agent=agent_name, error=err)
            else:
                completed.add(agent_name)
                yield _sse(
                    "agent_done",
                    agent=agent_name,
                    data={"agent": agent_name, "timing_s": context.timings.get(agent_name, 0)},
                )

        yield _sse(
            "pipeline_done",
            data={
                "profile": context.profile,
                "specs": context.specs,
                "compute_results": context.compute_results,
                "cards": context.cards,
                "errors": context.errors,
                "partial_failure": context.partial_failure,
                "timings": context.timings,
            },
        )

    async def _run_agent_fn(self, agent: Any, ctx: PipelineContext) -> PipelineContext:
        """Adapter: run an agent against the context and update ctx in place."""
        if isinstance(agent, PipelineAgent):
            return await agent.run_pipeline(ctx)
        elif hasattr(agent, "run"):
            if ctx.df is not None:
                result = await agent.run(
                    query="pipeline run", dataset_id=ctx.dataset_id, user_id=ctx.user_id, df=ctx.df
                )
            else:
                result = await agent.run(
                    query="pipeline run", dataset_id=ctx.dataset_id, user_id=ctx.user_id
                )
            if hasattr(agent, "__class__") and agent.__class__.__name__ == "ProfileAgent":
                ctx.profile = result.get("profile")
                ctx.specs = result.get("specs", [])
            return ctx
        else:
            logger.warning(f"Agent {agent} has no run_pipeline/run method")
            return ctx

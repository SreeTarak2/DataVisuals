"""
Per-agent-type async concurrency limiter.

Prevents N concurrent runs of the same agent class, protecting
memory, DB connections, and LLM provider rate limits.

Usage:
    from agents.resilience.concurrency import agent_concurrency_limiter

    async with agent_concurrency_limiter.acquire("AnalystAgent"):
        await agent.run(...)

    # or check without blocking:
    if agent_concurrency_limiter.try_acquire("AnalystAgent"):
        try:
            await agent.run(...)
        finally:
            agent_concurrency_limiter.release("AnalystAgent")
"""

import asyncio
import logging

from core.config import settings

logger = logging.getLogger(__name__)

# Max concurrent runs per agent type (env-configurable via AGENT_CONCURRENCY_MAX)
# Individual agent types can still override via AGENT_MAX_CONCURRENCY dict.
DEFAULT_MAX_CONCURRENCY = max(settings.AGENT_CONCURRENCY_MAX, 0)

AGENT_MAX_CONCURRENCY: dict[str, int] = {
    "ChatAgent": DEFAULT_MAX_CONCURRENCY,
    "AnalystAgent": DEFAULT_MAX_CONCURRENCY,
    "ProfileAgent": max(DEFAULT_MAX_CONCURRENCY, 5),
    "KPICAgent": DEFAULT_MAX_CONCURRENCY,
    "ChartAgent": DEFAULT_MAX_CONCURRENCY,
    "PipelineAgent:profile": max(DEFAULT_MAX_CONCURRENCY, 5),
    "PipelineAgent:kpi": DEFAULT_MAX_CONCURRENCY,
    "PipelineAgent:chart": DEFAULT_MAX_CONCURRENCY,
}


class AgentConcurrencyLimiter:
    """Per-agent-type semaphore-based concurrency limiter."""

    def __init__(self) -> None:
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def _get_semaphore(self, agent_type: str) -> asyncio.Semaphore:
        if agent_type not in self._semaphores:
            max_conc = AGENT_MAX_CONCURRENCY.get(agent_type, DEFAULT_MAX_CONCURRENCY)
            self._semaphores[agent_type] = asyncio.Semaphore(max_conc)
            logger.debug("[Concurrency] Created semaphore for %s (max=%d)", agent_type, max_conc)
        return self._semaphores[agent_type]

    async def acquire(self, agent_type: str) -> "AgentConcurrencyLimiter._AcquireCtx":
        """Context manager: await to acquire, auto-release on exit."""
        sem = self._get_semaphore(agent_type)
        logger.debug("[Concurrency] Waiting for %s slot...", agent_type)
        await sem.acquire()
        logger.debug("[Concurrency] Acquired %s slot (%d remaining)", agent_type, sem._value)
        return self._AcquireCtx(self, agent_type)

    async def try_acquire(self, agent_type: str) -> bool:
        """Non-blocking acquire. Returns True if slot acquired."""
        sem = self._get_semaphore(agent_type)
        if sem.locked():
            return False
        await sem.acquire()
        logger.debug("[Concurrency] Try-acquired %s slot", agent_type)
        return True

    def release(self, agent_type: str) -> None:
        """Release a previously acquired slot."""
        sem = self._get_semaphore(agent_type)
        sem.release()
        logger.debug("[Concurrency] Released %s slot (%d remaining)", agent_type, sem._value)

    class _AcquireCtx:
        def __init__(self, limiter: "AgentConcurrencyLimiter", agent_type: str):
            self._limiter = limiter
            self._agent_type = agent_type

        async def __aenter__(self) -> str:
            return self._agent_type

        async def __aexit__(
            self,
            exc_type: object,
            exc_val: object,
            exc_tb: object,
        ) -> None:
            self._limiter.release(self._agent_type)


agent_concurrency_limiter = AgentConcurrencyLimiter()

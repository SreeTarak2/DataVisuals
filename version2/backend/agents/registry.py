"""
AgentRegistry — public API for agent orchestration.

Single entry point for all agent execution. External code (API routes,
workers, tests) imports from here instead of directly importing agent
classes. This decouples consumers from agent implementation details.

Usage:
    from agents import AgentRegistry

    # Register at startup
    AgentRegistry.register("chat", ChatAgent)
    AgentRegistry.register("pipeline:kpi", KPICAgent)
    AgentRegistry.register_fn("eda", run_eda_pipeline)

    # Execute
    result = await AgentRegistry.run("chat", query=..., dataset_id=..., ...)
    async for event in AgentRegistry.run_streaming("eda", dataset_id=..., ...):
        ...
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any, Callable

from agents.base_agent import BaseAgent
from agents.multi.registry import MultiAgentToolRegistry

logger = logging.getLogger(__name__)


class _AgentWrapper:
    """Internal wrapper — normalises class-based and function-based agents."""

    def __init__(
        self,
        agent_cls: type[BaseAgent] | None = None,
        agent_fn: Callable | None = None,
    ) -> None:
        self.agent_cls = agent_cls
        self.agent_fn = agent_fn

    @property
    def needs_tools(self) -> bool:
        return self.agent_cls is not None

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        if self.agent_fn is not None:
            result = await self.agent_fn(**kwargs)
            return result if isinstance(result, dict) else {"response": result}
        if self.agent_cls is not None:
            tools = self._resolve_tools()
            agent = self.agent_cls(tools=tools)
            return await agent.run(**kwargs)
        raise ValueError("No agent class or function registered")

    async def run_streaming(self, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
        if self.agent_fn is not None:
            async for event in self.agent_fn(**kwargs):
                yield event
            return
        if self.agent_cls is not None:
            tools = self._resolve_tools()
            agent = self.agent_cls(tools=tools)
            if hasattr(agent, "run_streaming"):
                async for event in agent.run_streaming(**kwargs):
                    yield event
                return
            # Fallback: non-streaming agent, wrap result
            result = await agent.run(**kwargs)
            yield {"type": "response_complete", "full_response": result.get("response", "")}
            return
        raise ValueError("No agent class or function registered")

    def _resolve_tools(self) -> dict[str, Any]:
        """Auto-resolve tools from MultiAgentToolRegistry for BaseAgent subclasses."""
        if self.agent_cls is None or not issubclass(self.agent_cls, BaseAgent):
            return {}
        try:
            tool_names = self.agent_cls._select_tools()  # type: ignore[attr-defined]
            return MultiAgentToolRegistry.get_tools(tool_names)
        except AttributeError:
            # Agent doesn't declare _select_tools — use no tools
            return {}
        except KeyError as e:
            logger.error(
                "Tool resolution failed for %s — missing tool: %s. "
                "Check that MultiAgentToolRegistry.initialize_defaults() was called at startup.",
                self.agent_cls.__name__,
                e,
            )
            raise


class AgentRegistry:
    """
    Registry of all available agents.

    Agents can be BaseAgent subclasses (auto tool resolution) or plain
    async callables (e.g. LangGraph pipelines, EDA orchestrators).
    """

    _agents: dict[str, _AgentWrapper] = {}

    @classmethod
    def register(cls, name: str, agent_cls: type[BaseAgent]) -> None:
        """
        Register a BaseAgent subclass.

        Tools are auto-resolved from MultiAgentToolRegistry at call time
        using the agent's _select_tools() method.
        """
        cls._agents[name] = _AgentWrapper(agent_cls=agent_cls)
        logger.debug(f"AgentRegistry: registered class '{name}' → {agent_cls.__name__}")

    @classmethod
    def register_fn(cls, name: str, agent_fn: Callable) -> None:
        """
        Register an async function/callable as an agent.

        Use for agents that don't follow the BaseAgent pattern
        (e.g. LangGraph graphs, EDA pipelines, custom runners).
        """
        cls._agents[name] = _AgentWrapper(agent_fn=agent_fn)
        logger.debug(f"AgentRegistry: registered function '{name}' → {agent_fn.__name__}")

    @classmethod
    def available(cls) -> list[str]:
        """List all registered agent names."""
        return list(cls._agents.keys())

    @classmethod
    async def run(cls, name: str, **kwargs: Any) -> dict[str, Any]:
        """
        Run an agent by name.

        Args:
            name: Registered agent name (e.g. "chat", "analyst", "pipeline:kpi")
            **kwargs: Forwarded to the agent's run() method.

        Returns:
            Agent result dict.
        """
        wrapper = cls._agents.get(name)
        if wrapper is None:
            raise KeyError(
                f"Unknown agent '{name}'. Available: {cls.available()}"
            )
        return await wrapper.run(**kwargs)

    @classmethod
    async def run_streaming(
        cls, name: str, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Run an agent in streaming mode.

        Yields dict events (tokens, thinking steps, errors, done).
        """
        wrapper = cls._agents.get(name)
        if wrapper is None:
            yield {"type": "error", "content": f"Unknown agent '{name}'"}
            return
        async for event in wrapper.run_streaming(**kwargs):
            yield event

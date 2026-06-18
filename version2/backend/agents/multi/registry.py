"""
Multi-agent Tool Registry — central dependency injection container.

Agents declare which tools they need; the registry resolves and provides them.
This replaces hardcoded singletons on service classes with explicit wiring.

NOTE: This is the internal registry for the multi-agent pipeline system.
The public API entry point is agents.registry.AgentRegistry.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MultiAgentToolRegistry:
    """
    Global registry for all tools (services, wrappers, callables).

    Usage:
        MultiAgentToolRegistry.register("sql", sql_tool_callable)
        MultiAgentToolRegistry.register("profiler", data_profiler)
        tools = MultiAgentToolRegistry.get_tools(["sql", "profiler"])
        agent = ProfileAgent(tools)
    """

    _tools: dict[str, Any] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, name: str, tool: Any) -> None:
        cls._tools[name] = tool
        logger.debug(f"MultiAgentToolRegistry registered: {name}")

    @classmethod
    def get(cls, name: str) -> Any | None:
        return cls._tools.get(name)

    @classmethod
    def available(cls) -> list[str]:
        return list(cls._tools.keys())

    @classmethod
    def get_tools(cls, names: list[str]) -> dict[str, Any]:
        """Return a dict of requested tools, raising KeyError if any are missing."""
        result = {}
        for name in names:
            tool = cls.get(name)
            if tool is None:
                raise KeyError(
                    f"Tool '{name}' not registered. Available: {cls.available()}"
                )
            result[name] = tool
        return result

    @classmethod
    def initialize_defaults(cls) -> None:
        """
        Register all existing singleton services as tools.

        Call once at application startup. Safe to call multiple times.
        """
        if cls._initialized:
            return

        from services.agents.belief_store import get_belief_store
        from services.analysis.advanced_stats import (
            anomaly_detector,
            correlation_analyzer,
            effect_size_calculator,
            hypothesis_tester,
        )
        from services.datasets.faiss_vector_service import faiss_vector_service
        from services.pipeline.classifier import classify
        from services.pipeline.profiler import profile_dataframe
        from services.query.executor import query_executor

        cls.register("sql", query_executor)
        cls.register("hypothesis_tester", hypothesis_tester)
        cls.register("correlation_analyzer", correlation_analyzer)
        cls.register("anomaly_detector", anomaly_detector)
        cls.register("effect_size_calculator", effect_size_calculator)
        cls.register("rag", faiss_vector_service)
        cls.register("memory", get_belief_store())
        cls.register("profiler", profile_dataframe)
        cls.register("classifier", classify)

        cls._initialized = True
        logger.info(f"MultiAgentToolRegistry initialized with {len(cls._tools)} tools")

    @classmethod
    def reset(cls) -> None:
        """Clear all registrations. Use only in tests."""
        cls._tools.clear()
        cls._initialized = False

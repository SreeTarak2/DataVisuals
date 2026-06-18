"""
agents — Public API for all agent orchestration.

External code (API routes, workers, tests) imports only from this package.
Sub-packages like agents.multi are implementation details.
"""

from agents.base_agent import BaseAgent, AgentContext, ToolResult
from agents.registry import AgentRegistry

__all__ = [
    "BaseAgent",
    "AgentContext",
    "ToolResult",
    "AgentRegistry",
]

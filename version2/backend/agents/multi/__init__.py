"""
agents.multi — Internal multi-agent pipeline system.

This is an implementation detail. External code imports from agents.registry.
"""

from agents.multi.orchestrator import PipelineOrchestrator
from agents.multi.pipeline import PipelineContext, PipelineAgent
from agents.multi.registry import MultiAgentToolRegistry

__all__ = [
    "PipelineOrchestrator",
    "PipelineContext",
    "PipelineAgent",
    "MultiAgentToolRegistry",
]

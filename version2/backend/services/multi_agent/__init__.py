# TODO: REMOVE after Phase 9 — re-export shim
from agents.multi import (  # type: ignore[import-unused]
    PipelineOrchestrator, PipelineContext, PipelineAgent,
    MultiAgentToolRegistry,
)
from agents.multi.analyst_agent import AnalystAgent
from agents.multi.chart_agent import ChartAgent
from agents.multi.kpi_agent import KPICAgent
from agents.multi.profile_agent import ProfileAgent
__all__ = [
    "PipelineOrchestrator", "PipelineContext", "PipelineAgent",
    "MultiAgentToolRegistry", "AnalystAgent", "ChartAgent",
    "KPICAgent", "ProfileAgent",
]

"""
Per-agent-run token budget enforcement.

Complementary to the existing LLM cost tracker (llm/cost_tracker.py) which
handles per-user per-day budgets. This handles per-AGENT-RUN budgets —
preventing a single greedy agent run from burning through the whole day's
budget in one shot.

Usage:
    from agents.resilience.token_budget import get_run_budget, return_run_budget

    budget = get_run_budget("AnalystAgent")
    if budget.can_proceed(estimated_tokens=500):
        ...
        budget.deduct(actual_tokens=450, actual_cost=0.02)
    return_run_budget("AnalystAgent")
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RunBudget:
    max_tokens: int
    max_cost_cents: float
    tokens_used: int = 0
    cost_cents: float = 0.0

    def can_proceed(self, estimated_tokens: int = 0) -> bool:
        return (self.tokens_used + estimated_tokens) <= self.max_tokens

    def deduct(self, tokens: int, cost_cents: float = 0.0) -> None:
        self.tokens_used += tokens
        self.cost_cents += cost_cents

    @property
    def exhausted(self) -> bool:
        return self.tokens_used >= self.max_tokens or self.cost_cents >= self.max_cost_cents

    @property
    def pct_used(self) -> float:
        token_pct = (self.tokens_used / self.max_tokens * 100) if self.max_tokens else 0
        cost_pct = (self.cost_cents / self.max_cost_cents * 100) if self.max_cost_cents else 0
        return max(token_pct, cost_pct)


# Per-agent-class run limits (complementary to existing daily user budgets)
# ProfileAgent uses no LLM calls so it gets zero budget.
AGENT_RUN_LIMITS: dict[str, tuple[int, float]] = {
    "ChatAgent": (4_000, 3.0),
    "AnalystAgent": (8_000, 5.0),
    "ProfileAgent": (0, 0.0),
    "KPICAgent": (2_000, 2.0),
    "ChartAgent": (2_000, 2.0),
    # Pipeline-resilience-wrapped agent keys
    "PipelineAgent:profile": (1_000, 1.0),
    "PipelineAgent:kpi": (2_000, 2.0),
    "PipelineAgent:chart": (1_000, 1.0),
}

_run_budgets: dict[str, RunBudget] = {}


def get_run_budget(agent_class_name: str) -> RunBudget:
    max_tokens, max_cost = AGENT_RUN_LIMITS.get(agent_class_name, (2_000, 2.0))
    budget = RunBudget(max_tokens=max_tokens, max_cost_cents=max_cost)
    logger.debug(
        "[Budget] Created run budget for %s: max_tokens=%d, max_cost=%.2fc",
        agent_class_name,
        max_tokens,
        max_cost,
    )
    return budget


def return_run_budget(agent_class_name: str) -> None:
    _run_budgets.pop(agent_class_name, None)

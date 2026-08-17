import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest


class TestRunBudget:
    def test_can_proceed_within_limit(self):
        from agents.resilience.token_budget import RunBudget

        budget = RunBudget(max_tokens=1000, max_cost_cents=5.0)
        assert budget.can_proceed(estimated_tokens=500) is True

    def test_cannot_proceed_exceeds_limit(self):
        from agents.resilience.token_budget import RunBudget

        budget = RunBudget(max_tokens=1000, max_cost_cents=5.0)
        assert budget.can_proceed(estimated_tokens=1500) is False

    def test_deduct_tokens(self):
        from agents.resilience.token_budget import RunBudget

        budget = RunBudget(max_tokens=1000, max_cost_cents=5.0)
        budget.deduct(tokens=300, cost_cents=1.5)
        assert budget.tokens_used == 300
        assert budget.cost_cents == 1.5

    def test_exhausted_by_tokens(self):
        from agents.resilience.token_budget import RunBudget

        budget = RunBudget(max_tokens=1000, max_cost_cents=5.0)
        budget.deduct(tokens=1000)
        assert budget.exhausted is True

    def test_exhausted_by_cost(self):
        from agents.resilience.token_budget import RunBudget

        budget = RunBudget(max_tokens=1000, max_cost_cents=5.0)
        budget.deduct(tokens=0, cost_cents=5.0)
        assert budget.exhausted is True

    def test_not_exhausted_when_below_limits(self):
        from agents.resilience.token_budget import RunBudget

        budget = RunBudget(max_tokens=1000, max_cost_cents=5.0)
        budget.deduct(tokens=100, cost_cents=0.5)
        assert budget.exhausted is False

    def test_pct_used_returns_max_percentage(self):
        from agents.resilience.token_budget import RunBudget

        budget = RunBudget(max_tokens=1000, max_cost_cents=5.0)
        budget.deduct(tokens=500, cost_cents=1.0)
        pct = budget.pct_used
        assert pct == 50.0

    def test_pct_used_zero_when_no_usage(self):
        from agents.resilience.token_budget import RunBudget

        budget = RunBudget(max_tokens=1000, max_cost_cents=5.0)
        assert budget.pct_used == 0.0


class TestTokenBudgetLifecycle:
    def test_get_run_budget_creates_new(self):
        from agents.resilience.token_budget import get_run_budget, _run_budgets

        _run_budgets.clear()
        budget = get_run_budget("AnalystAgent")
        assert budget.max_tokens == 8000
        assert budget.max_cost_cents == 5.0

    def test_get_run_budget_returns_fresh_instance(self):
        from agents.resilience.token_budget import get_run_budget, _run_budgets

        _run_budgets.clear()
        b1 = get_run_budget("ChatAgent")
        b2 = get_run_budget("ChatAgent")
        assert b1 is not b2  # P1-8: each call returns a new instance
        assert b1.max_tokens == b2.max_tokens

    def test_get_run_budget_uses_default_for_unknown(self):
        from agents.resilience.token_budget import get_run_budget, _run_budgets

        _run_budgets.clear()
        budget = get_run_budget("UnknownAgent")
        assert budget.max_tokens == 2000
        assert budget.max_cost_cents == 2.0

    def test_return_run_budget_does_not_crash(self):
        from agents.resilience.token_budget import return_run_budget

        return_run_budget("ChatAgent")  # no-op after P1-8, should not raise

    def test_profile_agent_has_zero_budget(self):
        from agents.resilience.token_budget import AGENT_RUN_LIMITS

        assert AGENT_RUN_LIMITS["ProfileAgent"] == (0, 0.0)

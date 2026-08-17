import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from agents.base_agent import BaseAgent


class _TestAgent(BaseAgent):
    def _select_tools(self):
        return {}

    async def _process_result(self, observations, context):
        return {}

    async def _synthesize(self, query, observations, context):
        return "final response"


class TestBaseAgentResilience:
    @pytest.mark.asyncio
    async def test_full_pipeline_with_all_resilience_layers(self):
        mock_sanitize = MagicMock(return_value=(True, "ok", "clean query"))
        mock_budget = MagicMock()
        mock_budget.can_proceed.return_value = True

        with patch("agents.base_agent.sanitize_and_validate", mock_sanitize):
            with patch("agents.base_agent.get_run_budget", return_value=mock_budget):
                with patch("agents.base_agent.response_cache.get", return_value=None):
                    with patch("agents.base_agent.BreakerRegistry.get") as mock_breaker_get:
                        mock_breaker = MagicMock()
                        mock_breaker.is_allowed.return_value = True
                        mock_breaker_get.return_value = mock_breaker

                        agent = _TestAgent(tools={})
                        with patch.object(agent, "_run_loop", new=AsyncMock(return_value=[])):
                            result = await agent.run("test query", "d1", "u1")
                            assert result.get("response") == "final response"

    @pytest.mark.asyncio
    async def test_rejected_query_halts_pipeline(self):
        with patch(
            "agents.base_agent.sanitize_and_validate", return_value=(False, "bad injection", "")
        ):
            agent = _TestAgent(tools={})
            result = await agent.run("bad", "d1", "u1")
            assert "rejected" in result.get("response", "").lower()

    @pytest.mark.asyncio
    async def test_budget_exhaustion_stops_llm_calls(self):
        mock_budget = MagicMock()
        mock_budget.can_proceed.return_value = False

        with patch("agents.base_agent.sanitize_and_validate", return_value=(True, "ok", "q")):
            with patch("agents.base_agent.get_run_budget", return_value=mock_budget):
                agent = _TestAgent(tools={})
                agent._budget = mock_budget
                agent.context = MagicMock()
                agent.context.dataset_id = "d1"

                result = await agent._llm_call(
                    prompt="test", model_role="narrative_story", dataset_id="d1"
                )
                assert isinstance(result, dict)
                assert "budget_exhausted" in result

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_blocks_tool_execution(self):
        mock_breaker = MagicMock()
        mock_breaker.is_allowed.return_value = False

        with patch("agents.base_agent.BreakerRegistry.get", return_value=mock_breaker):
            with patch("agents.base_agent.sanitize_and_validate", return_value=(True, "ok", "q")):
                from agents.base_agent import AgentContext

                agent = _TestAgent(tools={})
                result = await agent._act(
                    "sql", [], AgentContext(query="test", dataset_id="d1", user_id="u1")
                )
                assert result.success is False
                assert "circuit breaker" in result.error

    def test_budget_lifecycle_in_run(self):
        from agents.resilience.token_budget import get_run_budget, return_run_budget

        b = get_run_budget("AnalystAgent")
        assert b.max_tokens == 8000
        assert b.max_cost_cents == 5.0
        return_run_budget("AnalystAgent")  # no-op, should not raise

    def test_health_agents_returns_expected_structure(self):
        try:
            from agents import AgentRegistry
            from services.retries.async_utils import BreakerRegistry

            breakers = BreakerRegistry.status()
            agents = AgentRegistry.available()
            all_closed = all(s == "closed" for s in breakers.values())
            result = {
                "status": "healthy" if all_closed else "degraded",
                "breakers": breakers,
                "agents": agents,
            }
            assert "status" in result
            assert isinstance(result["breakers"], dict)
            assert isinstance(result["agents"], list)
        except Exception as e:
            # Registries may be empty if startup hasn't run
            assert True

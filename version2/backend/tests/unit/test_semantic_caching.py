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
        return "test"


class TestSemanticCachingIntegration:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_result(self):
        cached_result = {"response": "cached narrative"}
        with patch("agents.base_agent.response_cache.get", return_value=cached_result):
            agent = _TestAgent(tools={})
            agent._budget = MagicMock()
            agent._budget.can_proceed.return_value = True
            agent.context = MagicMock()
            agent.context.dataset_id = "d1"

            result = await agent._llm_call(
                prompt="test query",
                model_role="narrative_story",
                dataset_id="d1",
            )
            assert result == "cached narrative"

    @pytest.mark.asyncio
    async def test_cache_miss_calls_llm_and_stores(self):
        with patch("agents.base_agent.response_cache.get", return_value=None):
            with patch("agents.base_agent.response_cache.set") as mock_set:
                with patch("llm.router.llm_router") as mock_router:
                    mock_router.call = AsyncMock(return_value={"response": "llm response"})

                    agent = _TestAgent(tools={})
                    agent._budget = MagicMock()
                    agent._budget.can_proceed.return_value = True
                    agent.context = MagicMock()
                    agent.context.dataset_id = "d1"

                    result = await agent._llm_call(
                        prompt="test",
                        model_role="narrative_story",
                        dataset_id="d1",
                    )
                    assert result is not None
                    assert mock_router.call.called

    @pytest.mark.asyncio
    async def test_cache_skipped_for_non_cacheable_roles(self):
        with patch("agents.base_agent.response_cache.get") as mock_get:
            with patch("llm.router.llm_router") as mock_router:
                mock_router.call = AsyncMock(return_value={"response": "sql result"})

                agent = _TestAgent(tools={})
                agent._budget = MagicMock()
                agent._budget.can_proceed.return_value = True
                agent.context = MagicMock()
                agent.context.dataset_id = "d1"

                result = await agent._llm_call(
                    prompt="test",
                    model_role="sql_generation",
                    dataset_id="d1",
                )
                mock_get.assert_not_called()
                assert mock_router.call.called

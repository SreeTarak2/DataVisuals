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
        return "test response"


class TestInjectionGuardIntegration:
    @pytest.mark.asyncio
    async def test_run_rejects_invalid_query(self):
        with patch(
            "agents.base_agent.sanitize_and_validate",
            return_value=(False, "injection detected", ""),
        ):
            agent = _TestAgent(tools={})
            result = await agent.run("DROP TABLE users;", "d1", "u1")
            assert "rejected" in result.get("response", "").lower()

    @pytest.mark.asyncio
    async def test_run_allows_valid_query(self):
        with patch(
            "agents.base_agent.sanitize_and_validate", return_value=(True, "ok", "clean query")
        ):
            agent = _TestAgent(tools={})
            with patch.object(agent, "_run_loop", new=AsyncMock(return_value=[])):
                result = await agent.run("valid query", "d1", "u1")
                assert result.get("response") == "test response"

    @pytest.mark.asyncio
    async def test_run_streaming_rejects_injection(self):
        with patch(
            "agents.base_agent.sanitize_and_validate", return_value=(False, "bad query", "")
        ):
            agent = _TestAgent(tools={})
            events = []
            async for event in agent.run_streaming("malicious", "d1", "u1"):
                events.append(event)
            assert events == [{"type": "error", "content": "Query rejected: bad query"}]

    @pytest.mark.asyncio
    async def test_sanitize_called_with_query(self):
        mock_san = MagicMock(return_value=(True, "ok", "clean"))
        with patch("agents.base_agent.sanitize_and_validate", mock_san):
            agent = _TestAgent(tools={})
            with patch.object(agent, "_run_loop", new=AsyncMock(return_value=[])):
                await agent.run("my query", "d1", "u1")
                mock_san.assert_called_with("my query")

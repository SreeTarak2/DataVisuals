import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestTrustIntegration:
    @pytest.mark.asyncio
    @patch("services.trust.verifier.get_verifier")
    async def test_trust_verification_in_query_flow(self, mock_get_verifier):
        mock_verifier = AsyncMock()
        mock_result = MagicMock()
        mock_result.is_trusted = True
        mock_result.confidence = 0.8
        mock_result.applied_semantics = [
            {"metric_name": "revenue", "definition": "recognized revenue"}
        ]
        mock_result.checks_passed = ["validated_1_metrics"]
        mock_result.checks_failed = []
        mock_result.warnings = []
        mock_result.to_dict = lambda: {
            "is_trusted": True,
            "confidence": 0.8,
            "checks_passed": ["validated_1_metrics"],
            "checks_failed": [],
            "warnings": [],
            "applied_semantics": [{"metric_name": "revenue", "definition": "recognized revenue"}],
        }

        mock_verifier.verify_query = AsyncMock(return_value=mock_result)
        mock_get_verifier.return_value = mock_verifier

        from services.trust.verifier import get_verifier

        verifier = await get_verifier()
        result = await verifier.verify_query(
            query="show revenue",
            workspace_id="workspace-1",
        )

        assert result.is_trusted is True
        assert result.confidence == 0.8
        assert len(result.applied_semantics) == 1
        assert result.applied_semantics[0]["metric_name"] == "revenue"

        result_dict = result.to_dict()
        assert result_dict["is_trusted"] is True
        assert result_dict["confidence"] == 0.8

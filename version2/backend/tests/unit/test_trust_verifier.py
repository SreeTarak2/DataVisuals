import pytest
from unittest.mock import AsyncMock, MagicMock
from services.trust.verifier import TrustVerifier


class TestTrustVerifier:
    @pytest.fixture
    def mock_context_store(self):
        store = MagicMock()
        store.get_metric_semantics_for_workspace = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def verifier(self, mock_context_store):
        return TrustVerifier(mock_context_store)

    @pytest.mark.asyncio
    async def test_no_semantics_returns_trusted(self, verifier):
        result = await verifier.verify_query("show me the data", "workspace-1")
        assert result.is_trusted is True
        assert result.confidence < 0.6

    @pytest.mark.asyncio
    async def test_with_matching_metric(self, verifier):
        mock_semantic = MagicMock()
        mock_semantic.metric_name = "revenue"
        mock_semantic.definition = "recognized revenue"
        mock_semantic.formula = "sum(amount)"
        mock_semantic.source_columns = ["amount"]

        verifier.context_store.get_metric_semantics_for_workspace = AsyncMock(
            return_value=[mock_semantic]
        )

        result = await verifier.verify_query("show revenue", "workspace-1")
        assert len(result.applied_semantics) > 0
        assert result.confidence >= 0.6

    @pytest.mark.asyncio
    async def test_confidence_scales_with_coverage(self, verifier):
        mock_semantic = MagicMock()
        mock_semantic.metric_name = "revenue"
        mock_semantic.definition = "recognized revenue"
        mock_semantic.formula = None
        mock_semantic.source_columns = []

        verifier.context_store.get_metric_semantics_for_workspace = AsyncMock(
            return_value=[mock_semantic]
        )

        result = await verifier.verify_query("show costs", "workspace-1")
        assert result.confidence == 0.7
        assert result.is_trusted is True

    @pytest.mark.asyncio
    async def test_warning_on_column_mismatch(self, verifier):
        mock_semantic = MagicMock()
        mock_semantic.metric_name = "revenue"
        mock_semantic.definition = "sum(amount)"
        mock_semantic.formula = "sum(amount)"
        mock_semantic.source_columns = ["amount"]

        verifier.context_store.get_metric_semantics_for_workspace = AsyncMock(
            return_value=[mock_semantic]
        )

        result = await verifier.verify_query("show revenue", "workspace-1")
        assert len(result.warnings) > 0
        assert "amount" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_to_dict_serialization(self, verifier):
        result = await verifier.verify_query("test query", "workspace-1")
        d = result.to_dict()
        assert "is_trusted" in d
        assert "confidence" in d
        assert "checks_passed" in d
        assert "applied_semantics" in d

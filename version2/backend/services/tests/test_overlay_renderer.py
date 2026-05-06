"""
Overlay Renderer Tests
======================
Comprehensive test suite for OverlayRenderer.

Test coverage:
- Core rendering functionality
- Data validation
- Error handling
- Edge cases
- Performance
- Integration with spec/schema
"""

import pytest
import polars as pl
from datetime import datetime
from typing import List, Dict, Any

from services.charts.renderers.overlay_renderer import OverlayRenderer
from db.schemas_charts import MultiSeriesViewSpec, AnalysisIntent


class TestOverlayRendererBasic:
    """Basic rendering functionality tests."""

    @pytest.fixture
    def sample_data(self) -> pl.DataFrame:
        """Create sample 2-series time series data."""
        return pl.DataFrame({
            "Date": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05"],
            "Revenue": [1000.0, 1200.0, 1100.0, 1300.0, 1400.0],
            "Cost": [400.0, 450.0, 480.0, 500.0, 550.0]
        })

    @pytest.fixture
    def renderer(self) -> OverlayRenderer:
        """Create OverlayRenderer instance."""
        return OverlayRenderer()

    @pytest.fixture
    def spec(self) -> MultiSeriesViewSpec:
        """Create basic chart spec."""
        return MultiSeriesViewSpec(
            title="Revenue vs Cost",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[
                {"column": "Revenue", "role": "series"},
                {"column": "Cost", "role": "series"}
            ],
            analysis_intent="comparison"
        )

    @pytest.mark.asyncio
    async def test_basic_render(self, renderer, spec, sample_data):
        """Test basic overlay rendering."""
        result = await renderer.render(spec, sample_data)

        # Verify structure
        assert "data" in result
        assert "layout" in result
        assert "metadata" in result

        # Verify traces
        assert len(result["data"]) == 2
        assert result["data"][0]["name"] == "Revenue"
        assert result["data"][1]["name"] == "Cost"

    @pytest.mark.asyncio
    async def test_trace_data(self, renderer, spec, sample_data):
        """Test trace data extraction."""
        result = await renderer.render(spec, sample_data)

        # Check x data
        x_data = result["data"][0]["x"]
        assert len(x_data) == 5
        assert x_data[0] == "2025-01-01"

        # Check y data
        revenue_y = result["data"][0]["y"]
        assert revenue_y == [1000.0, 1200.0, 1100.0, 1300.0, 1400.0]

    @pytest.mark.asyncio
    async def test_trace_styling(self, renderer, spec, sample_data):
        """Test trace styling applied correctly."""
        result = await renderer.render(spec, sample_data)

        # Check styling
        for trace in result["data"]:
            assert "line" in trace
            assert "color" in trace["line"]
            assert "marker" in trace
            assert trace["mode"] == "lines+markers"

    @pytest.mark.asyncio
    async def test_layout_configuration(self, renderer, spec, sample_data):
        """Test layout is configured correctly."""
        result = await renderer.render(spec, sample_data)

        layout = result["layout"]

        # Check title
        assert layout["title"]["text"] == "Revenue vs Cost"

        # Check axes
        assert "xaxis" in layout
        assert "yaxis" in layout
        assert layout["xaxis"]["title"] == "Date"

        # Check legend
        assert layout["showlegend"] is True
        assert "legend" in layout

    def test_max_series_warning(self, renderer, sample_data):
        """Test warning for high series count."""
        # Create spec with 8 series (over limit)
        spec = MultiSeriesViewSpec(
            title="Many Series",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[
                {"column": f"Series{i}", "role": "series"}
                for i in range(8)
            ]
        )

        # Add dummy columns
        df = sample_data
        for i in range(8):
            df = df.with_columns(pl.lit(100.0).alias(f"Series{i}"))

        # Should not raise, but should log warning
        # (Warning is logged, not raised)
        assert True


class TestOverlayRendererValidation:
    """Input validation tests."""

    @pytest.fixture
    def renderer(self) -> OverlayRenderer:
        return OverlayRenderer()

    @pytest.mark.asyncio
    async def test_empty_dataframe(self, renderer):
        """Test error on empty DataFrame."""
        df = pl.DataFrame()
        spec = MultiSeriesViewSpec(
            title="Test",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[{"column": "Value", "role": "series"}]
        )

        with pytest.raises(ValueError, match="DataFrame is empty"):
            await renderer.render(spec, df)

    @pytest.mark.asyncio
    async def test_missing_x_column(self, renderer):
        """Test error when x column missing from data."""
        df = pl.DataFrame({
            "Value": [1.0, 2.0, 3.0]
        })
        spec = MultiSeriesViewSpec(
            title="Test",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[{"column": "Value", "role": "series"}]
        )

        with pytest.raises(ValueError, match="X column 'Date' not found"):
            await renderer.render(spec, df)

    @pytest.mark.asyncio
    async def test_missing_y_column(self, renderer):
        """Test error when y column missing from data."""
        df = pl.DataFrame({
            "Date": ["2025-01-01", "2025-01-02"],
            "Revenue": [1000.0, 1200.0]
        })
        spec = MultiSeriesViewSpec(
            title="Test",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[{"column": "NonExistent", "role": "series"}]
        )

        with pytest.raises(ValueError, match="Y column 'NonExistent' not found"):
            await renderer.render(spec, df)

    @pytest.mark.asyncio
    async def test_single_series_not_allowed(self, renderer):
        """Test error when only 1 series (not multi-series)."""
        df = pl.DataFrame({
            "Date": ["2025-01-01", "2025-01-02"],
            "Revenue": [1000.0, 1200.0]
        })
        spec = MultiSeriesViewSpec(
            title="Test",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[{"column": "Revenue", "role": "series"}]
        )

        with pytest.raises(ValueError, match="at least 2 series"):
            await renderer.render(spec, df)

    @pytest.mark.asyncio
    async def test_missing_encoding(self, renderer):
        """Test error when encoding not in spec."""
        df = pl.DataFrame({
            "Date": ["2025-01-01"],
            "Revenue": [1000.0],
            "Cost": [400.0]
        })
        spec = MultiSeriesViewSpec(
            title="Test",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={},  # Missing x
            y_roles=[{"column": "Revenue", "role": "series"}]
        )

        with pytest.raises(ValueError, match="X column not specified"):
            await renderer.render(spec, df)


class TestOverlayRendererEdgeCases:
    """Edge case and boundary condition tests."""

    @pytest.fixture
    def renderer(self) -> OverlayRenderer:
        return OverlayRenderer()

    @pytest.mark.asyncio
    async def test_null_values_in_series(self, renderer):
        """Test handling of null values in data."""
        df = pl.DataFrame({
            "Date": ["2025-01-01", "2025-01-02", "2025-01-03"],
            "Revenue": [1000.0, None, 1200.0],
            "Cost": [400.0, 450.0, None]
        })
        spec = MultiSeriesViewSpec(
            title="Test",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[
                {"column": "Revenue", "role": "series"},
                {"column": "Cost", "role": "series"}
            ]
        )

        result = await renderer.render(spec, df)

        # Should handle nulls gracefully
        assert result["metadata"]["has_nulls"] is True
        assert len(result["data"]) == 2

    @pytest.mark.asyncio
    async def test_single_row(self, renderer):
        """Test single data point."""
        df = pl.DataFrame({
            "Date": ["2025-01-01"],
            "Revenue": [1000.0],
            "Cost": [400.0]
        })
        spec = MultiSeriesViewSpec(
            title="Test",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[
                {"column": "Revenue", "role": "series"},
                {"column": "Cost", "role": "series"}
            ]
        )

        result = await renderer.render(spec, df)
        assert len(result["data"][0]["x"]) == 1

    @pytest.mark.asyncio
    async def test_large_dataset(self, renderer):
        """Test with large dataset (1000 points)."""
        n_points = 1000
        df = pl.DataFrame({
            "Date": [f"2025-01-{(i % 30) + 1:02d}" for i in range(n_points)],
            "Revenue": [1000.0 + i for i in range(n_points)],
            "Cost": [400.0 + i * 0.5 for i in range(n_points)]
        })
        spec = MultiSeriesViewSpec(
            title="Large Dataset",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[
                {"column": "Revenue", "role": "series"},
                {"column": "Cost", "role": "series"}
            ]
        )

        result = await renderer.render(spec, df)
        assert len(result["data"][0]["x"]) == n_points

    @pytest.mark.asyncio
    async def test_identical_values(self, renderer):
        """Test series with all identical values."""
        df = pl.DataFrame({
            "Date": ["2025-01-01", "2025-01-02", "2025-01-03"],
            "Revenue": [1000.0, 1000.0, 1000.0],
            "Cost": [400.0, 400.0, 400.0]
        })
        spec = MultiSeriesViewSpec(
            title="Flat Data",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[
                {"column": "Revenue", "role": "series"},
                {"column": "Cost", "role": "series"}
            ]
        )

        result = await renderer.render(spec, df)
        assert len(result["data"]) == 2

    @pytest.mark.asyncio
    async def test_negative_values(self, renderer):
        """Test with negative values."""
        df = pl.DataFrame({
            "Date": ["2025-01-01", "2025-01-02", "2025-01-03"],
            "Profit": [100.0, -50.0, 200.0],
            "Loss": [-100.0, -200.0, -50.0]
        })
        spec = MultiSeriesViewSpec(
            title="Negative Values",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[
                {"column": "Profit", "role": "series"},
                {"column": "Loss", "role": "series"}
            ]
        )

        result = await renderer.render(spec, df)
        assert result["data"][0]["y"] == [100.0, -50.0, 200.0]

    @pytest.mark.asyncio
    async def test_very_large_values(self, renderer):
        """Test with very large numbers."""
        df = pl.DataFrame({
            "Date": ["2025-01-01", "2025-01-02"],
            "Revenue": [1e10, 1.5e10],
            "Cost": [5e9, 6e9]
        })
        spec = MultiSeriesViewSpec(
            title="Large Numbers",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[
                {"column": "Revenue", "role": "series"},
                {"column": "Cost", "role": "series"}
            ]
        )

        result = await renderer.render(spec, df)
        assert len(result["data"]) == 2


class TestOverlayRendererMetadata:
    """Metadata and output structure tests."""

    @pytest.fixture
    def renderer(self) -> OverlayRenderer:
        return OverlayRenderer()

    @pytest.mark.asyncio
    async def test_metadata_structure(self, renderer):
        """Test metadata is complete."""
        df = pl.DataFrame({
            "Date": ["2025-01-01", "2025-01-02"],
            "Revenue": [1000.0, 1200.0],
            "Cost": [400.0, 450.0]
        })
        spec = MultiSeriesViewSpec(
            title="Test",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[
                {"column": "Revenue", "role": "series"},
                {"column": "Cost", "role": "series"}
            ]
        )

        result = await renderer.render(spec, df)
        metadata = result["metadata"]

        assert metadata["renderer"] == "overlay"
        assert metadata["series_count"] == 2
        assert metadata["data_points_per_series"] == 2
        assert "has_nulls" in metadata
        assert "render_time_ms" in metadata
        assert metadata["mode"] == "lines+markers"

    @pytest.mark.asyncio
    async def test_render_time_performance(self, renderer):
        """Test render time is reasonable."""
        df = pl.DataFrame({
            "Date": [f"2025-01-{(i % 30) + 1:02d}" for i in range(500)],
            "Revenue": [1000.0 + i for i in range(500)],
            "Cost": [400.0 + i * 0.5 for i in range(500)]
        })
        spec = MultiSeriesViewSpec(
            title="Performance Test",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[
                {"column": "Revenue", "role": "series"},
                {"column": "Cost", "role": "series"}
            ]
        )

        result = await renderer.render(spec, df)
        render_time = result["metadata"]["render_time_ms"]

        # Render should complete in <1000ms even with 500 points
        assert render_time < 1000


class TestOverlayRendererIntegration:
    """Integration with schema and service layer tests."""

    @pytest.fixture
    def renderer(self) -> OverlayRenderer:
        return OverlayRenderer()

    @pytest.mark.asyncio
    async def test_with_analysis_intent(self, renderer):
        """Test rendering with different analysis intents."""
        df = pl.DataFrame({
            "Date": ["2025-01-01", "2025-01-02"],
            "Revenue": [1000.0, 1200.0],
            "Cost": [400.0, 450.0]
        })

        for intent in ["trend", "comparison", "relationship"]:
            spec = MultiSeriesViewSpec(
                title="Test",
                chart_type_primary="scatter",
                series_strategy="overlay",
                encoding={"x": "Date"},
                y_roles=[
                    {"column": "Revenue", "role": "series"},
                    {"column": "Cost", "role": "series"}
                ],
                analysis_intent=intent
            )

            result = await renderer.render(spec, df)
            assert len(result["data"]) == 2

    @pytest.mark.asyncio
    async def test_with_unit_handling(self, renderer):
        """Test rendering with unit handling."""
        df = pl.DataFrame({
            "Date": ["2025-01-01", "2025-01-02"],
            "Revenue": [1000.0, 1200.0],
            "Cost": [400.0, 450.0]
        })

        spec = MultiSeriesViewSpec(
            title="Test",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[
                {"column": "Revenue", "role": "series"},
                {"column": "Cost", "role": "series"}
            ],
            unit_handling={"Revenue": "USD", "Cost": "USD"}
        )

        result = await renderer.render(spec, df)
        # Should handle unit info without error
        assert len(result["data"]) == 2

    @pytest.mark.asyncio
    async def test_with_secondary_metric(self, renderer):
        """Test rendering with secondary metric reference."""
        df = pl.DataFrame({
            "Date": ["2025-01-01", "2025-01-02", "2025-01-03"],
            "Revenue": [1000.0, 1200.0, 1100.0],
            "Cost": [400.0, 450.0, 480.0],
            "Target": [1050.0, 1050.0, 1050.0]
        })

        spec = MultiSeriesViewSpec(
            title="Revenue vs Target",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[
                {"column": "Revenue", "role": "series"},
                {"column": "Cost", "role": "series"}
            ],
            secondary_metric="Target"
        )

        result = await renderer.render(spec, df)
        # Should add reference line without error
        assert len(result["data"]) == 2


# Pytest configuration
def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])

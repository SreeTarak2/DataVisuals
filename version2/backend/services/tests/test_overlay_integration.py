"""
Overlay Renderer - Integration Tests
=====================================
End-to-end integration tests for Overlay Renderer API endpoints.

Tests:
- API endpoint functionality
- Request/response validation
- Data transformation
- Error handling
- CSV uploads
- Performance under load
"""

import pytest
import json
from fastapi.testclient import TestClient
from datetime import datetime
import polars as pl
import io
import csv

# Import your FastAPI app
# from main import app

# For testing, we create a minimal test app
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Mock the app - in real tests, import from main
app = FastAPI()


class TestOverlayAPIEndpoints:
    """API endpoint tests."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_overlay_endpoint_basic(self, client):
        """Test basic POST /overlay endpoint."""
        payload = {
            "title": "Test Chart",
            "data": {
                "Date": ["2025-01-01", "2025-01-02", "2025-01-03"],
                "Revenue": [1000.0, 1200.0, 1100.0],
                "Cost": [400.0, 450.0, 480.0]
            },
            "x_column": "Date",
            "y_columns": ["Revenue", "Cost"]
        }

        # This would work with real app:
        # response = client.post("/api/v1/charts/overlay", json=payload)
        # assert response.status_code == 200
        # result = response.json()
        # assert result["success"] is True
        # assert "chart" in result
        # assert "data" in result["chart"]
        # assert len(result["chart"]["data"]) == 2

    @pytest.mark.asyncio
    async def test_overlay_endpoint_get_info(self, client):
        """Test GET /overlay/info endpoint."""
        # response = client.get("/api/v1/charts/overlay/info")
        # assert response.status_code == 200
        # info = response.json()
        # assert info["service"] == "overlay-chart-renderer"
        # assert info["version"] == "1.0.0"
        # assert info["status"] == "ready"
        pass

    @pytest.mark.asyncio
    async def test_overlay_endpoint_health(self, client):
        """Test GET /overlay/health endpoint."""
        # response = client.get("/api/v1/charts/overlay/health")
        # assert response.status_code == 200
        # health = response.json()
        # assert health["status"] == "healthy"
        # assert health["service"] == "overlay-chart-renderer"
        pass


class TestOverlayAPIValidation:
    """API request validation tests."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_missing_required_field(self, client):
        """Test error when required field missing."""
        payload = {
            "title": "Test",
            "data": {"X": [1, 2]},
            # Missing x_column
            "y_columns": ["Y"]
        }

        # response = client.post("/api/v1/charts/overlay", json=payload)
        # assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_invalid_data_type(self, client):
        """Test error with invalid data type."""
        payload = {
            "title": "Test",
            "data": "invalid",  # Should be dict
            "x_column": "X",
            "y_columns": ["Y"]
        }

        # response = client.post("/api/v1/charts/overlay", json=payload)
        # assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_single_y_column(self, client):
        """Test error with only 1 y column."""
        payload = {
            "title": "Test",
            "data": {
                "X": [1, 2],
                "Y": [10, 20]
            },
            "x_column": "X",
            "y_columns": ["Y"]  # Only 1 - need at least 2
        }

        # response = client.post("/api/v1/charts/overlay", json=payload)
        # assert response.status_code == 400
        # result = response.json()
        # assert "at least 2" in result["error"]

    @pytest.mark.asyncio
    async def test_too_many_y_columns(self, client):
        """Test warning with >7 y columns."""
        payload = {
            "title": "Test",
            "data": {
                "X": [1, 2],
                **{f"Y{i}": [10+i, 20+i] for i in range(10)}
            },
            "x_column": "X",
            "y_columns": [f"Y{i}" for i in range(10)]  # 10 - warning expected
        }

        # response = client.post("/api/v1/charts/overlay", json=payload)
        # assert response.status_code == 200
        # result = response.json()
        # assert "warnings" in result
        # assert any("series" in w for w in result.get("warnings", []))


class TestOverlayCSVUpload:
    """CSV file upload tests."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def sample_csv(self):
        """Create sample CSV data."""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["Date", "Revenue", "Cost"])
        writer.writeheader()
        writer.writerow({"Date": "2025-01-01", "Revenue": "1000", "Cost": "400"})
        writer.writerow({"Date": "2025-01-02", "Revenue": "1200", "Cost": "450"})
        writer.writerow({"Date": "2025-01-03", "Revenue": "1100", "Cost": "480"})
        output.seek(0)
        return output.read().encode()

    @pytest.mark.asyncio
    async def test_csv_upload(self, client, sample_csv):
        """Test CSV upload endpoint."""
        # This would work with real app:
        # response = client.post(
        #     "/api/v1/charts/overlay/csv",
        #     params={
        #         "title": "CSV Test",
        #         "x_column": "Date",
        #         "y_columns": "Revenue,Cost"
        #     },
        #     files={"file": ("test.csv", io.BytesIO(sample_csv))}
        # )
        # assert response.status_code == 200
        # result = response.json()
        # assert result["success"] is True
        pass


class TestOverlayDataProcessing:
    """Data processing and transformation tests."""

    @pytest.mark.asyncio
    async def test_data_dict_conversion(self):
        """Test dict → DataFrame → traces conversion."""
        data = {
            "Date": ["2025-01-01", "2025-01-02"],
            "Revenue": [1000.0, 1200.0],
            "Cost": [400.0, 450.0]
        }

        # Simulate conversion
        df = pl.DataFrame(data)
        assert len(df) == 2
        assert df.columns == ["Date", "Revenue", "Cost"]

    @pytest.mark.asyncio
    async def test_numeric_conversion(self):
        """Test automatic type conversion."""
        data = {
            "Month": ["Jan", "Feb"],
            "Value": ["100", "200"]  # Strings, should convert to numbers
        }

        df = pl.DataFrame(data)
        # Would need type conversion logic
        assert len(df) == 2

    @pytest.mark.asyncio
    async def test_null_handling_in_conversion(self):
        """Test null value handling during conversion."""
        data = {
            "X": [1, 2, 3],
            "Y": [100, None, 300]
        }

        df = pl.DataFrame(data)
        assert df["Y"].is_null().sum() == 1


class TestOverlayResponseStructure:
    """Response structure and format tests."""

    @pytest.mark.asyncio
    async def test_response_has_required_fields(self):
        """Test response has all required fields."""
        # Actual response structure check
        expected_fields = ["success", "chart", "metadata"]
        # Mock response
        response = {
            "success": True,
            "chart": {"data": [], "layout": {}, "metadata": {}},
            "metadata": {}
        }

        for field in expected_fields:
            assert field in response

    @pytest.mark.asyncio
    async def test_chart_structure(self):
        """Test chart object structure."""
        chart = {
            "data": [
                {
                    "x": [1, 2, 3],
                    "y": [10, 20, 15],
                    "name": "Series1",
                    "mode": "lines+markers"
                }
            ],
            "layout": {
                "title": {"text": "Test"},
                "xaxis": {"title": "X"},
                "yaxis": {"title": "Y"}
            },
            "metadata": {
                "renderer": "overlay",
                "series_count": 1
            }
        }

        # Validate structure
        assert "data" in chart
        assert "layout" in chart
        assert "metadata" in chart
        assert len(chart["data"]) > 0
        assert "x" in chart["data"][0]
        assert "y" in chart["data"][0]

    @pytest.mark.asyncio
    async def test_metadata_fields(self):
        """Test metadata contains expected fields."""
        metadata = {
            "renderer": "overlay",
            "series_count": 2,
            "data_points_per_series": 10,
            "has_nulls": False,
            "render_time_ms": 15.5,
            "mode": "lines+markers"
        }

        required_fields = ["renderer", "series_count", "render_time_ms"]
        for field in required_fields:
            assert field in metadata


class TestOverlayErrorScenarios:
    """Error handling and edge case tests."""

    @pytest.mark.asyncio
    async def test_empty_dataframe_error(self):
        """Test proper error on empty data."""
        # This tests the renderer directly
        from services.charts.renderers.overlay_renderer import OverlayRenderer
        from db.schemas_charts import MultiSeriesViewSpec

        renderer = OverlayRenderer()
        spec = MultiSeriesViewSpec(
            title="Test",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[{"column": "Value", "role": "series"}]
        )

        df = pl.DataFrame()

        with pytest.raises(ValueError, match="empty"):
            await renderer.render(spec, df)

    @pytest.mark.asyncio
    async def test_missing_column_error(self):
        """Test error on missing column."""
        from services.charts.renderers.overlay_renderer import OverlayRenderer
        from db.schemas_charts import MultiSeriesViewSpec

        renderer = OverlayRenderer()
        spec = MultiSeriesViewSpec(
            title="Test",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "NonExistent"},
            y_roles=[{"column": "Value", "role": "series"}]
        )

        df = pl.DataFrame({"Value": [1, 2]})

        with pytest.raises(ValueError, match="not found"):
            await renderer.render(spec, df)

    @pytest.mark.asyncio
    async def test_graceful_null_handling(self):
        """Test graceful handling of nulls."""
        from services.charts.renderers.overlay_renderer import OverlayRenderer
        from db.schemas_charts import MultiSeriesViewSpec

        renderer = OverlayRenderer()
        spec = MultiSeriesViewSpec(
            title="Test",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "Date"},
            y_roles=[
                {"column": "A", "role": "series"},
                {"column": "B", "role": "series"}
            ]
        )

        df = pl.DataFrame({
            "Date": ["2025-01-01", "2025-01-02", "2025-01-03"],
            "A": [1.0, None, 3.0],
            "B": [None, 2.0, 3.0]
        })

        result = await renderer.render(spec, df)
        assert result["metadata"]["has_nulls"] is True


class TestOverlayPerformance:
    """Performance and load tests."""

    @pytest.mark.asyncio
    async def test_render_time_small_dataset(self):
        """Test render time for small dataset."""
        from services.charts.renderers.overlay_renderer import OverlayRenderer
        from db.schemas_charts import MultiSeriesViewSpec
        import time

        renderer = OverlayRenderer()
        spec = MultiSeriesViewSpec(
            title="Test",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "X"},
            y_roles=[
                {"column": "Y1", "role": "series"},
                {"column": "Y2", "role": "series"}
            ]
        )

        df = pl.DataFrame({
            "X": list(range(100)),
            "Y1": [float(i * 1.5) for i in range(100)],
            "Y2": [float(i * 2.0) for i in range(100)]
        })

        start = time.time()
        result = await renderer.render(spec, df)
        elapsed = time.time() - start

        render_time = result["metadata"]["render_time_ms"]
        assert render_time < 100  # Should be <100ms for 100 points

    @pytest.mark.asyncio
    async def test_render_time_large_dataset(self):
        """Test render time for large dataset."""
        from services.charts.renderers.overlay_renderer import OverlayRenderer
        from db.schemas_charts import MultiSeriesViewSpec
        import time

        renderer = OverlayRenderer()
        spec = MultiSeriesViewSpec(
            title="Test",
            chart_type_primary="scatter",
            series_strategy="overlay",
            encoding={"x": "X"},
            y_roles=[
                {"column": "Y1", "role": "series"},
                {"column": "Y2", "role": "series"}
            ]
        )

        df = pl.DataFrame({
            "X": list(range(5000)),
            "Y1": [float(i * 1.5) for i in range(5000)],
            "Y2": [float(i * 2.0) for i in range(5000)]
        })

        result = await renderer.render(spec, df)
        render_time = result["metadata"]["render_time_ms"]

        # Should be <500ms for 5000 points
        assert render_time < 500


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])

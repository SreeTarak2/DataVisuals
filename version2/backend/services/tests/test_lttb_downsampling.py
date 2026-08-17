"""
Unit tests for LTTB downsampling + sampling metadata aggregation
in services/charts/hydrate.py (Phase 1 — honest truncation).
"""
import math
import sys

import polars as pl
import pytest

# services/tests/conftest.py pre-seeds `services.charts.hydrate` in sys.modules
# as a MagicMock (to keep the heavy services/ai import chain from loading real
# dependencies). Our tests exercise the real implementation, so drop the mock
# BEFORE importing the module.
sys.modules.pop("services.charts.hydrate", None)

from services.charts.hydrate import (  # noqa: E402
    _lttb_downsample,
    _lttb_downsample_df,
    aggregate_sampling_metadata,
)


# ── _lttb_downsample ──────────────────────────────────────────────────────────


class TestLttbDownsample:
    def test_small_series_untouched(self):
        x = list(range(5))
        y = [float(v) for v in range(5)]
        sx, sy = _lttb_downsample(x, y, 100)
        assert sx == x
        assert sy == y

    def test_respects_threshold(self):
        n = 10_000
        x = list(range(n))
        y = [math.sin(i / 50.0) + (i % 7) for i in x]
        sx, sy = _lttb_downsample(x, y, 500)
        assert len(sx) == 500
        assert len(sy) == 500

    def test_preserves_endpoints(self):
        n = 10_000
        x = list(range(n))
        y = [float(i) for i in x]
        sx, sy = _lttb_downsample(x, y, 250)
        assert sx[0] == x[0]
        assert sx[-1] == x[-1]
        assert sy[0] == y[0]
        assert sy[-1] == y[-1]

    def test_preserves_spike_shape(self):
        """The whole point of LTTB: an isolated spike must survive downsampling
        even though every-nth sampling would drop it."""
        n = 1_000
        x = list(range(n))
        y = [1.0] * n
        y[500] = 99.0  # single spike in the middle
        sx, sy = _lttb_downsample(x, y, 100)
        assert 99.0 in sy, "LTTB dropped the spike — shape not preserved"

    def test_tracks_sine_shape(self):
        n = 20_000
        x = list(range(n))
        y = [math.sin(i / 100.0) for i in x]
        sx, sy = _lttb_downsample(x, y, 400)
        # Max deviation from the true sine at any sampled point must be small.
        max_dev = max(abs(v - math.sin(i / 100.0)) for i, v in zip(sx, sy))
        assert max_dev < 0.15

    def test_string_date_x_values(self):
        """Date strings (e.g. '2024-01-01') cannot be float()-ed — the
        triangle math must fall back to index coordinates and preserve the
        original x labels in the output."""
        from datetime import date, timedelta

        start = date(2020, 1, 1)
        x = [(start + timedelta(days=i)).isoformat() for i in range(5000)]
        y = [math.sin(i / 50.0) for i in range(5000)]
        sx, sy = _lttb_downsample(x, y, 200)
        assert len(sx) == 200
        assert sx[0] == x[0]
        assert sx[-1] == x[-1]
        assert all(isinstance(v, str) for v in sx)  # labels preserved

    def test_datetime_x_values(self):
        """Real datetime objects must also survive downsampling."""
        from datetime import datetime, timedelta

        start = datetime(2020, 1, 1)
        x = [start + timedelta(days=i) for i in range(5000)]
        y = [math.sin(i / 50.0) for i in range(5000)]
        sx, sy = _lttb_downsample(x, y, 150)
        assert len(sx) == 150
        assert sx[0] == x[0]
        assert sx[-1] == x[-1]
        assert all(isinstance(v, datetime) for v in sx)


class TestLttbDownsampleDf:
    def test_returns_original_when_small(self):
        df = pl.DataFrame({"x": [1, 2, 3], "y": [10.0, 20.0, 30.0]})
        out, original = _lttb_downsample_df(df, 100)
        assert original == 3
        assert len(out) == 3

    def test_downsamples_large(self):
        n = 5_000
        df = pl.DataFrame(
            {"x": list(range(n)), "y": [math.sin(i / 50.0) for i in range(n)]}
        )
        out, original = _lttb_downsample_df(df, 300)
        assert original == n
        assert len(out) == 300

    def test_downsamples_temporal_x(self):
        """End-to-end through the df helper with a Datetime x column — the
        exact path a large daily time-series line chart takes."""
        from datetime import datetime, timedelta

        n = 5_000
        start = datetime(2020, 1, 1)
        df = pl.DataFrame(
            {
                "x": [start + timedelta(days=i) for i in range(n)],
                "y": [math.sin(i / 50.0) for i in range(n)],
            }
        )
        out, original = _lttb_downsample_df(df, 300)
        assert original == n
        assert len(out) == 300
        assert out["x"].dtype == pl.Datetime


# ── aggregate_sampling_metadata ───────────────────────────────────────────────


class TestAggregateSamplingMetadata:
    def test_none_when_no_sampling(self):
        traces = [{"type": "bar", "x": [1], "y": [2]}]
        assert aggregate_sampling_metadata(traces) is None

    def test_aggregates_single_trace(self):
        traces = [
            {
                "type": "scatter",
                "_sampled": {"original_count": 12_000, "shown": 1_000, "method": "lttb"},
            }
        ]
        result = aggregate_sampling_metadata(traces)
        assert result == {"shown": 1_000, "original_count": 12_000, "method": "lttb"}

    def test_aggregates_multi_trace_max_original(self):
        traces = [
            {"type": "scatter", "_sampled": {"original_count": 8_000, "shown": 1_000, "method": "lttb"}},
            {"type": "scatter", "_sampled": {"original_count": 12_000, "shown": 1_000, "method": "lttb"}},
        ]
        result = aggregate_sampling_metadata(traces)
        assert result["original_count"] == 12_000
        assert result["shown"] == 2_000
        assert result["method"] == "lttb"

    def test_returns_none_when_original_not_larger(self):
        traces = [
            {"type": "bar", "_sampled": {"original_count": 10, "shown": 10, "method": "top_n"}}
        ]
        assert aggregate_sampling_metadata(traces) is None

    def test_missing_method_defaults(self):
        traces = [
            {"type": "scatter", "_sampled": {"original_count": 500, "shown": 100}}
        ]
        result = aggregate_sampling_metadata(traces)
        assert result["method"] == "sampled"

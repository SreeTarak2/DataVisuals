"""Unit tests for services.charts.semantic_types — Flint-inspired inference + auto-layout."""

from __future__ import annotations

import polars as pl
import pytest

from services.charts.semantic_types import (
    SemanticType,
    apply_auto_layout,
    format_spec_for,
    infer_column_semantic_type,
    infer_semantic_types,
)


# ─────────────────────────────────────────────────────────────────────
# infer_column_semantic_type
# ─────────────────────────────────────────────────────────────────────

class TestInferColumnSemanticType:
    def test_currency_by_name(self):
        assert (
            infer_column_semantic_type("total_revenue", pl.Float64)
            == SemanticType.CURRENCY
        )
        assert (
            infer_column_semantic_type("unit_price", pl.Float64)
            == SemanticType.CURRENCY
        )

    def test_currency_by_value(self):
        # String column whose samples carry currency symbols
        st = infer_column_semantic_type(
            "amount", pl.Utf8, sample_values=["$12.50", "$9.99", "$100.00"]
        )
        assert st == SemanticType.CURRENCY

    def test_percentage_by_name(self):
        assert (
            infer_column_semantic_type("conversion_rate", pl.Float64)
            == SemanticType.PERCENTAGE
        )

    def test_ratio_by_fraction_values(self):
        st = infer_column_semantic_type(
            "risk_ratio", pl.Float64, sample_values=[0.1, 0.5, 0.9]
        )
        assert st == SemanticType.RATIO

    def test_percent_suffix_values(self):
        st = infer_column_semantic_type(
            "margin", pl.Utf8, sample_values=["12%", "45%", "8%"]
        )
        assert st == SemanticType.PERCENTAGE

    def test_date_dtype(self):
        assert infer_column_semantic_type("sale_date", pl.Date) == SemanticType.DATE
        assert (
            infer_column_semantic_type("created_at", pl.Datetime)
            == SemanticType.DATETIME
        )

    def test_duration_by_name(self):
        assert (
            infer_column_semantic_type("response_time_ms", pl.Int64)
            == SemanticType.DURATION
        )

    def test_temperature(self):
        assert (
            infer_column_semantic_type("temperature", pl.Float64)
            == SemanticType.TEMPERATURE
        )

    def test_rank_and_score(self):
        assert infer_column_semantic_type("rank", pl.Int64) == SemanticType.RANK
        assert infer_column_semantic_type("nps_score", pl.Int64) == SemanticType.SCORE

    def test_identifier_suffix(self):
        assert (
            infer_column_semantic_type("customer_id", pl.Utf8)
            == SemanticType.IDENTIFIER
        )

    def test_quantity_by_name(self):
        assert (
            infer_column_semantic_type("order_count", pl.Int64)
            == SemanticType.QUANTITY
        )

    def test_year_like_numeric(self):
        st = infer_column_semantic_type("year", pl.Int64, sample_values=[2019, 2020, 2021])
        assert st == SemanticType.YEAR_MONTH

    def test_generic_numeric_fallback(self):
        assert infer_column_semantic_type("value_x", pl.Float64) == SemanticType.NUMBER

    def test_low_cardinality_string_is_dimension(self):
        st = infer_column_semantic_type(
            "region", pl.Utf8, sample_values=["N", "S", "E", "W"], cardinality=4, row_count=1000
        )
        assert st == SemanticType.DIMENSION


# ─────────────────────────────────────────────────────────────────────
# infer_semantic_types (overrides + df-based)
# ─────────────────────────────────────────────────────────────────────

class TestInferSemanticTypes:
    def _df(self):
        return pl.DataFrame(
            {
                "revenue": [100.0, 200.0, 300.0],
                "region": ["N", "S", "E"],
                "conversion": [0.05, 0.1, 0.2],
                "created_at": pl.Series(
                    ["2024-01-01", "2024-02-01", "2024-03-01"], dtype=pl.Datetime
                ),
            }
        )

    def test_infers_columns_of_interest(self):
        df = self._df()
        types = infer_semantic_types(df, {"columns": ["region", "revenue"]})
        assert types["revenue"] == SemanticType.CURRENCY
        assert types["region"] == SemanticType.DIMENSION

    def test_ai_override_wins(self):
        df = self._df()
        # AI-declared semantic_types win over inference (name alone would
        # infer "conversion" as RATIO given 0–1 samples — override forces %)
        config = {
            "columns": ["revenue", "conversion"],
            "semantic_types": {"conversion": "percentage"},
        }
        types = infer_semantic_types(df, config)
        assert types["conversion"] == SemanticType.PERCENTAGE


# ─────────────────────────────────────────────────────────────────────
# format_spec_for
# ─────────────────────────────────────────────────────────────────────

class TestFormatSpec:
    def test_currency_spec(self):
        spec = format_spec_for(SemanticType.CURRENCY)
        assert spec["tickprefix"] == "$"
        assert "tickformat" in spec

    def test_percentage_spec(self):
        spec = format_spec_for(SemanticType.PERCENTAGE)
        assert spec["ticksuffix"] == "%"

    def test_date_spec(self):
        spec = format_spec_for(SemanticType.DATE)
        assert spec["type"] == "date"

    def test_unknown_returns_empty(self):
        assert format_spec_for(SemanticType.UNKNOWN) == {}


# ─────────────────────────────────────────────────────────────────────
# apply_auto_layout
# ─────────────────────────────────────────────────────────────────────

class TestAutoLayout:
    def _payload(self):
        return {
            "layout": {"xaxis": {}, "yaxis": {}},
            "traces": [{"type": "bar", "x": ["A", "B", "C"], "y": [1, 2, 3]}],
        }

    def test_adds_axis_titles(self):
        layout = apply_auto_layout(
            {"xaxis": {}, "yaxis": {}},
            {"revenue": SemanticType.CURRENCY, "region": SemanticType.DIMENSION},
            {"columns": ["region", "revenue"], "chart_type": "bar"},
            [],
        )
        assert layout["xaxis"]["title"]["text"] == "Region"
        assert layout["yaxis"]["title"]["text"] == "Revenue"

    def test_currency_tick_formatting(self):
        layout = apply_auto_layout(
            {"xaxis": {}, "yaxis": {}},
            {"revenue": SemanticType.CURRENCY},
            {"columns": ["region", "revenue"], "chart_type": "bar"},
            [],
        )
        assert layout["yaxis"]["tickprefix"] == "$"

    def test_date_xaxis_type(self):
        layout = apply_auto_layout(
            {"xaxis": {}, "yaxis": {}},
            {"date": SemanticType.DATE, "value": SemanticType.NUMBER},
            {"columns": ["date", "value"], "chart_type": "line"},
            [],
        )
        assert layout["xaxis"]["type"] == "date"

    def test_zero_baseline_for_bars(self):
        layout = apply_auto_layout(
            {"xaxis": {}, "yaxis": {}},
            {"value": SemanticType.NUMBER},
            {"columns": ["cat", "value"], "chart_type": "bar"},
            [],
        )
        assert layout["yaxis"].get("rangemode") == "tozero"

    def test_no_baseline_for_line(self):
        layout = apply_auto_layout(
            {"xaxis": {}, "yaxis": {}},
            {"value": SemanticType.NUMBER},
            {"columns": ["cat", "value"], "chart_type": "line"},
            [],
        )
        assert "rangemode" not in layout["yaxis"]

    def test_dense_categories_rotate_labels(self):
        many = [f"Category Long Name {i}" for i in range(12)]
        layout = apply_auto_layout(
            {"xaxis": {}, "yaxis": {}},
            {"cat": SemanticType.DIMENSION, "value": SemanticType.NUMBER},
            {"columns": ["cat", "value"], "chart_type": "bar"},
            [{"type": "bar", "x": many, "y": list(range(12))}],
        )
        assert layout["xaxis"].get("tickangle") is not None

    def test_attaches_trace_metadata(self):
        traces = [{"type": "bar", "x": ["A", "B"], "y": [1, 2]}]
        apply_auto_layout(
            {"xaxis": {}, "yaxis": {}},
            {"cat": SemanticType.DIMENSION, "value": SemanticType.CURRENCY},
            {"columns": ["cat", "value"], "chart_type": "bar"},
            traces,
        )
        assert traces[0]["_axis_metadata"]["y"]["semantic_type"] == "currency"
        assert traces[0]["_axis_metadata"]["x"]["semantic_type"] == "dimension"

    def test_never_raises(self):
        # Malformed inputs should degrade gracefully, never raise
        layout = apply_auto_layout(None, {}, {}, None)
        assert layout is None or isinstance(layout, dict)

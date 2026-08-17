import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import polars as pl
import pytest
from services.pipeline.unpivot_fixer import (
    detect_unpivot_candidates,
    apply_unpivot,
    _extract_time_meta,
)
from services.chat.cleaning_guard import classify_cleaning_state, CRITICAL_ACTION_TYPES


class TestExtractTimeMeta:
    @pytest.mark.parametrize(
        "col,expected",
        [
            ("jan_revenue", ("Jan", "revenue", "month")),
            ("feb_revenue", ("Feb", "revenue", "month")),
            ("revenue_jan", ("Jan", "revenue", "month")),
            ("q1_2023", ("Q1 2023", "value", "quarter")),
            ("Q2_2023", ("Q2 2023", "value", "quarter")),
            ("2023", ("2023", "value", "year")),
            ("sales_2024", ("2024", "sales", "year")),
        ],
    )
    def test_recognizes_time_columns(self, col, expected):
        assert _extract_time_meta(col) == expected

    @pytest.mark.parametrize(
        "col",
        ["revenue", "product", "region", "customer_id", "sku_code"],
    )
    def test_rejects_non_time_columns(self, col):
        assert _extract_time_meta(col) is None


class TestDetectUnpivotCandidates:
    def _month_df(self):
        return pl.DataFrame(
            {
                "id": [1, 2],
                "jan_revenue": [10, 20],
                "feb_revenue": [30, 40],
                "mar_revenue": [50, 60],
                "product": ["A", "B"],
            }
        )

    def test_detects_month_columns(self):
        proposals = detect_unpivot_candidates(self._month_df())
        assert len(proposals) == 1
        p = proposals[0]
        assert p["action_type"] == "unpivot_columns"
        assert p["target_columns"] == ["feb_revenue", "jan_revenue", "mar_revenue"]
        assert p["new_column_names"] == ["month", "revenue"]
        assert p["approved"] is None  # pending → guardrail blocks
        assert p["value_mapping"]["jan_revenue"] == "Jan"

    def test_requires_at_least_three_columns(self):
        df = pl.DataFrame(
            {
                "id": [1, 2],
                "jan_revenue": [10, 20],
                "feb_revenue": [30, 40],
                "product": ["A", "B"],
            }
        )
        assert detect_unpivot_candidates(df) == []

    def test_mixed_dtype_group_rejected(self):
        df = pl.DataFrame(
            {
                "id": [1, 2],
                "jan_revenue": [10, 20],            # numeric
                "feb_revenue": ["30", "40"],        # string — mismatch
                "mar_revenue": [50, 60],
                "product": ["A", "B"],
            }
        )
        assert detect_unpivot_candidates(df) == []

    def test_clean_table_no_proposals(self):
        df = pl.DataFrame({"product": ["A", "B"], "revenue": [10, 20]})
        assert detect_unpivot_candidates(df) == []

    def test_year_columns_detected(self):
        df = pl.DataFrame(
            {"id": [1, 2], "2023": [10, 20], "2024": [30, 40], "2025": [50, 60]}
        )
        proposals = detect_unpivot_candidates(df)
        assert len(proposals) == 1
        assert proposals[0]["new_column_names"] == ["year", "value"]


class TestApplyUnpivot:
    def test_unpivots_and_drops_null_rows(self):
        df = pl.DataFrame(
            {
                "id": [1, 2],
                "jan_revenue": [10, 20],
                "feb_revenue": [30, None],  # id=2 had no Feb sales
                "mar_revenue": [50, 60],
            }
        )
        entry = {
            "action_type": "unpivot_columns",
            "target_columns": ["jan_revenue", "feb_revenue", "mar_revenue"],
            "new_column_names": ["month", "revenue"],
            "value_mapping": {"jan_revenue": "Jan", "feb_revenue": "Feb", "mar_revenue": "Mar"},
        }
        warnings: list[str] = []
        out = apply_unpivot(df, entry, warnings)
        assert out.columns == ["id", "month", "revenue"]
        assert out.height == 5  # 6 pivoted rows − 1 null
        assert sorted(out["month"].unique().to_list()) == ["Feb", "Jan", "Mar"]
        assert out.filter(pl.col("month") == "Jan")["revenue"].to_list() == [10, 20]

    def test_fewer_than_three_columns_warns(self):
        df = pl.DataFrame({"jan_revenue": [1], "feb_revenue": [2], "id": [1]})
        entry = {
            "action_type": "unpivot_columns",
            "target_columns": ["jan_revenue", "feb_revenue"],
            "new_column_names": ["month", "revenue"],
            "value_mapping": {"jan_revenue": "Jan", "feb_revenue": "Feb"},
        }
        warnings: list[str] = []
        out = apply_unpivot(df, entry, warnings)
        assert out is df
        assert any("at least 3" in w for w in warnings)

    def test_missing_target_columns_warns(self):
        df = pl.DataFrame({"product": ["A"]})
        entry = {
            "action_type": "unpivot_columns",
            "target_columns": ["jan_revenue", "feb_revenue", "mar_revenue"],
            "new_column_names": ["month", "revenue"],
            "value_mapping": {},
        }
        warnings: list[str] = []
        out = apply_unpivot(df, entry, warnings)
        assert out is df
        assert any("at least 3" in w for w in warnings)


class TestGuardCriticality:
    def test_unpivot_columns_pending_blocks_chat(self):
        assert "unpivot_columns" in CRITICAL_ACTION_TYPES
        manifest = [
            {
                "action_type": "unpivot_columns",
                "target_columns": ["jan", "feb", "mar"],
                "approved": None,
            }
        ]
        state = classify_cleaning_state(manifest)
        assert state.block
        assert state.pending_critical == 1

    def test_unpivot_columns_settled_does_not_block(self):
        manifest = [
            {
                "action_type": "unpivot_columns",
                "target_columns": ["jan", "feb", "mar"],
                "approved": True,
            }
        ]
        state = classify_cleaning_state(manifest)
        assert not state.block


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

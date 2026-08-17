import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import polars as pl
import pytest
from services.pipeline.date_fixer import (
    detect_date_candidates,
    apply_date_coercion,
    _looks_date_like,
)
from services.chat.cleaning_guard import (
    classify_cleaning_state,
    CRITICAL_ACTION_TYPES,
)


class TestLooksDateLike:
    @pytest.mark.parametrize(
        "value",
        [
            "02/01/24",
            "2024-02-01",
            "Feb 1, 2024",
            "1st Feb 2024",
            "2024/02/01",
            "February 2024",
        ],
    )
    def test_accepts_real_date_strings(self, value):
        assert _looks_date_like(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            "Shirts",
            "123456",
            "100",
            "REVENUE",
            "ABC-1234",
        ],
    )
    def test_rejects_non_dates(self, value):
        assert _looks_date_like(value) is False


class TestDetectDateCandidates:
    def test_detects_mixed_format_date_column(self):
        df = pl.DataFrame(
            {
                "date_logged": [
                    "02/01/24",
                    "Feb 1, 2024",
                    "2024-03-15",
                    "04/20/2024",
                    "May 5, 2024",
                ],
                "product": ["Shirts", "Pants", "Hats", "Socks", "Belts"],
            }
        )
        proposals = detect_date_candidates(df)
        assert len(proposals) == 1
        p = proposals[0]
        assert p["action_type"] == "type_coercion"
        assert p["target_column"] == "date_logged"
        assert p["approved"] is None  # pending → guardrail blocks
        assert p["state"] == "proposed"
        assert len(p["evidence"]["before"]) == 5
        assert p["evidence"]["after"][0]  # ISO strings present

    def test_does_not_propose_numeric_or_label_columns(self):
        df = pl.DataFrame(
            {
                "revenue": [100, 200, 300, 400, 500],
                "product": ["Shirts", "Pants", "Hats", "Socks", "Belts"],
            }
        )
        proposals = detect_date_candidates(df)
        assert proposals == []

    def test_rejects_mostly_nondate_string_column(self):
        df = pl.DataFrame(
            {
                "mixed": ["02/01/24", "Shirts", "Pants", "Hats", "Socks"],
            }
        )
        proposals = detect_date_candidates(df)
        assert proposals == []

    def test_bare_years_not_treated_as_dates(self):
        df = pl.DataFrame({"year": ["2024", "2023", "2022", "2021", "2020"]})
        proposals = detect_date_candidates(df)
        assert proposals == []


class TestApplyDateCoercion:
    def test_coerces_string_column_to_datetime(self):
        df = pl.DataFrame(
            {
                "date_logged": ["2024-02-01", "2024-03-15", "2024-05-05"],
                "product": ["A", "B", "C"],
            }
        )
        entry = {"action_type": "type_coercion", "target_column": "date_logged"}
        warnings: list[str] = []
        out = apply_date_coercion(df, entry, warnings)
        assert str(out["date_logged"].dtype).startswith("Datetime")
        assert out["date_logged"].to_list()[0].year == 2024

    def test_mixed_formats_fall_back_to_dateutil(self):
        df = pl.DataFrame(
            {
                "date_logged": ["02/01/24", "Feb 1, 2024", "garbage"],
            }
        )
        entry = {"action_type": "type_coercion", "target_column": "date_logged"}
        warnings: list[str] = []
        out = apply_date_coercion(df, entry, warnings)
        assert str(out["date_logged"].dtype).startswith("Datetime")
        values = out["date_logged"].to_list()
        assert values[0] is not None and values[1] is not None
        assert values[2] is None  # unparseable → null, never a crash

    def test_missing_column_warns_and_noops(self):
        df = pl.DataFrame({"product": ["A"]})
        warnings: list[str] = []
        out = apply_date_coercion(
            df, {"target_column": "nope", "action_type": "type_coercion"}, warnings
        )
        assert out is df
        assert any("not found" in w for w in warnings)

    def test_already_date_column_warns(self):
        df = pl.DataFrame({"d": [1]})
        df = df.with_columns(pl.col("d").cast(pl.Datetime("us")))
        warnings: list[str] = []
        out = apply_date_coercion(
            df, {"target_column": "d", "action_type": "type_coercion"}, warnings
        )
        assert any("already a date" in w for w in warnings)


class TestGuardCriticality:
    def test_type_coercion_pending_blocks_chat(self):
        assert "type_coercion" in CRITICAL_ACTION_TYPES
        manifest = [
            {
                "action_type": "type_coercion",
                "target_column": "date_logged",
                "approved": None,
            }
        ]
        state = classify_cleaning_state(manifest)
        assert state.block
        assert state.pending_critical == 1

    def test_type_coercion_settled_does_not_block(self):
        manifest = [
            {
                "action_type": "type_coercion",
                "target_column": "date_logged",
                "approved": True,
            }
        ]
        state = classify_cleaning_state(manifest)
        assert not state.block


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

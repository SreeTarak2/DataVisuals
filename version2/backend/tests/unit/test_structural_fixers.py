import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import polars as pl
import pytest
from services.pipeline.structural_fixers import (
    apply_structural_fixers,
    shift_header_row,
    drop_total_rows,
)


class TestShiftHeaderRow:
    def test_no_shift_when_header_is_clean(self):
        df = pl.DataFrame(
            {
                "product": ["Shirts", "Pants"],
                "revenue": [100, 200],
            }
        )
        out, entries = shift_header_row(df)
        assert out.columns == ["product", "revenue"]
        assert entries == []

    def test_prose_title_with_digit_signal_shifts(self):
        # "Fiscal Year 2024" carries a digit → the title row is detectable,
        # and the next row is identifier-like → shift is correct and safe.
        df = pl.DataFrame(
            {
                "Q3 Report": ["Revenue by Region", "region", "west", "east"],
                "More": ["Fiscal Year 2024", "revenue", "100", "200"],
            }
        )
        out, entries = shift_header_row(df)
        assert len(entries) == 1
        assert out.columns == ["region", "revenue"]
        assert out.height == 2

    def test_undetectable_title_row_is_not_shifted(self):
        # All short prose, no digits, no blanks — indistinguishable from a
        # real header. Safety first: a false shift corrupts the dataset.
        df = pl.DataFrame(
            {
                "col0": ["Revenue Overview", "region", "west", "east"],
                "col1": ["Margin Analysis", "revenue", "100", "200"],
            }
        )
        out, entries = shift_header_row(df)
        assert entries == []
        assert out.height == 4

    def test_shifts_title_then_headers(self):
        # 2 rows of prose/blank above a real header row
        df = pl.DataFrame(
            {
                "Company Name": ["Annual Sales Summary 2024", "product", "Shirts", "Pants"],
                "Unnamed: 1": [None, "revenue", "100", "200"],
                "Unnamed: 2": [None, "region", "west", "east"],
            }
        )
        out, entries = shift_header_row(df)
        assert len(entries) == 1
        assert entries[0]["action_type"] == "shift_header"
        assert entries[0]["approved"] is True
        assert out.columns == ["product", "revenue", "region"]
        assert out.height == 2
        assert out["product"].to_list() == ["Shirts", "Pants"]

    def test_blank_first_row_shifts_to_row_one(self):
        df = pl.DataFrame(
            {
                "Unnamed: 0": [None, "product", "Shirts"],
                "Unnamed: 1": [None, "revenue", "100"],
            }
        )
        out, entries = shift_header_row(df)
        assert len(entries) == 1
        assert out.columns == ["product", "revenue"]
        assert out.height == 1

    def test_no_shift_when_no_data_rows_remain(self):
        # Title + header only — nothing left to analyze after the shift.
        df = pl.DataFrame(
            {
                "Title": [
                    "This is a very long title line for the report that keeps "
                    "going well past forty characters for sure",
                    "product",
                ],
                "More": [
                    "Another long prose line that also exceeds forty characters "
                    "by quite a wide margin indeed",
                    "revenue",
                ],
            }
        )
        out, entries = shift_header_row(df)
        assert entries == []
        assert out.height == 2


class TestDropTotalRows:
    def _df(self):
        return pl.DataFrame(
            {
                "product": ["Shirts", "Pants", "TOTAL"],
                "revenue": [100, 200, 300],
            }
        )

    def test_drops_total_row_with_matching_sum(self):
        df = self._df()
        out, entries = drop_total_rows(df)
        assert len(entries) == 1
        assert entries[0]["action_type"] == "drop_row"
        assert entries[0]["approved"] is True
        assert out.height == 2
        assert out["product"].to_list() == ["Shirts", "Pants"]

    def test_keeps_row_when_numbers_do_not_match(self):
        df = pl.DataFrame(
            {
                "product": ["Shirts", "Pants", "TOTAL"],
                "revenue": [100, 200, 999],  # 999 != 300
            }
        )
        out, entries = drop_total_rows(df)
        assert entries == []
        assert out.height == 3

    def test_matches_grand_total_and_case_insensitive(self):
        df = pl.DataFrame(
            {
                "product": ["A", "B", "Grand Total"],
                "revenue": [10, 20, 30],
            }
        )
        out, entries = drop_total_rows(df)
        assert len(entries) == 1
        assert out.height == 2

    def test_does_not_touch_normal_product_named_total(self):
        # A product literally called "Total" (data, not a summary) must be kept
        # when its numbers do not match the column sum.
        df = pl.DataFrame(
            {
                "product": ["Shirts", "Pants", "Total"],
                "revenue": [100, 200, 42],
            }
        )
        out, entries = drop_total_rows(df)
        assert entries == []
        assert out.height == 3

    def test_blank_numeric_cell_on_total_row_is_accepted(self):
        df = pl.DataFrame(
            {
                "product": ["A", "B", "TOTAL"],
                "revenue": [10, 20, None],  # blank numeric on the summary row
                "note": ["x", "y", "sum"],
            }
        )
        out, entries = drop_total_rows(df)
        assert len(entries) == 1
        assert out.height == 2


class TestApplyStructuralFixers:
    def test_full_pipeline_on_messy_file(self):
        df = pl.DataFrame(
            {
                "Quarterly Report": ["product", "revenue", "TOTAL"],
                "Unnamed: 1": ["Quarterly Report", "region", "TOTAL"],
            }
        )
        out, entries = apply_structural_fixers(df)
        # Header stays put (row 0 is short/distinct); TOTAL row dropped.
        assert len(entries) == 1
        assert entries[0]["action_type"] == "drop_row"
        assert out.height == 2

    def test_clean_file_untouched(self):
        df = pl.DataFrame({"product": ["A", "B"], "revenue": [1, 2]})
        out, entries = apply_structural_fixers(df)
        assert entries == []
        assert out.height == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import polars as pl
import pytest
from services.pipeline.category_fixer import (
    detect_category_merges,
    apply_merge_values,
    _normalize,
)
from services.chat.cleaning_guard import classify_cleaning_state, CRITICAL_ACTION_TYPES


class TestNormalize:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Shirts", "shirts"),
            ("shirts ", "shirts"),
            ("SHIRTS!", "shirts"),
            ("T-Shirt", "tshirt"),
            ("  Revenue   Stream ", "revenue stream"),
        ],
    )
    def test_normalizes(self, raw, expected):
        assert _normalize(raw) == expected


class TestDetectCategoryMerges:
    def test_detects_case_space_variants(self):
        # No category dominates (>50%) → targeted fuzzy merge mode.
        df = pl.DataFrame(
            {
                "product": [
                    "Shirts", "Shirts", "shirts ", "SHIRTS!",
                    "Pants", "Pants", "Pants",
                    "Hats", "Hats",
                ],
            }
        )
        proposals = detect_category_merges(df)
        assert len(proposals) == 1
        p = proposals[0]
        assert p["action_type"] == "merge_values"
        assert p["target_column"] == "product"
        assert p["approved"] is None  # pending → guardrail blocks
        assert p["mode"] == "fuzzy"
        assert p["mapping"]["shirts "] == "Shirts"
        assert p["mapping"]["SHIRTS!"] == "Shirts"

    def test_does_not_propose_clean_column(self):
        df = pl.DataFrame(
            {"product": ["Shirts", "Pants", "Hats", "Socks", "Belts"] * 10}
        )
        assert detect_category_merges(df) == []

    def test_skips_high_cardinality(self):
        df = pl.DataFrame({"note": [f"value_{i}" for i in range(200)]})
        assert detect_category_merges(df) == []

    def test_apple_snapple_not_merged(self):
        # token_sort_ratio("snapple", "apple") ≈ 83% < 85% — and with a
        # dominant category the whole column normalizes. The critical safety
        # property: "Snapple" must stay its OWN category, never collapse
        # into "apple".
        df = pl.DataFrame({"product": ["Apple"] * 50 + ["Snapple"] * 5 + ["Apple  "] * 20})
        proposals = detect_category_merges(df)
        assert len(proposals) == 1
        out = apply_merge_values(df, proposals[0], [])
        distinct = set(out["product"].drop_nulls().unique().to_list())
        assert "apple" in distinct and "snapple" in distinct

    def test_dominant_category_proposes_global_normalize(self):
        # "shirts" variants dominate (>50%) → normalize mode, not fuzzy.
        df = pl.DataFrame(
            {
                "product": [
                    "Shirts", "shirts ", "SHIRTS!", "shirts", "Shirts",
                    "Pants", "Pants",
                ],
            }
        )
        proposals = detect_category_merges(df)
        assert len(proposals) == 1
        assert proposals[0]["mode"] == "normalize"
        # normalize mode maps all non-canonical variants, including "Pants".
        assert proposals[0]["mapping"]["Pants"] == "pants"

    def test_skips_numeric_columns(self):
        df = pl.DataFrame({"revenue": [100, 200, 300]})
        assert detect_category_merges(df) == []


class TestApplyMergeValues:
    def test_replaces_variants_with_canonical(self):
        df = pl.DataFrame(
            {"product": ["Shirts", "shirts ", "Pants", "SHIRTS!"]}
        )
        entry = {
            "action_type": "merge_values",
            "target_column": "product",
            "mapping": {"shirts ": "Shirts", "SHIRTS!": "Shirts"},
        }
        warnings: list[str] = []
        out = apply_merge_values(df, entry, warnings)
        assert out["product"].to_list() == ["Shirts", "Shirts", "Pants", "Shirts"]

    def test_missing_column_warns(self):
        df = pl.DataFrame({"product": ["A"]})
        warnings: list[str] = []
        out = apply_merge_values(
            df, {"target_column": "nope", "action_type": "merge_values", "mapping": {"A": "a"}}, warnings
        )
        assert out is df
        assert any("not found" in w for w in warnings)

    def test_no_mapping_warns(self):
        df = pl.DataFrame({"product": ["A"]})
        warnings: list[str] = []
        out = apply_merge_values(
            df, {"target_column": "product", "action_type": "merge_values"}, warnings
        )
        assert any("No value mapping" in w for w in warnings)


class TestGuardCriticality:
    def test_merge_values_pending_blocks_chat(self):
        assert "merge_values" in CRITICAL_ACTION_TYPES
        manifest = [
            {
                "action_type": "merge_values",
                "target_column": "product",
                "approved": None,
            }
        ]
        state = classify_cleaning_state(manifest)
        assert state.block
        assert state.pending_critical == 1

    def test_merge_values_settled_does_not_block(self):
        manifest = [
            {
                "action_type": "merge_values",
                "target_column": "product",
                "approved": True,
            }
        ]
        state = classify_cleaning_state(manifest)
        assert not state.block


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

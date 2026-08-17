"""Tests for chart cross-filter helpers (core/chart_filter.py)."""

import polars as pl

from core.chart_filter import apply_df_filters


def _apply_df_filters(df, filters):
    # Local alias so test names stay focused on behavior, not import paths.
    return apply_df_filters(df, filters)


def _sample_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "region": ["West", "West", "East", "East", "North"],
            "product": ["A", "B", "A", "C", "B"],
            "revenue": [100, 200, 300, 400, 500],
        }
    )


def test_no_filters_returns_unchanged():
    df = _sample_df()
    out = _apply_df_filters(df, None)
    assert out.height == 5
    out2 = _apply_df_filters(df, [])
    assert out2.height == 5


def test_single_field_filter():
    df = _sample_df()
    out = _apply_df_filters(df, [{"field": "region", "value": "West"}])
    assert out.height == 2
    assert set(out["region"].to_list()) == {"West"}


def test_multiple_filters_compose_as_and():
    df = _sample_df()
    out = _apply_df_filters(
        df,
        [{"field": "region", "value": "West"}, {"field": "product", "value": "B"}],
    )
    assert out.height == 1
    assert out["revenue"].to_list() == [200]


def test_string_value_matches_numeric_column():
    df = _sample_df()
    out = _apply_df_filters(df, [{"field": "revenue", "value": "300"}])
    assert out.height == 1
    assert out["region"].to_list() == ["East"]


def test_unknown_field_is_ignored():
    df = _sample_df()
    out = _apply_df_filters(df, [{"field": "nonexistent", "value": "x"}])
    assert out.height == 5


def test_non_dict_filter_is_skipped():
    df = _sample_df()
    out = _apply_df_filters(df, ["garbage", {"field": "region", "value": "East"}])
    assert out.height == 2


def test_no_match_returns_empty_frame():
    df = _sample_df()
    out = _apply_df_filters(df, [{"field": "region", "value": "South"}])
    assert out.height == 0
    assert out.is_empty()


def test_multiple_values_same_field_compose_as_or():
    # Multi-select: clicking "West" then "North" keeps both regions.
    df = _sample_df()
    out = _apply_df_filters(
        df,
        [{"field": "region", "value": "West"}, {"field": "region", "value": "North"}],
    )
    assert out.height == 3
    assert set(out["region"].to_list()) == {"West", "North"}


def test_values_array_form_is_supported():
    df = _sample_df()
    out = _apply_df_filters(df, [{"field": "region", "values": ["West", "North"]}])
    assert out.height == 3
    assert set(out["region"].to_list()) == {"West", "North"}


def test_multi_field_with_multi_value_composes_and_then_or():
    # Region IN (West, East) AND product = B → West/B + East rows where product B.
    df = _sample_df()
    out = _apply_df_filters(
        df,
        [{"field": "region", "values": ["West", "East"]}, {"field": "product", "value": "B"}],
    )
    # West/B (200) matches; East rows are A and C — only West/B survives.
    assert out.height == 1
    assert out["revenue"].to_list() == [200]


def test_multi_value_intersection_same_field_empty():
    # Same field repeated entries are OR'd — never AND — so two disjoint
    # values never produce an empty result (the classic multi-select bug).
    df = _sample_df()
    out = _apply_df_filters(
        df,
        [{"field": "region", "value": "West"}, {"field": "region", "value": "East"}],
    )
    assert out.height == 4
    assert set(out["region"].to_list()) == {"West", "East"}


def test_mixed_shape_filters_are_tolerated():
    df = _sample_df()
    out = _apply_df_filters(
        df,
        [
            {"field": "region", "value": "West"},
            {"field": "product", "values": ["A", "B"]},
            "garbage",
            {"field": "nope", "value": "x"},
        ],
    )
    # West AND product IN (A, B) → West/A + West/B
    assert out.height == 2
    assert set(out["product"].to_list()) == {"A", "B"}

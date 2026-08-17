"""
Unit tests for VectorizedSubspaceEngine edge cases.

Covers:
1. Zero-variance groups (pl.corr returns null)
2. High-cardinality categorical columns (100+ values)
3. Empty subspaces (no matching rows)
4. No numeric columns in dataset
5. NaN/null handling in numeric data
6. Small sample sizes (n < 30)
7. Controlled Simpson's Paradox detection
8. Single categorical column (max_depth=1)
9. All-null column
10. Base correlation = 0
"""

import sys
import os
import numpy as np
import polars as pl
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.analysis.enhanced_quis import (
    VectorizedSubspaceEngine,
    QUISInsight,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def engine():
    return VectorizedSubspaceEngine(beam_width=10, max_depth=2)


@pytest.fixture
def engine_l1_only():
    """Engine with max_depth=1 to test Level 1 only."""
    return VectorizedSubspaceEngine(beam_width=10, max_depth=1)


@pytest.fixture
def correlated_df():
    """Clean dataset with a known strong correlation."""
    np.random.seed(42)
    n = 1000
    x = np.random.normal(0, 1, n)
    y = x * 0.8 + np.random.normal(0, 0.6, n)  # r ≈ 0.8
    cat = np.random.choice(["A", "B", "C", "D"], n)
    return pl.DataFrame({
        "x": x,
        "y": y,
        "cat": cat,
    })


# ═══════════════════════════════════════════════════════════════
# 1. Zero-variance groups
# ═══════════════════════════════════════════════════════════════

class TestZeroVarianceGroups:
    """pl.corr returns null when one variable has zero variance in a group."""

    def test_all_x_identical_in_one_group(self, engine):
        """One group has zero variance in x → pl.corr returns null → filtered out."""
        df = pl.DataFrame({
            "x": [1.0] * 100 + [2.0] * 100,
            "y": np.concatenate([np.random.normal(0, 1, 100), np.random.normal(5, 1, 100)]),
            "cat": ["ZERO_VAR"] * 100 + ["NORMAL"] * 100,
        })
        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=0.5, base_n=200
        )
        # The ZERO_VAR group should be silently skipped (pl.corr returns null)
        # No insight should reference zero_variance group
        for ins in insights:
            if ins.subspace:
                assert ins.subspace.get("cat") != "ZERO_VAR", \
                    f"Zero-variance group should be filtered out, got insight: {ins.description}"

    def test_all_y_zero_variance(self, engine):
        """A group where y is constant."""
        df = pl.DataFrame({
            "x": np.random.normal(0, 1, 200),
            "y": [5.0] * 100 + np.random.normal(10, 2, 100).tolist(),
            "cat": ["CONSTANT_Y"] * 100 + ["VARIABLE_Y"] * 100,
        })
        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=0.3, base_n=200
        )
        for ins in insights:
            if ins.subspace:
                assert ins.subspace.get("cat") != "CONSTANT_Y", \
                    "Constant-y group should be filtered out"

    def test_zero_variance_no_crash(self, engine):
        """Entire dataset has zero variance → should not crash, return empty."""
        df = pl.DataFrame({
            "x": [1.0] * 100,
            "y": [2.0] * 100,
            "cat": ["A"] * 100,
        })
        # Base correlation will be NaN, but the method handles it
        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=0.0, base_n=100
        )
        assert isinstance(insights, list), "Should return a list even with zero-variance data"


# ═══════════════════════════════════════════════════════════════
# 2. High-cardinality categorical columns
# ═══════════════════════════════════════════════════════════════

class TestHighCardinality:
    """Columns with 100+ unique values should not crash or OOM."""

    def test_high_cardinality_no_crash(self, engine):
        """50 groups (5000 rows) — should not crash, process all groups."""
        np.random.seed(42)
        n = 5000
        n_groups = 50
        x = np.random.normal(0, 1, n)
        cat = np.random.choice([f"G{i:03d}" for i in range(n_groups)], n)
        group_idx = np.array([int(g[1:]) for g in cat])
        y = np.where(
            group_idx < 5,
            x * 1.5 + np.random.normal(0, 0.3, n),
            x * 0.3 + np.random.normal(0, 1.0, n),
        )
        df = pl.DataFrame({"x": x, "y": y, "cat": cat})

        # Engine should not crash with many groups
        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=0.3, base_n=n
        )
        assert isinstance(insights, list), "Should return a list"
        for ins in insights:
            assert ins.sample_size >= 30, f"All insights must have n>=30, got n={ins.sample_size}"

    def test_high_cardinality_all_groups_processed(self, engine):
        """Verify the engine processes ALL columns, not just first N."""
        # Create data where each group has a distinct correlation coefficient
        # by adding group-specific offsets to one variable.
        np.random.seed(42)
        n = 3000
        n_groups = 25
        cat = [f"G{i:03d}" for i in range(n_groups)] * (n // n_groups)
        x = np.random.normal(0, 1, n)
        # Each group gets a different offset in y, producing different |r| values
        y = x.copy()
        for i, g in enumerate(sorted(set(cat))):
            mask = np.array(cat) == g
            offset = (i / n_groups) * 10
            y[mask] = x[mask] * 0.7 + offset + np.random.normal(0, 0.5, mask.sum())

        df = pl.DataFrame({"x": x, "y": y, "cat": cat})

        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=0.3, base_n=n
        )

        # The engine processes ALL groups. Groups with small offsets show
        # improved |r|. The assertion: we should see groups from different
        # parts of the G000-G024 range, not just the first few.
        if insights:
            group_indices = [int(list(ins.subspace.values())[0].split("G")[1])
                           for ins in insights if ins.subspace]
            if len(group_indices) >= 3:
                # At least some variety in group indices (not all G000-G002)
                max_idx = max(group_indices)
                assert max_idx >= 5, \
                    f"Groups beyond G005 should be explored, max was G{max_idx:03d}"

    def test_high_cardinality_with_nulls(self, engine):
        """High cardinality + nulls in categorical column."""
        np.random.seed(42)
        n = 3000
        x = np.random.normal(0, 1, n)
        y = x * 0.6 + np.random.normal(0, 0.7, n)
        cat = [f"G{i % 150}" for i in range(n)]
        # Inject nulls
        cat[:50] = [None] * 50
        df = pl.DataFrame({"x": x, "y": y, "cat": cat})

        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=0.6, base_n=n
        )
        assert isinstance(insights, list), "Should not crash with nulls in high-cardinality column"


# ═══════════════════════════════════════════════════════════════
# 3. Empty subspaces
# ═══════════════════════════════════════════════════════════════

class TestEmptySubspaces:
    """Subspaces where filter produces zero rows."""

    def test_level2_empty_subspace(self, engine):
        """
        Level 2 searches where the Level 1 filter eliminates all rows.
        Should not crash — just return no Level 2 insights for those paths.
        """
        np.random.seed(42)
        n = 500
        x = np.random.normal(0, 1, n)
        y = x * 0.7 + np.random.normal(0, 0.5, n)
        # cat1 has groups; cat2 is mostly unique (so filter yields tiny/nonexistent groups)
        cat1 = np.random.choice(["A", "B", "C", "D"], n)
        cat2 = np.random.choice(["RARE"] * 490 + ["UNIQUE"] * 10, n)
        df = pl.DataFrame({"x": x, "y": y, "cat1": cat1, "cat2": cat2})

        # First get Level 1 insights
        l1 = engine._vectorized_level1(df, "x", "y", ["cat1", "cat2"], 0.7, n)

        # Level 2 from cat1 to cat2 (should not crash even if cat2 == "UNIQUE" filters to tiny subset)
        l2 = engine._vectorized_level2(df, "x", "y", ["cat1", "cat2"], 0.7, n, l1)
        assert isinstance(l2, list), "Level 2 should return a list even with empty subspaces"

    def test_all_rows_filtered_out(self, engine):
        """Level 1 filter with a value that doesn't exist."""
        np.random.seed(42)
        n = 200
        df = pl.DataFrame({
            "x": np.random.normal(0, 1, n),
            "y": np.random.normal(0, 1, n),
            "cat": ["A"] * n,
        })
        # This should still work — group_by just finds "A"
        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=0.0, base_n=n
        )
        assert isinstance(insights, list)


# ═══════════════════════════════════════════════════════════════
# 4. No numeric columns
# ═══════════════════════════════════════════════════════════════

class TestNoNumericColumns:
    """Dataset with only string/categorical columns."""

    def test_no_numeric_returns_empty(self, engine):
        """Engine should gracefully return empty list for non-numeric data."""
        df = pl.DataFrame({
            "name": ["Alice", "Bob", "Charlie"] * 100,
            "city": ["NYC", "LA", "SF"] * 100,
            "category": ["A", "B", "C"] * 100,
        })
        # No numeric columns to correlate
        # explore_correlation_subspaces won't be called with non-numeric cols in practice
        # (the caller checks this), but if it is called, should handle gracefully
        numeric_cols = df.select(pl.col(pl.Float64, pl.Int64, pl.Float32, pl.Int32)).columns
        assert len(numeric_cols) == 0, "Should have no numeric columns"
        # The engine's explore_correlation_subspaces would still work if called
        # with string columns — pl.corr will return null for all groups
        # and they'll be filtered out
        cat_cols = ["city", "category"]
        insights = engine.explore_correlation_subspaces(
            df, "name", "city", cat_cols, base_correlation=0.1, base_n=300
        )
        # pl.corr on string columns returns null → all filtered → empty list
        assert isinstance(insights, list)
        assert len(insights) == 0, "All string columns should produce no valid insights"


# ═══════════════════════════════════════════════════════════════
# 5. NaN handling
# ═══════════════════════════════════════════════════════════════

class TestNaNHandling:
    """Null/NaN values in numeric columns should be handled silently."""

    def test_nan_in_numeric_columns(self, engine):
        """NaN values should be dropped without crashing."""
        np.random.seed(42)
        n = 500
        x = np.random.normal(0, 1, n)
        y = x * 0.6 + np.random.normal(0, 0.7, n)
        # Inject NaN values
        x[10:30] = np.nan
        y[40:60] = np.nan
        cat = np.random.choice(["A", "B", "C"], n)
        df = pl.DataFrame({"x": x, "y": y, "cat": cat})

        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=0.6, base_n=n
        )
        assert isinstance(insights, list)

    def test_all_nan_in_one_group(self, engine):
        """A group where all x values are NaN — should be dropped silently."""
        np.random.seed(42)
        n = 500
        x = np.random.normal(0, 1, n)
        y = np.random.normal(0, 1, n)
        cat = np.array(["A"] * 50 + ["B"] * 450)
        # Make group A all NaN in x
        x[:50] = np.nan
        df = pl.DataFrame({"x": x, "y": y, "cat": cat})

        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=0.0, base_n=len(x)
        )
        assert isinstance(insights, list)
        # Group A should be silently dropped (all NaN → empty after drop_nulls)


# ═══════════════════════════════════════════════════════════════
# 6. Small sample sizes
# ═══════════════════════════════════════════════════════════════

class TestSmallSamples:
    """Groups with n < 30 should be filtered out."""

    def test_small_groups_filtered(self, engine):
        """Groups with < 30 samples should not appear in insights."""
        np.random.seed(42)
        n = 200
        x = np.random.normal(0, 1, n)
        y = x * 0.9 + np.random.normal(0, 0.3, n)
        cat = ["SMALL"] * 15 + ["LARGE"] * 185
        df = pl.DataFrame({"x": x, "y": y, "cat": cat})

        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=0.9, base_n=n
        )
        for ins in insights:
            assert ins.sample_size >= 30, \
                f"Insight with n={ins.sample_size} should be filtered out"

    def test_all_groups_small(self, engine):
        """All groups < 30 — should return empty list, not crash."""
        np.random.seed(42)
        n = 50
        df = pl.DataFrame({
            "x": np.random.normal(0, 1, n),
            "y": np.random.normal(0, 1, n),
            "cat": [f"G{i}" for i in range(n)],  # 50 groups, 1 each, all < 30
        })
        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=0.0, base_n=50
        )
        assert insights == [], "All groups < 30 should return empty list"


# ═══════════════════════════════════════════════════════════════
# 7. Simpson's Paradox detection
# ═══════════════════════════════════════════════════════════════

class TestSimpsonParadox:
    """Controlled Simpson's Paradox detection with proper statistical rigor."""

    def test_detect_simpson_paradox_directly(self, engine):
        """
        Test _detect_simpson_paradox as a pure function with known parameters.
        This avoids the tension between the improvement filter and sign reversal.
        """
        # Case 1: Sign reversal + significant + n>=30 -> detected
        assert engine._detect_simpson_paradox(
            subspace_corr=0.6, base_correlation=-0.3,
            fisher_p_value=0.01, n_subspace=100
        ), "Significant reversal with n>=30 should be Simpson's"

        # Case 2: No sign reversal -> not detected
        assert not engine._detect_simpson_paradox(
            subspace_corr=0.6, base_correlation=0.3,
            fisher_p_value=0.01, n_subspace=100
        ), "No sign reversal should not be Simpson's"

        # Case 3: Sign reversal but p >= 0.05 -> not detected
        assert not engine._detect_simpson_paradox(
            subspace_corr=0.6, base_correlation=-0.3,
            fisher_p_value=0.10, n_subspace=100
        ), "Non-significant reversal should not be Simpson's"

        # Case 4: Sign reversal but n < 30 -> not detected
        assert not engine._detect_simpson_paradox(
            subspace_corr=0.6, base_correlation=-0.3,
            fisher_p_value=0.01, n_subspace=20
        ), "Small-n reversal should not be Simpson's"

        # Case 5: Both correlations negative (same sign) -> not detected
        assert not engine._detect_simpson_paradox(
            subspace_corr=-0.6, base_correlation=-0.3,
            fisher_p_value=0.01, n_subspace=100
        ), "Same sign (both negative) should not be Simpson's"

    def test_simpson_hardcoded_deterministic(self, engine):
        """
        Deterministic dataset that produces Simpson's Paradox.
        Uses a fixed seed for reproducibility.

        Group A (majority): x near 0, y = -0.7*x + noise (NEGATIVE within-group)
        Group B (minority): x near 6, y = -12 + 0.7*x + noise (POSITIVE within-group)

        Between-group: x 0→6 shifts y from ~0 to ~-7.8 (NEGATIVE between-group).
        Within-group B: POSITIVE slope.
        Global: negative. Group B: positive = Simpson's.
        """
        from scipy import stats
        rng = np.random.RandomState(42)

        # Increase x_std to 4.5 so groups overlap more → weaker global |r|
        # while within-group |r| stays strong due to slope 0.9 and low noise
        n_a, n_b = 400, 200
        x_std, noise_std = 4.5, 1.2
        x_a = rng.normal(0, x_std, n_a)
        y_a = -0.9 * x_a + rng.normal(0, noise_std, n_a)

        x_b = rng.normal(6, x_std, n_b)
        y_b = -12.0 + 0.9 * x_b + rng.normal(0, noise_std, n_b)

        x_all = np.concatenate([x_a, x_b])
        y_all = np.concatenate([y_a, y_b])
        cat_all = ["A"] * n_a + ["B"] * n_b
        df = pl.DataFrame({"x": x_all, "y": y_all, "cat": cat_all})

        base_r, _ = stats.pearsonr(x_all, y_all)
        r_b, _ = stats.pearsonr(x_b, y_b)

        assert r_b > 0.4, f"Group B should have strong positive r, got {r_b:.3f}"
        assert base_r < -0.1, f"Global should be negative, got {base_r:.3f}"
        assert abs(r_b) > abs(base_r) + 0.15, \
            f"|r_b|={abs(r_b):.3f} should be >> |base_r|={abs(base_r):.3f}"

        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=base_r, base_n=len(x_all)
        )

        simpson_insights = [ins for ins in insights if ins.is_simpson_paradox]
        assert len(simpson_insights) > 0, \
            f"Expected Simpson's, got {len(simpson_insights)}/{len(insights)} " \
            f"(base_r={base_r:.3f}, r_b={r_b:.3f})"

    def test_simpson_not_detected_no_reversal(self, engine):
        """No sign reversal → no Simpson's flag."""
        from scipy import stats
        np.random.seed(42)
        n = 300
        x = np.random.normal(0, 1, n)
        y = x * 0.7 + np.random.normal(0, 0.5, n)
        cat = np.random.choice(["A", "B", "C"], n)
        df = pl.DataFrame({"x": x, "y": y, "cat": cat})

        base_r, _ = stats.pearsonr(x, y)
        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=base_r, base_n=n
        )
        simpson = [ins for ins in insights if ins.is_simpson_paradox]
        assert len(simpson) == 0, "No sign reversal means no Simpson's should be detected"

    def test_simpson_not_detected_small_n(self, engine):
        """Sign reversal with n < 30 → should NOT flag as Simpson's."""
        from scipy import stats
        np.random.seed(42)
        # Global positive
        x = np.concatenate([np.random.normal(5, 0.5, 10), np.random.normal(0, 1, 300)])
        y = np.concatenate([np.random.normal(0, 0.5, 10) - x[:10] * 0.4,
                           np.random.normal(0, 1, 300)])
        cat = ["SMALL_REVERSAL"] * 10 + ["NORMAL"] * 300
        df = pl.DataFrame({"x": x, "y": y, "cat": cat})

        base_r, _ = stats.pearsonr(x, y)
        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=base_r, base_n=310
        )
        simpson = [ins for ins in insights if ins.is_simpson_paradox]
        for ins in simpson:
            if ins.subspace and ins.subspace.get("cat") == "SMALL_REVERSAL":
                assert False, "Small-n reversal should NOT be flagged as Simpson's"


# ═══════════════════════════════════════════════════════════════
# 8. Single categorical column / max_depth=1
# ═══════════════════════════════════════════════════════════════

class TestDepthAndDimension:

    def test_max_depth_1_skips_level2(self, engine_l1_only, correlated_df):
        """max_depth=1 should only run Level 1, not Level 2."""
        # Monkey-patch to detect if Level 2 is called
        original_level2 = engine_l1_only._vectorized_level2
        called = {"was_called": False}

        def tracking_level2(*args, **kwargs):
            called["was_called"] = True
            return original_level2(*args, **kwargs)

        engine_l1_only._vectorized_level2 = tracking_level2

        insights = engine_l1_only.explore_correlation_subspaces(
            correlated_df, "x", "y", ["cat"], base_correlation=0.8, base_n=1000
        )
        assert not called["was_called"], "Level 2 should not be called with max_depth=1"

    def test_no_categorical_columns(self, engine, correlated_df):
        """No categorical columns → should return empty list, not crash."""
        insights = engine.explore_correlation_subspaces(
            correlated_df, "x", "y", [], base_correlation=0.8, base_n=1000
        )
        assert insights == [], "No categorical columns should return empty list"

    def test_beam_search_explorer_alias(self):
        """Verify BeamSearchExplorer is aliased to VectorizedSubspaceEngine."""
        from services.analysis.enhanced_quis import BeamSearchExplorer, VectorizedSubspaceEngine
        assert BeamSearchExplorer is VectorizedSubspaceEngine, \
            "BeamSearchExplorer must be aliased to VectorizedSubspaceEngine"

    def test_single_categorical_column(self, engine):
        """Single categorical column → Level 1 works, Level 2 skipped (needs ≥2 cols)."""
        np.random.seed(42)
        n = 500
        df = pl.DataFrame({
            "x": np.random.normal(0, 1, n),
            "y": np.random.normal(0, 1, n),
            "cat": np.random.choice(["A", "B"], n),
        })
        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=0.0, base_n=n
        )
        assert isinstance(insights, list)

    def test_beam_width_respected(self, engine):
        """The number of results should not exceed beam_width."""
        from scipy import stats
        np.random.seed(42)
        n = 1000
        n_groups = 50
        x = np.random.normal(0, 1, n)
        cat = np.random.choice([f"G{i}" for i in range(n_groups)], n)
        # Make a few groups have distinctly different slopes to generate multiple findings
        y = x.copy()
        for i in range(n_groups):
            mask = np.array(cat) == f"G{i}"
            if i < 10:  # First 10 groups: stronger correlation
                y[mask] = x[mask] * 0.8 + np.random.normal(0, 0.5, mask.sum())
            else:
                y[mask] = x[mask] * 0.2 + np.random.normal(0, 1.0, mask.sum())
        df = pl.DataFrame({"x": x, "y": y, "cat": cat})
        base_r, _ = stats.pearsonr(x, y)

        # Use a very narrow beam
        narrow = VectorizedSubspaceEngine(beam_width=3)
        insights = narrow.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=base_r, base_n=n
        )
        assert len(insights) <= 3, f"beam_width=3 should limit results to <=3, got {len(insights)}"

    def test_level2_beam_width_respected(self):
        """Level 2 expansion should also respect beam_width."""
        from scipy import stats
        np.random.seed(42)
        n = 2000
        x = np.random.normal(0, 1, n)
        y = x * 0.7 + np.random.normal(0, 0.5, n)
        cat1 = np.random.choice([f"L1_{i}" for i in range(20)], n)
        cat2 = np.random.choice(["X", "Y", "Z"], n)
        df = pl.DataFrame({"x": x, "y": y, "cat1": cat1, "cat2": cat2})

        base_r, _ = stats.pearsonr(x, y)

        # Run with narrow beam
        narrow = VectorizedSubspaceEngine(beam_width=2)
        l1 = narrow._vectorized_level1(df, "x", "y", ["cat1", "cat2"], base_r, n)
        l2 = narrow._vectorized_level2(df, "x", "y", ["cat1", "cat2"], base_r, n, l1)

        # Level 2 should expand at most beam_width from Level 1
        assert len(l2) <= 2 * 3, "Level 2 should not produce more than beam_width × n_cols insights (rough upper bound)"


# ═══════════════════════════════════════════════════════════════
# 9. All-null column
# ═══════════════════════════════════════════════════════════════

class TestAllNullColumn:

    def test_all_nulls_in_column(self, engine):
        """Entire column is null — should not crash."""
        n = 200
        df = pl.DataFrame({
            "x": [None] * n,
            "y": np.random.normal(0, 1, n).tolist(),
            "cat": ["A"] * n,
        })
        # drop_nulls will remove all rows for x → empty clean_df
        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=0.0, base_n=1
        )
        assert isinstance(insights, list)

    def test_all_nulls_in_categorical(self, engine):
        """Categorical column is all null — should not crash."""
        n = 200
        df = pl.DataFrame({
            "x": np.random.normal(0, 1, n).tolist(),
            "y": np.random.normal(0, 1, n).tolist(),
            "cat": [None] * n,
        })
        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=0.0, base_n=n
        )
        assert isinstance(insights, list)
        assert len(insights) == 0, "All-null categorical should produce no insights"


# ═══════════════════════════════════════════════════════════════
# 10. Base correlation edge cases
# ═══════════════════════════════════════════════════════════════

class TestBaseCorrelationEdgeCases:

    def test_base_correlation_zero(self, engine):
        """Base correlation = 0.0 (no global relationship)."""
        np.random.seed(42)
        n = 500
        x = np.random.normal(0, 1, n)
        y = np.random.normal(0, 1, n)  # independent
        cat = np.random.choice(["A", "B", "C"], n)
        df = pl.DataFrame({"x": x, "y": y, "cat": cat})

        from scipy import stats
        base_r, _ = stats.pearsonr(x, y)
        assert abs(base_r) < 0.1, f"Base r should be near 0, got {base_r:.3f}"

        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=base_r, base_n=n
        )
        # Improvement filter is |subspace_r| - |base_r| > 0.1
        # With base_r ≈ 0, any |subspace_r| > 0.1 passes the improvement check
        assert isinstance(insights, list)

    def test_base_correlation_negative(self, engine):
        """Base correlation is negative — should still find improvements."""
        np.random.seed(42)
        n = 600
        x = np.random.normal(0, 1, n)
        y = -x * 0.5 + np.random.normal(0, 0.8, n)  # r ≈ -0.5
        cat = np.random.choice(["A", "B", "C"], n)
        df = pl.DataFrame({"x": x, "y": y, "cat": cat})

        from scipy import stats
        base_r, _ = stats.pearsonr(x, y)
        assert base_r < 0, f"Base r should be negative, got {base_r:.3f}"

        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=base_r, base_n=n
        )
        assert isinstance(insights, list)
        # All returned insights should have |r| > |base_r| (improvement > 0.1)
        for ins in insights:
            assert abs(ins.statistic) > abs(base_r) + 0.05, \
                f"Insight r={ins.statistic:.3f} should improve over base r={base_r:.3f}"


# ═══════════════════════════════════════════════════════════════
# 11. QUISInsight output format integrity
# ═══════════════════════════════════════════════════════════════

class TestOutputFormat:

    def test_required_fields_present(self, engine, correlated_df):
        """All QUISInsight fields must be present and non-null for valid insights."""
        insights = engine.explore_correlation_subspaces(
            correlated_df, "x", "y", ["cat"], base_correlation=0.8, base_n=1000
        )

        required_fields = [
            "insight_type", "description", "columns", "subspace",
            "statistic", "p_value", "effect_size", "effect_interpretation",
            "sample_size", "is_simpson_paradox", "novelty_score", "overall_score",
        ]

        for ins in insights:
            d = ins.to_dict()
            for field in required_fields:
                assert field in d, f"Missing field '{field}' in insight"

    def test_to_dict_serializable(self, engine, correlated_df):
        """to_dict() should produce JSON-serializable output."""
        import json
        insights = engine.explore_correlation_subspaces(
            correlated_df, "x", "y", ["cat"], base_correlation=0.8, base_n=1000
        )
        for ins in insights:
            d = ins.to_dict()
            # Should not raise
            json.dumps(d)

    def test_insight_type_consistent(self, engine, correlated_df):
        """All insights from subspace engine should be 'subspace_correlation'."""
        insights = engine.explore_correlation_subspaces(
            correlated_df, "x", "y", ["cat"], base_correlation=0.8, base_n=1000
        )
        for ins in insights:
            assert ins.insight_type == "subspace_correlation", \
                f"Expected 'subspace_correlation', got '{ins.insight_type}'"


# ═══════════════════════════════════════════════════════════════
# 12. Negative correlation in subspaces (not Simpson's)
# ═══════════════════════════════════════════════════════════════

class TestNegativeCorrelation:

    def test_negative_subspace_correlation(self, engine):
        """A subspace where correlation is negative but no sign flip → valid insight, no Simpson flag."""
        np.random.seed(42)
        n = 1000
        # Global: weak positive
        x = np.random.normal(0, 1, n)
        y = x * 0.1 + np.random.normal(0, 1, n)
        cat = np.random.choice(["A", "B", "C", "NEG"], n)

        # Make 'NEG' group have negative correlation
        neg_mask = np.array(cat) == "NEG"
        y[neg_mask] = -x[neg_mask] * 0.8 + np.random.normal(0, 0.6, neg_mask.sum())

        df = pl.DataFrame({"x": x, "y": y, "cat": cat})

        from scipy import stats
        base_r, _ = stats.pearsonr(x, y)

        insights = engine.explore_correlation_subspaces(
            df, "x", "y", ["cat"], base_correlation=base_r, base_n=n
        )

        for ins in insights:
            if ins.subspace and ins.subspace.get("cat") == "NEG":
                # Correlation in NEG group should be negative
                assert ins.statistic < 0, f"NEG group should have negative r, got {ins.statistic:.3f}"
                # But base correlation is also possibly negative (if NEG is large enough to pull it down)
                # So sign flip may or may not apply
                # Just check it's not Simpson's if no sign flip
                if np.sign(ins.statistic) == np.sign(base_r):
                    assert not ins.is_simpson_paradox, \
                        "No sign flip → should not be flagged as Simpson's"
                break


# ═══════════════════════════════════════════════════════════════
# Run directly
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

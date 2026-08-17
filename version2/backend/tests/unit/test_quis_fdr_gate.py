import asyncio

import numpy as np
import polars as pl
import pytest

from agents.quis.quis_graph import (
    _insight_family,
    _check_insight_stability,
    _build_retry_question,
    fdr_gate_node,
    critic_node,
)


class TestInsightFamily:
    def test_family_mapping(self):
        assert _insight_family("correlation") == "correlation"
        assert _insight_family("subspace_correlation") == "correlation"
        assert _insight_family("group_comparison") == "comparison"
        assert _insight_family("trend") == "trend"
        assert _insight_family("anomaly") == "other"


class TestFdrGate:
    def _make_insight(self, run_id, family="correlation", p=0.01):
        return {
            "insight_type": "correlation",
            "description": f"insight {run_id}",
            "columns": ["a", "b"],
            "statistic": 0.5,
            "p_value": p,
            "effect_size": 0.25,
            "sample_size": 200,
            "run_id": run_id,
            "family": family,
        }

    def test_drops_non_significant_after_bh(self):
        raw = [
            {"run_id": "q0-i0", "family": "correlation", "p_value": 0.01},
            {"run_id": "q0-i1", "family": "correlation", "p_value": 0.02},
            {"run_id": "q0-i2", "family": "correlation", "p_value": 0.40},
            {"run_id": "q1-i0", "family": "trend", "p_value": 0.001},
        ]
        approved = [
            self._make_insight("q0-i0"),
            self._make_insight("q0-i2", p=0.40),
            self._make_insight("q1-i0", family="trend", p=0.001),
            {**self._make_insight("legacy"), "run_id": None},  # pass-through
        ]
        state = {"raw_insight_pvalues": raw, "approved_insights": approved}

        result = asyncio.run(fdr_gate_node(state))

        kept_ids = {i.get("run_id") for i in result["approved_insights"]}
        assert kept_ids == {"q0-i0", "q1-i0", None}
        assert result["fdr_dropped_count"] == 1
        assert "q0-i2" not in kept_ids

    def test_empty_approved_is_safe(self):
        state = {"raw_insight_pvalues": [{"run_id": "x", "family": "correlation", "p_value": 0.01}], "approved_insights": []}
        result = asyncio.run(fdr_gate_node(state))
        assert result["approved_insights"] == []
        assert result["fdr_dropped_count"] == 0

    def test_no_pvalues_is_safe(self):
        state = {"raw_insight_pvalues": [], "approved_insights": [self._make_insight("a")]}
        result = asyncio.run(fdr_gate_node(state))
        assert len(result["approved_insights"]) == 1
        assert result["fdr_dropped_count"] == 0


class TestRetryQuestion:
    @pytest.fixture
    def df(self):
        rng = np.random.default_rng(1)
        n = 120
        return pl.DataFrame(
            {
                "revenue": rng.normal(100, 20, n),
                "cost": rng.normal(50, 10, n),
                "profit": rng.normal(30, 8, n),
                "region": np.array(["N", "S", "E", "W"] * (n // 4)),
                "segment": np.array(["A", "B", "C"] * (n // 3)),
                "channel": np.array(["Online", "Retail"] * (n // 2)),
                "customer_id": np.arange(n),
            }
        )

    def _q(self, qtype="correlation", target=None, filt=None):
        return {
            "question": "base question",
            "question_type": qtype,
            "target_columns": target or ["revenue", "cost"],
            "filter_column": filt,
            "priority": 0.9,
        }

    def test_correlation_decomposes_to_subspace(self, df):
        q = self._q()
        out = _build_retry_question(q, df, retry_index=0)
        assert out is not None
        assert out["question_type"] == "subspace"
        assert out["filter_column"] in {"region", "segment", "channel"}
        assert out["target_columns"] == ["revenue", "cost"]

    def test_sequential_retries_differ(self, df):
        # Deterministic builder + rotation by retry_index must produce DIFFERENT
        # questions on consecutive retries (regression: same-input retry).
        q = self._q()
        r1 = _build_retry_question(q, df, retry_index=0)
        r2 = _build_retry_question(q, df, retry_index=1)
        assert r1 is not None and r2 is not None
        assert r1["filter_column"] != r2["filter_column"]

    def test_subspace_rotates_filter(self, df):
        q = self._q(qtype="subspace", filt="region")
        r1 = _build_retry_question(q, df, retry_index=0)
        r2 = _build_retry_question(q, df, retry_index=1)
        assert r1 is not None and r2 is not None
        assert r1["filter_column"] != r2["filter_column"]
        assert r2["filter_column"] != "region"

    def test_comparison_rotates_numeric_target(self, df):
        q = self._q(qtype="comparison", target=["revenue"], filt="region")
        r1 = _build_retry_question(q, df, retry_index=0)
        r2 = _build_retry_question(q, df, retry_index=1)
        assert r1 is not None and r2 is not None
        assert r1["target_columns"] != r2["target_columns"]
        assert set(r1["target_columns"] + r2["target_columns"]) <= {"revenue", "cost", "profit"}

    def test_id_columns_never_used_as_filter(self, df):
        q = self._q()
        out = _build_retry_question(q, df, retry_index=0)
        assert out["filter_column"] != "customer_id"


class TestStabilityCheck:
    @pytest.fixture
    def df(self):
        rng = np.random.default_rng(42)
        n = 200
        a = np.arange(n, dtype=float)
        b = 2.0 * a + rng.normal(0, 10, n)
        t = np.arange(n, dtype=float)
        v = 0.1 * t + rng.normal(0, 2, n)
        g = np.array(["A", "B"] * (n // 2))
        base = np.where(g == "A", 10.0, 20.0)
        w = base + rng.normal(0, 0.5, n)
        return pl.DataFrame({"a": a, "b": b, "t": t, "v": v, "g": g, "w": w})

    class _Ins:
        def __init__(self, itype, cols):
            self.insight_type = itype
            self.columns = cols

    def test_strong_correlation_replicates(self, df):
        assert _check_insight_stability(df, self._Ins("correlation", ["a", "b"])) is True

    def test_strong_trend_replicates(self, df):
        assert _check_insight_stability(df, self._Ins("trend", ["v", "t"])) is True

    def test_group_comparison_replicates(self, df):
        assert _check_insight_stability(df, self._Ins("group_comparison", ["w", "g"])) is True

    def test_subspace_skipped(self, df):
        assert _check_insight_stability(df, self._Ins("subspace_correlation", ["a", "b"])) is None

    def test_noise_never_raises(self, df):
        rng = np.random.default_rng(7)
        df2 = df.with_columns(pl.Series("c", rng.normal(0, 1, len(df))))
        result = _check_insight_stability(df2, self._Ins("correlation", ["a", "c"]))
        assert result in (True, False, None)


class TestCriticGates:
    def _state(self, insights):
        return {
            "execution_result": "x",
            "current_insights": insights,
            "rejected_insights": [],
            "data_schema": None,
            "error_count": 0,
            "current_question_idx": 0,
            "iteration_count": 1,
        }

    def _insight(self, **overrides):
        base = {
            "insight_type": "correlation",
            "description": "r test",
            "columns": ["a", "b"],
            "statistic": 0.5,
            "p_value": 0.01,
            "effect_size": 0.25,
            "effect_interpretation": "moderate",
            "sample_size": 200,
            "is_simpson_paradox": False,
            "novelty_score": 0.5,
            "overall_score": 0.5,
        }
        base.update(overrides)
        return base

    def test_ci_includes_zero_rejected(self):
        state = self._state([self._insight(confidence_interval=[-0.5, 0.5])])
        result = asyncio.run(critic_node(state))
        assert result["critique"]["passed"] is False
        assert "ci_includes_zero" in result["rejected_insights"][0]["reason"]

    def test_unstable_finding_rejected(self):
        state = self._state([self._insight(stability_ok=False)])
        result = asyncio.run(critic_node(state))
        assert result["critique"]["passed"] is False
        assert "unstable_finding" in result["rejected_insights"][0]["reason"]

    def test_clean_insight_passes(self):
        state = self._state([self._insight()])
        result = asyncio.run(critic_node(state))
        assert result["critique"]["passed"] is True
        assert len(result["current_insights"]) == 1

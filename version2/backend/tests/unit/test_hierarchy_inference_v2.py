"""
Unit tests for Hierarchy Inference v2 — the tiered, Act-then-Validate ontology.

Proves:
  1. Verification is DETERMINISTIC and blocks bad proposals:
     - cardinality ordering violation → rejected
     - value-containment violation (child → many parents) → rejected
  2. Deterministic pass → validated, confidence 1.0, no LLM.
  3. LLM pass: proposal only becomes an assumption after deterministic
     verification passes; confident proposals are validated, weaker are
     provisional; LLM failure degrades to [] (deterministic is the floor).
  4. Drift: a finalized hierarchy that stops verifying reverts to provisional.
  5. effective_hierarchies: validated first, rejected excluded.
"""

import asyncio

import polars as pl

from services.profiling.models import (
    CardinalityInfo,
    ColumnQualityInfo,
    DatasetInfo,
    RawColumnProfile,
    RawProfilingResult,
)
from services.intelligence.hierarchy_inference_v2 import (
    effective_hierarchies,
    run_deterministic_pass,
    run_llm_pass,
    verify_assumption,
    verify_hierarchy_candidate,
)
from services.semantic.assumption_store import (
    PROVISIONAL,
    REJECTED,
    SOURCE_DETERMINISTIC,
    SOURCE_LLM,
    TYPE_HIERARCHY,
    VALIDATED,
    new_assumption,
)


def _run(coro):
    return asyncio.run(coro)


def _col(name, unique, total, nulls=0, dtype="Utf8", samples=None):
    return RawColumnProfile(
        name=name,
        dtype=dtype,
        cardinality=CardinalityInfo(
            unique_count=unique,
            total_count=total,
            null_count=nulls,
            cardinality_ratio=unique / max(total, 1),
            cardinality_level="low" if unique <= 50 else "medium",
        ),
        stats=None,
        sample_values=samples or [],
        top_values=[],
        patterns=[],
        quality=ColumnQualityInfo(),
    )


def _result(columns, row_count=1000):
    return RawProfilingResult(
        dataset=DatasetInfo(row_count=row_count, column_count=len(columns)),
        columns=columns,
    )


# A clean geo chain + a segment chain, with true functional dependencies.
_GEO_DF = pl.DataFrame(
    {
        "country": ["US", "US", "UK", "UK", "IN"],
        "state": ["NY", "CA", "EN", "EN", "MH"],
        "city": ["NYC", "SF", "London", "Manchester", "Mumbai"],
        "segment": ["ent", "ent", "sme", "sme", "sme"],
        "sub_segment": ["ent-a", "ent-b", "sme-x", "sme-y", "sme-z"],
    }
)


def _geo_result():
    return _result(
        [
            _col("country", 3, 5, samples=["US", "UK", "IN"]),
            _col("state", 4, 5, samples=["NY", "CA", "EN"]),
            _col("city", 5, 5, samples=["NYC", "SF", "London"]),
            _col("segment", 2, 5, samples=["ent", "sme"]),
            _col("sub_segment", 5, 5, samples=["ent-a", "sme-x"]),
            _col("revenue", 100, 5, dtype="Int64"),
        ],
        row_count=5,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Deterministic verification
# ─────────────────────────────────────────────────────────────────────────────


class TestVerification:
    def test_valid_chain_passes_with_high_confidence(self):
        ok, conf, evidence = verify_hierarchy_candidate(_geo_result(), _GEO_DF, ["country", "state", "city"])
        assert ok is True
        assert conf >= 0.85
        assert evidence["cardinality_order_ok"] is True
        assert evidence["containment_ok"] is True

    def test_cardinality_violation_rejected(self):
        # child has FEWER uniques than parent → ordering violated
        result = _result([_col("region", 50, 100), _col("country", 3, 100)])
        ok, conf, evidence = verify_hierarchy_candidate(result, None, ["region", "country"])
        assert ok is False
        assert "cardinality" in evidence.get("reason", "")

    def test_containment_violation_rejected(self):
        # a child value maps to TWO parents → not a hierarchy
        df = pl.DataFrame({"parent": ["A", "A", "B"], "child": ["x", "x", "x"]})
        result = _result([_col("parent", 2, 3), _col("child", 1, 3)])
        ok, conf, evidence = verify_hierarchy_candidate(result, df, ["parent", "child"])
        assert ok is False
        assert "multiple parents" in evidence.get("reason", "")

    def test_missing_column_rejected(self):
        ok, _, evidence = verify_hierarchy_candidate(_geo_result(), _GEO_DF, ["country", "nope"])
        assert ok is False
        assert "not in profile" in evidence.get("reason", "")

    def test_no_df_still_verifies_cardinality(self):
        # Without a df, containment is unknown → partial credit, still usable.
        ok, conf, evidence = verify_hierarchy_candidate(_geo_result(), None, ["country", "state", "city"])
        assert ok is True
        assert evidence["containment_ok"] is None
        assert 0.45 <= conf < 0.9


# ─────────────────────────────────────────────────────────────────────────────
# 2. Deterministic pass — auto-validated, no LLM
# ─────────────────────────────────────────────────────────────────────────────


class TestDeterministicPass:
    def test_pattern_hit_becomes_validated_confidence_1(self):
        assumptions = run_deterministic_pass(_geo_result(), _GEO_DF, "ds-1", "ws-A")
        geo = [a for a in assumptions if "country" in a.definition.get("columns", [])]
        assert geo, "country/state/city pattern must be detected"
        a = geo[0]
        assert a.state == VALIDATED
        assert a.confidence == 1.0
        assert a.source == SOURCE_DETERMINISTIC
        assert a.type == TYPE_HIERARCHY
        # Order preserved: parent → child
        assert a.definition["columns"] == ["country", "state", "city"]

    def test_deterministic_pass_never_llm(self):
        assumptions = run_deterministic_pass(_geo_result(), _GEO_DF, "ds-1", "ws-A")
        assert all(a.source == SOURCE_DETERMINISTIC for a in assumptions)


# ─────────────────────────────────────────────────────────────────────────────
# 3. LLM pass — proposes, determinism verifies
# ─────────────────────────────────────────────────────────────────────────────


class _FakeLLM:
    def __init__(self, response):
        self._response = response

    async def call(self, **kwargs):
        return self._response


class TestLLMPass:
    def test_valid_proposal_accepted_and_validated(self):
        llm = _FakeLLM(
            {
                "hierarchies": [
                    {"columns": ["segment", "sub_segment"], "reason": "plan rollup"},
                ]
            }
        )
        assumptions = _run(
            run_llm_pass(_geo_result(), _GEO_DF, "ds-1", "ws-A", llm_caller=llm)
        )
        assert len(assumptions) == 1
        a = assumptions[0]
        assert a.state == VALIDATED  # cardinality + containment + naming all strong
        assert a.source == SOURCE_LLM
        assert a.definition["columns"] == ["segment", "sub_segment"]

    def test_bad_proposal_rejected_by_verification(self):
        # sub_segment → segment is the real direction; reversed violates cardinality.
        llm = _FakeLLM(
            {
                "hierarchies": [
                    {"columns": ["sub_segment", "segment"], "reason": "wrong order"},
                ]
            }
        )
        assumptions = _run(
            run_llm_pass(_geo_result(), _GEO_DF, "ds-1", "ws-A", llm_caller=llm)
        )
        assert assumptions == []

    def test_nonexistent_columns_filtered(self):
        llm = _FakeLLM(
            {
                "hierarchies": [
                    {"columns": ["made_up", "segment"], "reason": "hallucinated"},
                ]
            }
        )
        assumptions = _run(
            run_llm_pass(_geo_result(), _GEO_DF, "ds-1", "ws-A", llm_caller=llm)
        )
        assert assumptions == []

    def test_llm_failure_degrades_to_empty(self):
        class _Boom:
            async def call(self, **kwargs):
                raise RuntimeError("provider down")

        assumptions = _run(
            run_llm_pass(_geo_result(), _GEO_DF, "ds-1", "ws-A", llm_caller=_Boom())
        )
        assert assumptions == []

    def test_covered_columns_not_reproposed(self):
        llm = _FakeLLM(
            {
                "hierarchies": [
                    {"columns": ["country", "state", "city"], "reason": "already known"},
                ]
            }
        )
        assumptions = _run(
            run_llm_pass(
                _geo_result(), _GEO_DF, "ds-1", "ws-A",
                llm_caller=llm, covered_columns={"country", "state", "city"},
            )
        )
        assert assumptions == []


# ─────────────────────────────────────────────────────────────────────────────
# 4. Drift — finalize is not permanent
# ─────────────────────────────────────────────────────────────────────────────


class TestDrift:
    def test_assumption_that_stops_verifying_reverts(self):
        assumption = new_assumption(
            dataset_id="ds-1", workspace_id="ws-A", type=TYPE_HIERARCHY,
            definition={"columns": ["segment", "sub_segment"]},
            confidence=0.99, evidence={}, state=VALIDATED, source=SOURCE_LLM,
        )
        # Same df → still verifies.
        ok, conf, _ = verify_assumption(_geo_result(), _GEO_DF, assumption)
        assert ok is True
        assert conf >= 0.85

        # NEW data breaks the containment: one sub_segment now maps to 2 segments.
        bad_df = pl.DataFrame(
            {
                "segment": ["ent", "sme", "sme"],
                "sub_segment": ["ent-a", "ent-a", "sme-x"],
            }
        )
        bad_result = _result(
            [_col("segment", 2, 3), _col("sub_segment", 2, 3)], row_count=3
        )
        ok, conf, evidence = verify_assumption(bad_result, bad_df, assumption)
        assert ok is False
        assert "multiple parents" in evidence.get("reason", "")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Effective hierarchies for consumption
# ─────────────────────────────────────────────────────────────────────────────


class TestEffectiveHierarchies:
    def _assumption(self, columns, state, confidence):
        return new_assumption(
            dataset_id="ds-1", workspace_id="ws-A", type=TYPE_HIERARCHY,
            definition={"columns": columns, "hierarchy_type": "suggested"},
            confidence=confidence, evidence={}, state=state, source=SOURCE_LLM,
        )

    def test_validated_first_provisional_second(self):
        assumptions = [
            self._assumption(["segment", "sub_segment"], PROVISIONAL, 0.62),
            self._assumption(["country", "state"], VALIDATED, 0.99),
        ]
        eff = effective_hierarchies(assumptions)
        assert [e["state"] for e in eff] == [VALIDATED, PROVISIONAL]
        assert eff[0]["columns"] == ["country", "state"]

    def test_rejected_excluded(self):
        assumptions = [
            self._assumption(["segment", "sub_segment"], REJECTED, 0.5),
            self._assumption(["country", "state"], VALIDATED, 0.99),
        ]
        eff = effective_hierarchies(assumptions)
        assert len(eff) == 1
        assert eff[0]["columns"] == ["country", "state"]

    def test_carries_state_and_evidence_for_ui_flagging(self):
        assumptions = [self._assumption(["a", "b"], PROVISIONAL, 0.6)]
        eff = effective_hierarchies(assumptions)
        assert eff[0]["state"] == PROVISIONAL
        assert "assumption_id" in eff[0]
        assert "confidence" in eff[0]

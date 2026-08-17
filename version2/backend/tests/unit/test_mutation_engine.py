"""
Unit tests for the cleaning mutation engine's pure decision functions.

Covers the two-phase mutation layer (services/cleaning/mutation_engine.py):

    - Approve a deterministic rename → no-op (already applied), state confirmed
    - Reject a deterministic rename → column actually renamed back
    - Restore a reverted rename → re-applied forward
    - Approve an AI proposal (remove/merge) → column actually dropped
    - Reject an AI proposal (never applied) → no-op, state rejected
    - Reject an already-applied destructive op → guarded ValueError
    - override_to renames the real parquet column (tolerates case drift)
    - Collision guards warn and no-op instead of corrupting data

Pure logic only — no MongoDB, no file I/O.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import polars as pl
import pytest

from services.cleaning.mutation_engine import (
    entry_state,
    execute_mutation,
    is_ai_proposal,
)


# ── Deterministic rename semantics ─────────────────────────────────────────


class TestDeterministicRenames:
    def _df(self):
        # Realistic post-pipeline dataframe: columns already normalized
        return pl.DataFrame(
            {"customer_name": ["a", "b"], "shirts": ["M", "L"], "revenue": [10, 20]}
        )

    RENAME = {"original_name": "Customer Name", "normalized_name": "customer_name"}

    def test_approve_is_noop_and_confirms(self):
        df = self._df()
        out, entry = execute_mutation(df, dict(self.RENAME), True)
        assert out.columns == df.columns
        assert entry["state"] == "confirmed"
        assert entry["approved"] is True

    def test_reject_renames_column_back(self):
        df = self._df()
        warnings = []
        out, entry = execute_mutation(df, dict(self.RENAME), False, warnings=warnings)
        assert "Customer Name" in out.columns
        assert "customer_name" not in out.columns
        assert entry["state"] == "reverted"
        assert entry["approved"] is False

    def test_restore_reapplies_rename_forward(self):
        df = self._df()
        reverted_df, reverted_entry = execute_mutation(df, dict(self.RENAME), False)
        assert "Customer Name" in reverted_df.columns

        restored_df, entry = execute_mutation(
            reverted_df, reverted_entry, True
        )
        assert "customer_name" in restored_df.columns
        assert "Customer Name" not in restored_df.columns
        assert entry["state"] == "confirmed"

    def test_revert_restore_revert_roundtrip(self):
        df = self._df()
        d1, e1 = execute_mutation(df, dict(self.RENAME), False)
        d2, e2 = execute_mutation(d1, e1, True)
        d3, e3 = execute_mutation(d2, e2, False)
        assert "Customer Name" in d3.columns
        assert e3["state"] == "reverted"

    def test_collision_guard_warns_and_noops(self):
        df = pl.DataFrame({"Customer Name": ["x"], "customer_name": ["y"]})
        warnings = []
        out, _ = execute_mutation(df, dict(self.RENAME), False, warnings=warnings)
        assert out.columns == df.columns
        assert any("already exists" in w for w in warnings)

    def test_rename_back_when_column_missing_warns(self):
        df = pl.DataFrame({"revenue": [10]})
        warnings = []
        out, _ = execute_mutation(df, dict(self.RENAME), False, warnings=warnings)
        assert out.columns == df.columns
        assert any("not found" in w for w in warnings)


# ── AI proposals (merge / remove) ──────────────────────────────────────────


class TestAiProposals:
    def test_remove_drops_column(self):
        df = pl.DataFrame({"customer_name": ["a"], "shirts": ["M"], "revenue": [10]})
        out, entry = execute_mutation(
            df, {"action_type": "remove", "target_columns": ["shirts"], "approved": None}, True
        )
        assert "shirts" not in out.columns
        assert entry["state"] == "applied"
        assert entry["approved"] is True

    def test_merge_drops_duplicate_columns(self):
        df = pl.DataFrame({"a": [1, 2], "b": [1, 2], "c": [3, 4]})
        out, entry = execute_mutation(
            df, {"action_type": "merge", "target_columns": ["a", "b"], "approved": None}, True
        )
        assert out.columns == ["a", "c"]
        assert entry["state"] == "applied"

    def test_reject_proposal_is_noop(self):
        df = pl.DataFrame({"customer_name": ["a"], "shirts": ["M"]})
        out, entry = execute_mutation(
            df, {"action_type": "remove", "target_columns": ["shirts"], "approved": None}, False
        )
        assert out.columns == df.columns
        assert entry["state"] == "rejected"
        assert entry["approved"] is False

    def test_reject_applied_remove_raises(self):
        df = pl.DataFrame({"customer_name": ["a"], "shirts": ["M"]})
        with pytest.raises(ValueError, match="already been applied"):
            execute_mutation(
                df,
                {"action_type": "remove", "target_columns": ["shirts"], "approved": True},
                False,
            )

    def test_reapprove_rejected_proposal_executes(self):
        df = pl.DataFrame({"customer_name": ["a"], "shirts": ["M"]})
        _, rejected = execute_mutation(
            df, {"action_type": "remove", "target_columns": ["shirts"], "approved": None}, False
        )
        out, entry = execute_mutation(df, rejected, True)
        assert "shirts" not in out.columns
        assert entry["state"] == "applied"


# ── Overrides ──────────────────────────────────────────────────────────────


class TestOverrides:
    def test_override_renames_actual_column(self):
        # Manifest says 'revenue' but the parquet column drifted to 'Revenue'
        df = pl.DataFrame({"Revenue": [10, 20]})
        warnings = []
        out, entry = execute_mutation(
            df,
            {"original_name": "Revenue", "normalized_name": "revenue"},
            True,
            override_to="net_revenue",
            warnings=warnings,
        )
        assert "net_revenue" in out.columns
        assert "Revenue" not in out.columns
        assert entry["state"] == "applied"
        assert entry["normalized_name"] == "net_revenue"

    def test_override_collision_warns_and_noops(self):
        df = pl.DataFrame({"revenue": [10], "net_revenue": [20]})
        warnings = []
        out, _ = execute_mutation(
            df,
            {"original_name": "Revenue", "normalized_name": "revenue"},
            True,
            override_to="net_revenue",
            warnings=warnings,
        )
        assert out.columns == df.columns
        assert any("already exists" in w for w in warnings)


# ── Reset + state derivation ───────────────────────────────────────────────


class TestResetAndState:
    def test_reset_returns_to_proposed(self):
        df = pl.DataFrame({"shirts": ["M"]})
        out, entry = execute_mutation(
            df, {"action_type": "remove", "target_columns": ["shirts"], "approved": None}, None
        )
        assert out.columns == df.columns
        assert entry["approved"] is None
        assert entry["state"] == "proposed"

    def test_entry_state_derivations(self):
        assert entry_state({"action_type": "remove", "approved": None}) == "proposed"
        assert entry_state({"action_type": "remove", "approved": True}) == "applied"
        assert entry_state({"action_type": "remove", "approved": False}) == "rejected"
        assert entry_state({"original_name": "a", "normalized_name": "b"}) == "applied_silently"
        assert entry_state({"original_name": "a", "normalized_name": "b", "approved": True}) == "confirmed"
        assert entry_state({"original_name": "a", "normalized_name": "b", "approved": False}) == "reverted"

    def test_is_ai_proposal(self):
        assert is_ai_proposal({"action_type": "remove"}) is True
        assert is_ai_proposal({"action_type": "merge"}) is True
        assert is_ai_proposal({"original_name": "a", "normalized_name": "b"}) is False

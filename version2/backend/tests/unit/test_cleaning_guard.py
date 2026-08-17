import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from services.chat.cleaning_guard import (
    classify_cleaning_state,
    build_block_message,
    build_warning_note,
)


def _entry(action_type, approved=None, target_columns=None, reasoning=None):
    return {
        "action_type": action_type,
        "approved": approved,
        "target_columns": target_columns or [],
        "reasoning": reasoning,
    }


class TestClassifyCleaningState:
    def test_empty_manifest_never_blocks(self):
        state = classify_cleaning_state([])
        assert state.pending_critical == 0
        assert state.pending_cosmetic == 0
        assert not state.block
        assert not state.has_warning

    def test_pending_merge_blocks(self):
        state = classify_cleaning_state([_entry("merge")])
        assert state.pending_critical == 1
        assert state.block

    def test_pending_remove_blocks(self):
        state = classify_cleaning_state([_entry("remove", target_columns=["TOTAL"])])
        assert state.block
        assert "TOTAL" in state.critical_descriptions[0]

    def test_pending_drop_blocks(self):
        state = classify_cleaning_state([_entry("drop")])
        assert state.block

    def test_pending_rename_warns_but_does_not_block(self):
        state = classify_cleaning_state(
            [_entry("rename", target_columns=["Customer Name"])]
        )
        assert state.pending_critical == 0
        assert state.pending_cosmetic == 1
        assert not state.block
        assert state.has_warning

    def test_settled_entries_ignored(self):
        manifest = [
            _entry("merge", approved=True),   # applied — settled
            _entry("remove", approved=False),  # rejected — settled
            _entry("rename", approved=True),   # confirmed — settled
        ]
        state = classify_cleaning_state(manifest)
        assert state.pending_critical == 0
        assert state.pending_cosmetic == 0
        assert not state.block
        assert not state.has_warning

    def test_mixed_pending_counts(self):
        manifest = [
            _entry("rename"),
            _entry("merge"),
            _entry("drop"),
            _entry("rename"),
        ]
        state = classify_cleaning_state(manifest)
        assert state.pending_critical == 2
        assert state.pending_cosmetic == 2
        assert state.block

    def test_unknown_action_type_treated_as_cosmetic(self):
        state = classify_cleaning_state([_entry("something_new")])
        assert state.pending_critical == 0
        assert state.pending_cosmetic == 1
        assert not state.block


class TestGuardMessages:
    def test_block_message_mentions_review(self):
        state = classify_cleaning_state([_entry("merge", target_columns=["Shirts"])])
        msg = build_block_message(state)
        assert "1 cleaning suggestion" in msg
        assert "Data Briefing" in msg

    def test_block_message_plural(self):
        state = classify_cleaning_state([_entry("merge"), _entry("drop")])
        msg = build_block_message(state)
        assert "2 cleaning suggestions" in msg

    def test_warning_note_mentions_renames(self):
        state = classify_cleaning_state([_entry("rename")])
        note = build_warning_note(state)
        assert "1 column rename suggestion" in note
        assert "Data Briefing" in note


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

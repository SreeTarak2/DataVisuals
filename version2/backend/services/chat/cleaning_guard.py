"""
Cleaning Guard — enforce "no analysis on dirty data" (Principle #0).

Pure logic, no I/O. Classifies a cleaning manifest into pending-critical
(number-changing) and pending-cosmetic (label-only) actions so the chat
pipeline can block or warn accordingly.

Critical actions are those that change the *numbers* an analyst would
query: dropping/removing rows or columns, and merging category values.
Cosmetic actions are column renames (label-only — they don't change values).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

# Actions that change query results — block chat until reviewed.
# type_coercion (string → date) and merge_values (fuzzy category merging)
# change how filters, aggregations, and time-series queries behave, so they
# block too.
CRITICAL_ACTION_TYPES = frozenset(
    {"drop", "remove", "merge", "type_coercion", "merge_values", "unpivot_columns"}
)

# Actions that only relabel columns — warn, never block.
COSMETIC_ACTION_TYPES = frozenset({"rename"})


@dataclass
class CleaningGuardState:
    pending_critical: int = 0
    pending_cosmetic: int = 0
    critical_descriptions: List[str] = field(default_factory=list)
    cosmetic_descriptions: List[str] = field(default_factory=list)

    @property
    def block(self) -> bool:
        """Number-changing cleaning is pending — refuse to analyze."""
        return self.pending_critical > 0

    @property
    def has_warning(self) -> bool:
        """Only cosmetic actions pending — answer, but flag the renames."""
        return not self.block and self.pending_cosmetic > 0


def _describe_action(entry: Dict[str, Any]) -> str:
    """Short human description of a manifest action for guard messages."""
    action_type = entry.get("action_type") or "unknown"
    target = entry.get("target_columns") or []
    if isinstance(target, str):
        target = [target]
    if target:
        cols = ", ".join(str(c) for c in target[:3])
        return f"{action_type} ({cols})"
    reasoning = entry.get("reasoning")
    if reasoning:
        return f"{action_type}: {str(reasoning)[:80]}"
    return action_type


def classify_cleaning_state(manifest: List[Dict[str, Any]]) -> CleaningGuardState:
    """Classify a cleaning manifest into critical vs cosmetic pending actions.

    Only unreviewed entries (``approved is None``) are actionable:
    - Deterministic renames are ``approved: None`` until reviewed.
    - AI proposals (merge/remove) are ``approved: None`` until decided.
    Settled entries (approved True/False) are ignored.
    """
    state = CleaningGuardState()
    for entry in manifest or []:
        if entry.get("approved") is not None:
            continue
        action_type = (entry.get("action_type") or "rename").lower()
        if action_type in CRITICAL_ACTION_TYPES:
            state.pending_critical += 1
            state.critical_descriptions.append(_describe_action(entry))
        else:
            state.pending_cosmetic += 1
            state.cosmetic_descriptions.append(_describe_action(entry))
    return state


def build_block_message(state: CleaningGuardState) -> str:
    """Message shown when chat refuses to analyze dirty data."""
    n = state.pending_critical
    examples = state.critical_descriptions[:3]
    detail = "\n".join(f"• {e}" for e in examples) if examples else ""
    suffix = "\n\n" + detail if detail else ""
    return (
        f"Before I can analyze this data, {n} cleaning suggestion"
        f"{'s' if n != 1 else ''} that would change your numbers still need your "
        f"review — like removing rows, merging categories, or dropping columns.{suffix}\n\n"
        "Please review and apply them on the Data Briefing page first, "
        "then I'll answer from data you've approved."
    )


def build_warning_note(state: CleaningGuardState) -> str:
    """Note appended to an answer when only cosmetic (rename) actions are pending."""
    n = state.pending_cosmetic
    return (
        f"\n\nNote: {n} column rename suggestion{'s' if n != 1 else ''} "
        "are still pending review on the Data Briefing page — column labels "
        "may change once you review them."
    )


__all__ = [
    "CleaningGuardState",
    "classify_cleaning_state",
    "build_block_message",
    "build_warning_note",
    "CRITICAL_ACTION_TYPES",
    "COSMETIC_ACTION_TYPES",
]

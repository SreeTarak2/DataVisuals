"""
Progressive Learning System
===========================

Tracks which charts, KPIs, and insights users interact with, then uses
that signal to intelligently pre-compute what matters to them.

Architecture
------------
1. SignalCollector   — receives raw interaction events from all surfaces
                      (dashboard, charts, chat, corrections)
2. PreferenceLearner — aggregates signals into ranked UserPreferenceProfile
                      with exponential decay over time
3. API Hooks         — signal collection injected into existing API routes
4. Pipeline Wires    — on pipeline completion, checks user profile to
                      selectively pre-compute preferred items

The system stores signals in the ``interaction_signals`` MongoDB collection
and preference profiles in the ``user_preferences`` MongoDB collection.
"""

from .signal_collector import signal_collector
from .preference_learner import preference_learner

__all__ = [
    "signal_collector",
    "preference_learner",
]

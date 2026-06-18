"""
proactive_notifications — Push relevant insights and alerts to users without them asking.

Architecture:
    ├── TriggerEngine      → Monitors events (new data, anomaly, schedule)
    ├── ContentComposer    → Selects format and composes message
    ├── RelevanceFilter    → Checks BeliefStore to avoid redundant pushes
    └── DeliveryManager    → Injects into chat stream or dashboard

Turns DataSage from "answer what I ask" into "tell me what matters."
"""

from .notifier import ProactiveNotificationAgent

__all__ = ["ProactiveNotificationAgent"]

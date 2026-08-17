"""
Learning System Schemas
=======================

Data models for:
- InteractionSignal: a single user interaction event
- UserPreferenceProfile: aggregated preferences for a user-dataset pair
- PreferenceSummary: lightweight view for the API endpoint
"""

from typing import Any
from datetime import datetime, timezone
from enum import Enum


class SignalType(str, Enum):
    """Types of interaction signals the system tracks."""

    # ── Dashboard signals ──────────────────────────────────────────
    KPI_VIEW = "kpi_view"
    KPI_PIN = "kpi_pin"
    KPI_EDIT = "kpi_edit"
    KPI_PRIORITY_SET = "kpi_priority_set"
    LAYOUT_SAVE = "layout_save"

    # ── Chart signals ──────────────────────────────────────────────
    CHART_VIEW = "chart_view"
    CHART_OPEN = "chart_open"
    CHART_EDIT = "chart_edit"
    CHART_RECOMMENDATION_VIEW = "chart_recommendation_view"
    CHART_RENDER = "chart_render"

    # ── Chat signals ───────────────────────────────────────────────
    QUERY = "query"
    FOLLOW_UP = "follow_up"
    CORRECTION = "correction"
    DELIGHT = "delight"  # Positive sentiment / thanks

    # ── Trust/Correction signals ────────────────────────────────────
    TRUST_ADJUSTMENT = "trust_adjustment"

    # ── Data cleaning signals ───────────────────────────────────────
    CLEANING_REJECTION = "cleaning_rejection"
    CLEANING_APPROVAL = "cleaning_approval"

    # ── Exploration signals ────────────────────────────────────────
    INSIGHT_VIEW = "insight_view"
    DATA_EXPLORE = "data_explore"
    DEEP_ANALYSIS = "deep_analysis"


# Default weight per signal type (used for implicit signals)
SIGNAL_WEIGHTS: dict[str, float] = {
    SignalType.KPI_VIEW: 1.0,
    SignalType.KPI_PIN: 3.0,
    SignalType.KPI_EDIT: 3.0,
    SignalType.KPI_PRIORITY_SET: 4.0,  # Explicit priority is a strong signal
    SignalType.LAYOUT_SAVE: 2.5,
    SignalType.CHART_VIEW: 1.0,
    SignalType.CHART_OPEN: 2.0,
    SignalType.CHART_EDIT: 3.0,
    SignalType.CHART_RECOMMENDATION_VIEW: 0.5,
    SignalType.CHART_RENDER: 1.5,
    SignalType.QUERY: 1.0,
    SignalType.FOLLOW_UP: 1.5,
    SignalType.CORRECTION: 2.0,
    SignalType.DELIGHT: 2.5,
    SignalType.INSIGHT_VIEW: 1.0,
    SignalType.DATA_EXPLORE: 1.0,
    SignalType.DEEP_ANALYSIS: 2.0,
    SignalType.TRUST_ADJUSTMENT: 2.5,
    SignalType.CLEANING_REJECTION: 2.5,  # Explicit rejection — strong signal to avoid similar suggestions
    SignalType.CLEANING_APPROVAL: 3.0,   # Explicit approval — strong signal to reinforce similar patterns
}


class InteractionSignal:
    """
    A single user interaction event with a dashboard component.

    Attributes:
        signal_type: Category of the interaction.
        user_id:     Who performed the action.
        workspace_id: Tenant scope.
        dataset_id:  Which dataset was acted upon.
        target_id:   Specific component ID (KPI card ID, chart ID, etc.).
        target_metadata: Structured context about the target (column names,
                        aggregation, chart_type, etc.).
        weight:      Importance of this signal (higher = stronger preference).
        timestamp:   When the interaction occurred.
        session_id:  Optional session identifier for deduplication.
        source:      Where the signal was emitted from (e.g. "dashboard",
                    "charts_studio", "chat_copilot").
    """

    def __init__(
        self,
        signal_type: str,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        target_id: str = "",
        target_metadata: dict | None = None,
        weight: float | None = None,
        timestamp: datetime | None = None,
        session_id: str | None = None,
        source: str = "",
    ):
        self.signal_type = signal_type
        self.user_id = user_id
        self.workspace_id = workspace_id
        self.dataset_id = dataset_id
        self.target_id = target_id
        self.target_metadata = target_metadata or {}
        self.weight = weight if weight is not None else SIGNAL_WEIGHTS.get(signal_type, 1.0)
        self.timestamp = timestamp or datetime.now(timezone.utc).replace(tzinfo=None)
        self.session_id = session_id
        self.source = source

    def to_dict(self) -> dict:
        """Serialize to a MongoDB-safe dict."""
        return {
            "signal_type": self.signal_type,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "dataset_id": self.dataset_id,
            "target_id": self.target_id,
            "target_metadata": self.target_metadata,
            "weight": self.weight,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "InteractionSignal":
        """Deserialize from a dict."""
        return cls(
            signal_type=d.get("signal_type", ""),
            user_id=d.get("user_id", ""),
            workspace_id=d.get("workspace_id", ""),
            dataset_id=d.get("dataset_id", ""),
            target_id=d.get("target_id", ""),
            target_metadata=d.get("target_metadata", {}),
            weight=d.get("weight"),
            timestamp=d.get("timestamp"),
            session_id=d.get("session_id"),
            source=d.get("source", ""),
        )


class LearnedPreference:
    """
    A single learned preference (one KPI, chart type, or query topic).

    Attributes:
        key:         Unique identifier (e.g. "revenue:sum" for a KPI,
                    "bar:sales,region" for a chart).
        label:       Human-readable name.
        score:       Aggregate preference score (higher = more preferred).
        last_interacted: When the user last engaged with this.
        interaction_count: How many times the user interacted.
        target_metadata: Structured context.
    """

    def __init__(
        self,
        key: str,
        label: str = "",
        score: float = 0.0,
        last_interacted: datetime | None = None,
        interaction_count: int = 0,
        target_metadata: dict | None = None,
    ):
        self.key = key
        self.label = label or key
        self.score = score
        self.last_interacted = last_interacted or datetime.now(timezone.utc).replace(tzinfo=None)
        self.interaction_count = interaction_count
        self.target_metadata = target_metadata or {}

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "score": round(self.score, 4),
            "last_interacted": self.last_interacted,
            "interaction_count": self.interaction_count,
            "target_metadata": self.target_metadata,
        }


class UserPreferenceProfile:
    """
    Aggregated preference profile for a (user, dataset) pair.

    Attributes:
        user_id:       Owner.
        workspace_id:  Tenant scope.
        dataset_id:    Dataset this profile applies to.
        top_kpis:      Ranked list of preferred KPI cards.
        top_charts:    Ranked list of preferred chart configurations.
        top_queries:   Ranked list of frequent query topics.
        top_columns:   Most-interacted columns.
        query_patterns: e.g. ["trend_analysis", "comparison", "diagnosis"].
        signal_count:  Total signals processed.
        confidence:    How confident the system is in this profile
                       (0.0 = no data, 1.0 = high confidence).
        last_updated:  When this profile was last recomputed.
    """

    def __init__(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        top_kpis: list[LearnedPreference] | None = None,
        top_charts: list[LearnedPreference] | None = None,
        top_queries: list[LearnedPreference] | None = None,
        top_columns: list[LearnedPreference] | None = None,
        query_patterns: list[str] | None = None,
        signal_count: int = 0,
        confidence: float = 0.0,
        last_updated: datetime | None = None,
    ):
        self.user_id = user_id
        self.workspace_id = workspace_id
        self.dataset_id = dataset_id
        self.top_kpis = top_kpis or []
        self.top_charts = top_charts or []
        self.top_queries = top_queries or []
        self.top_columns = top_columns or []
        self.query_patterns = query_patterns or []
        self.signal_count = signal_count
        self.confidence = min(confidence, 1.0)
        self.last_updated = last_updated or datetime.now(timezone.utc).replace(tzinfo=None)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "dataset_id": self.dataset_id,
            "top_kpis": [k.to_dict() for k in self.top_kpis],
            "top_charts": [c.to_dict() for c in self.top_charts],
            "top_queries": [q.to_dict() for q in self.top_queries],
            "top_columns": [c.to_dict() for c in self.top_columns],
            "query_patterns": self.query_patterns,
            "signal_count": self.signal_count,
            "confidence": round(self.confidence, 3),
            "last_updated": self.last_updated,
        }

    def to_api_summary(self) -> dict:
        """Return a lightweight version suitable for API responses."""
        return {
            "dataset_id": self.dataset_id,
            "top_kpis": [{"label": k.label, "score": round(k.score, 2)} for k in self.top_kpis[:6]],
            "top_charts": [
                {"label": c.label, "chart_type": c.target_metadata.get("chart_type", ""), "score": round(c.score, 2)}
                for c in self.top_charts[:6]
            ],
            "top_columns": [{"label": c.label, "score": round(c.score, 2)} for c in self.top_columns[:10]],
            "query_patterns": self.query_patterns,
            "signal_count": self.signal_count,
            "confidence": round(self.confidence, 2),
            "last_updated": self.last_updated.isoformat() if self.last_updated else "",
        }


class PreferenceSummary:
    """
    Cross-dataset preference summary for a user.
    Shows what the system has learned about the user across all their datasets.
    """

    def __init__(
        self,
        user_id: str,
        workspace_id: str,
        profile_count: int = 0,
        total_signals: int = 0,
        top_kpis_across_datasets: list[dict] | None = None,
        top_charts_across_datasets: list[dict] | None = None,
        overall_confidence: float = 0.0,
    ):
        self.user_id = user_id
        self.workspace_id = workspace_id
        self.profile_count = profile_count
        self.total_signals = total_signals
        self.top_kpis_across_datasets = top_kpis_across_datasets or []
        self.top_charts_across_datasets = top_charts_across_datasets or []
        self.overall_confidence = overall_confidence

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "profile_count": self.profile_count,
            "total_signals": self.total_signals,
            "overall_confidence": round(self.overall_confidence, 2),
            "top_kpis_across_datasets": self.top_kpis_across_datasets,
            "top_charts_across_datasets": self.top_charts_across_datasets,
        }

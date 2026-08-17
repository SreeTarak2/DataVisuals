"""
Signal Collector
================

Receives raw interaction events from all user-facing surfaces (dashboard,
charts, chat, datasets) and stores them in the ``interaction_signals``
MongoDB collection.

Each signal represents one atomic user action — viewing a KPI, opening a
chart, asking a question, making a correction. Signals are the raw material
the PreferenceLearner uses to build a ranked preference profile.

Usage (in API routes)::

    from services.learning.signal_collector import signal_collector

    # After serving a dashboard overview
    await signal_collector.record_kpi_view(
        user_id=user["id"],
        workspace_id=workspace_id,
        dataset_id=dataset_id,
        kpi_id=kpi["id"],
        kpi_metadata={"column": kpi["column"], "aggregation": kpi.get("aggregation")},
        source="dashboard",
    )
"""

import logging
from datetime import datetime, timezone
from typing import Any

from .schemas import InteractionSignal, SignalType, SIGNAL_WEIGHTS

logger = logging.getLogger(__name__)


class SignalCollector:
    """
    Collects user interaction signals and persists them to MongoDB.

    Each ``record_*`` method creates a normalized ``InteractionSignal`` and
    inserts it into the ``interaction_signals`` collection. Downstream, the
    ``PreferenceLearner`` aggregates these signals into preference profiles.

    All methods are idempotent and gracefully degrade: if MongoDB is
    unavailable, the signal is silently dropped with a warning log.
    """

    def __init__(self):
        self._indexes_initialized = False

    # ── Database helpers ───────────────────────────────────────────────────

    def _get_db(self):
        """Lazy-import db to avoid circular imports."""
        from db.database import get_database
        return get_database()

    async def init_indexes(self) -> None:
        """Create indexes on the interaction_signals collection for efficient queries.

        Includes a TTL index on ``timestamp`` (90-day auto-expiry) so old
        signals self-prune without manual maintenance.
        """
        if self._indexes_initialized:
            return
        try:
            db = self._get_db()
            signals_collection = db.interaction_signals

            # Query pattern index: find signals by (user, workspace, dataset, time)
            await signals_collection.create_index(
                [("user_id", 1), ("workspace_id", 1), ("dataset_id", 1), ("timestamp", -1)],
                name="signal_query_idx",
            )

            # TTL index: auto-delete signals older than 90 days
            await signals_collection.create_index(
                [("timestamp", 1)],
                expireAfterSeconds=90 * 24 * 3600,
                name="signal_ttl_idx",
            )

            # Index for cross-dataset user summary queries
            await signals_collection.create_index(
                [("user_id", 1), ("workspace_id", 1), ("signal_type", 1)],
                name="signal_type_idx",
            )

            # Index for engagement lookups in trust correlation:
            # workspace_id + signal_type + timestamp covers the most common
            # engagement query pattern in the trust correlation service.
            await signals_collection.create_index(
                [("workspace_id", 1), ("signal_type", 1), ("timestamp", -1)],
                name="signal_engagement_idx",
            )

            self._indexes_initialized = True
            logger.info("[SignalCollector] Indexes created on interaction_signals")
        except Exception as e:
            logger.warning("[SignalCollector] Index creation failed: %s", e)

    async def _insert_signal(self, signal: InteractionSignal) -> None:
        """Insert a signal into MongoDB. Failures are logged, not raised."""
        try:
            db = self._get_db()
            await db.interaction_signals.insert_one(signal.to_dict())
        except Exception as e:
            logger.warning(
                "[SignalCollector] Failed to record %s for user %s: %s",
                signal.signal_type, signal.user_id[:8], e,
            )

    async def _bulk_insert(self, signals: list[InteractionSignal]) -> None:
        """Insert multiple signals in a single batch operation."""
        if not signals:
            return
        try:
            db = self._get_db()
            await db.interaction_signals.insert_many(
                [s.to_dict() for s in signals],
                ordered=False,
            )
        except Exception as e:
            logger.warning(
                "[SignalCollector] Bulk insert of %d signals failed: %s",
                len(signals), e,
            )

    # ── KPI signals ────────────────────────────────────────────────────────

    async def record_kpi_view(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        kpi_id: str,
        kpi_metadata: dict | None = None,
        source: str = "dashboard",
    ) -> None:
        """Record that a user viewed a KPI card (passive signal, weight=1)."""
        signal = InteractionSignal(
            signal_type=SignalType.KPI_VIEW,
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            target_id=kpi_id,
            target_metadata=kpi_metadata or {},
            source=source,
        )
        await self._insert_signal(signal)

    async def record_kpi_view_bulk(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        kpis: list[dict],
        source: str = "dashboard",
    ) -> None:
        """Record that a user viewed multiple KPIs at once (dashboard load)."""
        signals = [
            InteractionSignal(
                signal_type=SignalType.KPI_VIEW,
                user_id=user_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                target_id=kpi.get("id", ""),
                target_metadata={
                    "column": kpi.get("column", ""),
                    "aggregation": kpi.get("aggregation", ""),
                    "title": kpi.get("title", ""),
                },
                source=source,
            )
            for kpi in kpis
            if kpi.get("id")
        ]
        await self._bulk_insert(signals)

    async def record_kpi_pin(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        kpi_id: str,
        kpi_metadata: dict | None = None,
        source: str = "dashboard",
    ) -> None:
        """Record that a user pinned or promoted a KPI (strong signal, weight=3)."""
        signal = InteractionSignal(
            signal_type=SignalType.KPI_PIN,
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            target_id=kpi_id,
            target_metadata=kpi_metadata or {},
            weight=SIGNAL_WEIGHTS.get(SignalType.KPI_PIN, 3.0),
            source=source,
        )
        await self._insert_signal(signal)

    async def record_kpi_edit(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        kpi_id: str,
        kpi_metadata: dict | None = None,
        source: str = "dashboard",
    ) -> None:
        """Record that a user edited a KPI (strong signal, weight=3)."""
        signal = InteractionSignal(
            signal_type=SignalType.KPI_EDIT,
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            target_id=kpi_id,
            target_metadata=kpi_metadata or {},
            weight=SIGNAL_WEIGHTS.get(SignalType.KPI_EDIT, 3.0),
            source=source,
        )
        await self._insert_signal(signal)

    async def record_kpi_priority(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        kpi_id: str,
        priority: str,
        kpi_metadata: dict | None = None,
        source: str = "dashboard",
    ) -> None:
        """Record that user set a priority on a KPI (very strong signal, weight=4)."""
        meta = dict(kpi_metadata or {})
        meta["priority"] = priority
        signal = InteractionSignal(
            signal_type=SignalType.KPI_PRIORITY_SET,
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            target_id=kpi_id,
            target_metadata=meta,
            weight=SIGNAL_WEIGHTS.get(SignalType.KPI_PRIORITY_SET, 4.0),
            source=source,
        )
        await self._insert_signal(signal)

    # ── Chart signals ──────────────────────────────────────────────────────

    async def record_chart_view(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        chart_id: str,
        chart_metadata: dict | None = None,
        source: str = "charts",
    ) -> None:
        """Record that a user viewed a chart."""
        signal = InteractionSignal(
            signal_type=SignalType.CHART_VIEW,
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            target_id=chart_id,
            target_metadata=chart_metadata or {},
            source=source,
        )
        await self._insert_signal(signal)

    async def record_chart_edit(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        chart_id: str,
        chart_metadata: dict | None = None,
        source: str = "charts",
    ) -> None:
        """Record that a user edited a chart."""
        signal = InteractionSignal(
            signal_type=SignalType.CHART_EDIT,
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            target_id=chart_id,
            target_metadata=chart_metadata or {},
            weight=SIGNAL_WEIGHTS.get(SignalType.CHART_EDIT, 3.0),
            source=source,
        )
        await self._insert_signal(signal)

    async def record_chart_recommendation_view(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        recommendations: list[dict],
        source: str = "charts",
    ) -> None:
        """Record that the user viewed chart recommendations (weak signal per rec)."""
        signals = [
            InteractionSignal(
                signal_type=SignalType.CHART_RECOMMENDATION_VIEW,
                user_id=user_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                target_id=rec.get("id", "") or rec.get("title", ""),
                target_metadata={
                    "chart_type": rec.get("chart_type", ""),
                    "columns": rec.get("columns", []),
                    "title": rec.get("title", ""),
                },
                weight=SIGNAL_WEIGHTS.get(SignalType.CHART_RECOMMENDATION_VIEW, 0.5),
                source=source,
            )
            for rec in recommendations
        ]
        await self._bulk_insert(signals)

    async def record_chart_render(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        chart_type: str,
        columns: list[str],
        aggregation: str = "sum",
        source: str = "charts",
    ) -> None:
        """Record that a user rendered a chart (user explicitly requested it)."""
        signal = InteractionSignal(
            signal_type=SignalType.CHART_RENDER,
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            target_id=f"{chart_type}:{','.join(columns)}",
            target_metadata={
                "chart_type": chart_type,
                "columns": columns,
                "aggregation": aggregation,
            },
            weight=SIGNAL_WEIGHTS.get(SignalType.CHART_RENDER, 1.5),
            source=source,
        )
        await self._insert_signal(signal)

    # ── Query signals ─────────────────────────────────────────────────────

    async def record_query(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        query_text: str,
        source: str = "chat",
    ) -> None:
        """Record that a user asked a question in chat."""
        # Extract a rough topic label from the query (first few meaningful words)
        topic = self._extract_topic(query_text) if query_text else "general"

        signal = InteractionSignal(
            signal_type=SignalType.QUERY,
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            target_id=f"query:{dataset_id[:8]}",
            target_metadata={
                "topic": topic,
                "query_preview": query_text[:200],
            },
            source=source,
        )
        await self._insert_signal(signal)

    async def record_correction(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        original_query: str,
        correction_text: str,
        source: str = "chat",
    ) -> None:
        """Record that a user corrected an AI response."""
        signal = InteractionSignal(
            signal_type=SignalType.CORRECTION,
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            target_id=f"correction:{dataset_id[:8]}",
            target_metadata={
                "original_query": original_query[:200],
                "correction": correction_text[:200],
            },
            weight=SIGNAL_WEIGHTS.get(SignalType.CORRECTION, 2.0),
            source=source,
        )
        await self._insert_signal(signal)

    # ── Insight signals ────────────────────────────────────────────────────

    async def record_insight_view(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        insight_id: str,
        insight_metadata: dict | None = None,
        source: str = "insights",
    ) -> None:
        """Record that a user viewed an insight."""
        signal = InteractionSignal(
            signal_type=SignalType.INSIGHT_VIEW,
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            target_id=insight_id,
            target_metadata=insight_metadata or {},
            source=source,
        )
        await self._insert_signal(signal)

    # ── Layout signals ─────────────────────────────────────────────────────

    async def record_layout_save(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        components: list[dict],
        source: str = "dashboard",
    ) -> None:
        """Record that the user saved a dashboard layout (strong signal per component)."""
        signals = []
        for comp in components:
            comp_type = comp.get("type", "unknown")
            if comp_type == "kpi":
                signals.append(
                    InteractionSignal(
                        signal_type=SignalType.KPI_PIN,
                        user_id=user_id,
                        workspace_id=workspace_id,
                        dataset_id=dataset_id,
                        target_id=comp.get("id", ""),
                        target_metadata={
                            "column": comp.get("column", ""),
                            "aggregation": comp.get("aggregation", ""),
                            "title": comp.get("title", ""),
                        },
                        weight=SIGNAL_WEIGHTS.get(SignalType.KPI_PIN, 3.0),
                        source=source,
                    )
                )
            elif comp_type == "chart":
                signals.append(
                    InteractionSignal(
                        signal_type=SignalType.CHART_VIEW,
                        user_id=user_id,
                        workspace_id=workspace_id,
                        dataset_id=dataset_id,
                        target_id=comp.get("id", ""),
                        target_metadata={
                            "chart_type": comp.get("chart_type", ""),
                            "columns": comp.get("columns", []),
                            "title": comp.get("title", ""),
                        },
                        weight=SIGNAL_WEIGHTS.get(SignalType.CHART_VIEW, 1.0),
                        source=source,
                    )
                )

        if signals:
            await self._bulk_insert(signals)

    # ── Data cleaning signals ────────────────────────────────────────────────

    async def record_cleaning_rejection(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        action_type: str,
        target_columns: list[str],
        action_index: int,
        action_metadata: dict | None = None,
        source: str = "cleaning_review",
    ) -> None:
        """
        Record that a user rejected a cleaning suggestion.

        This is a strong explicit signal — the user is telling us the suggestion
        was wrong. The PreferenceLearner will use this to lower confidence for
        similar cleaning suggestions on this dataset/org in the future.

        Args:
            user_id:         Who rejected the suggestion.
            workspace_id:    Tenant scope.
            dataset_id:      Dataset being cleaned.
            action_type:     "rename", "remove", or "merge".
            target_columns:  Column name(s) involved.
            action_index:    Index in the cleaning_manifest array.
            action_metadata: Full action dict for context (tier, confidence, reasoning, model_used).
            source:          Where the rejection came from.
        """
        metadata = dict(action_metadata or {})
        metadata["action_type"] = action_type
        metadata["target_columns"] = target_columns
        metadata["action_index"] = action_index

        signal = InteractionSignal(
            signal_type=SignalType.CLEANING_REJECTION,
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            target_id=f"cleaning:{dataset_id[:8]}:action:{action_index}",
            target_metadata=metadata,
            weight=SIGNAL_WEIGHTS.get(SignalType.CLEANING_REJECTION, 2.5),
            source=source,
        )
        await self._insert_signal(signal)

        logger.info(
            "[SignalCollector] Cleaning rejection recorded for %s/%s: "
            "type=%s, columns=%s, confidence=%s",
            user_id[:8], dataset_id[:8],
            action_type, target_columns,
            metadata.get("confidence", "?"),
        )

    async def record_cleaning_approval(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        action_type: str,
        target_columns: list[str],
        action_index: int,
        action_metadata: dict | None = None,
        source: str = "cleaning_review",
    ) -> None:
        """
        Record that a user approved a cleaning suggestion.

        This is a strong explicit positive signal — the user is confirming the
        suggestion was correct. The PreferenceLearner will use this to increase
        confidence for similar cleaning suggestions on this dataset/org.
        Weighted higher than rejection (3.0 vs 2.5) because an explicit approval
        requires deliberate action — the user had to click the checkmark.

        Args:
            user_id:         Who approved the suggestion.
            workspace_id:    Tenant scope.
            dataset_id:      Dataset being cleaned.
            action_type:     "rename", "remove", or "merge".
            target_columns:  Column name(s) involved.
            action_index:    Index in the cleaning_manifest array.
            action_metadata: Full action dict for context (tier, confidence, reasoning, model_used).
            source:          Where the approval came from.
        """
        metadata = dict(action_metadata or {})
        metadata["action_type"] = action_type
        metadata["target_columns"] = target_columns
        metadata["action_index"] = action_index

        signal = InteractionSignal(
            signal_type=SignalType.CLEANING_APPROVAL,
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            target_id=f"cleaning:{dataset_id[:8]}:action:{action_index}",
            target_metadata=metadata,
            weight=SIGNAL_WEIGHTS.get(SignalType.CLEANING_APPROVAL, 3.0),
            source=source,
        )
        await self._insert_signal(signal)

        logger.info(
            "[SignalCollector] Cleaning approval recorded for %s/%s: "
            "type=%s, columns=%s, confidence=%s",
            user_id[:8], dataset_id[:8],
            action_type, target_columns,
            metadata.get("confidence", "?"),
        )

    # ── Trust/Correction signals ────────────────────────────────────────────

    async def record_trust_adjustment(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        metric_name: str,
        definition: str,
        formula: str | None = None,
        confidence: float = 0.0,
        was_augmented: bool = True,
        source: str = "trust_verifier",
    ) -> None:
        """
        Record that the trust verifier made an adjustment to a query.

        This fires when the trust verifier finds a matching metric semantic
        definition for a term in the user's query and augments the query
        with that definition.

        Args:
            user_id:      User who asked the query.
            workspace_id: Tenant scope.
            dataset_id:   Dataset being queried.
            metric_name:  The metric term that was recognized.
            definition:   The semantic definition applied.
            formula:      Optional formula reference.
            confidence:   Confidence of the trust verification.
            was_augmented: Whether the query was actually augmented.
            source:       Source identifier.
        """
        signal = InteractionSignal(
            signal_type=SignalType.TRUST_ADJUSTMENT,
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            target_id=f"trust:{metric_name}:{dataset_id[:8]}",
            target_metadata={
                "metric_name": metric_name,
                "definition": definition,
                "formula": formula,
                "confidence": confidence,
                "was_augmented": was_augmented,
            },
            weight=SIGNAL_WEIGHTS.get(SignalType.TRUST_ADJUSTMENT, 2.5),
            source=source,
        )
        await self._insert_signal(signal)

    # ── Data exploration signals ───────────────────────────────────────────

    async def record_data_explore(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        columns: list[str] | None = None,
        source: str = "data_explorer",
    ) -> None:
        """Record that a user explored the raw data."""
        signal = InteractionSignal(
            signal_type=SignalType.DATA_EXPLORE,
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            target_id=f"explore:{dataset_id[:8]}",
            target_metadata={"columns": columns or []},
            source=source,
        )
        await self._insert_signal(signal)

    # ── Internal helpers ───────────────────────────────────────────────────

    @staticmethod
    def _extract_topic(query: str) -> str:
        """
        Extract a rough topic label from a query string.

        Uses simple keyword matching to categorize the query into one of:
        trend, comparison, composition, diagnosis, forecast, general.
        """
        q = query.lower()

        topics = {
            "trend": ["trend", "over time", "growth", "decline", "increase", "decrease",
                      "monthly", "quarterly", "yearly", "seasonal", "pattern"],
            "comparison": ["compare", "vs", "versus", "difference", "better", "worse",
                          "outperform", "underperform", "top", "bottom", "rank"],
            "composition": ["breakdown", "distribution", "composition", "made up of",
                           "percentage", "proportion", "share", "split", "segment"],
            "diagnosis": ["why", "reason", "cause", "driver", "impact", "correlation",
                         "relationship", "factor", "influence", "affect"],
            "forecast": ["predict", "forecast", "future", "next month", "next quarter",
                        "projection", "estimate", "expected"],
            "anomaly": ["anomaly", "outlier", "unusual", "spike", "drop", "sudden",
                       "unexpected", "abnormal"],
        }

        for topic, keywords in topics.items():
            for kw in keywords:
                if kw in q:
                    return topic
        return "general"


# Global singleton
signal_collector = SignalCollector()

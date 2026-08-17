"""
Preference Learner
==================

Aggregates raw interaction signals into ranked ``UserPreferenceProfile``
objects, using exponential decay to prioritize recent interactions.

Algorithm
---------
Each signal contributes ``weight × exp(-λ × days_since)`` to its target's
score, where λ (default 0.05) controls how quickly older signals decay.

A profile reaches "high confidence" after 20+ signals across 3+ categories.

Usage::

    from services.learning.preference_learner import preference_learner

    # Compute a profile for a (user, dataset) pair
    profile = await preference_learner.compute_profile(user_id, workspace_id, dataset_id)

    # Get the cross-dataset summary for a user
    summary = await preference_learner.get_user_summary(user_id, workspace_id)
"""

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from .schemas import (
    InteractionSignal,
    LearnedPreference,
    PreferenceSummary,
    SignalType,
    UserPreferenceProfile,
)

logger = logging.getLogger(__name__)

# Decay rate: how much older signals are discounted
# λ = 0.05 → a signal from 30 days ago contributes ~22% of its original weight
# λ = 0.03 → gentler decay (30-days-ago contributes ~41%)
_DECAY_LAMBDA = 0.05

# Minimum signals to produce a profile with any confidence
_MIN_SIGNALS_FOR_PROFILE = 5
# Minimum signals for "high confidence"
_HIGH_CONFIDENCE_SIGNALS = 20
# Minimum categories with signals for "high confidence"
_HIGH_CONFIDENCE_CATEGORIES = 3

# How long to cache a computed profile before re-computing (seconds)
_PROFILE_CACHE_TTL = 300  # 5 minutes


class PreferenceLearner:
    """
    Aggregates interaction signals into ranked user preference profiles.

    Profiles are stored in the ``user_preferences`` MongoDB collection and
    re-computed on demand when enough new signals have accumulated.
    """

    def __init__(self):
        pass

    # ── Database helpers ───────────────────────────────────────────────────

    def _get_db(self):
        """Lazy-import to avoid circular imports."""
        from db.database import get_database
        return get_database()

    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════

    async def compute_profile(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
        force_refresh: bool = False,
    ) -> UserPreferenceProfile:
        """
        Compute (or retrieve cached) preference profile for a (user, dataset).

        Args:
            user_id:        Owner.
            workspace_id:   Tenant scope.
            dataset_id:     Target dataset.
            force_refresh:  If True, recompute even if cached profile is fresh.

        Returns:
            UserPreferenceProfile (empty profile if no signals exist yet).
        """
        # ── 1. Check cache ──────────────────────────────────────────────
        if not force_refresh:
            cached = await self._get_cached_profile(user_id, workspace_id, dataset_id)
            if cached:
                return cached

        # ── 2. Fetch signals ────────────────────────────────────────────
        signals = await self._fetch_signals(user_id, workspace_id, dataset_id)
        if not signals:
            empty = UserPreferenceProfile(
                user_id=user_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                confidence=0.0,
            )
            await self._cache_profile(empty)
            return empty

        # ── 3. Aggregate into ranked preferences ────────────────────────
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Score accumulators: key -> {score, count, last_meta, last_time}
        kpi_scores: dict[str, dict] = {}
        chart_scores: dict[str, dict] = {}
        query_scores: dict[str, dict] = {}
        column_scores: dict[str, dict] = {}
        query_patterns: set[str] = set()
        category_counts: set[str] = set()

        for signal in signals:
            signal_type = signal.signal_type
            days_since = (now - signal.timestamp).total_seconds() / 86400.0
            decay = math.exp(-_DECAY_LAMBDA * days_since)
            effective_weight = signal.weight * decay

            category_counts.add(signal_type)

            if signal_type in (
                SignalType.KPI_VIEW,
                SignalType.KPI_PIN,
                SignalType.KPI_EDIT,
                SignalType.KPI_PRIORITY_SET,
            ):
                key = self._kpi_key(signal)
                self._accumulate(kpi_scores, key, effective_weight, signal)

                # Also track column-level preference
                col = signal.target_metadata.get("column", "")
                if col:
                    self._accumulate(
                        column_scores, col, effective_weight, signal,
                        label=col,
                    )

            elif signal_type in (
                SignalType.CHART_VIEW,
                SignalType.CHART_OPEN,
                SignalType.CHART_EDIT,
                SignalType.CHART_RENDER,
                SignalType.CHART_RECOMMENDATION_VIEW,
            ):
                key = self._chart_key(signal)
                self._accumulate(chart_scores, key, effective_weight, signal)

                # Track column-level preference from chart columns
                for col in (signal.target_metadata.get("columns") or []):
                    if isinstance(col, str) and col:
                        self._accumulate(
                            column_scores, col, effective_weight, signal,
                            label=col,
                        )

            elif signal_type in (SignalType.QUERY, SignalType.FOLLOW_UP):
                topic = signal.target_metadata.get("topic", "general")
                self._accumulate(
                    query_scores, topic, effective_weight, signal,
                    label=topic,
                )
                query_patterns.add(topic)

            elif signal_type == SignalType.CORRECTION:
                topic = signal.target_metadata.get("topic", "general")
                self._accumulate(
                    query_scores, f"correction:{topic}", effective_weight * 0.5, signal,
                    label=topic,
                )

        # ── 4. Rank by score ───────────────────────────────────────────
        top_kpis = sorted(
            [LearnedPreference(key=k, **v) for k, v in kpi_scores.items()],
            key=lambda x: x.score,
            reverse=True,
        )
        top_charts = sorted(
            [LearnedPreference(key=k, **v) for k, v in chart_scores.items()],
            key=lambda x: x.score,
            reverse=True,
        )
        top_queries = sorted(
            [LearnedPreference(key=k, **v) for k, v in query_scores.items()],
            key=lambda x: x.score,
            reverse=True,
        )
        top_columns = sorted(
            [LearnedPreference(key=k, **v) for k, v in column_scores.items()],
            key=lambda x: x.score,
            reverse=True,
        )

        # ── 5. Compute confidence ──────────────────────────────────────
        signal_count = len(signals)
        unique_categories = len(category_counts)
        if signal_count >= _HIGH_CONFIDENCE_SIGNALS and unique_categories >= _HIGH_CONFIDENCE_CATEGORIES:
            confidence = min(1.0, (signal_count / 50.0) * 0.5 + 0.5)
        elif signal_count >= _MIN_SIGNALS_FOR_PROFILE:
            confidence = min(0.6, signal_count / _HIGH_CONFIDENCE_SIGNALS * 0.6)
        else:
            confidence = 0.0

        profile = UserPreferenceProfile(
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            top_kpis=top_kpis,
            top_charts=top_charts,
            top_queries=top_queries,
            top_columns=top_columns,
            query_patterns=sorted(query_patterns),
            signal_count=signal_count,
            confidence=confidence,
            last_updated=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        # ── 6. Cache ───────────────────────────────────────────────────
        await self._cache_profile(profile)

        logger.info(
            "[Learner] Profile for %s on %s: %d signals, %d KPIs, %d charts, %.2f confidence",
            user_id[:8], dataset_id[:8], signal_count,
            len(top_kpis), len(top_charts), confidence,
        )

        return profile

    async def get_user_summary(
        self,
        user_id: str,
        workspace_id: str,
    ) -> PreferenceSummary:
        """
        Get a cross-dataset preference summary for the user.

        Aggregates top KPIs and charts the user interacts with across all
        their datasets to identify global preferences.
        """
        try:
            db = self._get_db()
            profiles_cursor = db.user_preferences.find(
                {"user_id": user_id, "workspace_id": workspace_id},
            ).sort("last_updated", -1).limit(50)
            profiles = await profiles_cursor.to_list(length=50)
        except Exception as e:
            logger.warning("[Learner] Failed to fetch profiles: %s", e)
            profiles = []

        if not profiles:
            return PreferenceSummary(
                user_id=user_id,
                workspace_id=workspace_id,
                profile_count=0,
                total_signals=0,
            )

        # Aggregate top KPIs and charts across datasets
        all_kpis: dict[str, dict] = {}
        all_charts: dict[str, dict] = {}
        total_signals = 0

        for profile_doc in profiles:
            total_signals += profile_doc.get("signal_count", 0)

            for kpi in profile_doc.get("top_kpis", []):
                key = kpi.get("key", "")
                if key and key not in all_kpis:
                    all_kpis[key] = {
                        "label": kpi.get("label", key),
                        "score": kpi.get("score", 0),
                        "dataset_id": profile_doc.get("dataset_id", ""),
                    }

            for chart in profile_doc.get("top_charts", []):
                key = chart.get("key", "")
                if key and key not in all_charts:
                    all_charts[key] = {
                        "label": chart.get("label", key),
                        "chart_type": chart.get("target_metadata", {}).get("chart_type", ""),
                        "score": chart.get("score", 0),
                        "dataset_id": profile_doc.get("dataset_id", ""),
                    }

        # Sort by score descending
        sorted_kpis = sorted(all_kpis.values(), key=lambda x: x["score"], reverse=True)[:10]
        sorted_charts = sorted(all_charts.values(), key=lambda x: x["score"], reverse=True)[:10]

        profile_count = len(profiles)
        overall_confidence = min(1.0, (total_signals / 100.0) * 0.5 + (profile_count / 10.0) * 0.5)

        return PreferenceSummary(
            user_id=user_id,
            workspace_id=workspace_id,
            profile_count=profile_count,
            total_signals=total_signals,
            top_kpis_across_datasets=sorted_kpis,
            top_charts_across_datasets=sorted_charts,
            overall_confidence=overall_confidence,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # INTERNAL — Signal aggregation helpers
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _kpi_key(signal: InteractionSignal) -> str:
        """Generate a unique key for a KPI signal."""
        col = signal.target_metadata.get("column", "")
        agg = signal.target_metadata.get("aggregation", "count")
        return f"kpi:{col}:{agg}" if col else signal.target_id

    @staticmethod
    def _chart_key(signal: InteractionSignal) -> str:
        """Generate a unique key for a chart signal."""
        chart_type = signal.target_metadata.get("chart_type", "unknown")
        columns = signal.target_metadata.get("columns", [])
        agg = signal.target_metadata.get("aggregation", "sum")
        cols_str = ",".join(sorted(columns)) if isinstance(columns, list) else str(columns)
        return f"chart:{chart_type}:{cols_str}:{agg}" if cols_str else signal.target_id

    @staticmethod
    def _accumulate(
        scores: dict[str, dict],
        key: str,
        weight: float,
        signal: InteractionSignal,
        label: str | None = None,
    ) -> None:
        """
        Accumulate a weighted signal into the scores dict.

        Each entry tracks:
            - score: cumulative decayed weight
            - interaction_count: raw count of interactions
            - last_interacted: timestamp of most recent interaction
            - target_metadata: last signal's metadata (for context)
            - label: human-readable name
        """
        if not key:
            return
        entry = scores.get(key)
        if entry is None:
            entry = {
                "score": 0.0,
                "interaction_count": 0,
                "last_interacted": signal.timestamp,
                "target_metadata": dict(signal.target_metadata),
                "label": label or key,
            }
            scores[key] = entry

        entry["score"] += weight
        entry["interaction_count"] += 1
        # Keep the most recent timestamp
        if signal.timestamp > entry["last_interacted"]:
            entry["last_interacted"] = signal.timestamp
            # Merge metadata (keep latest context)
            entry["target_metadata"].update(signal.target_metadata)

    # ═══════════════════════════════════════════════════════════════════════
    # INTERNAL — Cache management
    # ═══════════════════════════════════════════════════════════════════════

    async def _get_cached_profile(
        self,
        user_id: str,
        workspace_id: str,
        dataset_id: str,
    ) -> UserPreferenceProfile | None:
        """Return cached profile if it's fresh enough."""
        try:
            db = self._get_db()
            doc = await db.user_preferences.find_one(
                {"user_id": user_id, "workspace_id": workspace_id, "dataset_id": dataset_id},
            )
            if not doc:
                return None

            last_updated = doc.get("last_updated")
            if not isinstance(last_updated, datetime):
                return None

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if (now - last_updated).total_seconds() > _PROFILE_CACHE_TTL:
                return None  # Stale — need to recompute

            return self._doc_to_profile(doc)

        except Exception as e:
            logger.warning("[Learner] Cache read failed: %s", e)
            return None

    async def _cache_profile(self, profile: UserPreferenceProfile) -> None:
        """Persist a preference profile to MongoDB."""
        try:
            db = self._get_db()
            data = profile.to_dict()
            await db.user_preferences.update_one(
                {
                    "user_id": profile.user_id,
                    "workspace_id": profile.workspace_id,
                    "dataset_id": profile.dataset_id,
                },
                {"$set": data},
                upsert=True,
            )
        except Exception as e:
            logger.warning("[Learner] Cache write failed: %s", e)

    @staticmethod
    def _doc_to_profile(doc: dict) -> UserPreferenceProfile:
        """Convert a MongoDB document to a UserPreferenceProfile."""
        def _pref_list(items: list) -> list[LearnedPreference]:
            return [
                LearnedPreference(
                    key=item.get("key", ""),
                    label=item.get("label", ""),
                    score=item.get("score", 0.0),
                    last_interacted=item.get("last_interacted"),
                    interaction_count=item.get("interaction_count", 0),
                    target_metadata=item.get("target_metadata", {}),
                )
                for item in items
            ]

        return UserPreferenceProfile(
            user_id=doc.get("user_id", ""),
            workspace_id=doc.get("workspace_id", ""),
            dataset_id=doc.get("dataset_id", ""),
            top_kpis=_pref_list(doc.get("top_kpis", [])),
            top_charts=_pref_list(doc.get("top_charts", [])),
            top_queries=_pref_list(doc.get("top_queries", [])),
            top_columns=_pref_list(doc.get("top_columns", [])),
            query_patterns=doc.get("query_patterns", []),
            signal_count=doc.get("signal_count", 0),
            confidence=doc.get("confidence", 0.0),
            last_updated=doc.get("last_updated"),
        )


# Global singleton
preference_learner = PreferenceLearner()

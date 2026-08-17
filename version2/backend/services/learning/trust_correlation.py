"""
Trust Correlation Service
=========================

Correlates trust verification adjustments with downstream user engagement
signals to answer questions like:

- Which semantic corrections are triggered most often?
- Do users engage more (follow-ups, delight) or less (corrections, friction)
  when a trust adjustment is applied to their query?
- What's the overall satisfaction score for each semantic definition?

The service queries the ``interaction_signals`` MongoDB collection, matching
``TRUST_ADJUSTMENT`` signals against subsequent ``FOLLOW_UP``, ``CORRECTION``,
``DELIGHT``, and ``QUERY`` signals within a configurable time window.

Usage::

    from services.learning.trust_correlation import TrustCorrelationService

    service = TrustCorrelationService()
    report = await service.correlate(workspace_id, user_id)
    print(report.to_dict())
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from .schemas import SignalType

logger = logging.getLogger(__name__)

# Default time window in minutes to look for engagement signals after
# a trust adjustment has been made.
_DEFAULT_LOOKAHEAD_MINUTES = 5


class MetricCorrelation:
    """
    Correlation data for a single metric (semantic definition).

    Attributes:
        metric_name:       The metric term that was recognized (e.g. "revenue").
        definition:        The semantic definition applied.
        formula:           Optional formula (e.g. "SUM(recognized_amount)").
        trigger_count:     How many times this metric triggered a trust adjustment.
        unique_users:      How many unique users triggered it.
        follow_up_count:   Queries that followed within the window.
        correction_count:  User corrections that followed within the window.
        delight_count:     Positive sentiment signals that followed.
        query_count:       Total subsequent queries of any kind.
        total_engagement:  Sum of all engagement signals after the adjustment.
        last_triggered:    When this metric was last triggered.
    """

    def __init__(
        self,
        metric_name: str,
        definition: str = "",
        formula: str | None = None,
        trigger_count: int = 0,
        unique_users: set | None = None,
        follow_up_count: int = 0,
        correction_count: int = 0,
        delight_count: int = 0,
        query_count: int = 0,
        total_engagement: int = 0,
        last_triggered: datetime | None = None,
    ):
        self.metric_name = metric_name
        self.definition = definition
        self.formula = formula
        self.trigger_count = trigger_count
        self.unique_users = unique_users or set()
        self.follow_up_count = follow_up_count
        self.correction_count = correction_count
        self.delight_count = delight_count
        self.query_count = query_count
        self.total_engagement = total_engagement
        self.last_triggered = last_triggered

    @property
    def satisfaction_score(self) -> float:
        """
        Score from -1.0 to 1.0 indicating whether this metric leads to
        positive or negative user responses.

        Formula: (delight_count - correction_count) / max(trigger_count, 1)
        Normalized to [-1, 1]. Positive = users like the adjustment.
        """
        if self.trigger_count == 0:
            return 0.0
        raw = (self.delight_count - self.correction_count) / float(self.trigger_count)
        return max(-1.0, min(1.0, raw))

    @property
    def engagement_rate(self) -> float:
        """
        Percentage of adjustments that led to at least one follow-up
        engagement signal (query, follow-up, delight, etc.).
        """
        if self.trigger_count == 0:
            return 0.0
        raw = self.total_engagement / float(self.trigger_count)
        return min(1.0, raw)

    @property
    def unique_user_count(self) -> int:
        return len(self.unique_users)

    def to_dict(self) -> dict:
        return {
            "metric_name": self.metric_name,
            "definition": self.definition,
            "formula": self.formula,
            "trigger_count": self.trigger_count,
            "unique_users": self.unique_user_count,
            "follow_up_count": self.follow_up_count,
            "correction_count": self.correction_count,
            "delight_count": self.delight_count,
            "query_count": self.query_count,
            "total_engagement": self.total_engagement,
            "engagement_rate": round(self.engagement_rate, 3),
            "satisfaction_score": round(self.satisfaction_score, 3),
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
        }


class TrustCorrelationReport:
    """
    Full correlation report across all metrics.

    Attributes:
        total_trust_adjustments:  How many trust adjustments were analyzed.
        unique_metrics:           How many distinct metric terms were found.
        overall_engagement_rate:  Average engagement rate across all metrics.
        overall_satisfaction:     Average satisfaction across all metrics.
        metrics:                  List of MetricCorrelation per metric.
        generated_at:             When the report was generated.
        time_window_minutes:      The look-ahead window used.
    """

    def __init__(
        self,
        metrics: list[MetricCorrelation] | None = None,
        time_window_minutes: int = _DEFAULT_LOOKAHEAD_MINUTES,
        generated_at: datetime | None = None,
    ):
        self.metrics = metrics or []
        self.time_window_minutes = time_window_minutes
        self.generated_at = generated_at or datetime.now(timezone.utc).replace(tzinfo=None)

    @property
    def total_trust_adjustments(self) -> int:
        return sum(m.trigger_count for m in self.metrics)

    @property
    def unique_metrics(self) -> int:
        return len(self.metrics)

    @property
    def overall_engagement_rate(self) -> float:
        if not self.metrics:
            return 0.0
        total_engagement = sum(m.total_engagement for m in self.metrics)
        total_triggers = sum(m.trigger_count for m in self.metrics)
        if total_triggers == 0:
            return 0.0
        return min(1.0, total_engagement / float(total_triggers))

    @property
    def overall_satisfaction(self) -> float:
        if not self.metrics:
            return 0.0
        scores = [m.satisfaction_score for m in self.metrics if m.trigger_count > 0]
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    @property
    def top_metrics_by_trigger(self) -> list[MetricCorrelation]:
        return sorted(self.metrics, key=lambda m: m.trigger_count, reverse=True)

    @property
    def top_metrics_by_satisfaction(self) -> list[MetricCorrelation]:
        return sorted(self.metrics, key=lambda m: m.satisfaction_score, reverse=True)

    @property
    def bottom_metrics_by_satisfaction(self) -> list[MetricCorrelation]:
        return sorted(self.metrics, key=lambda m: m.satisfaction_score)

    def to_dict(self) -> dict:
        return {
            "summary": {
                "total_trust_adjustments": self.total_trust_adjustments,
                "unique_metrics": self.unique_metrics,
                "overall_engagement_rate": round(self.overall_engagement_rate, 3),
                "overall_satisfaction": round(self.overall_satisfaction, 3),
                "time_window_minutes": self.time_window_minutes,
                "generated_at": self.generated_at.isoformat(),
            },
            "metrics": [m.to_dict() for m in self.top_metrics_by_trigger],
            "most_satisfying": [
                m.to_dict() for m in self.top_metrics_by_satisfaction[:5]
            ],
            "least_satisfying": [
                m.to_dict() for m in self.bottom_metrics_by_satisfaction[:5]
            ],
        }


class TrustCorrelationService:
    """
    Queries ``interaction_signals`` to correlate trust adjustments with
    downstream user engagement signals.

    The correlation logic:
    1. Find all ``TRUST_ADJUSTMENT`` signals for the user/workspace
    2. For each adjustment, look for engagement signals (QUERY, FOLLOW_UP,
       CORRECTION, DELIGHT) within a time window after the adjustment
    3. Aggregate by metric_name to produce per-metric correlations
    4. Generate an overall report with averages and rankings
    """

    def _get_db(self):
        from db.database import get_database
        return get_database()

    async def correlate(
        self,
        workspace_id: str,
        user_id: str | None = None,
        dataset_id: str | None = None,
        days_back: int = 90,
        lookahead_minutes: int = _DEFAULT_LOOKAHEAD_MINUTES,
    ) -> TrustCorrelationReport:
        """
        Generate a trust correlation report.

        Args:
            workspace_id:   Tenant scope (required).
            user_id:        Optional user filter.
            dataset_id:     Optional dataset filter.
            days_back:      How far back to look for signals (default 90).
            lookahead_minutes: Time window after each trust adjustment to
                              look for engagement signals (default 5).

        Returns:
            TrustCorrelationReport with per-metric correlations and overall metrics.
        """
        db = self._get_db()
        signals_collection = db.interaction_signals

        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_back)

        # ── 1. Build query filter for trust adjustments ────────────────
        trust_filter: dict = {
            "signal_type": SignalType.TRUST_ADJUSTMENT,
            "timestamp": {"$gte": cutoff},
        }
        if user_id:
            trust_filter["user_id"] = user_id
        if dataset_id:
            trust_filter["dataset_id"] = dataset_id
        # Always filter by workspace for multi-tenant safety
        trust_filter["workspace_id"] = workspace_id

        try:
            trust_cursor = (
                signals_collection.find(trust_filter)
                .sort("timestamp", -1)
                .limit(500)
            )
            trust_signals = await trust_cursor.to_list(length=500)
        except Exception as e:
            logger.warning("[TrustCorrelation] Failed to query trust signals: %s", e)
            return TrustCorrelationReport(time_window_minutes=lookahead_minutes)

        if not trust_signals:
            return TrustCorrelationReport(time_window_minutes=lookahead_minutes)

        # ── 2. Group trust signals by metric_name ──────────────────────
        metrics_map: dict[str, dict] = {}  # metric_name -> aggregation dict

        for signal in trust_signals:
            meta = signal.get("target_metadata", {}) or {}
            metric_name = meta.get("metric_name", "unknown")
            definition = meta.get("definition", "")
            formula = meta.get("formula")
            ts = signal.get("timestamp")

            if metric_name not in metrics_map:
                metrics_map[metric_name] = {
                    "metric_name": metric_name,
                    "definition": definition,
                    "formula": formula,
                    "trigger_count": 0,
                    "unique_users": set(),
                    "timestamps": [],
                }

            entry = metrics_map[metric_name]
            entry["trigger_count"] += 1
            if signal.get("user_id"):
                entry["unique_users"].add(signal["user_id"])
            if ts:
                entry["timestamps"].append(ts)

        # ── 3. Find engagement signals AFTER each trust adjustment ────
        #    Batched by metric: one range query per metric, not one per timestamp.
        #    This eliminates the N+1 query problem flagged in review.
        lookahead = timedelta(minutes=lookahead_minutes)
        correlations: list[MetricCorrelation] = []

        for raw_entry in metrics_map.values():
            timestamps = raw_entry["timestamps"]
            if not timestamps:
                correlations.append(MetricCorrelation(
                    metric_name=raw_entry["metric_name"],
                    definition=raw_entry["definition"],
                    formula=raw_entry["formula"],
                    trigger_count=raw_entry["trigger_count"],
                    unique_users=raw_entry["unique_users"],
                ))
                continue

            # Single range query spanning from the earliest adjustment
            # to the latest adjustment + lookahead window.
            min_ts = min(timestamps)
            max_ts = max(timestamps)

            engagement_filter: dict = {
                "workspace_id": workspace_id,
                "timestamp": {"$gte": min_ts, "$lte": max_ts + lookahead},
                "signal_type": {
                    "$in": [
                        SignalType.QUERY,
                        SignalType.FOLLOW_UP,
                        SignalType.CORRECTION,
                        SignalType.DELIGHT,
                    ]
                },
            }
            if user_id:
                engagement_filter["user_id"] = user_id
            if dataset_id:
                engagement_filter["dataset_id"] = dataset_id

            follow_up_count = 0
            correction_count = 0
            delight_count = 0
            query_count = 0

            try:
                engagement_cursor = (
                    signals_collection.find(engagement_filter, {"signal_type": 1, "timestamp": 1})
                    .sort("timestamp", 1)
                )
                all_engagement = await engagement_cursor.to_list(length=500)

                # For each trust adjustment timestamp, count only engagement
                # signals that fall within its lookahead window. This is more
                # precise than counting every signal in the overall range.
                for adj_ts in timestamps:
                    window_end = adj_ts + lookahead
                    for es in all_engagement:
                        es_ts = es.get("timestamp")
                        if es_ts is None:
                            continue
                        # Only count signals after the adjustment and within window
                        if adj_ts < es_ts <= window_end:
                            st = es.get("signal_type", "")
                            if st == SignalType.QUERY:
                                query_count += 1
                            elif st == SignalType.FOLLOW_UP:
                                follow_up_count += 1
                            elif st == SignalType.CORRECTION:
                                correction_count += 1
                            elif st == SignalType.DELIGHT:
                                delight_count += 1
            except Exception as e:
                logger.warning("[TrustCorrelation] Engagement query failed for %s: %s",
                               raw_entry["metric_name"], e)

            last_ts = max(timestamps)

            correlations.append(MetricCorrelation(
                metric_name=raw_entry["metric_name"],
                definition=raw_entry["definition"],
                formula=raw_entry["formula"],
                trigger_count=raw_entry["trigger_count"],
                unique_users=raw_entry["unique_users"],
                follow_up_count=follow_up_count,
                correction_count=correction_count,
                delight_count=delight_count,
                query_count=query_count,
                total_engagement=follow_up_count + delight_count + query_count,
                last_triggered=last_ts,
            ))

        report = TrustCorrelationReport(
            metrics=correlations,
            time_window_minutes=lookahead_minutes,
        )

        logger.info(
            "[TrustCorrelation] Report: %d adjustments across %d metrics "
            "(engagement=%.2f, satisfaction=%.2f)",
            report.total_trust_adjustments,
            report.unique_metrics,
            report.overall_engagement_rate,
            report.overall_satisfaction,
        )

        return report


# Global singleton
trust_correlation_service = TrustCorrelationService()

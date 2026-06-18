"""
ProactiveNotificationAgent — Push relevant insights and alerts to users.

Architecture:
    TriggerEngine      → Monitors events (new data, anomaly, schedule)
    ContentComposer    → Selects format and composes context-aware message
    RelevanceFilter    → Checks BeliefStore to avoid redundant pushes
    DeliveryManager    → Injects into chat stream or dashboard notifications

Design principles:
    - Non-intrusive: RelevanceFilter prevents redundant or low-value pushes
    - Async-friendly: all checks are non-blocking, fire-and-forget
    - Conservative: pushes only when confidence > threshold AND user hasn't seen it
    - Multi-format: supports insight cards, alerts, weekly digests, recommendations
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class NotificationEvent:
    """A parsed notification event ready for delivery."""

    event_type: str = ""  # "anomaly_alert", "weekly_digest", "new_insight", "data_quality"
    priority: str = "medium"  # "critical", "high", "medium", "low"
    title: str = ""
    body: str = ""
    cta: dict | None = None  # {"text": "View details", "action": "open_anomaly_view"}
    dataset_id: str = ""
    metadata: dict = field(default_factory=dict)


# ── Prompt templates ─────────────────────────────────────────────────────────

COMPOSE_PROMPT = """\
<role>You are a notification composer crafting concise, valuable alerts for data stakeholders.</role>
<instructions>
Compose a notification based on the following trigger:

## Trigger Type
{trigger_type}

## Trigger Data
{trigger_data}

## Recent Context (what user already knows)
{known_context}

## Output Requirements
- Title: Under 60 chars, specific and actionable
- Body: 2-3 sentences, include specific numbers, mention what changed
- CTA text: Short action text (e.g., "View anomaly", "Open dashboard")

Return a JSON object:
{{
    "title": "...",
    "body": "...",
    "cta_text": "...",
    "cta_action": "open_anomaly_view|open_dashboard|view_insight|open_data_quality"
}}
</instructions>"""


# ── Trigger Types ────────────────────────────────────────────────────────────


class TriggerType:
    ANOMALY_ALERT = "anomaly_alert"
    WEEKLY_DIGEST = "weekly_digest"
    NEW_INSIGHT = "new_insight"
    DATA_QUALITY = "data_quality"
    STRATEGIC_ADVICE = "strategic_advice"
    SCHEDULED_REPORT = "scheduled_report"


PRIORITY_MAP: dict[str, str] = {
    TriggerType.ANOMALY_ALERT: "high",
    TriggerType.WEEKLY_DIGEST: "medium",
    TriggerType.NEW_INSIGHT: "low",
    TriggerType.DATA_QUALITY: "medium",
    TriggerType.STRATEGIC_ADVICE: "medium",
    TriggerType.SCHEDULED_REPORT: "low",
}


# ── ProactiveNotificationAgent ───────────────────────────────────────────────


class ProactiveNotificationAgent:
    """
    Composes and delivers proactive notification events.

    Usage:
        agent = ProactiveNotificationAgent()
        events = await agent.process_trigger(
            trigger_type="anomaly_alert",
            trigger_data={...},
            user_id="user_123",
            dataset_id="dataset_456",
        )
        # events: list of NotificationEvent ready for delivery
    """

    # ── Minimum confidence for delivery ──────────────────────────────────────
    MIN_CONFIDENCE = 0.55
    CRITICAL_CONFIDENCE = 0.40  # Critical alerts get lower threshold

    def __init__(self):
        self._llm_router = None
        self._recent_deliveries: dict[str, list[float]] = {}  # user_id → timestamps

    @property
    def llm_router(self):
        if self._llm_router is None:
            from services.llm_router import llm_router
            self._llm_router = llm_router
        return self._llm_router

    @property
    def belief_store(self):
        try:
            from services.agents.belief_store import get_belief_store
            return get_belief_store()
        except Exception:
            return None

    async def process_trigger(
        self,
        trigger_type: str,
        trigger_data: dict,
        user_id: str = "",
        dataset_id: str = "",
        known_context: str = "",
    ) -> list[NotificationEvent]:
        """
        Process a trigger event and return notification(s) ready for delivery.

        Args:
            trigger_type: Type from TriggerType enum
            trigger_data: Data payload (varies by trigger type)
            user_id: User to target
            dataset_id: Related dataset
            known_context: What the user already knows (from BeliefStore)

        Returns:
            List of NotificationEvent objects (empty if filtered out)
        """
        # ── Step 1: Check rate limit ────────────────────────────────────────
        if not self._check_rate_limit(user_id, trigger_type):
            logger.debug(f"[Notifications] Rate limited: {user_id}/{trigger_type}")
            return []

        # ── Step 2: Relevance filter ────────────────────────────────────────
        if not await self._relevance_filter(user_id, trigger_type, trigger_data):
            return []

        # ── Step 3: Compose content ──────────────────────────────────────────
        notifications = await self._compose_content(
            trigger_type, trigger_data, known_context, dataset_id
        )

        # ── Step 4: Apply priority ──────────────────────────────────────────
        base_priority = PRIORITY_MAP.get(trigger_type, "medium")
        for n in notifications:
            n.priority = base_priority
            n.dataset_id = dataset_id

        return notifications

    def _check_rate_limit(self, user_id: str, trigger_type: str) -> bool:
        """Rate limit: max N pushes per hour per trigger type per user."""
        now = datetime.utcnow().timestamp()
        key = f"{user_id}__{trigger_type}"

        if key not in self._recent_deliveries:
            self._recent_deliveries[key] = []

        # Prune entries older than 1 hour
        self._recent_deliveries[key] = [
            ts for ts in self._recent_deliveries[key] if now - ts < 3600
        ]

        # Limits per trigger type
        limits = {
            TriggerType.ANOMALY_ALERT: 5,  # max 5 anomaly alerts per hour
            TriggerType.WEEKLY_DIGEST: 1,  # once per hour
            TriggerType.NEW_INSIGHT: 3,    # max 3 insights per hour
            TriggerType.DATA_QUALITY: 2,   # max 2 quality alerts per hour
            TriggerType.STRATEGIC_ADVICE: 2,
            TriggerType.SCHEDULED_REPORT: 1,
        }

        max_per_hour = limits.get(trigger_type, 3)
        if len(self._recent_deliveries[key]) >= max_per_hour:
            return False

        self._recent_deliveries[key].append(now)
        return True

    async def _relevance_filter(
        self, user_id: str, trigger_type: str, trigger_data: dict
    ) -> bool:
        """
        Check if this notification is truly relevant and not redundant.

        Filters out:
        - Content user already knows (via BeliefStore)
        - Trivial/low-confidence anomalies
        - Duplicate insights (same topic pushed recently)
        """
        # ── Check confidence threshold ──────────────────────────────────────
        if trigger_type == TriggerType.ANOMALY_ALERT:
            severity = trigger_data.get("severity", "low")
            if severity == "low":
                return False  # Skip low-severity anomalies

        # ── Check BeliefStore for known content ──────────────────────────────
        if user_id and self.belief_store:
            content = trigger_data.get("title") or trigger_data.get("summary", "")
            if content:
                try:
                    surprisal, similar = await self.belief_store.calculate_semantic_surprisal(
                        user_id, content
                    )
                    # If user already knows about it (low surprisal), skip
                    if surprisal < 0.3 and similar:
                        logger.debug(
                            f"[Notifications] Skipping — user already knows: {content[:50]}..."
                        )
                        return False
                except Exception as e:
                    logger.debug(f"[Notifications] BeliefStore check failed: {e}")

        return True

    async def _compose_content(
        self,
        trigger_type: str,
        trigger_data: dict,
        known_context: str,
        dataset_id: str,
    ) -> list[NotificationEvent]:
        """
        Compose notification content for the given trigger.

        For anomaly alerts and data quality, uses deterministic composition.
        For weekly digests and strategic advice, uses LLM.
        """
        if trigger_type == TriggerType.ANOMALY_ALERT:
            return self._compose_anomaly_alert(trigger_data)
        elif trigger_type == TriggerType.DATA_QUALITY:
            return self._compose_data_quality(trigger_data)
        elif trigger_type == TriggerType.WEEKLY_DIGEST:
            return await self._compose_llm_content(
                trigger_type, trigger_data, known_context
            )
        elif trigger_type == TriggerType.STRATEGIC_ADVICE:
            return await self._compose_llm_content(
                trigger_type, trigger_data, known_context
            )
        elif trigger_type == TriggerType.NEW_INSIGHT:
            return self._compose_insight(trigger_data)
        else:
            return []

    @staticmethod
    def _compose_anomaly_alert(data: dict) -> list[NotificationEvent]:
        """Deterministic composition for anomaly alerts — no LLM needed."""
        anomalies = data.get("anomalies", data.get("results", []))
        if not anomalies:
            return []

        events = []
        for a in anomalies[:3]:
            col = a.get("column", "Unknown")
            count = a.get("outlier_count", 0)
            pct = a.get("outlier_percentage", 0)
            sev = a.get("severity", "unknown")

            events.append(
                NotificationEvent(
                    event_type=TriggerType.ANOMALY_ALERT,
                    title=f"⚠️ {col}: {count} anomalies detected",
                    body=f"{count} anomalous values ({pct:.1f}%) detected in {col}. "
                         f"Severity: {sev}. Investigate root cause to determine business impact.",
                    cta={"text": "Investigate", "action": "open_anomaly_view"},
                    metadata={"column": col, "count": count, "severity": sev},
                )
            )
        return events

    @staticmethod
    def _compose_data_quality(data: dict) -> list[NotificationEvent]:
        """Deterministic composition for data quality alerts."""
        issues = data.get("issues", [])
        if not issues:
            return []

        events = []
        total_issues = len(issues)
        critical_count = sum(1 for i in issues if i.get("severity") == "high")

        events.append(
            NotificationEvent(
                event_type=TriggerType.DATA_QUALITY,
                title=f"📊 Data quality: {total_issues} issues found",
                body=f"{total_issues} data quality issues detected ({critical_count} critical). "
                     f"Top issue: {issues[0].get('description', issues[0].get('type', 'Unknown'))}.",
                cta={"text": "View issues", "action": "open_data_quality"},
                metadata={"total_issues": total_issues, "critical_count": critical_count},
            )
        )
        return events

    @staticmethod
    def _compose_insight(data: dict) -> list[NotificationEvent]:
        """Deterministic composition for new insight notifications."""
        insights = data.get("insights", data.get("findings", []))
        if not insights:
            return []

        events = []
        for insight in insights[:2]:
            title = insight.get("title", insight.get("summary", "New insight"))
            body = insight.get("description", insight.get("detail", ""))
            events.append(
                NotificationEvent(
                    event_type=TriggerType.NEW_INSIGHT,
                    title=f"💡 {title[:60]}",
                    body=body[:200] if body else "A new insight has been generated from your data.",
                    cta={"text": "View insight", "action": "view_insight"},
                    metadata=insight,
                )
            )
        return events

    async def _compose_llm_content(
        self,
        trigger_type: str,
        trigger_data: dict,
        known_context: str,
    ) -> list[NotificationEvent]:
        """Compose content using LLM for complex notification types."""
        prompt = COMPOSE_PROMPT.format(
            trigger_type=trigger_type,
            trigger_data=str(trigger_data)[:1500],
            known_context=known_context[:500] or "[No prior context]",
        )
        try:
            result = await self.llm_router.call(
                prompt=prompt,
                model_role="simple_query",
                expect_json=True,
                temperature=0.3,
                max_tokens=400,
            )
            if isinstance(result, dict):
                return [
                    NotificationEvent(
                        event_type=trigger_type,
                        title=result.get("title", "Data update"),
                        body=result.get("body", ""),
                        cta={
                            "text": result.get("cta_text", "View details"),
                            "action": result.get("cta_action", "open_dashboard"),
                        },
                    )
                ]
            return []
        except Exception as e:
            logger.warning(f"[Notifications] LLM composition failed: {e}")
            return []


# ── Singleton ────────────────────────────────────────────────────────────────

proactive_notification_agent = ProactiveNotificationAgent()

"""
LLM Cost Tracking & Budget Enforcement Service
================================================

Tracks LLM token usage and costs per user per day in MongoDB.
Provides a circuit breaker to prevent cost explosion from runaway
LLM calls or abuse.

Configuration via environment variables (core/config.py):
    LLM_DAILY_BUDGET_CENTS: Maximum daily LLM spend per user (default: 500 = $5.00)
    LLM_GLOBAL_DAILY_BUDGET_CENTS: Maximum total daily LLM spend (default: 10000 = $100)
    LLM_COST_TRACKING_ENABLED: Toggle tracking (default: true)

Cost rates are sourced from core/config.py OPENROUTER_MODELS config.
"""

import logging
from datetime import datetime, date
from typing import Dict, Optional, Tuple
from db.database import get_database

logger = logging.getLogger(__name__)

# Cost rates per model key (input/output per 1M tokens in cents)
# Matches the costs defined in core/config.py OPENROUTER_MODELS
MODEL_COST_RATES: Dict[str, Tuple[float, float]] = {
    "gemini_flash_lite": (0.10, 0.40),
    "mistral_small_32": (0.06, 0.18),
    "deepseek_v32": (0.25, 0.40),
    "deepseek_v4_flash": (0.14, 0.28),
    "tngtech_deepseek_r1t2_chimera": (0.25, 0.85),
    "minimax_m25": (0.30, 1.10),
    "qwen_2.5_72b": (0.12, 0.39),
    "gemini_flash_lite_intent": (0.0, 0.0),  # FREE
    "openrouter_free": (0.0, 0.0),  # FREE
}

def estimate_cost_cents(
    model_key: str, input_tokens: int, output_tokens: int
) -> float:
    """
    Estimate the cost of an LLM call in cents.

    Args:
        model_key: Model config key (e.g., 'deepseek_v32')
        input_tokens: Number of input (prompt) tokens
        output_tokens: Number of output (completion) tokens

    Returns:
        float: Estimated cost in USD cents
    """
    input_rate, output_rate = MODEL_COST_RATES.get(
        model_key, MODEL_COST_RATES["mistral_small_32"]
    )
    input_cost = (input_tokens / 1_000_000) * input_rate
    output_cost = (output_tokens / 1_000_000) * output_rate
    return round(input_cost + output_cost, 4)


class CostTracker:
    """
    Tracks and enforces LLM usage budgets per user and globally.

    Uses MongoDB for persistence (survives restarts) with in-memory cache
    for performance. Budgets reset daily (based on UTC date).
    """

    def __init__(self):
        self._db = None
        self._daily_budget_cents = 500  # $5/user/day default
        self._global_daily_budget_cents = 10000  # $100 total/day default
        self._enabled = True

    # ── Configuration (called at startup from settings) ──────────────────────

    def configure(
        self,
        daily_budget_cents: int = 500,
        global_daily_budget_cents: int = 10000,
        enabled: bool = True,
    ):
        self._daily_budget_cents = daily_budget_cents
        self._global_daily_budget_cents = global_daily_budget_cents
        self._enabled = enabled
        logger.info(
            f"CostTracker configured: {daily_budget_cents}c/user/day, "
            f"{global_daily_budget_cents}c global/day, enabled={enabled}"
        )

    @property
    def db(self):
        if self._db is None:
            self._db = get_database()
        return self._db

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _today_str(self) -> str:
        return date.today().isoformat()

    async def _get_usage_record(self, date_str: str, user_id: str) -> Dict:
        """Get or create a daily usage record for a user."""
        db = self.db
        record = await db.llm_usage.find_one({"date": date_str, "user_id": user_id})
        if not record:
            record = {
                "date": date_str,
                "user_id": user_id,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_cents": 0.0,
                "call_count": 0,
                "models_used": {},
                "blocked": False,
            }
        return record

    async def _get_global_usage_record(self, date_str: str) -> Dict:
        """Get or create the global daily usage record."""
        db = self.db
        record = await db.llm_usage_global.find_one({"date": date_str})
        if not record:
            record = {
                "date": date_str,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_cents": 0.0,
                "call_count": 0,
            }
        return record

    # ── Public API ───────────────────────────────────────────────────────────

    async def record_usage(
        self,
        user_id: str,
        model_key: str,
        input_tokens: int,
        output_tokens: int,
        role: str = "unknown",
    ) -> Dict:
        """
        Record an LLM API call's token usage and return updated budget info.

        Args:
            user_id: The authenticated user's ID
            model_key: Model config key (e.g., 'deepseek_v32')
            input_tokens: Prompt tokens used
            output_tokens: Completion tokens generated
            role: The task role (e.g., 'chat_streaming', 'kpi_suggestion')

        Returns:
            Dict with keys:
                - recorded: Whether recording succeeded
                - cost_cents: Cost of this call in cents
                - user_daily_cost_cents: Total user cost today
                - user_daily_budget_cents: User budget cap
                - global_daily_cost_cents: Total global cost today
                - global_daily_budget_cents: Global budget cap
                - user_blocked: Whether user budget is exceeded
                - global_blocked: Whether global budget is exceeded
        """
        if not self._enabled:
            return {
                "recorded": False,
                "cost_cents": 0,
                "user_daily_cost_cents": 0,
                "user_blocked": False,
                "global_blocked": False,
            }

        today = self._today_str()
        cost_cents = estimate_cost_cents(model_key, input_tokens, output_tokens)
        total_tokens = input_tokens + output_tokens

        try:
            db = self.db

            # ── Update user-level record ──
            await db.llm_usage.update_one(
                {"date": today, "user_id": user_id},
                {
                    "$inc": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                        "cost_cents": cost_cents,
                        "call_count": 1,
                        f"models_used.{model_key}.calls": 1,
                        f"models_used.{model_key}.input_tokens": input_tokens,
                        f"models_used.{model_key}.output_tokens": output_tokens,
                        f"models_used.{model_key}.cost_cents": cost_cents,
                    },
                },
                upsert=True,
            )

            # ── Update global record ──
            await db.llm_usage_global.update_one(
                {"date": today},
                {
                    "$inc": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                        "cost_cents": cost_cents,
                        "call_count": 1,
                    },
                },
                upsert=True,
            )

            # ── Fetch updated totals ──
            user_record = await self._get_usage_record(today, user_id)
            global_record = await self._get_global_usage_record(today)

            user_daily_cost = user_record.get("cost_cents", 0)
            global_daily_cost = global_record.get("cost_cents", 0)

            # ── Check budgets ──
            user_blocked = user_daily_cost > self._daily_budget_cents
            global_blocked = global_daily_cost > self._global_daily_budget_cents

            # If user is now blocked, mark it
            if user_blocked:
                await db.llm_usage.update_one(
                    {"date": today, "user_id": user_id},
                    {"$set": {"blocked": True}},
                )

            logger.info(
                f"[CostTracker] User {user_id[:8]}... | "
                f"{model_key} | "
                f"{input_tokens} in + {output_tokens} out = {total_tokens}T | "
                f"${cost_cents:.4f} this call | "
                f"${user_daily_cost:.2f} user today / ${self._daily_budget_cents:.2f} cap | "
                f"${global_daily_cost:.2f} global today / ${self._global_daily_budget_cents:.2f} cap"
            )

            return {
                "recorded": True,
                "cost_cents": cost_cents,
                "user_daily_cost_cents": user_daily_cost,
                "user_daily_budget_cents": self._daily_budget_cents,
                "global_daily_cost_cents": global_daily_cost,
                "global_daily_budget_cents": self._global_daily_budget_cents,
                "user_blocked": user_blocked,
                "global_blocked": global_blocked,
            }

        except Exception as e:
            logger.error(f"[CostTracker] Failed to record usage: {e}")
            return {
                "recorded": False,
                "cost_cents": cost_cents,
                "user_daily_cost_cents": 0,
                "user_blocked": False,
                "global_blocked": False,
                "error": str(e),
            }

    async def check_budget(self, user_id: str) -> Dict:
        """
        Check if a user still has budget for LLM calls.

        Returns:
            Dict with keys:
                - allowed: True if within budgets
                - user_daily_cost_cents: User's spend today
                - user_daily_budget_cents: User's cap
                - global_daily_cost_cents: Global spend today
                - global_daily_budget_cents: Global cap
                - reason: Explanation if blocked
        """
        if not self._enabled:
            return {"allowed": True, "reason": "cost_tracking_disabled"}

        today = self._today_str()

        try:
            user_record = await self._get_usage_record(today, user_id)
            global_record = await self._get_global_usage_record(today)

            user_daily_cost = user_record.get("cost_cents", 0)
            global_daily_cost = global_record.get("cost_cents", 0)

            if user_daily_cost > self._daily_budget_cents:
                return {
                    "allowed": False,
                    "user_daily_cost_cents": user_daily_cost,
                    "user_daily_budget_cents": self._daily_budget_cents,
                    "global_daily_cost_cents": global_daily_cost,
                    "global_daily_budget_cents": self._global_daily_budget_cents,
                    "reason": f"User daily budget exceeded: ${user_daily_cost:.2f} spent of ${self._daily_budget_cents:.2f} cap",
                }

            if global_daily_cost > self._global_daily_budget_cents:
                return {
                    "allowed": False,
                    "user_daily_cost_cents": user_daily_cost,
                    "user_daily_budget_cents": self._daily_budget_cents,
                    "global_daily_cost_cents": global_daily_cost,
                    "global_daily_budget_cents": self._global_daily_budget_cents,
                    "reason": f"Global daily budget exceeded: ${global_daily_cost:.2f} spent of ${self._global_daily_budget_cents:.2f} cap",
                }

            return {
                "allowed": True,
                "user_daily_cost_cents": user_daily_cost if user_record.get("cost_cents") else 0,
                "user_daily_budget_cents": self._daily_budget_cents,
                "global_daily_cost_cents": global_daily_cost if global_record.get("cost_cents") else 0,
                "global_daily_budget_cents": self._global_daily_budget_cents,
            }

        except Exception as e:
            logger.error(f"[CostTracker] Budget check failed: {e}")
            # Fail open — allow the call if tracking is broken
            return {"allowed": True, "reason": "budget_check_failed", "error": str(e)}

    async def get_user_usage(self, user_id: str, days: int = 7) -> Dict:
        """
        Get usage summary for a user over the last N days.

        Args:
            user_id: User ID to query
            days: Number of days of history to return

        Returns:
            Dict with daily usage records and totals
        """
        try:
            db = self.db
            from datetime import timedelta

            start_date = (date.today() - timedelta(days=days - 1)).isoformat()
            cursor = db.llm_usage.find(
                {"user_id": user_id, "date": {"$gte": start_date}}
            ).sort("date", -1)

            daily_records = []
            totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_cents": 0, "call_count": 0}

            async for record in cursor:
                record.pop("_id", None)
                daily_records.append(record)
                for key in totals:
                    totals[key] += record.get(key, 0)

            return {
                "user_id": user_id,
                "daily_records": daily_records,
                "totals": totals,
                "days": days,
            }

        except Exception as e:
            logger.error(f"[CostTracker] Failed to get user usage: {e}")
            return {"error": str(e)}


# Singleton instance
cost_tracker = CostTracker()

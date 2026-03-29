"""
Explanation Quality Validator
=============================
Used by the /charts/explain API endpoint to:
  1. Prefer validated LLM fields over heuristic helper fallbacks
  2. Normalize and trim whitespace
  3. Reject placeholder/generic strings
  4. Enforce expected lengths/counts before accepting cached or fresh content

This module does NOT replace output_validator.py — it supplements it
specifically for chart explanation responses.

Usage in charts.py:
    from services.charts.explanation_validator import (
        validate_and_normalize_explanation,
        should_use_llm_field,
    )

    # After getting enhanced_insight from chart_insights_service:
    if enhanced_insight:
        result = validate_and_normalize_explanation(enhanced_insight, chart_config)
        if result["valid"]:
            explanation = result["explanation"]
            key_insights = result["key_insights"]
            reading_guide = result["reading_guide"]
            anomaly_flag = result["anomaly_flag"]
        else:
            # fall back to heuristic helpers
            ...

Author: DataSage AI Team
Version: 1.0
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# WEAK PATTERN LISTS (shared with chart_insights_service.py)
# ─────────────────────────────────────────────────────────────

WEAK_EXPLANATION_PATTERNS = [
    "stable data points",
    "this chart shows",
    "the data reveals",
    "as seen in",
    "values for ",
    "are consistently",
    "data distributions",
    "explore this data further",
    "consider filtering by different",
    "gain insights",
    "further analysis",
    "the chart displays",
    "a variety of",
    "various data points",
    "interesting patterns",
]

WEAK_READING_GUIDE_PATTERNS = [
    "filter by the highest-value segment",
    "explore this data further",
    "see what drives it",
    "consider filtering by different",
    "gain insights",
    "look for patterns",
    "examine the data",
]


def _is_weak(text: str, patterns: List[str]) -> bool:
    """Return True if text matches any weak pattern or is too short."""
    if not text or not isinstance(text, str):
        return True
    lower = text.lower().strip()
    if len(lower) < 10:
        return True
    return any(p in lower for p in patterns)


def _has_number(text: str) -> bool:
    """Return True if text contains at least one digit, %, or currency symbol."""
    return bool(re.search(r'[\d£$€%]', text or ""))


def _trim(text: str, max_length: int = 300) -> str:
    """Trim and normalize whitespace."""
    if not text or not isinstance(text, str):
        return ""
    cleaned = " ".join(text.strip().split())
    return cleaned[:max_length]


def _is_json_like_string(text: str) -> bool:
    """Detect malformed JSON-like strings that shouldn't be in key_insights."""
    if not text:
        return False
    stripped = text.strip()
    return stripped.startswith("{") or stripped.startswith("[") or stripped.startswith('"')


def should_use_llm_field(
    llm_value: Optional[str],
    heuristic_value: Optional[str],
    weak_patterns: List[str],
) -> Tuple[str, str]:
    """
    Decide whether to use LLM-generated field or heuristic fallback.

    Returns:
        Tuple of (chosen_value, source) where source is "llm" or "heuristic"
    """
    # If LLM value exists and is not weak, prefer it
    if llm_value and not _is_weak(llm_value, weak_patterns) and _has_number(llm_value):
        return _trim(llm_value), "llm"

    # If LLM value exists but has no number, still prefer it over a weak heuristic
    if llm_value and not _is_weak(llm_value, weak_patterns):
        return _trim(llm_value), "llm"

    # Fall back to heuristic
    if heuristic_value and not _is_weak(heuristic_value, weak_patterns):
        return _trim(heuristic_value), "heuristic"

    # Both are weak — return LLM if it exists, otherwise heuristic
    if llm_value:
        return _trim(llm_value), "llm_fallback"
    if heuristic_value:
        return _trim(heuristic_value), "heuristic_fallback"

    return "", "none"


def validate_and_normalize_explanation(
    enhanced_insight: Dict[str, Any],
    chart_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Validate and normalize an enhanced_insight payload.

    Args:
        enhanced_insight: Dict from chart_insights_service with
            explanation, key_insights, reading_guide, anomaly_flag
        chart_config: Optional chart config for entity validation

    Returns:
        Dict with:
            valid: bool — whether the payload passes quality gates
            explanation: str — cleaned explanation
            key_insights: List[str] — cleaned insights (max 2)
            reading_guide: str | None — cleaned guide
            anomaly_flag: str | None — cleaned flag
            rejection_reasons: List[str] — why it was rejected (if invalid)
    """
    result = {
        "valid": True,
        "explanation": "",
        "key_insights": [],
        "reading_guide": None,
        "anomaly_flag": None,
        "rejection_reasons": [],
    }

    if not enhanced_insight or not isinstance(enhanced_insight, dict):
        result["valid"] = False
        result["rejection_reasons"].append("enhanced_insight is missing or not a dict")
        return result

    # ── Explanation ──
    explanation = _trim(enhanced_insight.get("explanation", ""))
    if _is_weak(explanation, WEAK_EXPLANATION_PATTERNS):
        result["rejection_reasons"].append(
            f"weak explanation: '{explanation[:60]}...'"
        )
    if not _has_number(explanation):
        # Not an instant rejection, but flag it
        result["rejection_reasons"].append("explanation has no numeric anchor")

    result["explanation"] = explanation

    # ── Key Insights ──
    raw_insights = enhanced_insight.get("key_insights", [])
    if isinstance(raw_insights, str):
        raw_insights = [raw_insights]
    if not isinstance(raw_insights, list):
        raw_insights = []

    clean_insights = []
    for ki in raw_insights[:3]:
        if not isinstance(ki, str):
            continue
        ki = _trim(ki)
        if _is_json_like_string(ki):
            result["rejection_reasons"].append(f"malformed JSON in key_insight: '{ki[:40]}'")
            continue
        if _is_weak(ki, WEAK_EXPLANATION_PATTERNS):
            continue
        clean_insights.append(ki)

    if not clean_insights:
        result["rejection_reasons"].append("no valid key_insights after filtering")

    result["key_insights"] = clean_insights[:2]

    # ── Reading Guide ──
    reading_guide = _trim(enhanced_insight.get("reading_guide", "") or "")
    if reading_guide:
        if _is_weak(reading_guide, WEAK_READING_GUIDE_PATTERNS):
            result["rejection_reasons"].append(
                f"weak reading_guide: '{reading_guide[:60]}...'"
            )
            result["reading_guide"] = None
        else:
            result["reading_guide"] = reading_guide
    else:
        result["reading_guide"] = None

    # ── Anomaly Flag ──
    anomaly = enhanced_insight.get("anomaly_flag")
    if anomaly and isinstance(anomaly, str) and anomaly.lower() not in ("null", "none", ""):
        result["anomaly_flag"] = _trim(anomaly)
    else:
        result["anomaly_flag"] = None

    # ── Final Validity ──
    # Invalid if explanation is weak AND no valid insights
    if (
        _is_weak(result["explanation"], WEAK_EXPLANATION_PATTERNS)
        and not result["key_insights"]
    ):
        result["valid"] = False

    if result["rejection_reasons"]:
        logger.info(
            f"Explanation validation: {len(result['rejection_reasons'])} issue(s) — "
            f"{result['rejection_reasons']}"
        )

    return result


def validate_cached_explanation(
    cached_payload: Dict[str, Any],
    required_cache_version: str = "v3.0",
) -> bool:
    """
    Check if a cached explanation is still valid (correct version, not expired).

    Args:
        cached_payload: Cached insight dict
        required_cache_version: Expected CACHE_VERSION (from chart_insights_service)

    Returns:
        True if cache is valid and usable, False if stale
    """
    if not cached_payload or not isinstance(cached_payload, dict):
        return False

    cache_version = cached_payload.get("cache_version", "")
    if cache_version != required_cache_version:
        logger.info(
            f"Cache version mismatch: got '{cache_version}', expected '{required_cache_version}'"
        )
        return False

    # Optional: check age (e.g., invalidate after 24 hours)
    # from datetime import datetime, timedelta
    # generated_at = cached_payload.get("generated_at")
    # if generated_at:
    #     try:
    #         ts = datetime.fromisoformat(generated_at)
    #         if datetime.utcnow() - ts > timedelta(hours=24):
    #             logger.info("Cache expired (>24h old)")
    #             return False
    #     except Exception as e:
    #         logger.warning(f"Failed to check cache age: {e}")

    return True

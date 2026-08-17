"""
Pricing-tier aware file size limits for dataset uploads.

The effective upload limit for a user is::

    min(tier_limit_mb, PIPELINE_MAX_FILE_SIZE_MB)

where ``tier_limit_mb`` comes from the user's billing tier (Free / Pro /
Enterprise, read from their user document) and ``PIPELINE_MAX_FILE_SIZE_MB``
is the server-side memory-safety ceiling — CSV→Polars can expand 5-10× in
memory, so the pipeline must never be handed a file it cannot safely parse.

Tier detection is best-effort: user documents are inspected for
``subscription`` / ``plan`` / ``tier`` / ``billing_plan`` fields
(case-insensitive; nested dicts like ``{"name": "pro"}`` are supported).
Unknown or missing values fall back to the Free tier. This keeps the system
working today (billing is not wired end-to-end yet) while making the limits
pricing-ready: bump a user's ``plan`` field and their upload ceiling changes
immediately, no code change.
"""

from core.config import settings

DEFAULT_TIER = "free"

# Normalize arbitrary plan strings onto the three product tiers.
TIER_ALIASES: dict[str, str] = {
    "free": "free",
    "basic": "free",
    "starter": "free",
    "trial": "free",
    "pro": "pro",
    "premium": "pro",
    "professional": "pro",
    "team": "pro",
    "growth": "pro",
    "enterprise": "enterprise",
    "business": "enterprise",
    "org": "enterprise",
    "organization": "enterprise",
    "scale": "enterprise",
}

# Fields inspected (in priority order) to determine a user's tier.
_TIER_FIELDS = ("subscription", "plan", "tier", "billing_plan")


def resolve_user_tier(user_doc: dict | None) -> str:
    """Best-effort tier resolution from a user document.

    Returns one of ``"free"`` / ``"pro"`` / ``"enterprise"``. Any user doc
    without a recognizable plan field resolves to ``"free"``.
    """
    if not user_doc:
        return DEFAULT_TIER

    for key in _TIER_FIELDS:
        raw = user_doc.get(key)
        if raw is None:
            continue
        if isinstance(raw, dict):
            # e.g. subscription: {"name": "Pro", "status": "active"}
            raw = raw.get("name") or raw.get("tier") or raw.get("plan")
        if isinstance(raw, str):
            normalized = raw.strip().lower()
            if normalized in TIER_ALIASES:
                return TIER_ALIASES[normalized]

    return DEFAULT_TIER


def tier_size_limit_mb(tier: str) -> int:
    """Raw per-tier upload limit in MB (from config)."""
    return settings.TIER_FILE_SIZE_LIMITS_MB.get(
        tier, settings.TIER_FILE_SIZE_LIMITS_MB[DEFAULT_TIER]
    )


def effective_size_limit_mb(
    tier: str | None = None,
    user_doc: dict | None = None,
) -> int:
    """Effective upload limit (MB) for a user.

    ``min(tier_limit, PIPELINE_MAX_FILE_SIZE_MB)`` — the pipeline memory
    ceiling always wins, no matter what tier a user is on.

    Args:
        tier:      Explicit tier string. When provided, ``user_doc`` is
                   ignored (the caller resolved it already).
        user_doc:  User document used to resolve the tier when ``tier`` is
                   omitted. May be ``None`` → resolves to the Free tier.
    """
    resolved = tier or resolve_user_tier(user_doc)
    limit = tier_size_limit_mb(resolved)
    return min(limit, settings.PIPELINE_MAX_FILE_SIZE_MB)


def effective_size_limit_bytes(
    tier: str | None = None,
    user_doc: dict | None = None,
) -> int:
    """Effective upload limit in bytes."""
    return effective_size_limit_mb(tier, user_doc) * 1024 * 1024


def size_limit_error_message(size_mb: float, limit_mb: int, tier: str) -> str:
    """Human-readable 413 message for an over-limit file."""
    msg = (
        f"File size {size_mb:.1f}MB exceeds the {limit_mb}MB upload limit for "
        f"your plan ({tier}). Large files cause memory pressure "
        f"(CSV→Polars can expand 5-10×). Split the file into smaller parts "
        f"and upload them separately."
    )
    if tier != "enterprise":
        msg += (
            f" Upgrade to Pro or Enterprise for a larger upload limit "
            f"({settings.TIER_FILE_SIZE_LIMITS_MB.get('pro', 500)}MB / "
            f"{settings.TIER_FILE_SIZE_LIMITS_MB.get('enterprise', 1024)}MB)."
        )
    return msg

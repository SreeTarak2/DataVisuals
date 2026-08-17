"""Pricing-tier upload size limit test runner.

Verifies the tier-aware file size limit system end-to-end at boundary
sizes, without a server. Tests:

  1. Tier resolution from user documents (free/pro/enterprise, nested
     subscription dicts, case-insensitive plans, unknown → free).
  2. Effective limit math: ``min(tier limit, PIPELINE_MAX_FILE_SIZE_MB)``
     including the pipeline-ceiling cap for enterprise.
  3. The boundary decision logic used by ``upload_dataset``: files
     exactly at the limit are accepted, files 1 byte over are rejected.
  4. 413 error messages (with/without the upgrade hint).

Optionally performs a REAL HTTP upload against a running backend
(``--base-url`` + ``--token``) for every tier × boundary combination.

Usage (from version2/backend/):
  python scripts/test_upload_size_limits.py                 # logic only
  python scripts/test_upload_size_limits.py --verbose
  python scripts/test_upload_size_limits.py --base-url http://localhost:8000 --token <jwt>
"""

import argparse
import io
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Ensure the backend root is on sys.path so that "from core.config" etc. work
_backend_root = str(Path(__file__).resolve().parent.parent)
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

from core.config import settings  # noqa: E402
from services.datasets.size_limits import (  # noqa: E402
    DEFAULT_TIER,
    effective_size_limit_bytes,
    effective_size_limit_mb,
    resolve_user_tier,
    size_limit_error_message,
    tier_size_limit_mb,
)

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} {detail}")


# ── 1. Tier resolution ───────────────────────────────────────────────────────

def test_tier_resolution() -> None:
    print("\n══ 1. Tier resolution from user documents ══")

    cases = [
        ("no doc", None, "free"),
        ("empty doc", {}, "free"),
        ("plan: Pro", {"plan": "Pro"}, "pro"),
        ("plan: pro (lower)", {"plan": "pro"}, "pro"),
        ("plan: enterprise", {"plan": "enterprise"}, "enterprise"),
        ("plan: Business", {"plan": "Business"}, "enterprise"),
        ("tier: premium", {"tier": "premium"}, "pro"),
        ("subscription nested name", {"subscription": {"name": "Pro", "status": "active"}}, "pro"),
        ("subscription nested tier", {"subscription": {"tier": "Enterprise"}}, "enterprise"),
        ("billing_plan: team", {"billing_plan": "team"}, "pro"),
        ("unknown plan → free", {"plan": "mega-ultra-2000"}, "free"),
        ("wrong type (int)", {"plan": 42}, "free"),
        ("trial → free", {"plan": "trial"}, "free"),
        ("free explicit", {"plan": "free"}, "free"),
    ]
    for name, doc, expected in cases:
        got = resolve_user_tier(doc)
        check(name, got == expected, f"(got {got!r}, want {expected!r})")


# ── 2. Effective limit math ──────────────────────────────────────────────────

def test_effective_limits() -> None:
    print("\n══ 2. Effective limit = min(tier, pipeline ceiling) ══")

    ceiling = settings.PIPELINE_MAX_FILE_SIZE_MB
    for tier in ("free", "pro", "enterprise"):
        raw = tier_size_limit_mb(tier)
        expected = min(raw, ceiling)
        got = effective_size_limit_mb(tier=tier)
        check(
            f"tier={tier}: {raw}MB → effective {expected}MB",
            got == expected,
            f"(got {got}MB, want {expected}MB)",
        )
        # Bytes variant is consistent
        check(
            f"tier={tier}: bytes = MB × 1024²",
            effective_size_limit_bytes(tier=tier) == expected * 1024 * 1024,
            f"(got {effective_size_limit_bytes(tier=tier)})",
        )

    # Resolving from a doc must match resolving from the tier string
    doc = {"plan": "Pro"}
    check(
        "user_doc resolution matches explicit tier",
        effective_size_limit_mb(user_doc=doc) == effective_size_limit_mb(tier="pro"),
    )

    # Default (no doc) is the free tier
    check(
        "no doc → free tier limit",
        effective_size_limit_mb() == min(tier_size_limit_mb("free"), ceiling),
        f"(got {effective_size_limit_mb()}MB)",
    )

    print(f"\n  Config summary (PIPELINE_MAX_FILE_SIZE_MB={ceiling}):")
    for tier in ("free", "pro", "enterprise"):
        print(f"    {tier:<12} raw={tier_size_limit_mb(tier):>5}MB  effective={effective_size_limit_mb(tier=tier):>5}MB")


# ── 3. Boundary decision logic (mirrors upload_dataset streaming check) ─────

def decide(size_bytes: int, limit_mb: int) -> tuple[bool, str]:
    """Return (accepted?, message) the same way the streaming loop decides."""
    if size_bytes > limit_mb * 1024 * 1024:
        return False, size_limit_error_message(
            size_bytes / (1024 * 1024), limit_mb, "free"
        )
    return True, ""


def test_boundaries() -> None:
    print("\n══ 3. Boundary sizes (accept at limit, reject 1 byte over) ══")

    for tier in ("free", "pro", "enterprise"):
        limit_mb = effective_size_limit_mb(tier=tier)
        limit_bytes = limit_mb * 1024 * 1024

        # Exactly at the limit → accepted
        ok, _ = decide(limit_bytes, limit_mb)
        check(
            f"{tier}: {limit_mb}MB exactly → accepted",
            ok,
        )
        # 1 byte over → rejected with 413 message
        ok, msg = decide(limit_bytes + 1, limit_mb)
        check(
            f"{tier}: {limit_mb}MB + 1 byte → rejected",
            not ok and "exceeds" in msg,
            f"(accepted={ok}, msg={msg[:80]!r})",
        )
        # Way over (e.g. 311MB on free tier) → rejected
        if tier == "free":
            ok, msg = decide(311 * 1024 * 1024, limit_mb)
            check(
                "free: 311MB file (the original bug) → rejected",
                not ok and "311.0MB" in msg and "upgrade" in msg.lower(),
                f"(accepted={ok}, msg={msg[:120]!r})",
            )


# ── 4. Error messages ────────────────────────────────────────────────────────

def test_error_messages() -> None:
    print("\n══ 4. 413 error messages ══")

    free_msg = size_limit_error_message(311.0, 200, "free")
    check(
        "free-tier message mentions the limit and split advice",
        "200MB" in free_msg and "Split the file" in free_msg,
        f"({free_msg[:120]!r})",
    )
    check(
        "free-tier message includes upgrade hint",
        "Upgrade to Pro" in free_msg,
    )

    ent_msg = size_limit_error_message(500.0, 1024, "enterprise")
    check(
        "enterprise message has no upgrade hint",
        "Upgrade" not in ent_msg,
        f"({ent_msg[:120]!r})",
    )


# ── 5. Optional live HTTP uploads ────────────────────────────────────────────

async def _upload_file(base_url: str, token: str, filename: str, data: bytes) -> int:
    import httpx

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{base_url}/api/datasets/upload",
            files={"file": (filename, io.BytesIO(data), "text/csv")},
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp.status_code


async def test_live_uploads(base_url: str, token: str) -> None:
    print("\n══ 5. Live uploads against the running backend ══")

    if not token:
        print("  Skipped — pass --token to run live upload tests.")
        return

    # A tiny CSV header so a rejected file is never accidentally processed
    header = b"col_a,col_b\n1,foo\n"
    for tier in ("free", "pro", "enterprise"):
        limit_mb = effective_size_limit_mb(tier=tier)
        limit_bytes = limit_mb * 1024 * 1024

        # At the limit (minus header room) → expect 202 accepted
        filler = b"x" * (limit_bytes - len(header))
        at_limit = header + filler
        status = await _upload_file(base_url, token, f"at-limit-{tier}.csv", at_limit)
        check(
            f"{tier}: file at {limit_mb}MB → 202 accepted",
            status == 202,
            f"(got HTTP {status})",
        )

        # 1 byte over → expect 413
        over = header + filler + b"y"
        status = await _upload_file(base_url, token, f"over-limit-{tier}.csv", over)
        check(
            f"{tier}: file at {limit_mb}MB + 1 byte → 413 rejected",
            status == 413,
            f"(got HTTP {status})",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="print per-case details")
    parser.add_argument("--base-url", default="", help="backend base URL for live tests")
    parser.add_argument("--token", default="", help="JWT for live tests")
    args = parser.parse_args()

    print("=" * 64)
    print("UPLOAD SIZE LIMIT TESTS")
    print(f"Pipeline ceiling: {settings.PIPELINE_MAX_FILE_SIZE_MB}MB")
    print(f"Tier limits: {settings.TIER_FILE_SIZE_LIMITS_MB}")
    print(f"Default tier: {DEFAULT_TIER}")
    print("=" * 64)

    test_tier_resolution()
    test_effective_limits()
    test_boundaries()
    test_error_messages()

    if args.base_url:
        import asyncio

        asyncio.run(test_live_uploads(args.base_url, args.token))
    else:
        print("\n  Live upload tests skipped — pass --base-url to run them.")

    print("\n" + "=" * 64)
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 64)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()

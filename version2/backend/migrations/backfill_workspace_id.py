"""
Migration Script: Backfill workspace_id on legacy documents
============================================================

One-time migration that tags every legacy tenant-scoped document with the
``workspace_id`` of its owner's **personal workspace**, so the ``$or`` legacy
hatch in ``db/tenant_guard.py`` can eventually be removed and the composite
``(workspace_id, ...)`` indexes are always used.

Scope
-----
Collections backfilled (all registered in ``db/tenant_guard.TENANT_SCOPED_COLLECTIONS``):

1. ``uploads``              — resolved via the owner's personal workspace
2. ``dataset_profiles``     — copied from the parent ``uploads`` doc
3. ``dataset_intelligence`` — copied from the parent ``uploads`` doc
4. ``dataset_analytics``    — resolved via the owner's personal workspace
5. ``pipeline_stages``      — resolved via the owner's personal workspace

Idempotency
-----------
Only documents whose ``workspace_id`` is **missing or null** are touched
(MongoDB's ``{"workspace_id": None}`` matches both). Re-running is a no-op,
and every write re-checks ``workspace_id: None`` so concurrent runs cannot
overwrite a value set by another process.

Personal workspace resolution
-----------------------------
For each owner we look up ``workspaces`` where ``owner_id == user_id`` and
``is_personal == True``. If no personal workspace exists, one is **created**
(same shape as ``workspace_service.create_workspace``), because that is what
the application does on login — so this migration never leaves a document
un-tagged for a user the app would auto-provision.

**Read-only modes never write.** ``--check`` and ``--dry-run`` do not create
workspaces or modify documents; missing personal workspaces are reported as
\"would create\" instead.

Run this BEFORE rolling out code that relies on workspace-scoped reads.
Recommended:
    python -m migrations.backfill_workspace_id --check        # inspect first
    python -m migrations.backfill_workspace_id --dry-run      # plan only
    python -m migrations.backfill_workspace_id -y             # apply

Options:
    --check          Report how many documents need backfilling, write nothing
    --dry-run        Show every change that would be made, write nothing
    --collections X  Comma-separated subset (uploads,dataset_profiles,...)
    --limit N        Cap documents examined per collection (default: unlimited)
    -y, --yes        Skip the confirmation prompt

Author: DataSage platform team
Version: 1.1
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo import MongoClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Collections keyed by dataset_id — workspace_id is copied from the parent
# uploads document rather than resolved by owner.
_COPY_FROM_UPLOADS = ("dataset_profiles", "dataset_intelligence")

# Collections carrying user_id — workspace_id is resolved by owner.
_BY_OWNER_COLLECTIONS = ("dataset_analytics", "pipeline_stages")

ALL_COLLECTIONS = ("uploads",) + _COPY_FROM_UPLOADS + _BY_OWNER_COLLECTIONS

# Same defaults as db.schemas_workspace.WorkspaceSettings — kept inline to
# keep this migration dependency-light.
_DEFAULT_WORKSPACE_SETTINGS = {
    "default_date_range": "last_30_days",
    "preferred_domain": None,
    "timezone": "UTC",
    "currency": "USD",
}


def get_mongo_client() -> tuple[MongoClient, Any, str]:
    """Get MongoDB client + database handle."""
    mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    database_name = os.getenv("DATABASE_NAME", "signal_ai")
    client = MongoClient(mongo_url)
    return client, client[database_name], database_name


# ── Helpers ─────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _legacy_filter() -> dict[str, Any]:
    """Matches documents whose workspace_id is missing OR null (legacy)."""
    return {"workspace_id": None}


def _to_object_id(value: str) -> Optional[ObjectId]:
    """Convert a string to ObjectId when possible (None otherwise)."""
    try:
        return ObjectId(value)
    except Exception:
        return None


def _fetch(db, collection: str, filter_dict: dict[str, Any], limit: Optional[int] = None):
    """List documents for a filter (helper so the logic is easily testable)."""
    cursor = db[collection].find(filter_dict)
    if limit is not None:
        cursor = cursor.limit(limit)
    return list(cursor)


def _get_username(db, user_id: str) -> Optional[str]:
    """Best-effort username lookup for naming newly created workspaces."""
    # users._id is an ObjectId; try that form first (matches the app's _to_id).
    oid = _to_object_id(user_id)
    if oid is not None:
        try:
            user = db.users.find_one({"_id": oid})
            if user and user.get("username"):
                return user["username"]
        except Exception:
            pass
    try:
        user = db.users.find_one({"_id": user_id})
        if user and user.get("username"):
            return user["username"]
    except Exception:
        pass
    return None


def resolve_personal_workspace(
    db,
    user_id: str,
    workspace_cache: dict[str, Optional[str]],
    create_if_missing: bool = True,
) -> tuple[Optional[str], bool, bool]:
    """
    Return ``(workspace_id, created, would_create)`` for a user's personal workspace.

    - ``workspace_id``: the resolved personal workspace id, or None.
    - ``created``: True if this call inserted a new workspace.
    - ``would_create``: True if no workspace exists but creation was skipped
      (``create_if_missing=False`` — used by read-only modes).

    Reuses ``workspace_cache`` (user_id -> workspace_id) to avoid re-querying.
    Creating a workspace mirrors ``workspace_service.create_workspace``.

    Returns ``(None, False, False)`` for users with no resolvable identity.
    """
    if not user_id:
        return None, False, False
    user_id = str(user_id)

    if user_id in workspace_cache:
        wid = workspace_cache[user_id]
        return (wid, False, False) if wid else (None, False, False)

    # 1. Look up existing personal workspace
    doc = db.workspaces.find_one({"owner_id": user_id, "is_personal": True})
    if doc:
        wid = str(doc["_id"])
        workspace_cache[user_id] = wid
        return wid, False, False

    # 2. Read-only modes: report "would create", never write.
    if not create_if_missing:
        logger.info("  would create personal workspace for owner %s", user_id[:8])
        workspace_cache[user_id] = None
        return None, False, True

    # 3. Create one (same shape as workspace_service.create_workspace)
    try:
        username = _get_username(db, user_id) or user_id[:8]
        workspace_doc = {
            "name": f"{username}'s Workspace",
            "description": "",
            "owner_id": user_id,
            "settings": dict(_DEFAULT_WORKSPACE_SETTINGS),
            "is_personal": True,
            "member_count": 1,
            "dataset_count": 0,
            "created_at": _now(),
            "updated_at": _now(),
        }
        result = db.workspaces.insert_one(workspace_doc)
        wid = str(result.inserted_id)

        db.workspace_members.insert_one(
            {
                "workspace_id": wid,
                "user_id": user_id,
                "role": "owner",
                "added_by": user_id,
                "joined_at": _now(),
            }
        )
        workspace_cache[user_id] = wid
        logger.info("  Created personal workspace %s for owner %s", wid[:8], user_id[:8])
        return wid, True, False
    except Exception as e:
        logger.warning("  Failed to create personal workspace for %s: %s", user_id[:8], e)
        workspace_cache[user_id] = None
        return None, False, False


def _lookup_uploads_workspace(db, dataset_id: Any) -> Optional[str]:
    """
    Return the workspace_id of the parent uploads doc, handling both
    string-UUID and ObjectId ``_id`` forms (legacy datasets used ObjectIds).
    """
    if not dataset_id:
        return None
    oid = _to_object_id(str(dataset_id))
    for candidate in ([oid, dataset_id] if oid is not None else [dataset_id]):
        try:
            parent = db.uploads.find_one({"_id": candidate}, {"workspace_id": 1})
        except Exception:
            parent = None
        if parent and parent.get("workspace_id"):
            return parent["workspace_id"]
    return None


# ── Backfill steps ──────────────────────────────────────────────────────────


def backfill_uploads(
    db,
    *,
    dry_run: bool,
    limit: Optional[int] = None,
    workspace_cache: Optional[dict[str, Optional[str]]] = None,
) -> dict[str, int]:
    """Tag legacy uploads docs with their owner's personal workspace id."""
    workspace_cache = workspace_cache if workspace_cache is not None else {}
    summary = {"updated": 0, "skipped_no_owner": 0, "skipped_no_workspace": 0}

    legacy = _fetch(db, "uploads", _legacy_filter(), limit)
    for doc in legacy:
        user_id = doc.get("user_id")
        if not user_id:
            summary["skipped_no_owner"] += 1
            continue

        wid, _created, would_create = resolve_personal_workspace(
            db, str(user_id), workspace_cache, create_if_missing=not dry_run
        )

        if dry_run:
            # Workspace creation is suppressed; the doc would be tagged in
            # apply mode (either with an existing or a newly created workspace).
            summary["updated"] += 1
            if would_create:
                logger.info("  would tag upload %s (workspace would be created)", doc["_id"])
            continue

        if not wid:
            summary["skipped_no_workspace"] += 1
            continue

        result = db.uploads.update_one(
            {"_id": doc["_id"], "workspace_id": None},
            {"$set": {"workspace_id": wid, "updated_at": _now()}},
        )
        summary["updated"] += result.modified_count

    return summary


def backfill_split_from_uploads(
    db,
    collection: str,
    *,
    dry_run: bool,
    limit: Optional[int] = None,
) -> dict[str, int]:
    """Copy workspace_id from the parent uploads doc onto split collections."""
    summary = {"updated": 0, "skipped_no_parent": 0, "skipped_parent_untagged": 0}

    legacy = _fetch(db, collection, _legacy_filter(), limit)
    for doc in legacy:
        wid = _lookup_uploads_workspace(db, doc.get("dataset_id"))
        if wid is None:
            summary["skipped_no_parent"] += 1
            continue

        if dry_run:
            summary["updated"] += 1
            continue

        result = db[collection].update_one(
            {"_id": doc["_id"], "workspace_id": None},
            {"$set": {"workspace_id": wid, "updated_at": _now()}},
        )
        summary["updated"] += result.modified_count

    return summary


def backfill_by_owner(
    db,
    collection: str,
    *,
    dry_run: bool,
    limit: Optional[int] = None,
    workspace_cache: Optional[dict[str, Optional[str]]] = None,
) -> dict[str, int]:
    """Tag docs that carry a user_id by resolving the owner's workspace."""
    workspace_cache = workspace_cache if workspace_cache is not None else {}
    summary = {"updated": 0, "skipped_no_owner": 0, "skipped_no_workspace": 0}

    legacy = _fetch(db, collection, _legacy_filter(), limit)
    for doc in legacy:
        user_id = doc.get("user_id")
        if not user_id:
            summary["skipped_no_owner"] += 1
            continue

        wid, _created, would_create = resolve_personal_workspace(
            db, str(user_id), workspace_cache, create_if_missing=not dry_run
        )

        if dry_run:
            summary["updated"] += 1
            if would_create:
                logger.info(
                    "  would tag %s doc %s (workspace would be created)",
                    collection,
                    doc["_id"],
                )
            continue

        if not wid:
            summary["skipped_no_workspace"] += 1
            continue

        result = db[collection].update_one(
            {"_id": doc["_id"], "workspace_id": None},
            {"$set": {"workspace_id": wid, "updated_at": _now()}},
        )
        summary["updated"] += result.modified_count

    return summary


def run_backfill(
    db,
    *,
    check_only: bool = False,
    dry_run: bool = False,
    collections: Optional[tuple[str, ...]] = None,
    limit: Optional[int] = None,
) -> dict[str, dict[str, int]]:
    """Run the backfill for the requested collections. Returns per-collection summaries."""
    targets = collections or ALL_COLLECTIONS
    mode = "CHECK" if check_only else ("DRY-RUN" if dry_run else "APPLY")
    logger.info("=" * 60)
    logger.info("BACKFILL workspace_id — mode: %s", mode)
    logger.info("Collections: %s", ", ".join(targets))
    logger.info("=" * 60)

    # Share the workspace resolution cache across steps for consistency.
    workspace_cache: dict[str, Optional[str]] = {}
    results: dict[str, dict[str, int]] = {}

    for coll in targets:
        if coll == "uploads":
            summary = backfill_uploads(
                db, dry_run=dry_run, limit=limit, workspace_cache=workspace_cache
            )
        elif coll in _COPY_FROM_UPLOADS:
            summary = backfill_split_from_uploads(db, coll, dry_run=dry_run, limit=limit)
        elif coll in _BY_OWNER_COLLECTIONS:
            summary = backfill_by_owner(
                db, coll, dry_run=dry_run, limit=limit, workspace_cache=workspace_cache
            )
        else:
            logger.warning("  Unknown collection '%s' — skipping", coll)
            continue

        results[coll] = summary
        logger.info(
            "  %-22s updated=%d skipped_no_owner=%d skipped_no_workspace=%d skipped_no_parent=%d",
            coll,
            summary.get("updated", 0),
            summary.get("skipped_no_owner", 0),
            summary.get("skipped_no_workspace", 0),
            summary.get("skipped_no_parent", 0),
        )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill workspace_id on legacy tenant-scoped documents"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report how many documents need backfilling without writing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing",
    )
    parser.add_argument(
        "--collections",
        default=None,
        help="Comma-separated subset of: " + ",".join(ALL_COLLECTIONS),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap documents examined per collection (default: unlimited)",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip confirmation prompt"
    )
    args = parser.parse_args()

    collections = (
        tuple(c.strip() for c in args.collections.split(",") if c.strip())
        if args.collections
        else None
    )

    client, db, db_name = get_mongo_client()
    try:
        logger.info("Connected to database: %s", db_name)

        if args.check:
            summaries = run_backfill(
                db, check_only=True, dry_run=True, collections=collections, limit=args.limit
            )
            total = sum(s.get("updated", 0) for s in summaries.values())
            logger.info("Documents needing backfill: %d", total)
            return 0

        if args.dry_run:
            run_backfill(db, dry_run=True, collections=collections, limit=args.limit)
            logger.info("DRY-RUN COMPLETE — no changes written")
            return 0

        if not args.yes:
            confirm = input(
                "This will write workspace_id to legacy documents. Continue? (yes/no): "
            )
            if confirm.lower() != "yes":
                logger.info("Backfill cancelled")
                return 0

        run_backfill(db, dry_run=False, collections=collections, limit=args.limit)
        logger.info("BACKFILL COMPLETE")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())

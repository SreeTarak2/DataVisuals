"""
Database-Layer Tenant Guard
===========================

Fail-closed enforcement that tenant-scoped collections are only ever read or
written inside the caller's workspace boundary.

Post-backfill model
-------------------
After ``migrations/backfill_workspace_id.py`` has been run, every document in
a tenant-scoped collection carries a real ``workspace_id`` (its owner's
personal workspace, or the shared workspace it was uploaded into). There are
no legacy untagged documents any more — so reads are **strictly
workspace-scoped** and no legacy hatches are needed.

Design
------
- ``TENANT_SCOPED_COLLECTIONS``: collections whose documents belong to exactly
  one workspace (tenant). Anything in this set MUST be queried with a
  workspace-scoped filter.
- ``resolve_workspace_id()``: canonical tenant resolution for **tagging**
  writes. When a caller supplies ``workspace_id`` it wins; otherwise the
  caller's own ``user_id`` is used as a last-resort personal-workspace id.
  Prefer passing a real workspace id — callers with async access should use
  ``workspace_service.resolve_effective_workspace_id`` instead.
- ``tenant_scope_query()``: builds the read filter. **Strictly
  workspace-scoped** — ``{**base_filter, "workspace_id": wid}``. Raises
  ``TenantIsolationError`` if no ``workspace_id`` is provided (a caller that
  cannot name a workspace must never touch tenant-scoped data; async callers
  should resolve one via ``workspace_service`` first).
- ``enforce_workspace_filter()``: fail-closed validator for direct raw-filter
  queries. Raises ``TenantIsolationError`` if a query on a tenant-scoped
  collection does not pin ``workspace_id`` to the caller's workspace.
- ``assert_doc_workspace()``: validates a fetched/being-written document
  belongs to the caller's workspace. Retains a defensive pre-backfill
  fallback (a document with no ``workspace_id`` must be owned by the caller)
  so environments that have not yet run the migration stay safe.

Usage
-----
    from db.tenant_guard import tenant_scope_query, resolve_workspace_id

    wid = resolve_workspace_id(workspace_id, user_id)          # for tagging writes
    query = tenant_scope_query("uploads", {"_id": dataset_id}, wid, user_id)
    doc = await db.uploads.find_one(query)
"""

from __future__ import annotations

from typing import Any, Optional

# Collections whose documents are bound to exactly one workspace.
# Kept intentionally conservative — only collections we actively write
# ``workspace_id`` into are enforced here. Adding a collection to this set
# makes reads/writes on it fail closed unless workspace-scoped.
TENANT_SCOPED_COLLECTIONS: frozenset[str] = frozenset(
    {
        "uploads",  # dataset documents (the primary tenant boundary)
        "dataset_profiles",
        "dataset_intelligence",
        "dataset_analytics",
        "pipeline_stages",
        # Project workspace (analysis containers + their sources/cells)
        "projects",
        "project_sources",
        "project_cells",
        # Ontology assumptions (semantic state machine) — workspace-scoped
        "semantic_assumptions",
    }
)


class TenantIsolationError(Exception):
    """Raised when code attempts to read/write outside its workspace boundary."""

    def __init__(self, message: str):
        super().__init__(f"Tenant isolation violation: {message}")


def is_tenant_scoped(collection: str) -> bool:
    """Return True if ``collection`` is registered as tenant-scoped."""
    return collection in TENANT_SCOPED_COLLECTIONS


def resolve_workspace_id(
    workspace_id: Optional[str],
    user_id: Optional[str],
) -> str:
    """
    Resolve the effective tenant id to TAG a write with.

    Returns ``workspace_id`` when provided. Otherwise falls back to
    ``user_id``, which is the id of the user's *personal* workspace in the
    legacy single-tenant model. Async callers that can hit the database
    should prefer ``workspace_service.resolve_effective_workspace_id`` so
    the personal workspace ObjectId (the canonical tag post-backfill) is
    used instead of the raw user_id.

    Raises ``TenantIsolationError`` if neither is available — a caller with
    no tenant identity must never touch tenant-scoped data.
    """
    if workspace_id:
        return str(workspace_id)
    if user_id:
        return str(user_id)
    raise TenantIsolationError("caller has no workspace_id or user_id")


def enforce_workspace_filter(
    collection: str,
    filter_dict: dict[str, Any],
    workspace_id: Optional[str],
    operation: str = "query",
) -> None:
    """
    Fail-closed check: a raw query on a tenant-scoped collection MUST pin
    ``workspace_id`` to the caller's workspace.

    Raises ``TenantIsolationError`` if:
      - the collection is tenant-scoped and no ``workspace_id`` is provided, or
      - the filter's ``workspace_id`` does not match (or is not strictly
        equal to) the caller's workspace id.

    ``filter_dict`` is not mutated. This guards direct raw-filter usage;
    ``tenant_scope_query`` is the recommended way to build read filters and
    ``assert_doc_workspace`` guards document-level operations.
    """
    if not is_tenant_scoped(collection):
        return

    wid = resolve_workspace_id(workspace_id, None) if workspace_id else None
    if wid is None:
        raise TenantIsolationError(
            f"workspace_id is required for {operation} on '{collection}'"
        )

    actual = filter_dict.get("workspace_id")
    if actual is None:
        raise TenantIsolationError(
            f"filter for '{collection}' is missing workspace_id (required for {operation})"
        )

    # Operator forms that are strictly pinned to the caller's workspace.
    if isinstance(actual, dict):
        eq = actual.get("$eq")
        if eq is not None and str(eq) == wid:
            return
        in_list = actual.get("$in")
        if in_list is not None and [str(x) for x in in_list] == [wid]:
            return
        raise TenantIsolationError(
            f"filter for '{collection}' pins workspace_id to a value other than "
            f"the caller's workspace ({wid[:8]}...) during {operation}"
        )

    if str(actual) != wid:
        raise TenantIsolationError(
            f"filter for '{collection}' targets workspace {str(actual)[:8]}... "
            f"but caller's workspace is {wid[:8]}... during {operation}"
        )


def tenant_scope_query(
    collection: str,
    base_filter: dict[str, Any],
    workspace_id: Optional[str],
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build a **strictly workspace-scoped** MongoDB query filter.

    For tenant-scoped collections the returned filter is::

        {**base_filter, "workspace_id": wid}

    No legacy hatches exist: post-backfill every document carries a real
    ``workspace_id``, so an unscoped query is never valid. Callers without a
    workspace context MUST resolve one first (e.g.
    ``workspace_service.resolve_effective_workspace_id``) rather than relying
    on owner-scoping — owner scoping was removed to guarantee strict tenant
    isolation.

    Raises ``TenantIsolationError`` if:
      - the collection is tenant-scoped and no ``workspace_id`` is provided, or
      - ``base_filter`` already contains ``$or`` (this helper owns the
        top-level query shape and would otherwise silently change semantics).

    For non-tenant-scoped collections, ``base_filter`` is returned unchanged.
    """
    if not is_tenant_scoped(collection):
        return base_filter or {}

    if not workspace_id:
        raise TenantIsolationError(
            f"workspace_id is required to scope a query on '{collection}' — "
            "no legacy owner-scoped fallback exists"
        )

    scope_filter = dict(base_filter or {})
    scope_filter.pop("workspace_id", None)  # this helper owns workspace scoping

    if "$or" in scope_filter:
        raise TenantIsolationError(
            f"base_filter for '{collection}' must not contain '$or' — "
            "tenant_scope_query owns the top-level query shape"
        )

    scope_filter["workspace_id"] = str(workspace_id)
    return scope_filter


def assert_doc_workspace(
    doc: Optional[dict[str, Any]],
    workspace_id: Optional[str],
    user_id: Optional[str],
) -> None:
    """
    Verify a document belongs to the caller's workspace.

    - Docs carrying a non-null ``workspace_id`` must match the caller's
      workspace id.
    - Docs with no ``workspace_id`` (pre-backfill window) must be owned by
      ``user_id`` — a defensive fallback that keeps environments which have
      not yet run the migration safe. It is NOT a read path: reads always go
      through ``tenant_scope_query``.

    Raises ``TenantIsolationError`` on mismatch. ``None`` docs pass (caller
    decides how to handle "not found").
    """
    if not doc:
        return

    wid = resolve_workspace_id(workspace_id, user_id)
    doc_wid = doc.get("workspace_id")
    if doc_wid:
        if str(doc_wid) != str(wid):
            raise TenantIsolationError(
                f"document belongs to workspace {str(doc_wid)[:8]}..., "
                f"not caller's workspace {str(wid)[:8]}..."
            )
        return

    # Defensive pre-backfill fallback — must be owned by the caller.
    if user_id and doc.get("user_id") and str(doc.get("user_id")) != str(user_id):
        raise TenantIsolationError("legacy document is owned by another user")


__all__ = [
    "TENANT_SCOPED_COLLECTIONS",
    "TenantIsolationError",
    "is_tenant_scoped",
    "resolve_workspace_id",
    "enforce_workspace_filter",
    "tenant_scope_query",
    "assert_doc_workspace",
]

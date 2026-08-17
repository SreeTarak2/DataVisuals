"""
Unit tests for the database-layer tenant guard (db/tenant_guard.py).

Post-backfill model (migrations/backfill_workspace_id.py has run): every
document in a tenant-scoped collection carries a real ``workspace_id``, so
reads are **strictly workspace-scoped** — no legacy owner-scoped hatches.

Verifies the fail-closed guarantees that power workspace isolation:
  - tenant-scoped collections cannot be queried without a workspace id
  - cross-workspace filters raise TenantIsolationError
  - queries are strictly pinned to the caller's workspace (no $or hatches)
  - writes/reads are rejected for documents belonging to another workspace
  - callers without a workspace context MUST resolve one (via
    workspace_service.resolve_effective_workspace_id) — they never fall back
    to owner scoping
"""

import pytest

from db.tenant_guard import (
    TENANT_SCOPED_COLLECTIONS,
    TenantIsolationError,
    assert_doc_workspace,
    enforce_workspace_filter,
    is_tenant_scoped,
    resolve_workspace_id,
    tenant_scope_query,
)


class TestIsTenantScoped:
    def test_uploads_is_tenant_scoped(self):
        assert is_tenant_scoped("uploads") is True

    def test_non_scoped_collection_passes(self):
        assert is_tenant_scoped("db_connections") is False


class TestResolveWorkspaceId:
    def test_prefers_workspace_id(self):
        assert resolve_workspace_id("ws-1", "user-1") == "ws-1"

    def test_falls_back_to_user_id(self):
        assert resolve_workspace_id(None, "user-1") == "user-1"

    def test_raises_when_no_identity(self):
        with pytest.raises(TenantIsolationError):
            resolve_workspace_id(None, None)


class TestEnforceWorkspaceFilter:
    def test_scoped_collection_requires_workspace_id(self):
        with pytest.raises(TenantIsolationError):
            enforce_workspace_filter("uploads", {"user_id": "u1"}, None)

    def test_missing_workspace_key_raises(self):
        with pytest.raises(TenantIsolationError):
            enforce_workspace_filter("uploads", {"user_id": "u1"}, "ws-1")

    def test_matching_workspace_passes(self):
        # Should not raise
        enforce_workspace_filter("uploads", {"workspace_id": "ws-1"}, "ws-1")

    def test_cross_workspace_filter_raises(self):
        with pytest.raises(TenantIsolationError):
            enforce_workspace_filter("uploads", {"workspace_id": "ws-2"}, "ws-1")

    def test_eq_operator_matching_passes(self):
        enforce_workspace_filter("uploads", {"workspace_id": {"$eq": "ws-1"}}, "ws-1")

    def test_eq_operator_cross_workspace_raises(self):
        with pytest.raises(TenantIsolationError):
            enforce_workspace_filter("uploads", {"workspace_id": {"$eq": "ws-2"}}, "ws-1")

    def test_in_operator_only_own_workspace_passes(self):
        enforce_workspace_filter("uploads", {"workspace_id": {"$in": ["ws-1"]}}, "ws-1")
        with pytest.raises(TenantIsolationError):
            enforce_workspace_filter(
                "uploads", {"workspace_id": {"$in": ["ws-1", "ws-2"]}}, "ws-1"
            )

    def test_ne_operator_rejected_fail_closed(self):
        # A $ne filter is not a strict pin — must be rejected.
        with pytest.raises(TenantIsolationError):
            enforce_workspace_filter("uploads", {"workspace_id": {"$ne": "ws-2"}}, "ws-1")

    def test_non_scoped_collection_ignored(self):
        # Should not raise even with a cross-workspace-looking filter
        enforce_workspace_filter("users", {"user_id": "u1"}, "ws-1")


class TestTenantScopeQueryStrictScoping:
    def test_scoped_collection_pinned_to_workspace(self):
        q = tenant_scope_query(
            "uploads", {"_id": "d1", "is_active": True}, "ws-1", "user-1"
        )
        # Strictly workspace-scoped — no $or legacy hatch.
        assert q == {"_id": "d1", "is_active": True, "workspace_id": "ws-1"}
        assert "$or" not in q

    def test_workspace_only_filter(self):
        q = tenant_scope_query("uploads", {}, "ws-1", None)
        assert q == {"workspace_id": "ws-1"}

    def test_base_filter_workspace_id_overwritten(self):
        # The helper owns workspace scoping: any caller-supplied workspace_id
        # in base_filter is replaced with the resolved tenant.
        q = tenant_scope_query(
            "uploads", {"workspace_id": "ws-2", "is_active": True}, "ws-1", "user-1"
        )
        assert q == {"is_active": True, "workspace_id": "ws-1"}

    def test_non_scoped_collection_passthrough(self):
        base = {"user_id": "user-1"}
        q = tenant_scope_query("db_connections", base, "ws-1", "user-1")
        assert q == base

    def test_existing_or_in_base_filter_raises(self):
        # Silently dropping a caller's $or would change query semantics.
        with pytest.raises(TenantIsolationError):
            tenant_scope_query(
                "uploads",
                {"$or": [{"status": "active"}, {"status": "pending"}]},
                "ws-1",
                "user-1",
            )


class TestTenantScopeQueryNoWorkspace:
    def test_no_workspace_raises(self):
        # Strict post-backfill model: a caller that cannot name a workspace
        # must never touch tenant-scoped data. No owner-scoped fallback.
        with pytest.raises(TenantIsolationError):
            tenant_scope_query("uploads", {"_id": "d1"}, None, "user-1")

    def test_no_identity_raises(self):
        with pytest.raises(TenantIsolationError):
            tenant_scope_query("uploads", {}, None, None)


class TestAssertDocWorkspace:
    def test_doc_in_caller_workspace_passes(self):
        assert_doc_workspace({"workspace_id": "ws-1"}, "ws-1", "user-1")

    def test_doc_in_other_workspace_raises(self):
        with pytest.raises(TenantIsolationError):
            assert_doc_workspace({"workspace_id": "ws-2"}, "ws-1", "user-1")

    def test_doc_tagged_with_workspace_oid_matches(self):
        # A doc tagged with a workspace ObjectId passes when the caller names
        # that same workspace.
        assert_doc_workspace({"workspace_id": "65f0abc"}, "65f0abc", "user-1")

    def test_legacy_doc_owned_by_caller_passes(self):
        # Defensive pre-backfill window: untagged docs must be owned by caller.
        assert_doc_workspace({"user_id": "user-1"}, "ws-1", "user-1")

    def test_legacy_doc_with_null_workspace_owned_by_caller_passes(self):
        assert_doc_workspace(
            {"workspace_id": None, "user_id": "user-1"}, "ws-1", "user-1"
        )

    def test_legacy_doc_owned_by_other_raises(self):
        with pytest.raises(TenantIsolationError):
            assert_doc_workspace({"user_id": "user-2"}, "ws-1", "user-1")

    def test_none_doc_passes(self):
        assert_doc_workspace(None, "ws-1", "user-1")

    def test_registry_contains_core_tenant_collections(self):
        assert {"uploads", "dataset_profiles", "dataset_intelligence"} <= set(
            TENANT_SCOPED_COLLECTIONS
        )

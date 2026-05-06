"""Backward-compatible import shim for legacy audit service path."""

from services.audit import audit_service

__all__ = ["audit_service"]

"""Backward-compatible import shim for legacy auth service path."""

from services.auth import auth_service, get_current_user

__all__ = ["auth_service", "get_current_user"]

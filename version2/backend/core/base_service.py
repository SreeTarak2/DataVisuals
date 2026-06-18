"""
Base service — common contract for all application services.

Provides structured logging, error wrapping, and lifecycle hooks
so that every service follows the same patterns.
"""

from __future__ import annotations

import logging
from typing import Any

from core.exceptions import AppError


class BaseService:
    """
    Shared base for all domain services.

    Subclasses override:
    - _service_name()  → label used in log messages
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(self._service_name())

    @property
    def _service_name(self) -> str:
        return self.__class__.__name__

    # ── Convenience log helpers ────────────────────────────────────────────

    def log_info(self, msg: str, **extra: Any) -> None:
        self._logger.info(f"[{self._service_name}] {msg}", extra=extra)

    def log_warning(self, msg: str, **extra: Any) -> None:
        self._logger.warning(f"[{self._service_name}] {msg}", extra=extra)

    def log_error(self, msg: str, exc_info: bool = True, **extra: Any) -> None:
        self._logger.error(f"[{self._service_name}] {msg}", exc_info=exc_info, extra=extra)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Called once at application startup. Override to inject dependencies."""
        self.log_info("Initialized")

    async def shutdown(self) -> None:
        """Called once at application shutdown. Override to release resources."""
        self.log_info("Shutdown")

    # ── Error helpers ──────────────────────────────────────────────────────

    def _raise(self, error_class: type[AppError], message: str, **context: Any) -> None:
        """Raise a typed AppError with structured context."""
        raise error_class(message, code=f"{self._service_name}.{error_class.__name__}")

"""Backward-compatible import shim for legacy llm_router path."""

from services.llm import llm_router

__all__ = ["llm_router"]

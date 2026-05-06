"""Backward-compatible import shim for legacy query executor path."""

from services.query.executor import QueryClassifier, query_classifier, query_executor

__all__ = ["query_executor", "query_classifier", "QueryClassifier"]

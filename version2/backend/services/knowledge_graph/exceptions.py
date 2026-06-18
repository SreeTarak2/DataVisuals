"""
Graph Storage Exceptions
=========================

Custom exceptions for graph operations.
"""


class GraphStorageError(Exception):
    """Base exception for graph storage operations"""

    pass


class GraphConnectionError(GraphStorageError):
    """Raised when connection to graph database fails"""

    pass


class NodeNotFoundError(GraphStorageError):
    """Raised when a node doesn't exist"""

    pass


class RelationshipError(GraphStorageError):
    """Raised when relationship operation fails"""

    pass


class QueryError(GraphStorageError):
    """Raised when graph query fails"""

    pass


class GraphTimeoutError(GraphStorageError):
    """Raised when operation times out"""

    pass


__all__ = [
    "GraphStorageError",
    "GraphConnectionError",
    "NodeNotFoundError",
    "RelationshipError",
    "QueryError",
    "GraphTimeoutError",
]

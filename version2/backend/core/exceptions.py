"""
Core exceptions — base exception hierarchy for the application.

All domain-level exceptions should inherit from AppError to ensure
consistent error handling and logging across the stack.
"""


class AppError(Exception):
    """Base exception for all application-level errors."""

    def __init__(self, message: str = "", *args, code: str | None = None) -> None:
        self.code = code or self.__class__.__name__
        super().__init__(message, *args)


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""


class ValidationError(AppError):
    """Raised when input data fails validation."""


class ConfigurationError(AppError):
    """Raised when the application is misconfigured."""


class ExternalServiceError(AppError):
    """Raised when an external service (LLM, DB, etc.) fails."""


class AuthenticationError(AppError):
    """Raised when authentication fails."""


class AuthorizationError(AppError):
    """Raised when the user lacks permission."""


class RateLimitError(AppError):
    """Raised when a rate limit is exceeded."""


class RetryExhaustedError(AppError):
    """Raised when all retry attempts for an operation have been exhausted."""

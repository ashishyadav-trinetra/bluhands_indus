"""Custom exception hierarchy.

All application errors derive from ``AppError`` and carry a stable machine
``code`` plus a human ``message``. The global handler renders them as the error
envelope — internal details and stack traces are never exposed to clients.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for all expected application errors.

    Args:
        message: Human-readable, safe-to-expose message.
        code: Stable machine-readable error code (SCREAMING_SNAKE_CASE).
        http_status: HTTP status code to return.
        details: Optional structured, non-sensitive context.
    """

    code: str = "APP_ERROR"
    http_status: int = 400

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.details = details or {}


class AuthenticationError(AppError):
    """Caller is not authenticated (401)."""

    code = "UNAUTHENTICATED"
    http_status = 401


class AuthorizationError(AppError):
    """Caller is authenticated but lacks permission (403)."""

    code = "FORBIDDEN"
    http_status = 403


class NotFoundError(AppError):
    """Requested resource does not exist (404)."""

    code = "NOT_FOUND"
    http_status = 404


class ConflictError(AppError):
    """Resource conflict, e.g. duplicate (409)."""

    code = "CONFLICT"
    http_status = 409


class ValidationError(AppError):
    """Domain validation failed (422)."""

    code = "VALIDATION_ERROR"
    http_status = 422


class RateLimitError(AppError):
    """Rate limit exceeded (429). ``retry_after`` is seconds to wait."""

    code = "RATE_LIMITED"
    http_status = 429

    def __init__(self, message: str = "Too many requests", *, retry_after: int = 60) -> None:
        super().__init__(message, details={"retry_after": retry_after})
        self.retry_after = retry_after


class InsufficientCreditsError(AppError):
    """Organization does not have enough credits (402)."""

    code = "INSUFFICIENT_CREDITS"
    http_status = 402

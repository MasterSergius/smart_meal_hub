"""Domain exceptions raised by the service layer.

Services raise these instead of ``fastapi.HTTPException`` so business logic stays
independent of the transport. ``app.main`` registers a single handler that turns
any ``AppError`` into a JSON response with the matching HTTP status code, using the
same ``{"detail": ...}`` body shape FastAPI uses for its own errors.
"""

from fastapi import status


class AppError(Exception):
    """Base class for all expected, client-facing application errors.

    Subclasses only set ``status_code`` (and optionally ``headers``); the message
    passed to the constructor becomes the ``detail`` field of the response.
    """

    status_code: int = status.HTTP_400_BAD_REQUEST
    headers: dict[str, str] | None = None

    def __init__(self, detail: str) -> None:
        """Store the human-readable message that is returned to the client as ``detail``."""
        super().__init__(detail)
        self.detail = detail


class NotFoundError(AppError):
    """The requested resource does not exist (HTTP 404)."""

    status_code = status.HTTP_404_NOT_FOUND


class ForbiddenError(AppError):
    """The caller is authenticated but not allowed to perform the action (HTTP 403)."""

    status_code = status.HTTP_403_FORBIDDEN


class ConflictError(AppError):
    """The action conflicts with existing data, e.g. a duplicate email (HTTP 409)."""

    status_code = status.HTTP_409_CONFLICT


class UnauthorizedError(AppError):
    """Missing, invalid or expired credentials (HTTP 401).

    Adds the ``WWW-Authenticate: Bearer`` header required by RFC 7235 so clients
    know which authentication scheme to retry with.
    """

    status_code = status.HTTP_401_UNAUTHORIZED
    headers = {"WWW-Authenticate": "Bearer"}

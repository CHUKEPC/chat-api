"""Domain exceptions for Chat API.

Provides custom exception hierarchy for consistent error handling
and clean status code mapping across API layers.
"""

from typing import Any


class ChatAPIError(Exception):
    """Base exception for all chat-api domain errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize exception with human-readable message and optional details.

        Args:
            message: Explanation of the error.
            details: Optional contextual metadata for debugging.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


# Backward compatibility alias
ChatAPIException = ChatAPIError


class NotFoundError(ChatAPIError):
    """Raised when a requested resource does not exist."""


class UserNotFoundError(NotFoundError):
    """Raised when a user cannot be found."""


class ChatNotFoundError(NotFoundError):
    """Raised when a chat room cannot be found."""


class MessageNotFoundError(NotFoundError):
    """Raised when a message cannot be found."""


class AuthenticationError(ChatAPIError):
    """Raised when credentials or tokens fail authentication."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when username/email and password combination is invalid."""


class InvalidTokenError(AuthenticationError):
    """Raised when JWT token signature or payload is invalid."""


class TokenExpiredError(AuthenticationError):
    """Raised when JWT token timestamp has expired."""


class PermissionDeniedError(ChatAPIError):
    """Raised when an authenticated actor lacks role or scope to perform action."""


class ConflictError(ChatAPIError):
    """Raised when a resource creation conflicts with existing state."""


class UserAlreadyExistsError(ConflictError):
    """Raised when username or email is already registered."""


class ChatAlreadyExistsError(ConflictError):
    """Raised when direct chat already exists between participants."""


class InvalidOperationError(ChatAPIError):
    """Raised when an action violates business rules."""


class UserMutedError(InvalidOperationError):
    """Raised when a muted participant attempts to send a message."""


class UserBannedError(InvalidOperationError):
    """Raised when a banned participant attempts to access a chat."""


class RateLimitExceededError(ChatAPIError):
    """Raised when request frequency breaches permitted thresholds."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60) -> None:
        """Initialize rate limit error with retry duration.

        Args:
            message: Error description.
            retry_after: Seconds before client may retry.
        """
        super().__init__(message, details={"retry_after": retry_after})
        self.retry_after = retry_after

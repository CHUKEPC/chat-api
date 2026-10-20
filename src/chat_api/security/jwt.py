"""JWT generation, decoding, and validation utilities."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from chat_api.config import get_settings
from chat_api.exceptions import InvalidTokenError, TokenExpiredError

settings = get_settings()


def create_token(
    data: dict[str, Any],
    expires_delta: timedelta,
    token_type: str,
) -> str:
    """Create a signed JWT token with designated type and expiration.

    Args:
        data: Payload claims to embed in token.
        expires_delta: Duration until expiration.
        token_type: Token classification ('access' or 'refresh').

    Returns:
        str: Encoded JWT string.
    """
    now = datetime.now(UTC)
    to_encode = data.copy()
    to_encode.update(
        {
            "exp": now + expires_delta,
            "iat": now,
            "type": token_type,
        }
    )
    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_access_token(
    user_id: int,
    username: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a short-lived access token for API authorization.

    Args:
        user_id: Identifier of authenticated user.
        username: Username string.
        role: User role (admin, moderator, user).
        expires_delta: Optional custom duration override.

    Returns:
        str: Encoded access JWT token.
    """
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_token(
        data={"sub": str(user_id), "username": username, "role": role},
        expires_delta=delta,
        token_type="access",
    )


def create_refresh_token(
    user_id: int,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a long-lived refresh token for renewing access tokens.

    Args:
        user_id: Identifier of authenticated user.
        expires_delta: Optional custom duration override.

    Returns:
        str: Encoded refresh JWT token.
    """
    delta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return create_token(
        data={"sub": str(user_id)},
        expires_delta=delta,
        token_type="refresh",
    )


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: Raw JWT string.
        expected_type: Optional expected token classification ('access' or 'refresh').

    Returns:
        dict[str, Any]: Decoded claims dictionary.

    Raises:
        TokenExpiredError: If token expiration timestamp has passed.
        InvalidTokenError: If token is malformed, has invalid signature, or type mismatch.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(f"Could not validate token: {exc}") from exc

    if expected_type and payload.get("type") != expected_type:
        raise InvalidTokenError(
            f"Invalid token type: expected {expected_type}, got {payload.get('type')}"
        )

    return payload

"""Unit tests for JWT generation and verification."""

from datetime import timedelta

import pytest

from chat_api.exceptions import InvalidTokenError, TokenExpiredError
from chat_api.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_create_and_decode_access_token() -> None:
    """Test generating and decoding valid access token."""
    token = create_access_token(user_id=1, username="alice", role="user")
    payload = decode_token(token, expected_type="access")

    assert payload["sub"] == "1"
    assert payload["username"] == "alice"
    assert payload["role"] == "user"
    assert payload["type"] == "access"


def test_create_and_decode_refresh_token() -> None:
    """Test generating and decoding valid refresh token."""
    token = create_refresh_token(user_id=42)
    payload = decode_token(token, expected_type="refresh")

    assert payload["sub"] == "42"
    assert payload["type"] == "refresh"


def test_decode_token_type_mismatch() -> None:
    """Test decoding fails when token type does not match expectation."""
    token = create_access_token(user_id=1, username="alice", role="user")
    with pytest.raises(InvalidTokenError, match="Invalid token type"):
        decode_token(token, expected_type="refresh")


def test_decode_token_expired() -> None:
    """Test token expiration triggers TokenExpiredError."""
    token = create_access_token(
        user_id=1,
        username="alice",
        role="user",
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(TokenExpiredError):
        decode_token(token)


def test_decode_invalid_token_string() -> None:
    """Test malformed token string raises InvalidTokenError."""
    with pytest.raises(InvalidTokenError):
        decode_token("not.a.valid.jwt.string")

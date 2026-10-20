"""Unit tests for authentication service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.exceptions import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from chat_api.models.user import User
from chat_api.schemas.auth import UserLoginRequest, UserRegisterRequest
from chat_api.security.jwt import create_refresh_token
from chat_api.services import auth as auth_service


async def test_register_user_success(db_session: AsyncSession) -> None:
    """Test successful user registration."""
    req = UserRegisterRequest(
        username="charlie",
        email="charlie@example.com",
        password="ValidPassword123!",
        role="user",
    )
    user = await auth_service.register_user(db_session, req)
    assert user.id is not None
    assert user.username == "charlie"
    assert user.email == "charlie@example.com"
    assert user.role == "user"
    assert user.is_active is True


async def test_register_duplicate_username(db_session: AsyncSession, test_user: User) -> None:
    """Test registration fails with duplicate username."""
    req = UserRegisterRequest(
        username=test_user.username,
        email="other@example.com",
        password="ValidPassword123!",
    )
    with pytest.raises(UserAlreadyExistsError, match=r"Username.*already registered"):
        await auth_service.register_user(db_session, req)


async def test_register_duplicate_email(db_session: AsyncSession, test_user: User) -> None:
    """Test registration fails with duplicate email."""
    req = UserRegisterRequest(
        username="unique_name",
        email=test_user.email,
        password="ValidPassword123!",
    )
    with pytest.raises(UserAlreadyExistsError, match=r"Email.*already registered"):
        await auth_service.register_user(db_session, req)


async def test_authenticate_user_success(db_session: AsyncSession, test_user: User) -> None:
    """Test authentication with valid credentials."""
    # Authenticate by username
    req_username = UserLoginRequest(
        username_or_email=test_user.username,
        password="Password123!",
    )
    auth_user = await auth_service.authenticate_user(db_session, req_username)
    assert auth_user.id == test_user.id

    # Authenticate by email
    req_email = UserLoginRequest(
        username_or_email=test_user.email,
        password="Password123!",
    )
    auth_user2 = await auth_service.authenticate_user(db_session, req_email)
    assert auth_user2.id == test_user.id


async def test_authenticate_user_invalid_password(
    db_session: AsyncSession, test_user: User
) -> None:
    """Test authentication fails on wrong password."""
    req = UserLoginRequest(
        username_or_email=test_user.username,
        password="WrongPassword123!",
    )
    with pytest.raises(InvalidCredentialsError):
        await auth_service.authenticate_user(db_session, req)


async def test_authenticate_inactive_user(db_session: AsyncSession, test_user: User) -> None:
    """Test authentication fails for deactivated user."""
    test_user.is_active = False
    await db_session.commit()

    req = UserLoginRequest(
        username_or_email=test_user.username,
        password="Password123!",
    )
    with pytest.raises(InvalidCredentialsError, match="inactive"):
        await auth_service.authenticate_user(db_session, req)


async def test_login_generates_tokens(db_session: AsyncSession, test_user: User) -> None:
    """Test login service returns access and refresh tokens."""
    req = UserLoginRequest(
        username_or_email=test_user.username,
        password="Password123!",
    )
    tokens = await auth_service.login(db_session, req)
    assert tokens.access_token is not None
    assert tokens.refresh_token is not None
    assert tokens.token_type == "bearer"
    assert tokens.expires_in > 0


async def test_refresh_tokens_success(db_session: AsyncSession, test_user: User) -> None:
    """Test refreshing tokens using valid refresh token."""
    refresh_token = create_refresh_token(user_id=test_user.id)
    tokens = await auth_service.refresh_tokens(db_session, refresh_token)

    assert tokens.access_token is not None
    assert tokens.refresh_token is not None


async def test_refresh_tokens_user_not_found(db_session: AsyncSession) -> None:
    """Test refresh token with nonexistent user ID raises UserNotFoundError."""
    refresh_token = create_refresh_token(user_id=99999)
    with pytest.raises(UserNotFoundError):
        await auth_service.refresh_tokens(db_session, refresh_token)

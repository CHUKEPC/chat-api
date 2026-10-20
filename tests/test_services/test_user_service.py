"""Unit tests for user service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.exceptions import (
    PermissionDeniedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from chat_api.models.user import User
from chat_api.schemas.user import UserUpdateRequest
from chat_api.services import user as user_service


async def test_get_user_by_id_and_username(db_session: AsyncSession, test_user: User) -> None:
    """Test user lookup by id and username."""
    user1 = await user_service.get_user_by_id(db_session, test_user.id)
    assert user1.username == test_user.username

    user2 = await user_service.get_user_by_username(db_session, test_user.username)
    assert user2.id == test_user.id

    with pytest.raises(UserNotFoundError):
        await user_service.get_user_by_id(db_session, 99999)

    with pytest.raises(UserNotFoundError):
        await user_service.get_user_by_username(db_session, "nonexistent_user")


async def test_list_users_filters(
    db_session: AsyncSession,
    test_user: User,
    test_user_2: User,
    test_admin: User,
) -> None:
    """Test user listing with pagination and filters."""
    users = await user_service.list_users(db_session, skip=0, limit=10)
    assert len(users) >= 3

    # Filter search by username
    search_users = await user_service.list_users(db_session, search="alice")
    assert len(search_users) == 1
    assert search_users[0].username == "alice"

    # Filter by online status
    online_users = await user_service.list_users(db_session, is_online=True)
    assert all(u.is_online for u in online_users)


async def test_update_user_self(db_session: AsyncSession, test_user: User) -> None:
    """Test updating user profile by the user themselves."""
    req = UserUpdateRequest(email="alice_new@example.com")
    updated = await user_service.update_user(
        db=db_session,
        user_id=test_user.id,
        request=req,
        actor=test_user,
    )
    assert updated.email == "alice_new@example.com"


async def test_update_user_admin_changes_role(
    db_session: AsyncSession,
    test_user: User,
    test_admin: User,
) -> None:
    """Test administrator can change another user's role and active status."""
    req = UserUpdateRequest(role="moderator", is_active=False)
    updated = await user_service.update_user(
        db=db_session,
        user_id=test_user.id,
        request=req,
        actor=test_admin,
    )
    assert updated.role == "moderator"
    assert updated.is_active is False


async def test_update_user_non_admin_cannot_change_role_or_other(
    db_session: AsyncSession,
    test_user: User,
    test_user_2: User,
) -> None:
    """Test non-admin cannot update role or modify someone else's profile."""
    # Attempting to modify other user
    with pytest.raises(PermissionDeniedError, match="Cannot modify another user profile"):
        await user_service.update_user(
            db=db_session,
            user_id=test_user_2.id,
            request=UserUpdateRequest(email="bob_hacked@example.com"),
            actor=test_user,
        )

    # Attempting to elevate own role
    with pytest.raises(PermissionDeniedError, match="Only administrators"):
        await user_service.update_user(
            db=db_session,
            user_id=test_user.id,
            request=UserUpdateRequest(role="admin"),
            actor=test_user,
        )


async def test_update_user_duplicate_email(
    db_session: AsyncSession,
    test_user: User,
    test_user_2: User,
) -> None:
    """Test updating email to an existing email raises UserAlreadyExistsError."""
    req = UserUpdateRequest(email=test_user_2.email)
    with pytest.raises(UserAlreadyExistsError, match=r"Email.*already taken"):
        await user_service.update_user(
            db=db_session,
            user_id=test_user.id,
            request=req,
            actor=test_user,
        )


async def test_set_user_online_status(db_session: AsyncSession, test_user: User) -> None:
    """Test setting online presence updates status."""
    user = await user_service.set_user_online_status(
        db=db_session,
        user_id=test_user.id,
        is_online=False,
    )
    assert user.is_online is False

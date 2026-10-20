"""Unit tests for role-based permissions and chat access authorization."""

import pytest

from chat_api.exceptions import PermissionDeniedError
from chat_api.security.permissions import (
    Role,
    check_chat_permission,
    has_sufficient_role,
    require_role,
)


def test_has_sufficient_role_hierarchy() -> None:
    """Test role privilege hierarchy ordering."""
    assert has_sufficient_role("admin", Role.USER) is True
    assert has_sufficient_role("admin", Role.MODERATOR) is True
    assert has_sufficient_role("admin", Role.ADMIN) is True

    assert has_sufficient_role("moderator", Role.USER) is True
    assert has_sufficient_role("moderator", Role.MODERATOR) is True
    assert has_sufficient_role("moderator", Role.ADMIN) is False

    assert has_sufficient_role("user", Role.USER) is True
    assert has_sufficient_role("user", Role.MODERATOR) is False
    assert has_sufficient_role("user", Role.ADMIN) is False

    assert has_sufficient_role("invalid_role", Role.USER) is False


def test_require_role_checker() -> None:
    """Test require_role dependency factory."""
    admin_checker = require_role(Role.ADMIN)
    admin_checker("admin")

    with pytest.raises(PermissionDeniedError):
        admin_checker("user")

    user_checker = require_role(Role.USER)
    user_checker("user")
    user_checker("moderator")
    user_checker("admin")


def test_check_chat_permission() -> None:
    """Test chat operation permissions."""
    # System admin can do anything
    check_chat_permission("ban", "member", "admin")
    check_chat_permission("mute", "member", "admin")
    check_chat_permission("edit_chat", "member", "admin")

    # Chat owner can do anything in their chat
    check_chat_permission("ban", "owner", "user")
    check_chat_permission("mute", "owner", "user")
    check_chat_permission("edit_chat", "owner", "user")

    # Chat admin / moderator can mute and kick
    check_chat_permission("mute", "admin", "user")
    check_chat_permission("kick", "admin", "user")
    check_chat_permission("mute", "member", "moderator")

    # Regular member cannot mute, kick, or ban
    with pytest.raises(PermissionDeniedError):
        check_chat_permission("mute", "member", "user")

    with pytest.raises(PermissionDeniedError):
        check_chat_permission("kick", "member", "user")

    with pytest.raises(PermissionDeniedError):
        check_chat_permission("ban", "member", "user")

    with pytest.raises(PermissionDeniedError):
        check_chat_permission("edit_chat", "member", "user")

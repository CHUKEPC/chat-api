"""Role-based access control and authorization utilities."""

from collections.abc import Callable
from enum import StrEnum

from chat_api.exceptions import PermissionDeniedError


class Role(StrEnum):
    """System user roles with hierarchical privilege ordering."""

    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"


# Numerical level hierarchy for fast privilege comparison
ROLE_HIERARCHY: dict[Role, int] = {
    Role.ADMIN: 3,
    Role.MODERATOR: 2,
    Role.USER: 1,
}


def has_sufficient_role(user_role: str, required_role: Role) -> bool:
    """Check if user role meets or exceeds required hierarchy level.

    Args:
        user_role: Current user's assigned role string.
        required_role: Minimum role required.

    Returns:
        bool: True if sufficient privileges, False otherwise.
    """
    try:
        user_enum = Role(user_role)
    except ValueError:
        return False

    return ROLE_HIERARCHY.get(user_enum, 0) >= ROLE_HIERARCHY.get(required_role, 0)


def require_role(min_role: Role) -> Callable[[str], None]:
    """Dependency / assertion factory that validates user meets minimum role.

    Args:
        min_role: Minimum role enum value required.

    Returns:
        Callable[[str], None]: Function taking user role and raising if insufficient.
    """

    def checker(current_role: str) -> None:
        """Verify role or raise PermissionDeniedError.

        Args:
            current_role: Role of the active user.

        Raises:
            PermissionDeniedError: If role is insufficient.
        """
        if not has_sufficient_role(current_role, min_role):
            raise PermissionDeniedError(
                f"Action requires minimum '{min_role.value}' role, user has '{current_role}'"
            )

    return checker


def check_chat_permission(
    action: str,
    participant_role: str,
    user_system_role: str,
) -> None:
    """Verify participant or moderator permissions for chat operations.

    Args:
        action: Chat action identifier (e.g. 'mute', 'kick', 'ban', 'delete_message').
        participant_role: Role inside the specific chat ('owner', 'admin', 'member').
        user_system_role: System-wide global role ('admin', 'moderator', 'user').

    Raises:
        PermissionDeniedError: If operation is unauthorized.
    """
    # System admins can execute all operations anywhere
    if user_system_role == Role.ADMIN.value:
        return

    # Chat owners have full control over their chat
    if participant_role == "owner":
        return

    # System moderators or chat admins can moderate members
    if action in {"mute", "unmute", "kick"}:
        if user_system_role == Role.MODERATOR.value or participant_role == "admin":
            return
        raise PermissionDeniedError(f"Insufficient permissions to perform '{action}' on chat")

    if action in {"ban", "unban"}:
        # Banning requires chat owner, system moderator, or system admin
        if user_system_role == Role.MODERATOR.value or participant_role in {"owner", "admin"}:
            return
        raise PermissionDeniedError(f"Insufficient permissions to '{action}' user from chat")

    if action == "edit_chat":
        if participant_role in {"owner", "admin"}:
            return
        raise PermissionDeniedError("Only chat owners and admins can update chat details")

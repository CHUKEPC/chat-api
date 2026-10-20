"""User domain business logic service."""

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.exceptions import (
    PermissionDeniedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from chat_api.models.user import User
from chat_api.schemas.user import UserUpdateRequest
from chat_api.security.hashing import hash_password
from chat_api.security.permissions import Role


async def get_user_by_id(db: AsyncSession, user_id: int) -> User:
    """Retrieve user entity by primary key.

    Args:
        db: Database session.
        user_id: Unique user identifier.

    Returns:
        User: Target user model.

    Raises:
        UserNotFoundError: If user with given ID does not exist.
    """
    user = await db.get(User, user_id)
    if user is None:
        raise UserNotFoundError(f"User with id {user_id} not found")
    return user


async def get_user_by_username(db: AsyncSession, username: str) -> User:
    """Retrieve user entity by username.

    Args:
        db: Database session.
        username: Target username string.

    Returns:
        User: Target user model.

    Raises:
        UserNotFoundError: If matching username is not found.
    """
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise UserNotFoundError(f"User '{username}' not found")
    return user


async def list_users(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    is_online: bool | None = None,
) -> list[User]:
    """Query users with pagination and optional search filter.

    Args:
        db: Database session.
        skip: Offset rows.
        limit: Max rows returned.
        search: Optional case-insensitive substring for username/email.
        is_online: Optional presence filter.

    Returns:
        list[User]: List of matching user models.
    """
    stmt = select(User)

    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(or_(User.username.ilike(pattern), User.email.ilike(pattern)))

    if is_online is not None:
        stmt = stmt.where(User.is_online == is_online)

    stmt = stmt.order_by(User.id.asc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_user(
    db: AsyncSession,
    user_id: int,
    request: UserUpdateRequest,
    actor: User,
) -> User:
    """Modify user attributes with role-based restriction enforcement.

    Args:
        db: Database session.
        user_id: User identifier to modify.
        request: Change payload.
        actor: Authenticated caller initiating update.

    Returns:
        User: Updated persistent user instance.

    Raises:
        PermissionDeniedError: If non-admin attempts privileged updates.
        UserAlreadyExistsError: If new email is already occupied.
    """
    user = await get_user_by_id(db, user_id)

    # Only account owner or system admin may update profile
    is_admin = actor.role == Role.ADMIN.value
    if actor.id != user.id and not is_admin:
        raise PermissionDeniedError("Cannot modify another user profile")

    if request.role is not None:
        if not is_admin:
            raise PermissionDeniedError("Only administrators can reassign user roles")
        user.role = request.role

    if request.is_active is not None:
        if not is_admin:
            raise PermissionDeniedError("Only administrators can change active status")
        user.is_active = request.is_active

    if request.email and request.email != user.email:
        existing_stmt = select(User).where(User.email == request.email, User.id != user.id)
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            raise UserAlreadyExistsError(f"Email '{request.email}' is already taken")
        user.email = request.email

    if request.password:
        user.hashed_password = hash_password(request.password)

    await db.flush()
    await db.refresh(user)
    return user


async def set_user_online_status(db: AsyncSession, user_id: int, is_online: bool) -> User:
    """Update presence flag and last_seen_at timestamp.

    Args:
        db: Database session.
        user_id: Target user ID.
        is_online: Active connectivity status.

    Returns:
        User: Refreshed user record.
    """
    user = await get_user_by_id(db, user_id)
    user.is_online = is_online
    user.last_seen_at = datetime.now(UTC)
    await db.flush()
    return user

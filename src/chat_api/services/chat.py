"""Chat rooms and participant moderation business logic service."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from chat_api.exceptions import (
    ChatNotFoundError,
    ConflictError,
    InvalidOperationError,
    PermissionDeniedError,
    UserBannedError,
    UserNotFoundError,
)
from chat_api.models.chat import Chat, ChatParticipant, ChatType, ParticipantRole
from chat_api.models.user import User
from chat_api.schemas.chat import (
    AddParticipantRequest,
    BanUserRequest,
    ChatCreateRequest,
    ChatUpdateRequest,
    MuteUserRequest,
)
from chat_api.security.permissions import Role, check_chat_permission


async def _get_participant_record(
    db: AsyncSession,
    chat_id: int,
    user_id: int,
) -> ChatParticipant | None:
    """Helper to query single participant record."""
    stmt = (
        select(ChatParticipant)
        .where(
            and_(
                ChatParticipant.chat_id == chat_id,
                ChatParticipant.user_id == user_id,
            )
        )
        .options(selectinload(ChatParticipant.user))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_chat_or_404(db: AsyncSession, chat_id: int) -> Chat:
    """Retrieve chat by ID with participants loaded.

    Args:
        db: Database session.
        chat_id: Primary key of chat.

    Returns:
        Chat: Loaded chat ORM entity.

    Raises:
        ChatNotFoundError: If chat does not exist.
    """
    stmt = (
        select(Chat)
        .where(Chat.id == chat_id)
        .options(
            selectinload(Chat.participants).selectinload(ChatParticipant.user),
        )
    )
    result = await db.execute(stmt)
    chat = result.scalar_one_or_none()
    if chat is None:
        raise ChatNotFoundError(f"Chat with id {chat_id} not found")
    return chat


async def create_chat(
    db: AsyncSession,
    creator_id: int,
    request: ChatCreateRequest,
) -> Chat:
    """Create a new direct or group chat.

    Args:
        db: Database session.
        creator_id: ID of the user creating the chat.
        request: Creation parameters.

    Returns:
        Chat: Newly created chat entity.

    Raises:
        InvalidOperationError: For invalid participant configurations.
        UserNotFoundError: If specified participant ID does not exist.
    """
    creator = await db.get(User, creator_id)
    if creator is None:
        raise UserNotFoundError("Creator user not found")

    # Normalize participant IDs (remove creator if already present)
    other_participant_ids = [uid for uid in set(request.participant_ids) if uid != creator_id]

    if request.type == ChatType.DIRECT.value:
        if len(other_participant_ids) != 1:
            raise InvalidOperationError("Direct chat requires exactly one other participant")
        target_id = other_participant_ids[0]
        target_user = await db.get(User, target_id)
        if target_user is None:
            raise UserNotFoundError(f"User with id {target_id} not found")

        # Check if direct chat already exists between these users
        existing_stmt = (
            select(Chat.id)
            .join(ChatParticipant)
            .where(Chat.type == ChatType.DIRECT.value)
            .where(ChatParticipant.user_id.in_([creator_id, target_id]))
            .group_by(Chat.id)
            .having(func.count(ChatParticipant.user_id) == 2)
        )
        existing_chat_id = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing_chat_id is not None:
            return await get_chat_or_404(db, existing_chat_id)

        chat = Chat(
            type=ChatType.DIRECT.value,
            name=request.name or f"{creator.username} & {target_user.username}",
            description=request.description,
            created_by_id=creator_id,
        )
        db.add(chat)
        await db.flush()

        p1 = ChatParticipant(
            chat_id=chat.id,
            user_id=creator_id,
            role=ParticipantRole.OWNER.value,
        )
        p2 = ChatParticipant(
            chat_id=chat.id,
            user_id=target_id,
            role=ParticipantRole.MEMBER.value,
        )
        db.add_all([p1, p2])
        await db.flush()

    else:
        # Group chat
        if not request.name or not request.name.strip():
            raise InvalidOperationError("Group chat requires a non-empty name")

        chat = Chat(
            type=ChatType.GROUP.value,
            name=request.name.strip(),
            description=request.description,
            created_by_id=creator_id,
        )
        db.add(chat)
        await db.flush()

        p_owner = ChatParticipant(
            chat_id=chat.id,
            user_id=creator_id,
            role=ParticipantRole.OWNER.value,
        )
        db.add(p_owner)

        # Add initial participants
        for uid in other_participant_ids:
            user_exists = await db.get(User, uid)
            if user_exists:
                db.add(
                    ChatParticipant(
                        chat_id=chat.id,
                        user_id=uid,
                        role=ParticipantRole.MEMBER.value,
                    )
                )
        await db.flush()

    return await get_chat_or_404(db, chat.id)


async def get_chat(db: AsyncSession, chat_id: int, user_id: int) -> Chat:
    """Retrieve chat details ensuring user has access.

    Args:
        db: Database session.
        chat_id: Chat identifier.
        user_id: Active user accessing the chat.

    Returns:
        Chat: Chat room entity with participants.

    Raises:
        PermissionDeniedError: If caller is not a member.
        UserBannedError: If caller is banned from chat.
    """
    chat = await get_chat_or_404(db, chat_id)
    participant = next((p for p in chat.participants if p.user_id == user_id), None)

    # Global admin can view any chat
    user = await db.get(User, user_id)
    if user and user.role == Role.ADMIN.value:
        return chat

    if participant is None:
        raise PermissionDeniedError("You are not a member of this chat")

    if participant.is_banned:
        raise UserBannedError("You have been banned from this chat")

    return chat


async def list_user_chats(
    db: AsyncSession,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
) -> list[Chat]:
    """Retrieve all chats the user participates in and is not banned from.

    Args:
        db: Database session.
        user_id: User identifier.
        skip: Pagination offset.
        limit: Max chats to return.

    Returns:
        list[Chat]: List of chats with eager loaded relationships.
    """
    stmt = (
        select(Chat)
        .join(ChatParticipant, Chat.id == ChatParticipant.chat_id)
        .where(
            and_(
                ChatParticipant.user_id == user_id,
                ChatParticipant.is_banned.is_(False),
            )
        )
        .options(
            selectinload(Chat.participants).selectinload(ChatParticipant.user),
        )
        .order_by(Chat.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_chat(
    db: AsyncSession,
    chat_id: int,
    user_id: int,
    request: ChatUpdateRequest,
) -> Chat:
    """Update metadata for a chat room.

    Args:
        db: Database session.
        chat_id: Chat ID.
        user_id: Caller initiating update.
        request: Updated fields.

    Returns:
        Chat: Refreshed chat entity.

    Raises:
        PermissionDeniedError: If caller lacks owner/admin privileges.
    """
    chat = await get_chat_or_404(db, chat_id)
    user = await db.get(User, user_id)
    user_role = user.role if user else Role.USER.value

    participant = next((p for p in chat.participants if p.user_id == user_id), None)
    part_role = participant.role if participant else "member"

    check_chat_permission("edit_chat", part_role, user_role)

    if request.name is not None:
        chat.name = request.name.strip()
    if request.description is not None:
        chat.description = request.description.strip()

    await db.flush()
    return await get_chat_or_404(db, chat.id)


async def add_participant(
    db: AsyncSession,
    chat_id: int,
    actor_id: int,
    request: AddParticipantRequest,
) -> ChatParticipant:
    """Add a user to a group chat.

    Args:
        db: Database session.
        chat_id: Target group chat ID.
        actor_id: ID of actor adding the participant.
        request: Target user ID and role payload.

    Returns:
        ChatParticipant: Newly created membership record.

    Raises:
        InvalidOperationError: If attempting to add member to direct chat.
        UserBannedError: If target user is banned.
        ConflictError: If user is already an active member.
    """
    chat = await get_chat_or_404(db, chat_id)
    if chat.type == ChatType.DIRECT.value:
        raise InvalidOperationError("Cannot add extra participants to a direct chat")

    actor = await db.get(User, actor_id)
    actor_sys_role = actor.role if actor else Role.USER.value
    actor_part = next((p for p in chat.participants if p.user_id == actor_id), None)
    actor_part_role = actor_part.role if actor_part else "member"

    check_chat_permission("edit_chat", actor_part_role, actor_sys_role)

    target_user = await db.get(User, request.user_id)
    if target_user is None:
        raise UserNotFoundError(f"User with id {request.user_id} not found")

    existing_part = await _get_participant_record(db, chat_id, request.user_id)
    if existing_part is not None:
        if existing_part.is_banned:
            raise UserBannedError("User is banned from this chat; unban first")
        raise ConflictError("User is already a participant in this chat")

    participant = ChatParticipant(
        chat_id=chat_id,
        user_id=request.user_id,
        role=request.role,
    )
    db.add(participant)
    chat.participants.append(participant)
    await db.flush()
    return (await _get_participant_record(db, chat_id, request.user_id)) or participant


async def remove_participant(
    db: AsyncSession,
    chat_id: int,
    actor_id: int,
    target_user_id: int,
) -> None:
    """Remove participant from chat (self-leave or kick).

    Args:
        db: Database session.
        chat_id: Chat identifier.
        actor_id: Caller requesting removal.
        target_user_id: Target user being removed.

    Raises:
        InvalidOperationError: Cannot leave/kick in direct chat.
        PermissionDeniedError: If caller lacks kick permissions.
    """
    chat = await get_chat_or_404(db, chat_id)
    if chat.type == ChatType.DIRECT.value:
        raise InvalidOperationError("Cannot leave or kick in a direct chat")

    target_part = next((p for p in chat.participants if p.user_id == target_user_id), None)
    if target_part is None:
        target_part = await _get_participant_record(db, chat_id, target_user_id)
    if target_part is None:
        raise UserNotFoundError("Target user is not a participant in this chat")

    # If actor is leaving on their own
    if actor_id == target_user_id:
        if target_part.role == ParticipantRole.OWNER.value:
            # Transfer ownership or disallow if single owner with other members
            other_members = [
                p for p in chat.participants if p.user_id != actor_id and not p.is_banned
            ]
            if other_members:
                other_members[0].role = ParticipantRole.OWNER.value
        if target_part in chat.participants:
            chat.participants.remove(target_part)
        await db.delete(target_part)
        await db.flush()
        return

    # Actor is removing someone else -> kick
    actor = await db.get(User, actor_id)
    actor_sys_role = actor.role if actor else Role.USER.value
    actor_part = next((p for p in chat.participants if p.user_id == actor_id), None)
    actor_part_role = actor_part.role if actor_part else "member"

    check_chat_permission("kick", actor_part_role, actor_sys_role)

    if target_part.role == ParticipantRole.OWNER.value:
        raise PermissionDeniedError("Chat owner cannot be kicked")

    if target_part in chat.participants:
        chat.participants.remove(target_part)
    await db.delete(target_part)
    await db.flush()


async def mute_participant(
    db: AsyncSession,
    chat_id: int,
    actor_id: int,
    request: MuteUserRequest,
) -> ChatParticipant:
    """Mute a participant for a designated duration.

    Args:
        db: Database session.
        chat_id: Chat ID.
        actor_id: Moderator user ID.
        request: Target user and mute duration in minutes.

    Returns:
        ChatParticipant: Updated participant entity.
    """
    chat = await get_chat_or_404(db, chat_id)
    actor = await db.get(User, actor_id)
    actor_sys_role = actor.role if actor else Role.USER.value
    actor_part = next((p for p in chat.participants if p.user_id == actor_id), None)
    actor_part_role = actor_part.role if actor_part else "member"

    check_chat_permission("mute", actor_part_role, actor_sys_role)

    target_part = await _get_participant_record(db, chat_id, request.user_id)
    if target_part is None:
        raise UserNotFoundError("User is not a participant in this chat")

    if target_part.role == ParticipantRole.OWNER.value:
        raise PermissionDeniedError("Cannot mute chat owner")

    minutes = request.duration_minutes or 60
    target_part.is_muted = True
    target_part.muted_until = datetime.now(UTC) + timedelta(minutes=minutes)

    await db.flush()
    return target_part


async def unmute_participant(
    db: AsyncSession,
    chat_id: int,
    actor_id: int,
    target_user_id: int,
) -> ChatParticipant:
    """Remove mute restriction from a participant.

    Args:
        db: Database session.
        chat_id: Chat ID.
        actor_id: Moderator user ID.
        target_user_id: Muted user ID.

    Returns:
        ChatParticipant: Updated participant entity.
    """
    chat = await get_chat_or_404(db, chat_id)
    actor = await db.get(User, actor_id)
    actor_sys_role = actor.role if actor else Role.USER.value
    actor_part = next((p for p in chat.participants if p.user_id == actor_id), None)
    actor_part_role = actor_part.role if actor_part else "member"

    check_chat_permission("unmute", actor_part_role, actor_sys_role)

    target_part = await _get_participant_record(db, chat_id, target_user_id)
    if target_part is None:
        raise UserNotFoundError("User is not a participant in this chat")

    target_part.is_muted = False
    target_part.muted_until = None
    await db.flush()
    return target_part


async def ban_participant(
    db: AsyncSession,
    chat_id: int,
    actor_id: int,
    request: BanUserRequest,
) -> ChatParticipant:
    """Ban a participant from chat room.

    Args:
        db: Database session.
        chat_id: Chat ID.
        actor_id: Admin or moderator user ID.
        request: Target user ID to ban.

    Returns:
        ChatParticipant: Updated banned participant entity.
    """
    chat = await get_chat_or_404(db, chat_id)
    actor = await db.get(User, actor_id)
    actor_sys_role = actor.role if actor else Role.USER.value
    actor_part = next((p for p in chat.participants if p.user_id == actor_id), None)
    actor_part_role = actor_part.role if actor_part else "member"

    check_chat_permission("ban", actor_part_role, actor_sys_role)

    target_part = await _get_participant_record(db, chat_id, request.user_id)
    if target_part is None:
        # Create banned record to prevent future joins
        target_part = ChatParticipant(
            chat_id=chat_id,
            user_id=request.user_id,
            role=ParticipantRole.MEMBER.value,
            is_banned=True,
        )
        db.add(target_part)
    else:
        if target_part.role == ParticipantRole.OWNER.value:
            raise PermissionDeniedError("Cannot ban chat owner")
        target_part.is_banned = True

    await db.flush()
    return target_part


async def unban_participant(
    db: AsyncSession,
    chat_id: int,
    actor_id: int,
    target_user_id: int,
) -> ChatParticipant:
    """Unban a participant.

    Args:
        db: Database session.
        chat_id: Chat ID.
        actor_id: Admin or moderator user ID.
        target_user_id: Target user ID to unban.

    Returns:
        ChatParticipant: Updated unbanned participant entity.
    """
    chat = await get_chat_or_404(db, chat_id)
    actor = await db.get(User, actor_id)
    actor_sys_role = actor.role if actor else Role.USER.value
    actor_part = next((p for p in chat.participants if p.user_id == actor_id), None)
    actor_part_role = actor_part.role if actor_part else "member"

    check_chat_permission("unban", actor_part_role, actor_sys_role)

    target_part = await _get_participant_record(db, chat_id, target_user_id)
    if target_part is None:
        raise UserNotFoundError("User is not registered in this chat")

    target_part.is_banned = False
    await db.flush()
    return target_part

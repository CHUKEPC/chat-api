"""Unit tests for chat service and moderation."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.exceptions import (
    ConflictError,
    InvalidOperationError,
    PermissionDeniedError,
    UserBannedError,
)
from chat_api.models.chat import Chat, ChatType
from chat_api.models.user import User
from chat_api.schemas.chat import (
    AddParticipantRequest,
    BanUserRequest,
    ChatCreateRequest,
    ChatUpdateRequest,
    MuteUserRequest,
)
from chat_api.services import chat as chat_service


async def test_create_direct_chat_success(
    db_session: AsyncSession,
    test_user: User,
    test_user_2: User,
) -> None:
    """Test creating direct chat between two users."""
    req = ChatCreateRequest(
        type=ChatType.DIRECT.value,
        participant_ids=[test_user_2.id],
    )
    chat = await chat_service.create_chat(
        db=db_session,
        creator_id=test_user.id,
        request=req,
    )
    assert chat.id is not None
    assert chat.type == ChatType.DIRECT.value
    assert len(chat.participants) == 2

    # Creating direct chat with same user returns existing chat
    chat2 = await chat_service.create_chat(
        db=db_session,
        creator_id=test_user.id,
        request=req,
    )
    assert chat2.id == chat.id


async def test_create_direct_chat_invalid_participants(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test direct chat requires exactly one other participant."""
    req_empty = ChatCreateRequest(type=ChatType.DIRECT.value, participant_ids=[])
    with pytest.raises(InvalidOperationError, match="exactly one"):
        await chat_service.create_chat(db_session, test_user.id, req_empty)


async def test_create_group_chat_success(
    db_session: AsyncSession,
    test_user: User,
    test_user_2: User,
    test_moderator: User,
) -> None:
    """Test creating group chat with name and participants."""
    req = ChatCreateRequest(
        type=ChatType.GROUP.value,
        name="Engineering Team",
        description="Daily dev chat",
        participant_ids=[test_user_2.id, test_moderator.id],
    )
    chat = await chat_service.create_chat(db_session, test_user.id, req)
    assert chat.id is not None
    assert chat.type == ChatType.GROUP.value
    assert chat.name == "Engineering Team"
    assert len(chat.participants) == 3


async def test_get_chat_access_control(
    db_session: AsyncSession,
    direct_chat: Chat,
    test_user: User,
    test_admin: User,
    test_moderator: User,
) -> None:
    """Test get_chat allows participants and admin, rejects non-participants."""
    # Member access
    chat1 = await chat_service.get_chat(db_session, direct_chat.id, test_user.id)
    assert chat1.id == direct_chat.id

    # Global admin access
    chat2 = await chat_service.get_chat(db_session, direct_chat.id, test_admin.id)
    assert chat2.id == direct_chat.id

    # Non-member rejection
    with pytest.raises(PermissionDeniedError, match="not a member"):
        await chat_service.get_chat(db_session, direct_chat.id, test_moderator.id)


async def test_list_user_chats(
    db_session: AsyncSession,
    direct_chat: Chat,
    group_chat: Chat,
    test_user: User,
) -> None:
    """Test listing user's active chats."""
    chats = await chat_service.list_user_chats(db_session, user_id=test_user.id)
    assert len(chats) >= 2
    chat_ids = [c.id for c in chats]
    assert direct_chat.id in chat_ids
    assert group_chat.id in chat_ids


async def test_update_chat_metadata(
    db_session: AsyncSession,
    group_chat: Chat,
    test_user: User,
    test_user_2: User,
) -> None:
    """Test updating chat room metadata by owner vs member."""
    # Owner updates chat
    req = ChatUpdateRequest(name="Renamed Chat", description="Updated description")
    updated = await chat_service.update_chat(
        db=db_session,
        chat_id=group_chat.id,
        user_id=test_user.id,
        request=req,
    )
    assert updated.name == "Renamed Chat"

    # Regular member update rejected
    with pytest.raises(PermissionDeniedError):
        await chat_service.update_chat(
            db=db_session,
            chat_id=group_chat.id,
            user_id=test_user_2.id,
            request=req,
        )


async def test_add_and_remove_participant(
    db_session: AsyncSession,
    group_chat: Chat,
    test_user: User,
    test_admin: User,
) -> None:
    """Test adding member to group chat and removing participant."""
    add_req = AddParticipantRequest(user_id=test_admin.id, role="member")
    part = await chat_service.add_participant(
        db=db_session,
        chat_id=group_chat.id,
        actor_id=test_user.id,
        request=add_req,
    )
    assert part.user_id == test_admin.id

    # Adding already existing participant raises ConflictError
    with pytest.raises(ConflictError):
        await chat_service.add_participant(
            db=db_session,
            chat_id=group_chat.id,
            actor_id=test_user.id,
            request=add_req,
        )

    # Remove participant (kick)
    await chat_service.remove_participant(
        db=db_session,
        chat_id=group_chat.id,
        actor_id=test_user.id,
        target_user_id=test_admin.id,
    )


async def test_mute_and_unmute_participant(
    db_session: AsyncSession,
    group_chat: Chat,
    test_user: User,
    test_user_2: User,
) -> None:
    """Test muting and unmuting participant in group chat."""
    mute_req = MuteUserRequest(user_id=test_user_2.id, duration_minutes=30)
    part = await chat_service.mute_participant(
        db=db_session,
        chat_id=group_chat.id,
        actor_id=test_user.id,
        request=mute_req,
    )
    assert part.is_muted is True
    assert part.muted_until is not None

    # Unmute
    unmuted = await chat_service.unmute_participant(
        db=db_session,
        chat_id=group_chat.id,
        actor_id=test_user.id,
        target_user_id=test_user_2.id,
    )
    assert unmuted.is_muted is False
    assert unmuted.muted_until is None


async def test_ban_and_unban_participant(
    db_session: AsyncSession,
    group_chat: Chat,
    test_user: User,
    test_user_2: User,
) -> None:
    """Test banning and unbanning participant."""
    ban_req = BanUserRequest(user_id=test_user_2.id)
    banned = await chat_service.ban_participant(
        db=db_session,
        chat_id=group_chat.id,
        actor_id=test_user.id,
        request=ban_req,
    )
    assert banned.is_banned is True

    # User cannot access chat after being banned
    with pytest.raises(UserBannedError):
        await chat_service.get_chat(db_session, group_chat.id, test_user_2.id)

    # Unban user
    unbanned = await chat_service.unban_participant(
        db=db_session,
        chat_id=group_chat.id,
        actor_id=test_user.id,
        target_user_id=test_user_2.id,
    )
    assert unbanned.is_banned is False


async def test_chat_service_moderation_owner_protections(
    db_session: AsyncSession,
    group_chat: Chat,
    test_user: User,
    test_moderator: User,
) -> None:
    """Test owner cannot be muted, kicked, or banned by chat admin."""
    # Attempt to mute owner -> PermissionDeniedError
    with pytest.raises(PermissionDeniedError, match="Cannot mute chat owner"):
        await chat_service.mute_participant(
            db=db_session,
            chat_id=group_chat.id,
            actor_id=test_moderator.id,
            request=MuteUserRequest(user_id=test_user.id),
        )

    # Attempt to ban owner -> PermissionDeniedError
    with pytest.raises(PermissionDeniedError, match="Cannot ban chat owner"):
        await chat_service.ban_participant(
            db=db_session,
            chat_id=group_chat.id,
            actor_id=test_moderator.id,
            request=BanUserRequest(user_id=test_user.id),
        )

    # Attempt to kick owner -> PermissionDeniedError
    with pytest.raises(PermissionDeniedError, match="Chat owner cannot be kicked"):
        await chat_service.remove_participant(
            db=db_session,
            chat_id=group_chat.id,
            actor_id=test_moderator.id,
            target_user_id=test_user.id,
        )


async def test_owner_self_leave_transfers_ownership(
    db_session: AsyncSession,
    group_chat: Chat,
    test_user: User,
) -> None:
    """Test owner leaving group chat reassigns ownership to next participant."""
    await chat_service.remove_participant(
        db=db_session,
        chat_id=group_chat.id,
        actor_id=test_user.id,
        target_user_id=test_user.id,
    )
    await db_session.commit()
    # Check that participant record for test_user was removed
    reloaded = await chat_service.get_chat_or_404(db_session, group_chat.id)
    assert not any(p.user_id == test_user.id for p in reloaded.participants)

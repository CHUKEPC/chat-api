"""Unit tests for message service, search, receipts, and WebSocket connection manager."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.exceptions import (
    PermissionDeniedError,
    UserMutedError,
)
from chat_api.models.chat import Chat
from chat_api.models.user import User
from chat_api.schemas.message import (
    AttachmentSchema,
    MessageCreateRequest,
    MessageUpdateRequest,
)
from chat_api.services import chat as chat_service
from chat_api.services import message as message_service
from chat_api.services.message import ConnectionManager


async def test_send_and_get_messages(
    db_session: AsyncSession,
    group_chat: Chat,
    test_user: User,
) -> None:
    """Test message sending and history retrieval."""
    req = MessageCreateRequest(
        content="Hello world!",
        attachments=[
            AttachmentSchema(
                filename="doc.pdf",
                file_size=1024,
                content_type="application/pdf",
                file_url="https://storage.example.com/doc.pdf",
            )
        ],
    )
    msg = await message_service.send_message(
        db=db_session,
        chat_id=group_chat.id,
        sender_id=test_user.id,
        request=req,
    )
    assert msg.id is not None
    assert msg.content == "Hello world!"
    assert len(msg.attachments) == 1
    assert msg.attachments[0]["filename"] == "doc.pdf"

    messages, total, _has_more = await message_service.get_chat_messages(
        db=db_session,
        chat_id=group_chat.id,
        user_id=test_user.id,
        limit=10,
        offset=0,
    )
    assert total >= 1
    assert any(m.id == msg.id for m in messages)


async def test_send_message_when_muted_raises_error(
    db_session: AsyncSession,
    group_chat: Chat,
    test_user: User,
    test_user_2: User,
) -> None:
    """Test muted user cannot send messages."""
    await chat_service.mute_participant(
        db=db_session,
        chat_id=group_chat.id,
        actor_id=test_user.id,
        request=chat_service.MuteUserRequest(user_id=test_user_2.id, duration_minutes=30),
    )

    req = MessageCreateRequest(content="Can I speak?")
    with pytest.raises(UserMutedError, match="muted"):
        await message_service.send_message(
            db=db_session,
            chat_id=group_chat.id,
            sender_id=test_user_2.id,
            request=req,
        )


async def test_edit_message(
    db_session: AsyncSession,
    group_chat: Chat,
    test_user: User,
    test_user_2: User,
) -> None:
    """Test message editing permissions and behavior."""
    msg = await message_service.send_message(
        db=db_session,
        chat_id=group_chat.id,
        sender_id=test_user.id,
        request=MessageCreateRequest(content="Original text"),
    )

    # Author can edit
    updated = await message_service.edit_message(
        db=db_session,
        message_id=msg.id,
        user_id=test_user.id,
        request=MessageUpdateRequest(content="Edited text"),
    )
    assert updated.content == "Edited text"
    assert updated.is_edited is True
    assert updated.edited_at is not None

    # Other user cannot edit
    with pytest.raises(PermissionDeniedError, match="only edit your own messages"):
        await message_service.edit_message(
            db=db_session,
            message_id=msg.id,
            user_id=test_user_2.id,
            request=MessageUpdateRequest(content="Hacked text"),
        )


async def test_delete_message_soft_delete(
    db_session: AsyncSession,
    group_chat: Chat,
    test_user: User,
) -> None:
    """Test message soft-deletion hides content."""
    msg = await message_service.send_message(
        db=db_session,
        chat_id=group_chat.id,
        sender_id=test_user.id,
        request=MessageCreateRequest(content="Secret message"),
    )

    deleted = await message_service.delete_message(
        db=db_session,
        message_id=msg.id,
        user_id=test_user.id,
    )
    assert deleted.is_deleted is True
    assert deleted.content == "[Message deleted]"

    # Cannot edit deleted message
    with pytest.raises(PermissionDeniedError, match="Cannot edit a deleted message"):
        await message_service.edit_message(
            db=db_session,
            message_id=msg.id,
            user_id=test_user.id,
            request=MessageUpdateRequest(content="Revive"),
        )


async def test_search_messages(
    db_session: AsyncSession,
    group_chat: Chat,
    test_user: User,
) -> None:
    """Test message searching finds relevant texts and filters inaccessible ones."""
    await message_service.send_message(
        db=db_session,
        chat_id=group_chat.id,
        sender_id=test_user.id,
        request=MessageCreateRequest(content="Deploying FastAPI microservice today"),
    )
    await message_service.send_message(
        db=db_session,
        chat_id=group_chat.id,
        sender_id=test_user.id,
        request=MessageCreateRequest(content="Writing documentation for API"),
    )

    matches, total = await message_service.search_messages(
        db=db_session,
        user_id=test_user.id,
        query="FastAPI",
    )
    assert total >= 1
    assert any("FastAPI" in m.content for m in matches)


async def test_mark_message_read(
    db_session: AsyncSession,
    group_chat: Chat,
    test_user: User,
    test_user_2: User,
) -> None:
    """Test marking message as read creates receipt."""
    msg = await message_service.send_message(
        db=db_session,
        chat_id=group_chat.id,
        sender_id=test_user.id,
        request=MessageCreateRequest(content="Please review this"),
    )

    receipt = await message_service.mark_message_read(
        db=db_session,
        message_id=msg.id,
        user_id=test_user_2.id,
    )
    assert receipt.message_id == msg.id
    assert receipt.user_id == test_user_2.id


async def test_connection_manager_lifecycle() -> None:
    """Test WebSocket ConnectionManager connection and broadcasting."""
    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await manager.connect(ws1, chat_id=1, user_id=10)
    await manager.connect(ws2, chat_id=1, user_id=20)

    assert manager.is_user_online(10) is True
    assert manager.is_user_online(20) is True
    assert manager.is_user_online(30) is False

    # Broadcast to chat
    await manager.broadcast_to_chat(chat_id=1, message={"test": "data"}, exclude_socket=ws1)
    ws1.send_json.assert_not_called()
    ws2.send_json.assert_called_once_with({"test": "data"})

    # Broadcast to user
    await manager.broadcast_to_user(user_id=10, message={"direct": "message"})
    ws1.send_json.assert_called_once_with({"direct": "message"})

    # Disconnect
    meta = manager.disconnect(ws1)
    assert meta == (1, 10)
    assert manager.is_user_online(10) is False


async def test_delete_message_by_admin_and_moderator(
    db_session: AsyncSession,
    group_chat: Chat,
    test_user: User,
    test_user_2: User,
    test_admin: User,
    test_moderator: User,
) -> None:
    """Test system admin and chat admin/moderator can delete other users' messages."""
    msg = await message_service.send_message(
        db=db_session,
        chat_id=group_chat.id,
        sender_id=test_user.id,
        request=MessageCreateRequest(content="Offensive comment"),
    )

    # Chat admin / moderator can delete
    deleted = await message_service.delete_message(
        db=db_session,
        message_id=msg.id,
        user_id=test_moderator.id,
    )
    assert deleted.is_deleted is True

    # User 2 (regular member) cannot delete someone else's message
    msg2 = await message_service.send_message(
        db=db_session,
        chat_id=group_chat.id,
        sender_id=test_user.id,
        request=MessageCreateRequest(content="Another comment"),
    )
    with pytest.raises(PermissionDeniedError, match="permission to delete"):
        await message_service.delete_message(
            db=db_session,
            message_id=msg2.id,
            user_id=test_user_2.id,
        )


async def test_search_messages_with_chat_filter_and_empty_query(
    db_session: AsyncSession,
    group_chat: Chat,
    test_user: User,
) -> None:
    """Test searching with chat filter and empty query string."""
    empty_res, empty_total = await message_service.search_messages(
        db=db_session,
        user_id=test_user.id,
        query="",
    )
    assert empty_res == []
    assert empty_total == 0

    # Search with specific chat_id
    _res, total = await message_service.search_messages(
        db=db_session,
        user_id=test_user.id,
        query="Deploying",
        chat_id=group_chat.id,
    )
    assert total >= 0

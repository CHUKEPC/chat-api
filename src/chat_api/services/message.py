"""Message persistence, search, read receipts, and WebSocket connection management."""

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket
from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from chat_api.exceptions import (
    MessageNotFoundError,
    PermissionDeniedError,
    UserBannedError,
    UserMutedError,
)
from chat_api.models.chat import ChatParticipant
from chat_api.models.message import Message, MessageReceipt
from chat_api.models.user import User
from chat_api.schemas.message import (
    MessageCreateRequest,
    MessageUpdateRequest,
)
from chat_api.security.permissions import Role
from chat_api.services.chat import get_chat_or_404


class ConnectionManager:
    """Manages active WebSocket connections, presence tracking, and fan-out broadcasting."""

    def __init__(self) -> None:
        """Initialize connection mapping registries."""
        # Mapping: chat_id -> set of active WebSockets
        self.chat_connections: dict[int, set[WebSocket]] = defaultdict(set)
        # Mapping: user_id -> set of active WebSockets across all chats/tabs
        self.user_connections: dict[int, set[WebSocket]] = defaultdict(set)
        # Mapping: WebSocket -> (chat_id, user_id)
        self.socket_meta: dict[WebSocket, tuple[int, int]] = {}

    async def connect(self, websocket: WebSocket, chat_id: int, user_id: int) -> None:
        """Accept WebSocket connection and register in presence directories.

        Args:
            websocket: Connecting client socket.
            chat_id: Active room context.
            user_id: Authenticated user identifier.
        """
        await websocket.accept()
        self.chat_connections[chat_id].add(websocket)
        self.user_connections[user_id].add(websocket)
        self.socket_meta[websocket] = (chat_id, user_id)

    def disconnect(self, websocket: WebSocket) -> tuple[int, int] | None:
        """Remove socket from directories upon disconnection.

        Args:
            websocket: Disconnected socket.

        Returns:
            tuple[int, int] | None: (chat_id, user_id) if previously registered.
        """
        meta = self.socket_meta.pop(websocket, None)
        if meta is None:
            return None

        chat_id, user_id = meta
        if websocket in self.chat_connections[chat_id]:
            self.chat_connections[chat_id].discard(websocket)
            if not self.chat_connections[chat_id]:
                self.chat_connections.pop(chat_id, None)

        if websocket in self.user_connections[user_id]:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                self.user_connections.pop(user_id, None)

        return meta

    def is_user_online(self, user_id: int) -> bool:
        """Return True if user has any active sockets open.

        Args:
            user_id: User identifier.

        Returns:
            bool: Presence status flag.
        """
        return len(self.user_connections.get(user_id, set())) > 0

    async def broadcast_to_chat(
        self,
        chat_id: int,
        message: dict[str, Any],
        exclude_socket: WebSocket | None = None,
    ) -> None:
        """Send JSON frame to all connected clients in a specific chat.

        Args:
            chat_id: Chat identifier.
            message: JSON payload to transmit.
            exclude_socket: Optional socket to skip (e.g. sender).
        """
        sockets = list(self.chat_connections.get(chat_id, set()))
        for ws in sockets:
            if ws != exclude_socket:
                try:
                    await ws.send_json(message)
                except Exception:
                    self.disconnect(ws)

    async def broadcast_to_user(self, user_id: int, message: dict[str, Any]) -> None:
        """Send JSON payload directly to a specific user across all their sockets.

        Args:
            user_id: Destination user ID.
            message: JSON payload.
        """
        sockets = list(self.user_connections.get(user_id, set()))
        for ws in sockets:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws)


# Global connection manager singleton for real-time dispatch
ws_manager = ConnectionManager()


async def send_message(
    db: AsyncSession,
    chat_id: int,
    sender_id: int,
    request: MessageCreateRequest,
) -> Message:
    """Send and persist a message into a chat room.

    Args:
        db: Database session.
        chat_id: Destination chat identifier.
        sender_id: User ID of message author.
        request: Content and attachment payloads.

    Returns:
        Message: Saved message ORM instance.

    Raises:
        PermissionDeniedError: If sender is not an active participant.
        UserBannedError: If sender is banned from the chat.
        UserMutedError: If sender is currently muted.
    """
    chat = await get_chat_or_404(db, chat_id)
    participant = next((p for p in chat.participants if p.user_id == sender_id), None)

    if participant is None:
        raise PermissionDeniedError("Cannot post in a chat you are not a member of")

    if participant.is_banned:
        raise UserBannedError("You are banned from sending messages in this chat")

    now = datetime.now(UTC)
    if participant.is_muted:
        if participant.muted_until is None or participant.muted_until > now:
            raise UserMutedError("You are muted in this chat and cannot send messages")
        # Mute expired, auto-unmute
        participant.is_muted = False
        participant.muted_until = None

    attachments_data = [a.model_dump() for a in request.attachments]

    message = Message(
        chat_id=chat_id,
        sender_id=sender_id,
        content=request.content,
        is_edited=False,
        is_deleted=False,
        attachments=attachments_data,
        created_at=now,
    )
    db.add(message)
    chat.updated_at = now
    await db.flush()

    # Load sender details for serialization
    stmt = select(Message).where(Message.id == message.id).options(selectinload(Message.sender))
    saved = (await db.execute(stmt)).scalar_one()
    return saved


async def edit_message(
    db: AsyncSession,
    message_id: int,
    user_id: int,
    request: MessageUpdateRequest,
) -> Message:
    """Edit the content of an existing message.

    Args:
        db: Database session.
        message_id: Primary key of message.
        user_id: Caller initiating the edit.
        request: Updated text content.

    Returns:
        Message: Updated message entity.

    Raises:
        MessageNotFoundError: If message does not exist.
        PermissionDeniedError: If caller is not original author.
    """
    stmt = select(Message).where(Message.id == message_id).options(selectinload(Message.sender))
    message = (await db.execute(stmt)).scalar_one_or_none()

    if message is None:
        raise MessageNotFoundError(f"Message {message_id} not found")

    if message.is_deleted:
        raise PermissionDeniedError("Cannot edit a deleted message")

    if message.sender_id != user_id:
        raise PermissionDeniedError("You can only edit your own messages")

    message.content = request.content
    message.is_edited = True
    message.edited_at = datetime.now(UTC)

    await db.flush()
    return message


async def delete_message(
    db: AsyncSession,
    message_id: int,
    user_id: int,
) -> Message:
    """Perform soft deletion on a message.

    Args:
        db: Database session.
        message_id: Primary key of message.
        user_id: Caller requesting deletion.

    Returns:
        Message: Masked soft-deleted message entity.

    Raises:
        MessageNotFoundError: If message does not exist.
        PermissionDeniedError: If caller lacks deletion authorization.
    """
    stmt = select(Message).where(Message.id == message_id).options(selectinload(Message.sender))
    message = (await db.execute(stmt)).scalar_one_or_none()

    if message is None:
        raise MessageNotFoundError(f"Message {message_id} not found")

    # Author can delete own message
    if message.sender_id == user_id:
        message.is_deleted = True
        message.content = "[Message deleted]"
        await db.flush()
        return message

    # Check if caller is chat owner/admin or system moderator/admin
    caller = await db.get(User, user_id)
    if caller and caller.role in {Role.ADMIN.value, Role.MODERATOR.value}:
        message.is_deleted = True
        message.content = "[Message deleted]"
        await db.flush()
        return message

    chat = await get_chat_or_404(db, message.chat_id)
    participant = next((p for p in chat.participants if p.user_id == user_id), None)
    if participant and participant.role in {"owner", "admin"}:
        message.is_deleted = True
        message.content = "[Message deleted]"
        await db.flush()
        return message

    raise PermissionDeniedError("You do not have permission to delete this message")


async def get_chat_messages(
    db: AsyncSession,
    chat_id: int,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Message], int, bool]:
    """Fetch paginated message history for a chat.

    Args:
        db: Database session.
        chat_id: Target chat ID.
        user_id: Calling user ID.
        limit: Page size.
        offset: Offset cursor.

    Returns:
        tuple[list[Message], int, bool]: (messages, total_count, has_more).
    """
    chat = await get_chat_or_404(db, chat_id)
    caller = await db.get(User, user_id)
    is_admin = caller.role == Role.ADMIN.value if caller else False

    participant = next((p for p in chat.participants if p.user_id == user_id), None)
    if not is_admin:
        if participant is None:
            raise PermissionDeniedError("You are not a member of this chat")
        if participant.is_banned:
            raise UserBannedError("You are banned from this chat")

    count_stmt = select(func.count(Message.id)).where(Message.chat_id == chat_id)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .options(selectinload(Message.sender))
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    messages = list(result.scalars().all())

    has_more = (offset + limit) < total
    return messages, total, has_more


async def search_messages(
    db: AsyncSession,
    user_id: int,
    query: str,
    chat_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Message], int]:
    """Full-text and substring search over accessible messages.

    Args:
        db: Database session.
        user_id: User performing search.
        query: Search keywords.
        chat_id: Optional single chat filter.
        limit: Max results.
        offset: Pagination offset.

    Returns:
        tuple[list[Message], int]: (matched messages, total matching).
    """
    if not query or not query.strip():
        return [], 0

    # User can only search in chats they participate in (and are not banned from)
    accessible_chats_stmt = select(ChatParticipant.chat_id).where(
        and_(
            ChatParticipant.user_id == user_id,
            ChatParticipant.is_banned.is_(False),
        )
    )
    accessible_chat_ids = (await db.execute(accessible_chats_stmt)).scalars().all()

    if not accessible_chat_ids:
        return [], 0

    conditions: list[ColumnElement[bool]] = [
        Message.chat_id.in_(accessible_chat_ids),
        Message.is_deleted.is_(False),
        Message.content.ilike(f"%{query.strip()}%"),
    ]

    if chat_id is not None:
        if chat_id not in accessible_chat_ids:
            raise PermissionDeniedError("You do not have access to this chat")
        conditions.append(Message.chat_id == chat_id)

    count_stmt = select(func.count(Message.id)).where(and_(*conditions))
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Message)
        .where(and_(*conditions))
        .options(selectinload(Message.sender))
        .order_by(Message.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    messages = list((await db.execute(stmt)).scalars().all())
    return messages, total


async def mark_message_read(
    db: AsyncSession,
    message_id: int,
    user_id: int,
) -> MessageReceipt:
    """Record a read receipt acknowledging receipt of a message.

    Args:
        db: Database session.
        message_id: Target message ID.
        user_id: Reader user ID.

    Returns:
        MessageReceipt: Receipt ORM entity.
    """
    message = await db.get(Message, message_id)
    if message is None:
        raise MessageNotFoundError(f"Message {message_id} not found")

    # Ensure reader has access to the chat
    chat = await get_chat_or_404(db, message.chat_id)
    part = next((p for p in chat.participants if p.user_id == user_id), None)
    if part is None:
        raise PermissionDeniedError("Not a participant in this chat")

    # Update participant last_read_message_id
    if part.last_read_message_id is None or part.last_read_message_id < message_id:
        part.last_read_message_id = message_id

    # Check for existing receipt
    receipt_stmt = select(MessageReceipt).where(
        and_(
            MessageReceipt.message_id == message_id,
            MessageReceipt.user_id == user_id,
        )
    )
    existing_receipt = (await db.execute(receipt_stmt)).scalar_one_or_none()
    if existing_receipt is not None:
        return existing_receipt

    receipt = MessageReceipt(
        message_id=message_id,
        user_id=user_id,
        read_at=datetime.now(UTC),
    )
    db.add(receipt)
    await db.flush()
    return receipt

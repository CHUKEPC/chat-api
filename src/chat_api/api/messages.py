"""Message endpoints for sending, editing, deleting, searching, and read receipts."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.api.auth import get_current_user
from chat_api.db.session import get_db
from chat_api.exceptions import (
    InvalidOperationError,
    NotFoundError,
    PermissionDeniedError,
    UserBannedError,
    UserMutedError,
)
from chat_api.models.message import Message
from chat_api.models.user import User
from chat_api.schemas.message import (
    MessageCreateRequest,
    MessageListResponse,
    MessageResponse,
    MessageUpdateRequest,
    ReadReceiptResponse,
)
from chat_api.services import message as message_service

router = APIRouter(tags=["Messages"])


@router.post(
    "/chats/{chat_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send message to chat",
)
async def send_message(
    chat_id: int,
    request: MessageCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    """Send and persist a new message with optional attachments.

    Args:
        chat_id: Destination chat ID.
        request: Content and file attachments.
        db: Database session.
        current_user: Authenticated sender.

    Returns:
        MessageResponse: Created message payload.
    """
    try:
        msg = await message_service.send_message(
            db=db,
            chat_id=chat_id,
            sender_id=current_user.id,
            request=request,
        )
        response_data = MessageResponse.model_validate(msg)

        # Notify active WebSocket clients in the chat
        await message_service.ws_manager.broadcast_to_chat(
            chat_id=chat_id,
            message={
                "type": "new_message",
                "data": response_data.model_dump(mode="json"),
            },
        )
        return response_data
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except (PermissionDeniedError, UserBannedError, UserMutedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.message,
        ) from exc


@router.get(
    "/chats/{chat_id}/messages",
    response_model=MessageListResponse,
    summary="Get chat message history",
)
async def get_messages(
    chat_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> MessageListResponse:
    """Retrieve chronologically ordered message history with pagination.

    Args:
        chat_id: Target chat ID.
        db: Database session.
        current_user: Authenticated caller.
        limit: Page size.
        offset: Offset cursor.

    Returns:
        MessageListResponse: Messages list and pagination metadata.
    """
    try:
        messages, total, has_more = await message_service.get_chat_messages(
            db=db,
            chat_id=chat_id,
            user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
        items = [MessageResponse.model_validate(m) for m in messages]
        return MessageListResponse(items=items, total=total, has_more=has_more)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except (PermissionDeniedError, UserBannedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.message,
        ) from exc


@router.patch(
    "/messages/{message_id}",
    response_model=MessageResponse,
    summary="Edit message content",
)
async def edit_message(
    message_id: int,
    request: MessageUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    """Update message text content (author only).

    Args:
        message_id: Target message ID.
        request: New message content.
        db: Database session.
        current_user: Authenticated caller.

    Returns:
        MessageResponse: Updated message.
    """
    try:
        msg = await message_service.edit_message(
            db=db,
            message_id=message_id,
            user_id=current_user.id,
            request=request,
        )
        response_data = MessageResponse.model_validate(msg)

        # Broadcast edit event over WebSocket
        await message_service.ws_manager.broadcast_to_chat(
            chat_id=msg.chat_id,
            message={
                "type": "message_edited",
                "data": response_data.model_dump(mode="json"),
            },
        )
        return response_data
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.message,
        ) from exc


@router.delete(
    "/messages/{message_id}",
    response_model=MessageResponse,
    summary="Delete message (soft delete)",
)
async def delete_message(
    message_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    """Soft-delete a message, replacing content with tombstone placeholder.

    Args:
        message_id: Target message ID.
        db: Database session.
        current_user: Authenticated caller.

    Returns:
        MessageResponse: Masked message.
    """
    try:
        msg = await message_service.delete_message(
            db=db,
            message_id=message_id,
            user_id=current_user.id,
        )
        response_data = MessageResponse.model_validate(msg)

        # Broadcast deletion event over WebSocket
        await message_service.ws_manager.broadcast_to_chat(
            chat_id=msg.chat_id,
            message={
                "type": "message_deleted",
                "data": response_data.model_dump(mode="json"),
            },
        )
        return response_data
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.message,
        ) from exc


@router.get(
    "/messages/search",
    response_model=MessageListResponse,
    summary="Search messages",
)
async def search_messages(
    query: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    chat_id: int | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> MessageListResponse:
    """Search message contents across accessible chats.

    Args:
        query: Search string.
        db: Database session.
        current_user: Authenticated caller.
        chat_id: Optional single chat filter.
        limit: Limit count.
        offset: Offset cursor.

    Returns:
        MessageListResponse: Matching messages and counts.
    """
    try:
        messages, total = await message_service.search_messages(
            db=db,
            user_id=current_user.id,
            query=query,
            chat_id=chat_id,
            limit=limit,
            offset=offset,
        )
        items = [MessageResponse.model_validate(m) for m in messages]
        has_more = (offset + limit) < total
        return MessageListResponse(items=items, total=total, has_more=has_more)
    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.message,
        ) from exc


@router.post(
    "/messages/{message_id}/read",
    response_model=ReadReceiptResponse,
    summary="Mark message as read",
)
async def mark_read(
    message_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReadReceiptResponse:
    """Acknowledge message delivery and persist read receipt.

    Args:
        message_id: Read message ID.
        db: Database session.
        current_user: Authenticated reader.

    Returns:
        ReadReceiptResponse: Confirmed receipt.
    """
    try:
        receipt = await message_service.mark_message_read(
            db=db,
            message_id=message_id,
            user_id=current_user.id,
        )
        response_data = ReadReceiptResponse.model_validate(receipt)

        # Notify chat participants of read receipt
        stmt = select(Message.chat_id).where(Message.id == message_id)
        chat_id = (await db.execute(stmt)).scalar_one_or_none()
        if chat_id:
            await message_service.ws_manager.broadcast_to_chat(
                chat_id=chat_id,
                message={
                    "type": "read_receipt",
                    "data": response_data.model_dump(mode="json"),
                },
                exclude_socket=None,
            )

        return response_data
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except (PermissionDeniedError, InvalidOperationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.message,
        ) from exc

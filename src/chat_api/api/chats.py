"""Chat endpoints for room lifecycle, participation, and moderation."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.api.auth import get_current_user
from chat_api.db.session import get_db
from chat_api.exceptions import (
    ConflictError,
    InvalidOperationError,
    NotFoundError,
    PermissionDeniedError,
    UserBannedError,
)
from chat_api.models.user import User
from chat_api.schemas.chat import (
    AddParticipantRequest,
    BanUserRequest,
    ChatCreateRequest,
    ChatListResponse,
    ChatParticipantResponse,
    ChatResponse,
    ChatUpdateRequest,
    KickUserRequest,
    MuteUserRequest,
)
from chat_api.services import chat as chat_service

router = APIRouter(prefix="/chats", tags=["Chats"])


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create direct or group chat",
)
async def create_chat(
    request: ChatCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatResponse:
    """Create a new direct (1-on-1) or group chat room.

    Args:
        request: Chat creation options.
        db: Database session.
        current_user: Authenticated caller.

    Returns:
        ChatResponse: Detailed chat payload.
    """
    try:
        chat = await chat_service.create_chat(
            db=db,
            creator_id=current_user.id,
            request=request,
        )
        return ChatResponse.model_validate(chat)
    except (InvalidOperationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc


@router.get(
    "",
    response_model=ChatListResponse,
    summary="List caller's chats",
)
async def list_chats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> ChatListResponse:
    """List all chats the authenticated user belongs to.

    Args:
        db: Database session.
        current_user: Authenticated caller.
        skip: Pagination offset.
        limit: Limit count.

    Returns:
        ChatListResponse: List of active chat rooms.
    """
    chats = await chat_service.list_user_chats(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    items = [ChatResponse.model_validate(c) for c in chats]
    return ChatListResponse(items=items, total=len(items))


@router.get(
    "/{chat_id}",
    response_model=ChatResponse,
    summary="Get chat room details",
)
async def get_chat(
    chat_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatResponse:
    """Fetch details and participant roster for a given chat.

    Args:
        chat_id: Target chat ID.
        db: Database session.
        current_user: Authenticated caller.

    Returns:
        ChatResponse: Loaded chat room.
    """
    try:
        chat = await chat_service.get_chat(
            db=db,
            chat_id=chat_id,
            user_id=current_user.id,
        )
        return ChatResponse.model_validate(chat)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except UserBannedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.message,
        ) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.message,
        ) from exc


@router.patch(
    "/{chat_id}",
    response_model=ChatResponse,
    summary="Update chat room metadata",
)
async def update_chat(
    chat_id: int,
    request: ChatUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatResponse:
    """Update title or description of a chat room.

    Args:
        chat_id: Target chat ID.
        request: Update payload.
        db: Database session.
        current_user: Authenticated caller.

    Returns:
        ChatResponse: Updated chat entity.
    """
    try:
        chat = await chat_service.update_chat(
            db=db,
            chat_id=chat_id,
            user_id=current_user.id,
            request=request,
        )
        return ChatResponse.model_validate(chat)
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


@router.post(
    "/{chat_id}/participants",
    response_model=ChatParticipantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add participant to group chat",
)
async def add_participant(
    chat_id: int,
    request: AddParticipantRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatParticipantResponse:
    """Add a new member to a group chat room.

    Args:
        chat_id: Target chat ID.
        request: Target user and assigned role.
        db: Database session.
        current_user: Authenticated caller.

    Returns:
        ChatParticipantResponse: New participant membership info.
    """
    try:
        part = await chat_service.add_participant(
            db=db,
            chat_id=chat_id,
            actor_id=current_user.id,
            request=request,
        )
        return ChatParticipantResponse.model_validate(part)
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
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc
    except (InvalidOperationError, UserBannedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.delete(
    "/{chat_id}/participants/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove participant or leave chat",
)
async def remove_participant(
    chat_id: int,
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Remove a user from chat (leaving if user_id == me, kick if moderator).

    Args:
        chat_id: Target chat ID.
        user_id: User ID being removed.
        db: Database session.
        current_user: Authenticated caller.
    """
    try:
        await chat_service.remove_participant(
            db=db,
            chat_id=chat_id,
            actor_id=current_user.id,
            target_user_id=user_id,
        )
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
    except InvalidOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


# Moderation endpoints
@router.post(
    "/{chat_id}/moderation/mute",
    response_model=ChatParticipantResponse,
    summary="Mute participant in chat",
)
async def mute_user(
    chat_id: int,
    request: MuteUserRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatParticipantResponse:
    """Mute a participant for a designated time window.

    Args:
        chat_id: Target chat ID.
        request: Target user and duration.
        db: Database session.
        current_user: Moderator caller.

    Returns:
        ChatParticipantResponse: Muted participant state.
    """
    try:
        part = await chat_service.mute_participant(
            db=db,
            chat_id=chat_id,
            actor_id=current_user.id,
            request=request,
        )
        return ChatParticipantResponse.model_validate(part)
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


@router.post(
    "/{chat_id}/moderation/unmute/{user_id}",
    response_model=ChatParticipantResponse,
    summary="Unmute participant in chat",
)
async def unmute_user(
    chat_id: int,
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatParticipantResponse:
    """Remove mute restriction from a participant.

    Args:
        chat_id: Target chat ID.
        user_id: Target user ID.
        db: Database session.
        current_user: Moderator caller.

    Returns:
        ChatParticipantResponse: Unmuted participant state.
    """
    try:
        part = await chat_service.unmute_participant(
            db=db,
            chat_id=chat_id,
            actor_id=current_user.id,
            target_user_id=user_id,
        )
        return ChatParticipantResponse.model_validate(part)
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


@router.post(
    "/{chat_id}/moderation/kick",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Kick participant from chat",
)
async def kick_user(
    chat_id: int,
    request: KickUserRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Kick participant out of the group chat.

    Args:
        chat_id: Target chat ID.
        request: Target user ID.
        db: Database session.
        current_user: Moderator caller.
    """
    try:
        await chat_service.remove_participant(
            db=db,
            chat_id=chat_id,
            actor_id=current_user.id,
            target_user_id=request.user_id,
        )
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


@router.post(
    "/{chat_id}/moderation/ban",
    response_model=ChatParticipantResponse,
    summary="Ban participant from chat",
)
async def ban_user(
    chat_id: int,
    request: BanUserRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatParticipantResponse:
    """Permanently ban user from joining or reading the chat.

    Args:
        chat_id: Target chat ID.
        request: Target user ID.
        db: Database session.
        current_user: Moderator caller.

    Returns:
        ChatParticipantResponse: Banned participant record.
    """
    try:
        part = await chat_service.ban_participant(
            db=db,
            chat_id=chat_id,
            actor_id=current_user.id,
            request=request,
        )
        return ChatParticipantResponse.model_validate(part)
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


@router.post(
    "/{chat_id}/moderation/unban/{user_id}",
    response_model=ChatParticipantResponse,
    summary="Unban participant from chat",
)
async def unban_user(
    chat_id: int,
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatParticipantResponse:
    """Lift ban flag from a participant.

    Args:
        chat_id: Target chat ID.
        user_id: Target user ID.
        db: Database session.
        current_user: Moderator caller.

    Returns:
        ChatParticipantResponse: Unbanned participant record.
    """
    try:
        part = await chat_service.unban_participant(
            db=db,
            chat_id=chat_id,
            actor_id=current_user.id,
            target_user_id=user_id,
        )
        return ChatParticipantResponse.model_validate(part)
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

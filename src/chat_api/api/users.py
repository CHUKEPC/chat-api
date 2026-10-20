"""User endpoints for querying directory and managing profiles."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.api.auth import get_current_user
from chat_api.db.session import get_db
from chat_api.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from chat_api.models.user import User
from chat_api.schemas.user import (
    UserResponse,
    UserStatusUpdate,
    UserUpdateRequest,
)
from chat_api.services import user as user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "",
    response_model=list[UserResponse],
    summary="List users",
)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: str | None = Query(None, max_length=50),
    is_online: bool | None = None,
) -> list[UserResponse]:
    """Retrieve users directory with pagination and filters.

    Args:
        db: Database session.
        current_user: Authenticated caller.
        skip: Pagination offset.
        limit: Limit count.
        search: Optional search text.
        is_online: Filter by presence.

    Returns:
        list[UserResponse]: List of user profiles.
    """
    users = await user_service.list_users(
        db,
        skip=skip,
        limit=limit,
        search=search,
        is_online=is_online,
    )
    return [UserResponse.model_validate(u) for u in users]


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Retrieve details for a specific user.

    Args:
        user_id: Target user ID.
        db: Database session.
        current_user: Authenticated caller.

    Returns:
        UserResponse: User profile.
    """
    try:
        user = await user_service.get_user_by_id(db, user_id)
        return UserResponse.model_validate(user)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user profile",
)
async def update_user(
    user_id: int,
    request: UserUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Update profile details, email, password, or administrative role.

    Args:
        user_id: Target user ID.
        request: Update payload.
        db: Database session.
        current_user: Authenticated caller.

    Returns:
        UserResponse: Updated user profile.
    """
    try:
        user = await user_service.update_user(
            db=db,
            user_id=user_id,
            request=request,
            actor=current_user,
        )
        return UserResponse.model_validate(user)
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


@router.put(
    "/me/status",
    response_model=UserResponse,
    summary="Update online presence status",
)
async def update_status(
    request: UserStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Update caller's online/offline presence status.

    Args:
        request: Online status payload.
        db: Database session.
        current_user: Authenticated caller.

    Returns:
        UserResponse: Updated user profile.
    """
    user = await user_service.set_user_online_status(
        db=db,
        user_id=current_user.id,
        is_online=request.is_online,
    )
    return UserResponse.model_validate(user)

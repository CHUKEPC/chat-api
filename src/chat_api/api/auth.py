"""Authentication endpoints and token extraction dependencies."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.db.session import get_db
from chat_api.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
)
from chat_api.models.user import User
from chat_api.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
)
from chat_api.schemas.user import UserResponse
from chat_api.security.jwt import decode_token
from chat_api.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """FastAPI dependency to extract and authenticate current active user from JWT.

    Args:
        token: Bearer JWT from Authorization header.
        db: Database session.

    Returns:
        User: Authenticated user ORM instance.

    Raises:
        HTTPException: If token is missing, invalid, expired, or user not found.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(token, expected_type="access")
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = int(payload["sub"])
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return user


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    request: UserRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Register a new user account with unique username and email.

    Args:
        request: Registration payload.
        db: Database session.

    Returns:
        UserResponse: Created user profile.
    """
    try:
        user = await auth_service.register_user(db, request)
        return UserResponse.model_validate(user)
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login to obtain access and refresh tokens",
)
async def login(
    request: UserLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Authenticate with username/email and password.

    Args:
        request: Login payload.
        db: Database session.

    Returns:
        TokenResponse: Access and refresh tokens with TTL.
    """
    try:
        return await auth_service.login(db, request)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
        ) from exc


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Exchange a valid refresh token for a new token pair.

    Args:
        request: Token payload containing refresh_token.
        db: Database session.

    Returns:
        TokenResponse: Fresh tokens.
    """
    try:
        return await auth_service.refresh_tokens(db, request.refresh_token)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
        ) from exc
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return profile details for the currently authenticated caller.

    Args:
        current_user: Injected user instance.

    Returns:
        UserResponse: Caller's profile.
    """
    return UserResponse.model_validate(current_user)

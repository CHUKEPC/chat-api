"""Authentication and registration business logic service."""

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.config import get_settings
from chat_api.exceptions import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from chat_api.models.user import User
from chat_api.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
)
from chat_api.security.hashing import hash_password, verify_password
from chat_api.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
)

settings = get_settings()


async def register_user(db: AsyncSession, request: UserRegisterRequest) -> User:
    """Register a new user account with hashed password.

    Args:
        db: Database session.
        request: Registration payload.

    Returns:
        User: Newly created persistent user instance.

    Raises:
        UserAlreadyExistsError: If username or email is already taken.
    """
    stmt = select(User).where(
        or_(
            User.username == request.username,
            User.email == request.email,
        )
    )
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user is not None:
        if existing_user.username == request.username:
            raise UserAlreadyExistsError(f"Username '{request.username}' is already registered")
        raise UserAlreadyExistsError(f"Email '{request.email}' is already registered")

    user = User(
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        role=request.role,
        is_active=True,
        is_online=False,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, request: UserLoginRequest) -> User:
    """Validate credentials and return authenticated user.

    Args:
        db: Database session.
        request: Login payload containing username/email and plaintext password.

    Returns:
        User: Verified active user entity.

    Raises:
        InvalidCredentialsError: On unknown user, inactive account, or password mismatch.
    """
    stmt = select(User).where(
        or_(
            User.username == request.username_or_email,
            User.email == request.username_or_email,
        )
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise InvalidCredentialsError("Invalid username/email or password")

    if not verify_password(request.password, user.hashed_password):
        raise InvalidCredentialsError("Invalid username/email or password")

    if not user.is_active:
        raise InvalidCredentialsError("User account is inactive or disabled")

    return user


async def login(db: AsyncSession, request: UserLoginRequest) -> TokenResponse:
    """Authenticate credentials and generate token pair.

    Args:
        db: Database session.
        request: Login credentials.

    Returns:
        TokenResponse: Access and refresh tokens with expiration metadata.
    """
    user = await authenticate_user(db, request)

    user.is_online = True
    user.last_seen_at = datetime.now(UTC)
    await db.flush()

    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )
    refresh_token = create_refresh_token(user_id=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> TokenResponse:
    """Issue a fresh access and refresh token pair using an existing refresh token.

    Args:
        db: Database session.
        refresh_token: Valid refresh JWT string.

    Returns:
        TokenResponse: Newly generated token credentials.

    Raises:
        UserNotFoundError: If subject in token refers to deleted user.
        InvalidCredentialsError: If target account was deactivated.
    """
    payload = decode_token(refresh_token, expected_type="refresh")
    user_id = int(payload["sub"])

    user = await db.get(User, user_id)
    if user is None:
        raise UserNotFoundError("User associated with token does not exist")

    if not user.is_active:
        raise InvalidCredentialsError("Account is inactive")

    new_access = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )
    new_refresh = create_refresh_token(user_id=user.id)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

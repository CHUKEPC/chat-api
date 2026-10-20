"""Pydantic schemas for authentication and tokens."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterRequest(BaseModel):
    """Schema for user registration."""

    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="user", pattern=r"^(admin|moderator|user)$")


class UserLoginRequest(BaseModel):
    """Schema for user login using username/email and password."""

    username_or_email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """Schema for authentication token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Schema for refreshing access tokens."""

    refresh_token: str


class TokenPayload(BaseModel):
    """Decoded JWT payload data model."""

    sub: str
    username: str | None = None
    role: str = "user"
    type: str = "access"
    exp: int | None = None

    model_config = ConfigDict(extra="ignore")

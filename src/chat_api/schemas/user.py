"""Pydantic schemas for user profile and management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserResponse(BaseModel):
    """Public user profile schema."""

    id: int
    username: str
    email: EmailStr
    role: str
    is_active: bool
    is_online: bool
    last_seen_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserBriefResponse(BaseModel):
    """Abbreviated user schema for embedded relationships."""

    id: int
    username: str
    role: str
    is_online: bool

    model_config = ConfigDict(from_attributes=True)


class UserUpdateRequest(BaseModel):
    """Schema for updating user profile or admin attributes."""

    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: str | None = Field(default=None, pattern=r"^(admin|moderator|user)$")
    is_active: bool | None = None


class UserStatusUpdate(BaseModel):
    """Schema for changing presence status."""

    is_online: bool

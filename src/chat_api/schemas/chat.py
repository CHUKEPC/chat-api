"""Pydantic schemas for chat rooms and membership."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from chat_api.schemas.user import UserBriefResponse


class ChatParticipantResponse(BaseModel):
    """Schema representing participant membership in a chat."""

    id: int
    chat_id: int
    user_id: int
    user: UserBriefResponse | None = None
    role: str
    joined_at: datetime
    is_muted: bool
    muted_until: datetime | None = None
    is_banned: bool
    last_read_message_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class ChatCreateRequest(BaseModel):
    """Schema for initializing direct or group chats."""

    type: str = Field(default="group", pattern=r"^(direct|group)$")
    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    participant_ids: list[int] = Field(default_factory=list)


class ChatUpdateRequest(BaseModel):
    """Schema for updating chat metadata."""

    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ChatResponse(BaseModel):
    """Schema for chat details with participants list."""

    id: int
    type: str
    name: str | None = None
    description: str | None = None
    created_by_id: int | None = None
    created_at: datetime
    updated_at: datetime
    participants: list[ChatParticipantResponse] = Field(default_factory=list)
    unread_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ChatListResponse(BaseModel):
    """Paginated or listed chats container."""

    items: list[ChatResponse]
    total: int


class AddParticipantRequest(BaseModel):
    """Schema for adding new member to a group chat."""

    user_id: int
    role: str = Field(default="member", pattern=r"^(admin|member)$")


class MuteUserRequest(BaseModel):
    """Moderation schema for temporarily silencing a participant."""

    user_id: int
    duration_minutes: int | None = Field(default=60, ge=1, le=43200)


class KickUserRequest(BaseModel):
    """Moderation schema for removing a participant from chat."""

    user_id: int


class BanUserRequest(BaseModel):
    """Moderation schema for permanently banning a user from chat."""

    user_id: int

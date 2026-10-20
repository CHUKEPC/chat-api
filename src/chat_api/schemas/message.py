"""Pydantic schemas for messages, attachments, receipts, and search."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from chat_api.schemas.user import UserBriefResponse


class AttachmentSchema(BaseModel):
    """Metadata describing attached files."""

    filename: str = Field(..., max_length=255)
    file_size: int = Field(..., ge=0)
    content_type: str = Field(..., max_length=100)
    file_url: str = Field(..., max_length=1000)


class MessageCreateRequest(BaseModel):
    """Schema for composing and sending a message."""

    content: str = Field(..., min_length=1, max_length=10000)
    attachments: list[AttachmentSchema] = Field(default_factory=list)


class MessageUpdateRequest(BaseModel):
    """Schema for editing an existing message's text."""

    content: str = Field(..., min_length=1, max_length=10000)


class MessageResponse(BaseModel):
    """Full message payload representation."""

    id: int
    chat_id: int
    sender_id: int | None = None
    sender: UserBriefResponse | None = None
    content: str
    is_edited: bool
    is_deleted: bool
    edited_at: datetime | None = None
    created_at: datetime
    attachments: list[AttachmentSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class MessageListResponse(BaseModel):
    """Paginated list of messages for history queries."""

    items: list[MessageResponse]
    total: int
    has_more: bool


class ReadReceiptRequest(BaseModel):
    """Schema for acknowledging message delivery/read state."""

    message_id: int


class ReadReceiptResponse(BaseModel):
    """Schema for confirmed read receipt."""

    message_id: int
    user_id: int
    read_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TypingIndicatorSchema(BaseModel):
    """WebSocket typing indicator event payload."""

    chat_id: int
    is_typing: bool


class WebSocketMessage(BaseModel):
    """Standardized envelope for real-time WebSocket protocol frames."""

    type: str
    data: dict[str, Any] = Field(default_factory=dict)

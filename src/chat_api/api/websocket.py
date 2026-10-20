"""WebSocket real-time communication endpoint for messaging and presence."""

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from chat_api.db.session import get_session_factory
from chat_api.models.chat import Chat, ChatParticipant
from chat_api.models.user import User
from chat_api.schemas.message import MessageCreateRequest, MessageResponse
from chat_api.security.jwt import decode_token
from chat_api.services import message as message_service
from chat_api.services.message import ws_manager

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/{chat_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    chat_id: int,
    token: str | None = Query(None),
) -> None:
    """Full-duplex WebSocket endpoint for real-time messaging, typing, and receipts.

    Args:
        websocket: Connecting WebSocket client.
        chat_id: Target room identifier.
        token: Access JWT passed via query parameter.
    """
    if not token:
        await websocket.close(code=4001, reason="Authentication token required")
        return

    try:
        payload = decode_token(token, expected_type="access")
        user_id = int(payload["sub"])
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    # Verify membership and permissions within a dedicated session
    async with get_session_factory()() as session:
        user = await session.get(User, user_id)
        if not user or not user.is_active:
            await websocket.close(code=4001, reason="User account invalid")
            return

        chat = await session.get(Chat, chat_id)
        if not chat:
            await websocket.close(code=4004, reason="Chat not found")
            return

        part_stmt = select(ChatParticipant).where(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == user_id,
        )
        participant = (await session.execute(part_stmt)).scalar_one_or_none()
        if not participant:
            await websocket.close(code=4003, reason="Not a member of this chat")
            return

        if participant.is_banned:
            await websocket.close(code=4003, reason="Banned from this chat")
            return

        # Update online status
        user.is_online = True
        user.last_seen_at = datetime.now(UTC)
        await session.commit()
        username = user.username

    # Register socket in connection manager
    await ws_manager.connect(websocket, chat_id, user_id)

    # Broadcast presence notification
    await ws_manager.broadcast_to_chat(
        chat_id=chat_id,
        message={
            "type": "presence",
            "data": {
                "user_id": user_id,
                "username": username,
                "is_online": True,
            },
        },
    )

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                frame: dict[str, Any] = json.loads(raw_data)
            except Exception:
                await websocket.send_json({"type": "error", "message": "Invalid JSON frame"})
                continue

            event_type = frame.get("type")

            if event_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif event_type == "typing":
                is_typing = bool(frame.get("is_typing", True))
                await ws_manager.broadcast_to_chat(
                    chat_id=chat_id,
                    message={
                        "type": "typing",
                        "data": {
                            "chat_id": chat_id,
                            "user_id": user_id,
                            "username": username,
                            "is_typing": is_typing,
                        },
                    },
                    exclude_socket=websocket,
                )

            elif event_type == "message":
                content = frame.get("content", "")
                attachments = frame.get("attachments", [])
                if not content and not attachments:
                    continue

                async with get_session_factory()() as db:
                    try:
                        create_req = MessageCreateRequest(
                            content=content,
                            attachments=attachments,
                        )
                        saved_msg = await message_service.send_message(
                            db=db,
                            chat_id=chat_id,
                            sender_id=user_id,
                            request=create_req,
                        )
                        await db.commit()
                        serialized = MessageResponse.model_validate(saved_msg)
                        await ws_manager.broadcast_to_chat(
                            chat_id=chat_id,
                            message={
                                "type": "new_message",
                                "data": serialized.model_dump(mode="json"),
                            },
                        )
                    except Exception as exc:
                        await websocket.send_json({"type": "error", "message": str(exc)})

            elif event_type == "read":
                msg_id = frame.get("message_id")
                if isinstance(msg_id, int):
                    async with get_session_factory()() as db:
                        try:
                            receipt = await message_service.mark_message_read(
                                db=db,
                                message_id=msg_id,
                                user_id=user_id,
                            )
                            await db.commit()
                            await ws_manager.broadcast_to_chat(
                                chat_id=chat_id,
                                message={
                                    "type": "read_receipt",
                                    "data": {
                                        "message_id": msg_id,
                                        "user_id": user_id,
                                        "read_at": receipt.read_at.isoformat(),
                                    },
                                },
                            )
                        except Exception as exc:
                            await websocket.send_json({"type": "error", "message": str(exc)})

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        # If user has no more active sockets, update presence in DB
        if not ws_manager.is_user_online(user_id):
            async with get_session_factory()() as session:
                u = await session.get(User, user_id)
                if u:
                    u.is_online = False
                    u.last_seen_at = datetime.now(UTC)
                    await session.commit()

            await ws_manager.broadcast_to_chat(
                chat_id=chat_id,
                message={
                    "type": "presence",
                    "data": {
                        "user_id": user_id,
                        "username": username,
                        "is_online": False,
                    },
                },
            )
    except Exception:
        ws_manager.disconnect(websocket)

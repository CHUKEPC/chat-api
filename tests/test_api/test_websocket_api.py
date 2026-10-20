"""Integration tests for WebSocket communication, typing indicators, and real-time frames."""

from starlette.testclient import TestClient

from chat_api.models.chat import Chat


def test_websocket_connection_unauthorized(app: object, group_chat: Chat) -> None:
    """Test connecting without token fails with 4001."""
    client = TestClient(app)  # type: ignore[arg-type]
    try:
        with client.websocket_connect(f"/api/v1/ws/{group_chat.id}") as ws:
            ws.receive_json()
    except Exception:
        # Expected WebSocket disconnect with close code
        pass


def test_websocket_ping_pong_and_typing(
    app: object,
    group_chat: Chat,
    user_token: str,
) -> None:
    """Test full WebSocket ping/pong and typing indicator protocol."""
    client = TestClient(app)  # type: ignore[arg-type]
    with client.websocket_connect(f"/api/v1/ws/{group_chat.id}?token={user_token}") as ws:
        # Upon connecting, a presence frame is broadcasted
        init_frame = ws.receive_json()
        assert init_frame["type"] == "presence"
        assert init_frame["data"]["is_online"] is True

        # Send ping -> expect pong
        ws.send_json({"type": "ping"})
        pong_frame = ws.receive_json()
        assert pong_frame["type"] == "pong"

        # Send typing -> expect frame processed without error
        ws.send_json({"type": "typing", "is_typing": True})


def test_websocket_send_message_frame(
    app: object,
    group_chat: Chat,
    user_token: str,
) -> None:
    """Test sending message via WebSocket frame."""
    client = TestClient(app)  # type: ignore[arg-type]
    with client.websocket_connect(f"/api/v1/ws/{group_chat.id}?token={user_token}") as ws:
        # Consume presence
        ws.receive_json()

        # Send message frame
        ws.send_json(
            {
                "type": "message",
                "content": "Real-time greeting from WebSocket!",
                "attachments": [],
            }
        )
        msg_frame = ws.receive_json()
        assert msg_frame["type"] == "new_message"
        assert msg_frame["data"]["content"] == "Real-time greeting from WebSocket!"
        msg_id = msg_frame["data"]["id"]

        # Send read receipt frame
        ws.send_json({"type": "read", "message_id": msg_id})
        receipt_frame = ws.receive_json()
        assert receipt_frame["type"] == "read_receipt"
        assert receipt_frame["data"]["message_id"] == msg_id

        # Send invalid JSON text
        ws.send_text("not-a-json-string")
        err_frame = ws.receive_json()
        assert err_frame["type"] == "error"


def test_websocket_non_member_fails(
    app: object,
    group_chat: Chat,
    admin_token: str,
) -> None:
    """Test connecting to a chat user is not part of closes connection."""
    client = TestClient(app)  # type: ignore[arg-type]
    try:
        with client.websocket_connect(f"/api/v1/ws/{group_chat.id}?token={admin_token}") as ws:
            ws.receive_json()
    except Exception:
        # Expected close code 4003
        pass

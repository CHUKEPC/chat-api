"""Integration tests for messages, attachments, search, and read receipts."""

from httpx import AsyncClient

from chat_api.models.chat import Chat


async def test_send_and_get_messages_api(
    client: AsyncClient,
    auth_headers: dict[str, str],
    group_chat: Chat,
) -> None:
    """Test POST /api/v1/chats/{id}/messages and GET /api/v1/chats/{id}/messages."""
    post_resp = await client.post(
        f"/api/v1/chats/{group_chat.id}/messages",
        headers=auth_headers,
        json={
            "content": "API test message content",
            "attachments": [
                {
                    "filename": "screenshot.png",
                    "file_size": 2048,
                    "content_type": "image/png",
                    "file_url": "https://storage.example.com/screenshot.png",
                }
            ],
        },
    )
    assert post_resp.status_code == 201
    msg_data = post_resp.json()
    assert msg_data["content"] == "API test message content"
    assert len(msg_data["attachments"]) == 1

    # Get history
    get_resp = await client.get(
        f"/api/v1/chats/{group_chat.id}/messages",
        headers=auth_headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["total"] >= 1


async def test_edit_and_delete_message_api(
    client: AsyncClient,
    auth_headers: dict[str, str],
    group_chat: Chat,
) -> None:
    """Test PATCH /api/v1/messages/{id} and DELETE /api/v1/messages/{id}."""
    post_resp = await client.post(
        f"/api/v1/chats/{group_chat.id}/messages",
        headers=auth_headers,
        json={"content": "Before edit"},
    )
    msg_id = post_resp.json()["id"]

    # Edit
    patch_resp = await client.patch(
        f"/api/v1/messages/{msg_id}",
        headers=auth_headers,
        json={"content": "After edit"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["content"] == "After edit"
    assert patch_resp.json()["is_edited"] is True

    # Delete
    del_resp = await client.delete(
        f"/api/v1/messages/{msg_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["is_deleted"] is True
    assert del_resp.json()["content"] == "[Message deleted]"


async def test_search_messages_api(
    client: AsyncClient,
    auth_headers: dict[str, str],
    group_chat: Chat,
) -> None:
    """Test GET /api/v1/messages/search."""
    await client.post(
        f"/api/v1/chats/{group_chat.id}/messages",
        headers=auth_headers,
        json={"content": "Quantum computing breakthrough"},
    )

    search_resp = await client.get(
        "/api/v1/messages/search",
        headers=auth_headers,
        params={"query": "Quantum"},
    )
    assert search_resp.status_code == 200
    assert search_resp.json()["total"] >= 1


async def test_mark_message_read_api(
    client: AsyncClient,
    auth_headers: dict[str, str],
    user_2_headers: dict[str, str],
    group_chat: Chat,
) -> None:
    """Test POST /api/v1/messages/{id}/read."""
    post_resp = await client.post(
        f"/api/v1/chats/{group_chat.id}/messages",
        headers=auth_headers,
        json={"content": "Read me please"},
    )
    msg_id = post_resp.json()["id"]

    read_resp = await client.post(
        f"/api/v1/messages/{msg_id}/read",
        headers=user_2_headers,
    )
    assert read_resp.status_code == 200
    assert read_resp.json()["message_id"] == msg_id


async def test_messages_api_errors(
    client: AsyncClient,
    auth_headers: dict[str, str],
    user_2_headers: dict[str, str],
    group_chat: Chat,
) -> None:
    """Test error handling in messages endpoints."""
    # Post to nonexistent chat -> 404
    resp_404 = await client.post(
        "/api/v1/chats/99999/messages",
        headers=auth_headers,
        json={"content": "Hello"},
    )
    assert resp_404.status_code == 404

    # Get from nonexistent chat -> 404
    resp_get_404 = await client.get(
        "/api/v1/chats/99999/messages",
        headers=auth_headers,
    )
    assert resp_get_404.status_code == 404

    # Edit nonexistent message -> 404
    resp_edit_404 = await client.patch(
        "/api/v1/messages/99999",
        headers=auth_headers,
        json={"content": "New"},
    )
    assert resp_edit_404.status_code == 404

    # Delete nonexistent message -> 404
    resp_del_404 = await client.delete(
        "/api/v1/messages/99999",
        headers=auth_headers,
    )
    assert resp_del_404.status_code == 404

    # Mark nonexistent message read -> 404
    resp_read_404 = await client.post(
        "/api/v1/messages/99999/read",
        headers=auth_headers,
    )
    assert resp_read_404.status_code == 404

    # Edit another user's message -> 403
    post_resp = await client.post(
        f"/api/v1/chats/{group_chat.id}/messages",
        headers=auth_headers,
        json={"content": "Alice original"},
    )
    msg_id = post_resp.json()["id"]

    resp_edit_403 = await client.patch(
        f"/api/v1/messages/{msg_id}",
        headers=user_2_headers,
        json={"content": "Bob hack"},
    )
    assert resp_edit_403.status_code == 403

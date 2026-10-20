"""Integration tests for chats and moderation endpoints."""

from httpx import AsyncClient

from chat_api.models.chat import Chat
from chat_api.models.user import User


async def test_create_and_get_chat(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_user_2: User,
) -> None:
    """Test POST /api/v1/chats and GET /api/v1/chats/{id}."""
    resp = await client.post(
        "/api/v1/chats",
        headers=auth_headers,
        json={
            "type": "group",
            "name": "Backend Guild",
            "description": "API discussions",
            "participant_ids": [test_user_2.id],
        },
    )
    assert resp.status_code == 201
    chat_id = resp.json()["id"]

    get_resp = await client.get(f"/api/v1/chats/{chat_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Backend Guild"


async def test_list_chats_api(
    client: AsyncClient,
    auth_headers: dict[str, str],
    group_chat: Chat,
) -> None:
    """Test GET /api/v1/chats."""
    resp = await client.get("/api/v1/chats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert any(c["id"] == group_chat.id for c in data["items"])


async def test_update_chat_api(
    client: AsyncClient,
    auth_headers: dict[str, str],
    group_chat: Chat,
) -> None:
    """Test PATCH /api/v1/chats/{id}."""
    resp = await client.patch(
        f"/api/v1/chats/{group_chat.id}",
        headers=auth_headers,
        json={"name": "New Guild Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Guild Name"


async def test_add_and_remove_participant_api(
    client: AsyncClient,
    auth_headers: dict[str, str],
    group_chat: Chat,
    test_admin: User,
) -> None:
    """Test adding participant and then kicking them."""
    add_resp = await client.post(
        f"/api/v1/chats/{group_chat.id}/participants",
        headers=auth_headers,
        json={"user_id": test_admin.id, "role": "member"},
    )
    assert add_resp.status_code == 201

    del_resp = await client.delete(
        f"/api/v1/chats/{group_chat.id}/participants/{test_admin.id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204


async def test_moderation_mute_unmute_api(
    client: AsyncClient,
    auth_headers: dict[str, str],
    group_chat: Chat,
    test_user_2: User,
) -> None:
    """Test POST /api/v1/chats/{id}/moderation/mute and unmute."""
    mute_resp = await client.post(
        f"/api/v1/chats/{group_chat.id}/moderation/mute",
        headers=auth_headers,
        json={"user_id": test_user_2.id, "duration_minutes": 60},
    )
    assert mute_resp.status_code == 200
    assert mute_resp.json()["is_muted"] is True

    unmute_resp = await client.post(
        f"/api/v1/chats/{group_chat.id}/moderation/unmute/{test_user_2.id}",
        headers=auth_headers,
    )
    assert unmute_resp.status_code == 200
    assert unmute_resp.json()["is_muted"] is False


async def test_moderation_ban_unban_api(
    client: AsyncClient,
    auth_headers: dict[str, str],
    group_chat: Chat,
    test_user_2: User,
) -> None:
    """Test POST /api/v1/chats/{id}/moderation/ban and unban."""
    ban_resp = await client.post(
        f"/api/v1/chats/{group_chat.id}/moderation/ban",
        headers=auth_headers,
        json={"user_id": test_user_2.id},
    )
    assert ban_resp.status_code == 200
    assert ban_resp.json()["is_banned"] is True

    unban_resp = await client.post(
        f"/api/v1/chats/{group_chat.id}/moderation/unban/{test_user_2.id}",
        headers=auth_headers,
    )
    assert unban_resp.status_code == 200
    assert unban_resp.json()["is_banned"] is False


async def test_chats_api_errors(
    client: AsyncClient,
    auth_headers: dict[str, str],
    user_2_headers: dict[str, str],
    group_chat: Chat,
) -> None:
    """Test error handling on chat endpoints."""
    # Create invalid chat type -> 422
    resp_bad_type = await client.post(
        "/api/v1/chats",
        headers=auth_headers,
        json={"type": "invalid", "name": "Bad"},
    )
    assert resp_bad_type.status_code == 422

    # Direct chat with invalid participant count -> 400
    resp_bad_direct = await client.post(
        "/api/v1/chats",
        headers=auth_headers,
        json={"type": "direct", "participant_ids": []},
    )
    assert resp_bad_direct.status_code == 400

    # Get nonexistent chat -> 404
    resp_404 = await client.get("/api/v1/chats/99999", headers=auth_headers)
    assert resp_404.status_code == 404

    # Update nonexistent chat -> 404
    resp_update_404 = await client.patch(
        "/api/v1/chats/99999",
        headers=auth_headers,
        json={"name": "New"},
    )
    assert resp_update_404.status_code == 404

    # Member cannot update chat name -> 403
    resp_update_403 = await client.patch(
        f"/api/v1/chats/{group_chat.id}",
        headers=user_2_headers,
        json={"name": "Hacked Name"},
    )
    assert resp_update_403.status_code == 403

    # Add nonexistent participant -> 404
    resp_add_404 = await client.post(
        f"/api/v1/chats/{group_chat.id}/participants",
        headers=auth_headers,
        json={"user_id": 99999},
    )
    assert resp_add_404.status_code == 404

    # Kick endpoint
    kick_resp = await client.post(
        f"/api/v1/chats/{group_chat.id}/moderation/kick",
        headers=auth_headers,
        json={"user_id": 99999},
    )
    assert kick_resp.status_code == 404

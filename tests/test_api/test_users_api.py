"""Integration tests for users directory and profile endpoints."""

from httpx import AsyncClient

from chat_api.models.user import User


async def test_list_users_api(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """Test GET /api/v1/users."""
    resp = await client.get("/api/v1/users", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


async def test_get_user_by_id_api(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """Test GET /api/v1/users/{id}."""
    resp = await client.get(f"/api/v1/users/{test_user.id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == test_user.username

    # Not found
    resp404 = await client.get("/api/v1/users/99999", headers=auth_headers)
    assert resp404.status_code == 404


async def test_update_user_api_self(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """Test PATCH /api/v1/users/{id} for self profile."""
    resp = await client.patch(
        f"/api/v1/users/{test_user.id}",
        headers=auth_headers,
        json={"email": "alice_updated@example.com"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice_updated@example.com"


async def test_update_user_forbidden_for_other_user(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_user_2: User,
) -> None:
    """Test regular user cannot modify another user's profile."""
    resp = await client.patch(
        f"/api/v1/users/{test_user_2.id}",
        headers=auth_headers,
        json={"email": "hacked@example.com"},
    )
    assert resp.status_code == 403


async def test_update_user_admin_role_change(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_user: User,
) -> None:
    """Test admin can change user roles."""
    resp = await client.patch(
        f"/api/v1/users/{test_user.id}",
        headers=admin_headers,
        json={"role": "moderator"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "moderator"


async def test_update_user_presence_status(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Test PUT /api/v1/users/me/status updates presence."""
    resp = await client.put(
        "/api/v1/users/me/status",
        headers=auth_headers,
        json={"is_online": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_online"] is False

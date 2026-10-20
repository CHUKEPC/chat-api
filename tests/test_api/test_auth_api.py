"""Integration tests for authentication endpoints."""

from httpx import AsyncClient

from chat_api.models.user import User


async def test_register_api_success(client: AsyncClient) -> None:
    """Test POST /api/v1/auth/register."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "dave",
            "email": "dave@example.com",
            "password": "Password123!",
            "role": "user",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "dave"
    assert data["email"] == "dave@example.com"
    assert "id" in data


async def test_register_duplicate_conflict(client: AsyncClient, test_user: User) -> None:
    """Test duplicate registration returns 409 Conflict."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": test_user.username,
            "email": "another@example.com",
            "password": "Password123!",
        },
    )
    assert resp.status_code == 409


async def test_login_api_success(client: AsyncClient, test_user: User) -> None:
    """Test POST /api/v1/auth/login returns token pair."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": test_user.username,
            "password": "Password123!",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_invalid_credentials(client: AsyncClient) -> None:
    """Test login with wrong password returns 401 Unauthorized."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": "nobody",
            "password": "WrongPassword!",
        },
    )
    assert resp.status_code == 401


async def test_refresh_token_api(client: AsyncClient, test_user: User) -> None:
    """Test POST /api/v1/auth/refresh."""
    # First login to obtain refresh token
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": test_user.username,
            "password": "Password123!",
        },
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Exchange for new tokens
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_get_me_endpoint(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """Test GET /api/v1/auth/me returns current user profile."""
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "alice"


async def test_get_me_unauthorized(client: AsyncClient) -> None:
    """Test GET /api/v1/auth/me without header returns 401."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401

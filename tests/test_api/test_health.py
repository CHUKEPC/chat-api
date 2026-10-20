"""Integration test for application health check endpoint."""

from httpx import AsyncClient


async def test_health_check_endpoint(client: AsyncClient) -> None:
    """Test GET /health returns status ok."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data

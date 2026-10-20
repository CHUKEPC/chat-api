"""Unit and integration tests for rate limiting middleware."""

from starlette.requests import Request
from starlette.responses import PlainTextResponse

from chat_api.middleware.rate_limit import InMemoryRateLimiter, RateLimitMiddleware
from chat_api.security.jwt import create_access_token


def test_in_memory_rate_limiter_allows_under_limit() -> None:
    """Test requests within threshold are allowed."""
    limiter = InMemoryRateLimiter(limit=3, window_seconds=10)
    key = "user:1"

    allowed1, remaining1, _ = limiter.is_allowed(key)
    assert allowed1 is True
    assert remaining1 == 2

    allowed2, remaining2, _ = limiter.is_allowed(key)
    assert allowed2 is True
    assert remaining2 == 1

    allowed3, remaining3, _ = limiter.is_allowed(key)
    assert allowed3 is True
    assert remaining3 == 0

    # 4th request exceeds limit
    allowed4, remaining4, retry_after = limiter.is_allowed(key)
    assert allowed4 is False
    assert remaining4 == 0
    assert retry_after > 0


def test_in_memory_rate_limiter_reset() -> None:
    """Test limiter reset clears counters."""
    limiter = InMemoryRateLimiter(limit=1, window_seconds=10)
    key = "user:1"
    limiter.is_allowed(key)
    assert limiter.is_allowed(key)[0] is False

    limiter.reset()
    assert limiter.is_allowed(key)[0] is True


def test_rate_limit_middleware_extract_client_key() -> None:
    """Test client key extraction from Bearer token and fallback to IP."""

    async def mock_app(scope: object, receive: object, send: object) -> None:
        pass

    middleware = RateLimitMiddleware(mock_app, limit=10, window_seconds=60)

    # 1. Bearer token present
    token = create_access_token(user_id=123, username="test", role="user")
    req_token = Request(
        scope={
            "type": "http",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "client": ("192.168.1.5", 5000),
        }
    )
    assert middleware._extract_client_key(req_token) == "user:123"

    # 2. No bearer token -> falls back to client IP
    req_ip = Request(
        scope={
            "type": "http",
            "headers": [],
            "client": ("192.168.1.5", 5000),
        }
    )
    assert middleware._extract_client_key(req_ip) == "ip:192.168.1.5"

    # 3. Invalid token -> falls back to client IP
    req_bad = Request(
        scope={
            "type": "http",
            "headers": [(b"authorization", b"Bearer invalid_token_value")],
            "client": ("10.0.0.1", 5000),
        }
    )
    assert middleware._extract_client_key(req_bad) == "ip:10.0.0.1"


async def test_rate_limit_middleware_blocks_on_threshold() -> None:
    """Test middleware returns HTTP 429 when threshold exceeded."""

    async def dummy_app(scope: object, receive: object, send: object) -> None:
        response = PlainTextResponse("OK")
        await response(scope, receive, send)

    middleware = RateLimitMiddleware(dummy_app, limit=2, window_seconds=60)

    async def call_next(req: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")

    req = Request(
        scope={
            "type": "http",
            "path": "/api/v1/resource",
            "headers": [],
            "client": ("127.0.0.1", 1234),
        }
    )

    # 1st request -> OK
    res1 = await middleware.dispatch(req, call_next)
    assert res1.status_code == 200

    # 2nd request -> OK
    res2 = await middleware.dispatch(req, call_next)
    assert res2.status_code == 200

    # 3rd request -> 429 Too Many Requests
    res3 = await middleware.dispatch(req, call_next)
    assert res3.status_code == 429
    assert "Retry-After" in res3.headers

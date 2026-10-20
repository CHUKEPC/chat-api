"""Rate limiting middleware for API request throttling."""

import time
from collections import defaultdict
from typing import ClassVar

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from chat_api.config import get_settings
from chat_api.security.jwt import decode_token


class InMemoryRateLimiter:
    """Thread-safe sliding-window in-memory rate limiter."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        """Initialize limiter with request threshold and time window.

        Args:
            limit: Maximum requests permitted per window.
            window_seconds: Window duration in seconds.
        """
        self.limit = limit
        self.window_seconds = window_seconds
        # Mapping: client_identifier -> list of request timestamps (epoch floats)
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> tuple[bool, int, int]:
        """Check whether key has exceeded request quota.

        Args:
            key: Unique client identifier (e.g. user_id or client IP).

        Returns:
            tuple[bool, int, int]: (allowed, remaining_quota, retry_after_seconds).
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Prune timestamps older than window
        timestamps = [ts for ts in self.requests[key] if ts > window_start]
        self.requests[key] = timestamps

        if len(timestamps) >= self.limit:
            oldest_in_window = timestamps[0]
            retry_after = max(1, int(oldest_in_window + self.window_seconds - now))
            return False, 0, retry_after

        # Record this request
        timestamps.append(now)
        remaining = max(0, self.limit - len(timestamps))
        return True, remaining, 0

    def reset(self) -> None:
        """Clear all tracked request history."""
        self.requests.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ASGI Middleware enforcing rate limits per authenticated user or client IP."""

    EXEMPT_PATHS: ClassVar[set[str]] = {
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/api/v1/health",
    }

    def __init__(
        self, app: ASGIApp, limit: int | None = None, window_seconds: int | None = None
    ) -> None:
        """Initialize middleware with optional override limits.

        Args:
            app: Starlette/FastAPI application.
            limit: Requests per window override.
            window_seconds: Window duration override.
        """
        super().__init__(app)
        settings = get_settings()
        self.limit = limit or settings.RATE_LIMIT_REQUESTS
        self.window_seconds = window_seconds or settings.RATE_LIMIT_WINDOW_SECONDS
        self.limiter = InMemoryRateLimiter(self.limit, self.window_seconds)

    def _extract_client_key(self, request: Request) -> str:
        """Extract user_id from Bearer token if present, otherwise client host IP.

        Args:
            request: Incoming HTTP request.

        Returns:
            str: Limiter partitioning key.
        """
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            try:
                payload = decode_token(token, expected_type="access")
                user_id = payload.get("sub")
                if user_id:
                    return f"user:{user_id}"
            except Exception:
                # Token decode failed or expired, fall back to IP
                pass

        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Intercept request to enforce sliding-window rate limit.

        Args:
            request: Active HTTP request.
            call_next: Next endpoint handler.

        Returns:
            Response: HTTP response or 429 Too Many Requests JSON.
        """
        # Bypass exempt paths and WebSocket handshakes
        path = request.url.path
        if path in self.EXEMPT_PATHS or request.headers.get("upgrade") == "websocket":
            return await call_next(request)

        key = self._extract_client_key(request)
        allowed, remaining, retry_after = self.limiter.is_allowed(key)

        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded. Please wait before making more requests.",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(retry_after),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

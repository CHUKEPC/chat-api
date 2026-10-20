"""FastAPI application entry point.

Initializes middleware, routing, CORS, and lifecycle events.
Contains no business logic or inline route implementations.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chat_api.api.router import api_router
from chat_api.config import get_settings
from chat_api.db.session import Base, get_engine
from chat_api.middleware.rate_limit import RateLimitMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle hooks.

    Initializes database tables on start (for dev/sqlite) and disposes engine pool on shutdown.

    Args:
        app: FastAPI application instance.

    Yields:
        None
    """
    # Create tables if not running in migration-strict mode
    active_engine = get_engine()
    async with active_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Teardown database connections
    await active_engine.dispose()


def create_app() -> FastAPI:
    """Build and configure the main FastAPI application instance.

    Returns:
        FastAPI: Ready-to-serve application.
    """
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # CORS Middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate Limiting Middleware
    application.add_middleware(RateLimitMiddleware)

    # Mount API routers
    application.include_router(api_router, prefix="/api/v1")

    @application.get("/health", tags=["Health"], summary="Health check")
    async def health_check() -> dict[str, str]:
        """Verify service operational readiness.

        Returns:
            dict[str, str]: Service status payload.
        """
        return {"status": "ok", "version": settings.APP_VERSION}

    return application


app = create_app()

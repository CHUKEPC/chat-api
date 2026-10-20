"""Database session and async engine setup for SQLAlchemy 2.0."""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from chat_api.config import get_settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


settings = get_settings()

engine_kwargs: dict[str, Any] = {
    "echo": settings.DB_ECHO,
    "future": True,
}

# SQLite in-memory or file drivers used in tests do not support pool_size/max_overflow
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update(
        {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
        }
    )

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def get_engine() -> AsyncEngine:
    """Return active async database engine.

    Returns:
        AsyncEngine: Current SQLAlchemy async engine.
    """
    return engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return active async session factory.

    Returns:
        async_sessionmaker[AsyncSession]: Current sessionmaker callable.
    """
    return async_session_factory


def set_engine(new_engine: AsyncEngine | None = None) -> None:
    """Set global async engine and recreate session factory (useful for testing).

    Args:
        new_engine: Custom async engine or None to revert to default.
    """
    global engine, async_session_factory
    if new_engine is not None:
        engine = new_engine
        async_session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    else:
        engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)
        async_session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide transactional async database session dependency for FastAPI routes.

    Yields:
        AsyncSession: Active SQLAlchemy session.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

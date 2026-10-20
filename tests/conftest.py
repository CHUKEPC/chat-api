"""Global pytest configuration, fixtures, and in-memory test database setup."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from chat_api.config import Settings
from chat_api.db.session import Base, get_db, set_engine
from chat_api.main import create_app
from chat_api.models.chat import Chat, ChatParticipant, ChatType, ParticipantRole
from chat_api.models.user import User
from chat_api.security.hashing import hash_password
from chat_api.security.jwt import create_access_token


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Provide isolated application settings for testing.

    Returns:
        Settings: Test settings configured for in-memory execution.
    """
    return Settings(
        APP_NAME="Chat API Test",
        ENVIRONMENT="testing",
        DEBUG=True,
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        DATABASE_SYNC_URL="sqlite:///:memory:",
        SECRET_KEY="test-secret-key-that-is-at-least-32-chars-long",
        ACCESS_TOKEN_EXPIRE_MINUTES=60,
        REFRESH_TOKEN_EXPIRE_DAYS=7,
        RATE_LIMIT_REQUESTS=1000,
        RATE_LIMIT_WINDOW_SECONDS=60,
    )


@pytest.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Provide an in-memory SQLite asynchronous database engine with StaticPool.

    Yields:
        AsyncEngine: Prepared SQLite engine with tables created.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    set_engine(engine)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    set_engine(None)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an active database session for unit tests.

    Args:
        test_engine: Active test engine.

    Yields:
        AsyncSession: Active test session.
    """
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
async def app(test_engine: AsyncEngine) -> AsyncGenerator[object, None]:
    """Provide initialized FastAPI app with test DB session overrides.

    Args:
        test_engine: Active test engine.

    Yields:
        FastAPI: Configured application instance.
    """
    test_app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        session_factory = async_sessionmaker(
            bind=test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    test_app.dependency_overrides[get_db] = override_get_db
    yield test_app
    test_app.dependency_overrides.clear()


@pytest.fixture
async def client(app: object) -> AsyncGenerator[AsyncClient, None]:
    """Provide asynchronous HTTP test client.

    Args:
        app: Test application.

    Yields:
        AsyncClient: HTTPX test client.
    """
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create standard test user."""
    user = User(
        username="alice",
        email="alice@example.com",
        hashed_password=hash_password("Password123!"),
        role="user",
        is_active=True,
        is_online=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_user_2(db_session: AsyncSession) -> User:
    """Create second standard test user."""
    user = User(
        username="bob",
        email="bob@example.com",
        hashed_password=hash_password("Password123!"),
        role="user",
        is_active=True,
        is_online=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_moderator(db_session: AsyncSession) -> User:
    """Create test moderator user."""
    user = User(
        username="mod_user",
        email="mod@example.com",
        hashed_password=hash_password("Password123!"),
        role="moderator",
        is_active=True,
        is_online=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_admin(db_session: AsyncSession) -> User:
    """Create test admin user."""
    user = User(
        username="admin_user",
        email="admin@example.com",
        hashed_password=hash_password("Password123!"),
        role="admin",
        is_active=True,
        is_online=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def user_token(test_user: User) -> str:
    """Generate access token for test_user."""
    return create_access_token(
        user_id=test_user.id,
        username=test_user.username,
        role=test_user.role,
    )


@pytest.fixture
def auth_headers(user_token: str) -> dict[str, str]:
    """Generate Authorization headers for test_user."""
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def user_2_token(test_user_2: User) -> str:
    """Generate access token for test_user_2."""
    return create_access_token(
        user_id=test_user_2.id,
        username=test_user_2.username,
        role=test_user_2.role,
    )


@pytest.fixture
def user_2_headers(user_2_token: str) -> dict[str, str]:
    """Generate Authorization headers for test_user_2."""
    return {"Authorization": f"Bearer {user_2_token}"}


@pytest.fixture
def admin_token(test_admin: User) -> str:
    """Generate access token for test_admin."""
    return create_access_token(
        user_id=test_admin.id,
        username=test_admin.username,
        role=test_admin.role,
    )


@pytest.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    """Generate Authorization headers for test_admin."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def moderator_token(test_moderator: User) -> str:
    """Generate access token for test_moderator."""
    return create_access_token(
        user_id=test_moderator.id,
        username=test_moderator.username,
        role=test_moderator.role,
    )


@pytest.fixture
def moderator_headers(moderator_token: str) -> dict[str, str]:
    """Generate Authorization headers for test_moderator."""
    return {"Authorization": f"Bearer {moderator_token}"}


@pytest.fixture
async def direct_chat(
    db_session: AsyncSession,
    test_user: User,
    test_user_2: User,
) -> Chat:
    """Create direct chat between test_user and test_user_2."""
    chat = Chat(
        type=ChatType.DIRECT.value,
        name=f"{test_user.username} & {test_user_2.username}",
        created_by_id=test_user.id,
    )
    db_session.add(chat)
    await db_session.flush()

    p1 = ChatParticipant(
        chat_id=chat.id,
        user_id=test_user.id,
        role=ParticipantRole.OWNER.value,
    )
    p2 = ChatParticipant(
        chat_id=chat.id,
        user_id=test_user_2.id,
        role=ParticipantRole.MEMBER.value,
    )
    db_session.add_all([p1, p2])
    await db_session.commit()
    await db_session.refresh(chat)
    return chat


@pytest.fixture
async def group_chat(
    db_session: AsyncSession,
    test_user: User,
    test_user_2: User,
    test_moderator: User,
) -> Chat:
    """Create group chat with owner, admin, and member."""
    chat = Chat(
        type=ChatType.GROUP.value,
        name="General Discussion",
        description="A group chat for general topics",
        created_by_id=test_user.id,
    )
    db_session.add(chat)
    await db_session.flush()

    p1 = ChatParticipant(
        chat_id=chat.id,
        user_id=test_user.id,
        role=ParticipantRole.OWNER.value,
    )
    p2 = ChatParticipant(
        chat_id=chat.id,
        user_id=test_moderator.id,
        role=ParticipantRole.ADMIN.value,
    )
    p3 = ChatParticipant(
        chat_id=chat.id,
        user_id=test_user_2.id,
        role=ParticipantRole.MEMBER.value,
    )
    db_session.add_all([p1, p2, p3])
    await db_session.commit()
    await db_session.refresh(chat)
    return chat

import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.user import User

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# ── Database ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def engine():
    eng = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable SQLite foreign key enforcement so ondelete="CASCADE" is respected
    @event.listens_for(eng.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


# ── Users ─────────────────────────────────────────────────────────────────────

@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(id=uuid.uuid4(), email="test@example.com", name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def second_user(db_session: AsyncSession) -> User:
    user = User(id=uuid.uuid4(), email="other@example.com", name="Other User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ── HTTP clients ──────────────────────────────────────────────────────────────

_COMMON_PATCHES = [
    "app.main._init_storage",
    "app.main._pg_listen_loop",
    "app.main.init_checkpointer",
    "app.services.notification_service._pg_notify",
]


def _make_client(app, db_session: AsyncSession, user: User | None):
    """Return a context-managed AsyncClient with DB and optional auth overrides."""
    from app.main import app as _app

    async def _override_db():
        yield db_session

    async def _override_user():
        return user

    _app.dependency_overrides[get_db] = _override_db
    if user is not None:
        _app.dependency_overrides[get_current_user] = _override_user

    patches = [patch(p, new_callable=AsyncMock) for p in _COMMON_PATCHES]
    return patches, AsyncClient(transport=ASGITransport(app=_app), base_url="http://test")


@pytest.fixture
async def client(db_session: AsyncSession, test_user: User) -> AsyncGenerator[AsyncClient, None]:
    from app.main import app

    async def _override_db():
        yield db_session

    async def _override_user():
        return test_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    try:
        with (
            patch("app.main._init_storage", new_callable=AsyncMock),
            patch("app.main._pg_listen_loop", new_callable=AsyncMock),
            patch("app.main.init_checkpointer", new_callable=AsyncMock),
            patch("app.services.notification_service._pg_notify", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                yield ac
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def second_client(
    db_session: AsyncSession, second_user: User
) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated client acting as `second_user`."""
    from app.main import app

    async def _override_db():
        yield db_session

    async def _override_user():
        return second_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    try:
        with (
            patch("app.main._init_storage", new_callable=AsyncMock),
            patch("app.main._pg_listen_loop", new_callable=AsyncMock),
            patch("app.main.init_checkpointer", new_callable=AsyncMock),
            patch("app.services.notification_service._pg_notify", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                yield ac
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def unauth_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Client with no auth override — protected routes return 401."""
    from app.main import app

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    try:
        with (
            patch("app.main._init_storage", new_callable=AsyncMock),
            patch("app.main._pg_listen_loop", new_callable=AsyncMock),
            patch("app.main.init_checkpointer", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                yield ac
    finally:
        app.dependency_overrides.clear()


# ── Storage mock ──────────────────────────────────────────────────────────────

@pytest.fixture
def mock_storage():
    """
    Patches the storage service so tests never touch MinIO/S3.
    upload_file returns a fresh unique key on each call to avoid UNIQUE
    constraint violations when a single test uploads multiple files.
    """
    fake_url = "https://storage.example.com/presigned/file.bin?token=fake"

    async def _unique_key(*args, **kwargs):
        return f"tickets/test/{uuid.uuid4()}/file.bin"

    with (
        patch(
            "app.services.storage_service.upload_file",
            side_effect=_unique_key,
        ),
        patch(
            "app.services.storage_service.get_presigned_url",
            new_callable=AsyncMock,
            return_value=fake_url,
        ),
        patch(
            "app.services.storage_service.delete_file",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        yield {"url": fake_url}

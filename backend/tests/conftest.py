import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.user import User

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def engine():
    eng = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


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
            patch("app.services.notification_service._pg_notify", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                yield ac
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def unauth_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Client with no auth override — routes protected by get_current_user return 401."""
    from app.main import app

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    try:
        with (
            patch("app.main._init_storage", new_callable=AsyncMock),
            patch("app.main._pg_listen_loop", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                yield ac
    finally:
        app.dependency_overrides.clear()

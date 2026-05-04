from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Alias for services that expect a factory naming pattern (Senior Pattern)
async_session_factory = AsyncSessionLocal



async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

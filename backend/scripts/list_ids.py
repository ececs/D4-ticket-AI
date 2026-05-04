
import asyncio
from sqlalchemy import select
from app.core.config import settings
from app.models.ticket import Ticket
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

async def list_ids():
    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url)
    Session = async_sessionmaker(engine)
    async with Session() as session:
        res = await session.execute(select(Ticket.id, Ticket.title))
        for r in res.all():
            print(f"{r.id}: {r.title}")

if __name__ == "__main__":
    asyncio.run(list_ids())

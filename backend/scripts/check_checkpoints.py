
import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def list_tables():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public';"))
        print("TABLES:")
        for r in res.all():
            print(f"- {r.tablename}")

if __name__ == "__main__":
    asyncio.run(list_tables())

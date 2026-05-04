
import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT atttypmod FROM pg_attribute WHERE attrelid = 'tickets'::regclass AND attname = 'embedding';"))
        print(f"ATTTYPMOD: {res.scalar()}")

if __name__ == "__main__":
    asyncio.run(check())

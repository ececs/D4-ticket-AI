import asyncio
import os
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add current dir to path to import app
sys.path.append(os.getcwd())

async def patch_db():
    # Get DATABASE_URL from env or fallback to a default
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ticketai")
    
    print(f"Patching database at: {database_url}")
    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        try:
            # 1. Add client_url and client_summary to tickets
            await db.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS client_url VARCHAR(512)"))
            await db.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS client_summary TEXT"))
            print("Added client_url and client_summary to tickets table")
            
            # 2. Add chunk_metadata to knowledge_chunks table
            await db.execute(text("ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS chunk_metadata JSON"))
            print("Added chunk_metadata to knowledge_chunks table")
            
            await db.commit()
            print("Database patched successfully!")
        except Exception as e:
            print(f"Error patching database: {e}")
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(patch_db())

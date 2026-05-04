
import asyncio
from sqlalchemy import text
from app.core.config import settings

db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine(db_url)

async def fix():
    async with engine.begin() as conn:
        print("Fixing Production Database Dimensions (setting to 768)...")
        
        # 1. Drop existing indexes that depend on the embedding column
        print("Dropping indexes...")
        await conn.execute(text("DROP INDEX IF EXISTS tickets_embedding_hnsw;"))
        await conn.execute(text("DROP INDEX IF EXISTS knowledge_chunks_embedding_hnsw;"))
        
        # 2. Drop and Recreate columns as vector(768)
        print("Dropping and Recreating columns as vector(768)...")
        await conn.execute(text("ALTER TABLE tickets DROP COLUMN IF EXISTS embedding;"))
        await conn.execute(text("ALTER TABLE tickets ADD COLUMN embedding vector(768);"))
        
        await conn.execute(text("ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS embedding;"))
        await conn.execute(text("ALTER TABLE knowledge_chunks ADD COLUMN embedding vector(768);"))
        
        # 3. Recreate HNSW indexes
        print("Recreating HNSW indexes...")
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS tickets_embedding_hnsw 
            ON tickets USING hnsw (embedding vector_cosine_ops) 
            WITH (m = 16, ef_construction = 64);
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw 
            ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) 
            WITH (m = 16, ef_construction = 64);
        """))
        
        print("DONE: Production DB now uses 768 dimensions.")

if __name__ == "__main__":
    asyncio.run(fix())

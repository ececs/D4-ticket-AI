
"""
Migration script: Update all embeddings to 768 dimensions using gemini-embedding-2.
Usage: python -m scripts.migrate_embeddings_768
"""
import asyncio
import logging
from sqlalchemy import select
from app.core.config import settings

import os
from app.core.config import settings

# Prioritize DATABASE_PUBLIC_URL if running locally via Railway CLI
db_url = os.getenv("DATABASE_PUBLIC_URL") or settings.DATABASE_URL

# SQLAlchemy create_async_engine requires the +asyncpg prefix.
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
engine = create_async_engine(db_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

logging.basicConfig(level=logging.INFO)
from app.models.ticket import Ticket
from app.models.knowledge_chunk import KnowledgeChunk
from app.services.embedding_service import generate_ticket_embedding, generate_embedding

logger = logging.getLogger(__name__)

async def migrate_tickets(db):
    logger.info("Migrating Ticket embeddings...")
    result = await db.execute(select(Ticket))
    tickets = result.scalars().all()
    
    for ticket in tickets:
        logger.info(f"Processing Ticket #{ticket.id}: {ticket.title}")
        new_emb = await generate_ticket_embedding(ticket.title, ticket.description)
        if new_emb:
            ticket.embedding = new_emb
            logger.info(f"  ✓ Embedding updated (dim: {len(new_emb)})")
        else:
            logger.warning(f"  ✗ Generation failed for Ticket #{ticket.id}")
    
    await db.commit()

async def migrate_knowledge(db):
    logger.info("Migrating Knowledge Chunk embeddings...")
    result = await db.execute(select(KnowledgeChunk))
    chunks = result.scalars().all()
    
    for chunk in chunks:
        logger.info(f"Processing Chunk #{chunk.id}")
        new_emb = await generate_embedding(chunk.content, task_type="RETRIEVAL_DOCUMENT")
        if new_emb:
            chunk.embedding = new_emb
            logger.info(f"  ✓ Embedding updated (dim: {len(new_emb)})")
        else:
            logger.warning(f"  ✗ Generation failed for Chunk #{chunk.id}")
    
    await db.commit()

async def main():
    async with AsyncSessionLocal() as db:
        try:
            await migrate_tickets(db)
            await migrate_knowledge(db)
            logger.info("MIGRATION COMPLETED SUCCESSFULLY.")
        except Exception as e:
            logger.error(f"ERROR DURING MIGRATION: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(main())

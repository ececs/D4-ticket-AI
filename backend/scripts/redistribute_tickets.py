
import asyncio
import logging
import random
from sqlalchemy import select
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.user import User
from app.models.ticket import Ticket

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
engine = create_async_engine(db_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def redistribute():
    async with AsyncSessionLocal() as db:
        try:
            logger.info("Obteniendo usuarios y tickets...")
            
            # 1. Get all users
            users_res = await db.execute(select(User))
            users = users_res.scalars().all()
            if not users:
                logger.error("No hay usuarios en la DB.")
                return

            # 2. Get all tickets
            tickets_res = await db.execute(select(Ticket))
            tickets = tickets_res.scalars().all()
            logger.info(f"Redistribuyendo {len(tickets)} tickets entre {len(users)} usuarios...")

            # 3. Random assignment
            for ticket in tickets:
                new_assignee = random.choice(users)
                ticket.assignee_id = new_assignee.id
            
            await db.commit()
            logger.info(f"✅ ÉXITO: {len(tickets)} tickets redistribuidos correctamente.")
            
        except Exception as e:
            logger.error(f"Error en redistribución: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(redistribute())


import asyncio
import logging
from sqlalchemy import select
from app.core.config import settings
from app.models.ticket import Ticket, TicketStatus
from app.models.comment import Comment
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup logging for production visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def apply_updates() -> None:
    """
    Finds specific tickets by title and transitions them to 'in_progress' status.
    
    This function performs the following steps:
    1. Connects to the production database using an asynchronous engine.
    2. Searches for tickets with specific titles provided in target_titles.
    3. Updates the status of found tickets to TicketStatus.in_progress.
    4. Adds a professional tracking comment to each updated ticket.
    5. Commits the changes atomically to ensure data consistency.

    Returns:
        None
    
    Raises:
        Exception: If the database transaction fails during commit.
    """
    # Ensure we use the async-compatible driver for SQLAlchemy
    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with Session() as session:
        # Titles requested by the user for status transition
        target_titles = [
            "Actualizar dependencias de seguridad (CVE-2026)",
            "Integrar Stripe para pagos recurrentes"
        ]
        
        logger.info("Starting ticket updates in production environment...")
        
        for title in target_titles:
            # Query the ticket by title (robust identification strategy)
            result = await session.execute(select(Ticket).where(Ticket.title == title))
            ticket = result.scalar_one_or_none()
            
            if ticket:
                logger.info(f"Ticket match found: {title} (UUID: {ticket.id})")
                
                # 1. Update workflow status to 'in_progress'
                ticket.status = TicketStatus.in_progress
                
                # 2. Append a professional activity comment
                new_comment = Comment(
                    ticket_id=ticket.id,
                    author_id=ticket.author_id,
                    content="Estamos trabajando en ello. / Working on this task."
                )
                session.add(new_comment)
                logger.info(f"Transitioned status and appended comment for: {title}")
            else:
                logger.warning(f"Target ticket NOT FOUND in database: {title}")
        
        # Atomically commit all changes to the persistent store
        try:
            await session.commit()
            logger.info("TRANSACTION SUCCESS: All changes persisted to production.")
        except Exception as e:
            logger.error(f"TRANSACTION FAILED: Error during commit: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(apply_updates())

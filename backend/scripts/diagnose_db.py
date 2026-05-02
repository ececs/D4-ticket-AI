
import asyncio
import logging
from sqlalchemy import select
from app.core.config import settings
from app.models.ticket import Ticket, TicketStatus
from app.models.comment import Comment
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

logging.basicConfig(level=logging.INFO)

db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(db_url)
Session = async_sessionmaker(engine)

async def diagnose():
    async with Session() as session:
        print("\n--- 1. Checking Tickets ---")
        res = await session.execute(select(Ticket).limit(5))
        tickets = res.scalars().all()
        for t in tickets:
            print(f"ID: {t.id} | Title: {t.title} | Status: {t.status}")
        
        if not tickets:
            print("No tickets found!")
            return

        # Try to update a ticket status
        ticket = tickets[0]
        print(f"\n--- 2. Attempting Update on Ticket {ticket.id} ---")
        try:
            ticket.status = TicketStatus.in_progress
            await session.commit()
            print("Update Successful!")
        except Exception as e:
            print(f"Update Failed: {e}")
            await session.rollback()

        # Try to add a comment
        print(f"\n--- 3. Attempting to add a Comment to Ticket {ticket.id} ---")
        try:
            comment = Comment(
                content="Diagnostic comment",
                ticket_id=ticket.id,
                author_id=ticket.author_id
            )
            session.add(comment)
            await session.commit()
            print("Comment added successfully!")
        except Exception as e:
            print(f"Comment failed: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(diagnose())

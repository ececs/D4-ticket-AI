import asyncio
import uuid
from sqlalchemy import select, text
from app.db.session import async_session_factory
from app.models.ticket import Ticket
from app.models.knowledge_chunk import KnowledgeChunk

async def check_db():
    print("Checking database schema...")
    async with async_session_factory() as session:
        try:
            # Check tickets table
            result = await session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'tickets'"))
            columns = [row[0] for row in result.fetchall()]
            print(f"Tickets columns: {columns}")
            
            # Check knowledge_chunks table
            result = await session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'knowledge_chunks'"))
            columns = [row[0] for row in result.fetchall()]
            print(f"Knowledge chunks columns: {columns}")
            
            # Try to query a ticket
            result = await session.execute(select(Ticket).limit(1))
            ticket = result.scalar_one_or_none()
            if ticket:
                print(f"Sample ticket found: {ticket.id}")
                print(f"Client URL: {getattr(ticket, 'client_url', 'MISSING')}")
                print(f"Client Summary: {getattr(ticket, 'client_summary', 'MISSING')}")
            else:
                print("No tickets found.")
                
        except Exception as e:
            print(f"Error checking DB: {e}")

if __name__ == "__main__":
    asyncio.run(check_db())

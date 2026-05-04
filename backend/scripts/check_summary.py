import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.ticket import Ticket

async def check_last_ticket():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Ticket).order_by(Ticket.updated_at.desc()).limit(1))
        ticket = result.scalar_one_or_none()
        
        if not ticket:
            print("No hay tickets.")
            return
            
        print(f"\n--- ÚLTIMO TICKET MODIFICADO ---")
        print(f"ID: {ticket.id}")
        print(f"Título: {ticket.title}")
        print(f"URL: {ticket.client_url}")
        print(f"Resumen (client_summary): {'✅ POBLADO' if ticket.client_summary else '❌ VACÍO'}")
        if ticket.client_summary:
            print(f"Contenido: {ticket.client_summary[:200]}...")

if __name__ == "__main__":
    asyncio.run(check_last_ticket())

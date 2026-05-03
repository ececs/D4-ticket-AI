import asyncio
import logging
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.ticket import Ticket
from app.services import scraping_service

async def migrate_summaries():
    print("🚀 Iniciando migración de resúmenes...")
    async with AsyncSessionLocal() as db:
        # Buscamos tickets con URL pero sin resumen
        result = await db.execute(
            select(Ticket).where(Ticket.client_url.isnot(None), Ticket.client_summary.is_(None))
        )
        tickets = result.scalars().all()
        
        print(f"📦 Encontrados {len(tickets)} tickets para procesar.")
        
        for t in tickets:
            print(f"🔍 Procesando: {t.title} ({t.client_url})")
            # Ejecutamos el scraping (esta vez lo hacemos esperar para que sea síncrono en el script)
            try:
                await scraping_service.scrape_and_index_url(t.id, t.client_url)
                print(f"✅ Hecho para {t.id}")
            except Exception as e:
                print(f"❌ Error en {t.id}: {e}")
                
    print("\n✨ Migración completada. ¡Refresca el frontend!")

if __name__ == "__main__":
    asyncio.run(migrate_summaries())

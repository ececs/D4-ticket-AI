"""
Mass Seeding Script (100+ Tickets).
Replicates high-quality templates with variations to test UI scalability.
"""

import asyncio
import logging
import random
import uuid
from sqlalchemy import delete, select
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
engine = create_async_engine(db_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.comment import Comment
from app.models.user import User
from app.services.embedding_service import generate_ticket_embedding

TEMPLATES = [
    ("Error en pasarela de pagos", "Los clientes reportan errores 500 al intentar pagar con tarjeta de crédito en la zona de checkout."),
    ("Optimización de carga de imágenes", "Las imágenes de los productos tardan demasiado en cargar. Implementar Next/Image con lazy loading."),
    ("Bug en filtros de búsqueda", "El filtro por rango de precios no devuelve resultados correctos cuando se usa el slider."),
    ("Actualizar términos de servicio", "Es necesario actualizar el documento legal de términos y condiciones para cumplir con la nueva normativa."),
    ("Mejorar SEO en landings", "Añadir meta tags dinámicos y mejorar el sitemap para indexación en Google."),
    ("Fuga de memoria en el Agente", "El proceso del agente de IA consume memoria de forma lineal. Posible leak en el checkpointer."),
    ("Añadir soporte para modo oscuro", "Configurar variables CSS para que el dashboard sea legible en modo noche."),
    ("Exportar facturas a PDF", "Desarrollar el worker para generar PDFs de facturas y enviarlos por email.")
]

async def mass_seed(count: int = 100):
    async with AsyncSessionLocal() as db:
        try:
            logger.info(f"Iniciando Mass Seeding de {count} tickets...")
            
            # Get user
            res = await db.execute(select(User).limit(1))
            user = res.scalar_one_or_none()
            if not user:
                logger.error("No se encontró usuario. Logueate primero en la app.")
                return

            # Clean previous mass seeds (optional, but good for idempotency)
            # await db.execute(delete(Ticket)) 

            for i in range(count):
                title_base, desc_base = random.choice(TEMPLATES)
                title = f"{title_base} #{i+1}"
                desc = f"{desc_base} Generado automáticamente para pruebas de carga y escalabilidad."
                
                status = random.choice(list(TicketStatus))
                priority = random.choice(list(TicketPriority))
                
                logger.info(f"[{i+1}/{count}] Generando: {title}")
                
                # We generate embeddings for each to ensure RAG works
                embedding = await generate_ticket_embedding(title, desc)
                
                ticket = Ticket(
                    title=title,
                    description=desc,
                    status=status,
                    priority=priority,
                    author_id=user.id,
                    assignee_id=user.id,
                    embedding=embedding
                )
                db.add(ticket)
                
                if (i + 1) % 10 == 0:
                    await db.flush()
                    logger.info("Checkpoint: 10 tickets guardados.")

            await db.commit()
            logger.info(f"✅ ÉXITO: {count} tickets generados correctamente.")
            
        except Exception as e:
            logger.error(f"Error en mass seed: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(mass_seed(100))

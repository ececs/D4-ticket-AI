"""
Database Seeding Module (768-dimension Standard).

This script populates the D4-Ticket AI production database with a diverse set 
of high-quality, realistic test data. It is designed to be used after schema 
migrations or database resets.

Key Actions:
1. Clears existing data from 'tickets', 'comments', and 'knowledge_chunks'.
2. Generates 768-dimension embeddings using the gemini-embedding-2 model.
3. Creates a consistent set of 20 tickets across various workflow states.
4. Appends realistic threaded comments to simulate active project participation.

Requirements:
- GOOGLE_API_KEY: Must be valid for embedding generation.
- DATABASE_URL: Must point to the target production or staging database.
"""

import asyncio
import logging
import os
from sqlalchemy import delete, select
from app.core.config import settings

# Configure logging for production-grade visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure asyncpg driver is used for database connectivity
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
engine = create_async_engine(db_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.comment import Comment
from app.models.user import User
from app.services.embedding_service import generate_ticket_embedding

TICKETS_DATA = [
    # --- OPEN ---
    {
        "title": "Rediseño de la página de inicio del portal de clientes",
        "description": "El portal actual tiene una tasa de rebote del 68%. Necesitamos modernizar el diseño, mejorar la jerarquía visual y añadir CTAs más claros. Incluir versión mobile-first.",
        "status": TicketStatus.open,
        "priority": TicketPriority.high,
    },
    {
        "title": "Integrar Stripe para pagos recurrentes",
        "description": "Implementar Stripe Billing para suscripciones mensuales y anuales. El flujo debe soportar upgrades, downgrades y cancelaciones.",
        "status": TicketStatus.open,
        "priority": TicketPriority.critical,
    },
    {
        "title": "Configurar alertas de error en Sentry",
        "description": "Integrar Sentry en el backend y frontend. Configurar alertas por email cuando el error rate supere el 1%.",
        "status": TicketStatus.open,
        "priority": TicketPriority.medium,
    },
    {
        "title": "Investigar caída de performance en búsquedas",
        "description": "La búsqueda semántica tarda más de 3s en algunos casos. Revisar los parámetros del índice HNSW.",
        "status": TicketStatus.open,
        "priority": TicketPriority.high,
    },
    {
        "title": "Actualizar dependencias de seguridad (CVE-2026)",
        "description": "Se han detectado vulnerabilidades en bibliotecas de terceros. Requiere actualización inmediata.",
        "status": TicketStatus.open,
        "priority": TicketPriority.critical,
    },
    # --- IN PROGRESS ---
    {
        "title": "Migración de base de datos a PostgreSQL 16",
        "description": "Migrar la instancia actual de PostgreSQL 14 a PostgreSQL 16 para mejoras de rendimiento.",
        "status": TicketStatus.in_progress,
        "priority": TicketPriority.high,
    },
    {
        "title": "Añadir tests E2E con Playwright",
        "description": "Cubrir los flujos críticos: Login, Crear Ticket, Kanban, Notificaciones.",
        "status": TicketStatus.in_progress,
        "priority": TicketPriority.medium,
    },
    {
        "title": "Optimizar queries N+1 en el endpoint de tickets",
        "description": "Usar selectinload de SQLAlchemy para cargar relaciones en una sola query.",
        "status": TicketStatus.in_progress,
        "priority": TicketPriority.high,
    },
    {
        "title": "Implementar Auth MFA (Multi-Factor)",
        "description": "Añadir soporte para TOTP (Google Authenticator) como capa extra de seguridad.",
        "status": TicketStatus.in_progress,
        "priority": TicketPriority.medium,
    },
    # --- IN REVIEW ---
    {
        "title": "Implementar rate limiting en endpoints públicos",
        "description": "Añadir slowapi para limitar ataques de fuerza bruta y abuso de API.",
        "status": TicketStatus.in_review,
        "priority": TicketPriority.medium,
    },
    {
        "title": "Dark mode en el dashboard",
        "description": "Implementar tema oscuro usando Tailwind CSS y next-themes.",
        "status": TicketStatus.in_review,
        "priority": TicketPriority.low,
    },
    {
        "title": "Refactor de componentes de UI a React Server Components",
        "description": "Mejorar el LCP moviendo la lógica de datos al servidor.",
        "status": TicketStatus.in_review,
        "priority": TicketPriority.medium,
    },
    # --- CLOSED ---
    {
        "title": "Setup inicial del proyecto — Docker Compose + CI/CD",
        "description": "Configurar el entorno de desarrollo y pipelines de GitHub Actions.",
        "status": TicketStatus.closed,
        "priority": TicketPriority.high,
    },
    {
        "title": "Autenticación Google OAuth2 — flujo stateless",
        "description": "Implementar login con Google sin estado de servidor usando JWT.",
        "status": TicketStatus.closed,
        "priority": TicketPriority.critical,
    },
    {
        "title": "Notificaciones en tiempo real con WebSocket + PG NOTIFY",
        "description": "Sistema de notificaciones push sin polling.",
        "status": TicketStatus.closed,
        "priority": TicketPriority.high,
    },
    {
        "title": "Corregir bug: cookie httpOnly bloquea logout",
        "description": "Añadir ruta /api/auth/clear para borrar cookies server-side.",
        "status": TicketStatus.closed,
        "priority": TicketPriority.critical,
    },
    {
        "title": "Implementar Audit Log",
        "description": "Registrar cada cambio de estado en los tickets para trazabilidad.",
        "status": TicketStatus.closed,
        "priority": TicketPriority.medium,
    },
    {
        "title": "Exportar reportes a CSV/PDF",
        "description": "Funcionalidad para que los managers descarguen estadísticas mensuales.",
        "status": TicketStatus.closed,
        "priority": TicketPriority.low,
    },
    {
        "title": "Mejorar accesibilidad (WCAG 2.1)",
        "description": "Asegurar que el portal sea navegable mediante teclado y lectores de pantalla.",
        "status": TicketStatus.closed,
        "priority": TicketPriority.medium,
    },
    {
        "title": "Limpieza de logs antiguos",
        "description": "Script para rotar logs y liberar espacio en disco.",
        "status": TicketStatus.closed,
        "priority": TicketPriority.low,
    }
]

COMMENTS_DATA = {
    "Rediseño de la página": [
        "I've reviewed the analytics. Mobile traffic bounce rate is 70%. Priority: mobile-first.",
        "Let's use Framer Motion for hero animations. Excellent DX.",
        "@Team: share wireframes of previous designs to avoid repeating mistakes."
    ],
    "Integrar Stripe": [
        "Stripe test environment created. Keys in 1Password vault.",
        "Beware of webhooks: handle events idempotently.",
        "Confirming SEPA Direct Debit support?"
    ],
    "Migración de base de datos": [
        "Snapshot complete. Size: 2.3 GB. Dump took 8 mins.",
        "PG16 does not support the old pg_trgm version. Need to update migrations.",
        "First migration test in staging successful. No data corruption."
    ],
    "Optimizar queries": [
        "N+1 confirmed. selectinload is the correct choice for async.",
        "After fix: p95 latency dropped from 2.1s to 187ms. Amazing."
    ],
    "Setup inicial": [
        "Docker Compose working. up --build takes ~90s.",
        "CI/CD configured. Tests run in ~45s."
    ]
}

async def seed() -> None:
    """
    Main orchestration function for database seeding.
    
    1. Purges legacy data from primary tables.
    2. Identifies a valid User for data assignment.
    3. Iteratively generates embeddings and creates Ticket records.
    4. Populates related Comment threads.
    
    Raises:
        Exception: Captures and logs any database or API failures during the process.
    """
    async with AsyncSessionLocal() as db:
        try:
            # 1. Clean existing data to ensure idempotent runs
            logger.info("Purging legacy data from tickets and knowledge tables...")
            await db.execute(delete(Comment))
            await db.execute(delete(Ticket))
            await db.execute(delete(KnowledgeChunk))
            
            # 2. Identify the primary administrative user
            result = await db.execute(select(User).limit(1))
            user = result.scalar_one_or_none()
            if not user:
                logger.error("Seeding aborted: No User found. Log in via OAuth first.")
                return

            # 3. Provision tickets with semantic vectors
            logger.info(f"Provisioning {len(TICKETS_DATA)} tickets for User: {user.email}")
            created_tickets = []
            for data in TICKETS_DATA:
                logger.info(f"Embedding generation: {data['title']}")
                embedding = await generate_ticket_embedding(data['title'], data['description'])
                
                ticket = Ticket(
                    title=data['title'],
                    description=data['description'],
                    status=data['status'],
                    priority=data['priority'],
                    author_id=user.id,
                    assignee_id=user.id,
                    embedding=embedding
                )
                db.add(ticket)
                created_tickets.append((ticket, data['title']))
            
            # Flush to synchronize session state and retrieve generated UUIDs
            await db.flush()

            # 4. Provision threaded discussions
            logger.info("Appending simulated project comments...")
            for ticket, title in created_tickets:
                for key, comments in COMMENTS_DATA.items():
                    if key in title:
                        for content in comments:
                            comment = Comment(
                                content=content,
                                ticket_id=ticket.id,
                                author_id=user.id
                            )
                            db.add(comment)
                        break

            # Atomically commit the entire state transition
            await db.commit()
            logger.info(f"SUCCESS: Environment seeded with {len(TICKETS_DATA)} tickets and comments.")
            
        except Exception as e:
            logger.error(f"Seeding failed: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(seed())

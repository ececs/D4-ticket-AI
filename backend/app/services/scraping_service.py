import asyncio
import logging
import trafilatura
import uuid
from typing import Optional

from app.db.session import async_session_factory
from app.models.knowledge_chunk import KnowledgeChunk

logger = logging.getLogger(__name__)

async def scrape_and_index_url(ticket_id: uuid.UUID, url: str) -> None:
    """
    Scrapes a URL, extracts clean text, and indexes it into the vector DB.
    
    This task runs in the background. It uses asyncio.to_thread to prevent 
    the synchronous trafilatura calls from blocking the FastAPI event loop.
    
    Args:
        ticket_id: UUID of the ticket this context belongs to.
        url: The client website URL to analyze.
    """
    logger.info(f"Scraping Service: Starting analysis for ticket {ticket_id} -> {url}")
    
    try:
        # 1. Download and extract text (Offloaded to a thread to avoid blocking)
        # trafilatura is synchronous, so we use to_thread
        downloaded = await asyncio.to_thread(trafilatura.fetch_url, url)
        if not downloaded:
            logger.error(f"Scraping Service: Failed to fetch URL {url}")
            return
            
        text = await asyncio.to_thread(trafilatura.extract, downloaded)
        if not text:
            logger.error(f"Scraping Service: No meaningful text found in {url}")
            return
            
        # 2. Content Preparation
        # We take up to 4000 chars for a rich but manageable context
        content = text[:4000] 
        
        # 3. Generate embedding
        # This is already an async service call
        from app.services.embedding_service import generate_embedding
        embedding = await generate_embedding(content, task_type="RETRIEVAL_DOCUMENT")
        
        if embedding is None:
            logger.warning(f"Scraping Service: Could not generate embedding for {url}")
            return

        # 4. Persistence
        # We use the factory to create a dedicated session for this background task
        async with async_session_factory() as db:
            # 4.1 Save to Knowledge base (RAG)
            chunk = KnowledgeChunk(
                url=url,
                chunk_index=0,
                content=content,
                embedding=embedding,
                chunk_metadata={
                    "source": url,
                    "ticket_id": str(ticket_id),
                    "type": "client_web_context"
                }
            )
            db.add(chunk)
            
            # 4.2 Fetch ticket users to notify via WebSocket
            from app.models.ticket import Ticket
            from sqlalchemy import select
            ticket_res = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
            ticket = ticket_res.scalar_one_or_none()
            
            await db.commit()
            
            # 5. Notify via WebSocket (Live UI update)
            if ticket:
                from app.core.websocket_manager import manager
                notification = {
                    "type": "web_scrape_completed",
                    "ticket_id": str(ticket_id),
                    "message": "Análisis web finalizado"
                }
                # Notify both author and assignee
                users_to_notify = {str(ticket.author_id)}
                if ticket.assignee_id:
                    users_to_notify.add(str(ticket.assignee_id))
                
                for uid in users_to_notify:
                    await manager.broadcast_to_user(uid, notification)
            
        logger.info(f"Scraping Service: Successfully indexed web context for ticket {ticket_id}")
        
    except Exception as e:
        logger.error(f"Scraping Service: Critical error for ticket {ticket_id}: {str(e)}", exc_info=True)


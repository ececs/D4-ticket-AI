"""
AI Co-pilot Service.

Provides automated diagnosis and solution suggestions for tickets using:
1. Ticket context (title, description).
2. Historical discussion (comments).
3. Semantic search (RAG) over the knowledge base.
4. LLM reasoning with automatic failover.
"""

import logging
from typing import Optional
import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket
from app.models.comment import Comment
from app.ai.agent import get_llm
from app.services.knowledge_service import search as knowledge_search

logger = logging.getLogger(__name__)

async def get_ticket_diagnosis(db: AsyncSession, ticket_id: uuid.UUID) -> str:
    """
    Analyzes a ticket and provides a suggested solution for the technician.
    Uses a highly robust approach to avoid attribute errors and handle missing data.
    """
    logger.info(f"AI Co-pilot: Starting diagnosis for ticket {ticket_id}")
    
    try:
        # 1. Fetch Ticket with Author details
        ticket_result = await db.execute(
            select(Ticket)
            .options(selectinload(Ticket.author))
            .where(Ticket.id == ticket_id)
        )
        ticket = ticket_result.scalar_one_or_none()
        if not ticket:
            logger.warning(f"AI Co-pilot: Ticket {ticket_id} not found in DB")
            return f"Error: El ticket con ID {ticket_id} no existe en el sistema."

        # 2. Fetch last 5 comments for context
        comments_result = await db.execute(
            select(Comment)
            .options(selectinload(Comment.author))
            .where(Comment.ticket_id == ticket_id)
            .order_by(Comment.created_at.desc())
            .limit(5)
        )
        comments = comments_result.scalars().all()
        
        # Safe author name retrieval for comments
        comment_list = []
        for c in reversed(list(comments)):
            author_name = "System"
            try:
                if c.author:
                    # Try to get 'name', fallback to 'email', then 'System'
                    author_name = getattr(c.author, "name", getattr(c.author, "email", "Unknown User"))
            except Exception:
                author_name = "User"
            
            comment_list.append(f"- {author_name}: {c.content}")
        
        comments_text = "\n".join(comment_list)

        # 3. Semantic Search (RAG)
        search_query = f"{ticket.title} {ticket.description or ''}"
        rag_text = "No se encontró información específica en la base de conocimientos."
        try:
            knowledge_context = await knowledge_search(db, query=search_query, k=3)
            if knowledge_context:
                rag_text = "\n\n".join(knowledge_context)
        except Exception as rag_err:
            logger.error(f"AI Co-pilot: RAG search failed: {rag_err}")
            rag_text = "La búsqueda en la base de conocimientos falló temporalmente."

        # 4. Safe metadata extraction
        ticket_author_name = "Unknown"
        if ticket.author:
            ticket_author_name = getattr(ticket.author, "name", getattr(ticket.author, "email", "User"))
        
        priority_val = "medium"
        try:
            priority_val = ticket.priority.value
        except Exception:
            pass

        # 5. Prompt Engineering
        system_prompt = (
            "Eres un 'AI Co-pilot' experto en soporte técnico. Tu misión es ayudar al técnico a resolver "
            "este ticket de la forma más eficiente posible.\n\n"
            "REGLAS:\n"
            "1. Sé conciso y profesional.\n"
            "2. Identifica la causa raíz probable.\n"
            "3. Propón una solución paso a paso.\n"
            "4. Usa el contexto de la base de conocimientos si es relevante.\n"
            "5. Si no hay información en la base de conocimientos, usa tu lógica general de experto en IT."
        )

        user_prompt = (
            f"CONTEXTO DEL TICKET:\n"
            f"Título: {ticket.title}\n"
            f"Descripción: {ticket.description or 'Sin descripción'}\n"
            f"Autor: {ticket_author_name}\n"
            f"Prioridad: {priority_val}\n\n"
            f"HISTORIAL DE COMENTARIOS:\n{comments_text or 'Sin comentarios aún.'}\n\n"
            f"CONOCIMIENTO TÉCNICO ENCONTRADO (RAG):\n{rag_text}\n\n"
            f"Analiza esta información y dame una solución sugerida."
        )

        # 6. Call LLM (with automatic failover)
        llm = get_llm()
        response = await llm.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        
        logger.info(f"AI Co-pilot: Successfully generated diagnosis for {ticket_id}")
        return response.content

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"AI Co-pilot CRITICAL ERROR: {str(e)}\n{error_trace}")
        return f"*(Error interno del Co-pilot: {str(e)}. Por favor, contacta con soporte o intenta de nuevo.)*"

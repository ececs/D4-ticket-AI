"""
AI Co-pilot Service.

Provides automated diagnosis and solution suggestions for tickets using:
1. Ticket context (title, description).
2. Historical discussion (comments).
3. Semantic search (RAG) over the knowledge base.
4. LLM reasoning with automatic failover.
"""

import asyncio
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

async def _prepare_diagnosis_context(db: AsyncSession, ticket_id: uuid.UUID):
    """
    Helper to fetch and format all context needed for diagnosis.
    """
    # 1. Fetch data in parallel
    ticket_task = db.execute(
        select(Ticket).options(selectinload(Ticket.author)).where(Ticket.id == ticket_id)
    )
    comments_task = db.execute(
        select(Comment)
        .options(selectinload(Comment.author))
        .where(Comment.ticket_id == ticket_id)
        .order_by(Comment.created_at.desc())
        .limit(5)
    )
    
    ticket_res, comments_res = await asyncio.gather(ticket_task, comments_task)
    ticket = ticket_res.scalar_one_or_none()
    if not ticket:
        return None, None, None

    comments = comments_res.scalars().all()
    
    # 2. Format comments
    comment_list = [
        f"- {c.author.display_name if c.author else 'System'}: {c.content}" 
        for c in reversed(list(comments))
    ]
    comments_text = "\n".join(comment_list)

    # 3. RAG Search
    search_query = f"{ticket.title} {ticket.description or ''}"
    rag_text = "No se encontró información específica en la base de conocimientos."
    
    try:
        global_task = knowledge_search(db, query=search_query, k=2)
        ticket_web_task = knowledge_search(db, query=search_query, k=3, ticket_id=str(ticket_id))
        global_ctx, web_ctx = await asyncio.gather(global_task, ticket_web_task)
        
        all_context = []
        if web_ctx:
            all_context.append("CONTEXTO WEB DEL CLIENTE:\n" + "\n".join(web_ctx))
        if global_ctx:
            all_context.append("CONOCIMIENTO GLOBAL / HISTÓRICO:\n" + "\n".join(global_ctx))
        if all_context:
            rag_text = "\n\n---\n\n".join(all_context)
    except Exception as rag_err:
        logger.error(f"AI Co-pilot: RAG search failed: {rag_err}")

    # 4. Prompts
    system_prompt = (
        "Eres un 'AI Co-pilot' experto en soporte técnico. Tu misión es ayudar al técnico a resolver "
        "este ticket de la forma más eficiente posible.\n\n"
        "REGLAS:\n"
        "1. Sé conciso y profesional.\n"
        "2. Identifica la causa raíz probable.\n"
        "3. Propón una solución paso a paso.\n"
        "4. Usa el contexto de la base de conocimientos si es relevante."
    )

    user_prompt = (
        f"CONTEXTO DEL TICKET:\n"
        f"Título: {ticket.title}\n"
        f"Descripción: {ticket.description or 'Sin descripción'}\n"
        f"Autor: {ticket.author.display_name if ticket.author else 'Unknown'}\n"
        f"Prioridad: {ticket.priority.value if hasattr(ticket.priority, 'value') else 'medium'}\n\n"
        f"CONTEXTO DEL CLIENTE:\n"
        f"{ticket.client_summary or 'No hay información adicional.'}\n\n"
        f"HISTORIAL DE COMENTARIOS:\n{comments_text or 'Sin comentarios.'}\n\n"
        f"CONOCIMIENTO TÉCNICO (RAG):\n{rag_text}\n\n"
        f"Dame una solución sugerida."
    )

    return system_prompt, user_prompt, ticket


async def get_ticket_diagnosis(db: AsyncSession, ticket_id: uuid.UUID) -> str:
    """
    Non-streaming version of diagnosis.
    """
    try:
        sys_p, user_p, _ = await _prepare_diagnosis_context(db, ticket_id)
        if not sys_p:
            return "Error: Ticket no encontrado."

        llm = get_llm()
        response = await llm.ainvoke([
            {"role": "system", "content": sys_p},
            {"role": "user", "content": user_p}
        ])
        return response.content
    except Exception as e:
        logger.error(f"AI Co-pilot Error: {str(e)}", exc_info=True)
        return f"*(Error interno del Co-pilot: {str(e)})*"


async def stream_ticket_diagnosis(db: AsyncSession, ticket_id: uuid.UUID):
    """
    Async generator that yields diagnosis tokens for real-time streaming.
    """
    try:
        sys_p, user_p, _ = await _prepare_diagnosis_context(db, ticket_id)
        if not sys_p:
            yield "Error: Ticket no encontrado."
            return

        llm = get_llm()
        async for chunk in llm.astream([
            {"role": "system", "content": sys_p},
            {"role": "user", "content": user_p}
        ]):
            if chunk.content:
                yield chunk.content
    except Exception as e:
        logger.error(f"AI Co-pilot Stream Error: {str(e)}", exc_info=True)
        yield f"*(Error interno en el flujo del Co-pilot: {str(e)})*"

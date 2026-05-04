"""
Ticket Service Module.

This service encapsulates the core business logic for ticket management. 
By centralizing these operations, we ensure that both the REST API and the 
AI Agent follow the same rules, validation, and notification triggers.

Architecture (Senior Pattern):
- Decoupling: This service returns Pydantic schemas (`TicketOut`) instead of 
  SQLAlchemy models. This prevents "Lazy Loading" errors and ensures that the 
  calling layer (API or AI) cannot accidentally modify the database state 
  without going through the service.
- Atomicity: All write operations handle their own commits and flushes 
  within the provided transaction context.
"""

import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.user import User
from app.schemas.ticket import TicketOut
import asyncio
import logging
from . import notification_service, embedding_service, scraping_service, cache_service, history_service


async def get_ticket(db: AsyncSession, ticket_id: uuid.UUID) -> Optional[TicketOut]:
    """
    Retrieves a single ticket by its UUID with all relations eagerly loaded.

    Args:
        db: Asynchronous database session.
        ticket_id: The unique identifier of the ticket.

    Returns:
        Optional[TicketOut]: A validated Pydantic model of the ticket, 
            or None if not found.
    """
    result = await db.execute(
        select(Ticket)
        .options(
            selectinload(Ticket.author),    # type: ignore[attr-defined]
            selectinload(Ticket.assignee),  # type: ignore[attr-defined]
        )
        .where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        return None
        
    return TicketOut.model_validate(ticket)
    
    
async def create_ticket(
    db: AsyncSession,
    title: str,
    description: Optional[str],
    priority: TicketPriority,
    author_id: uuid.UUID,
    assignee_id: Optional[uuid.UUID] = None,
    client_url: Optional[str] = None,
    client_summary: Optional[str] = None,
) -> TicketOut:
    """
    Creates a new ticket and notifies the system.
    """
    # 1. Create model
    ticket = Ticket(
        title=title,
        description=description,
        priority=priority,
        author_id=author_id,
        assignee_id=assignee_id,
        client_url=client_url,
        client_summary=client_summary,
    )
    db.add(ticket)
    await db.flush() # Get the ID for notifications
    
    # 2. Fetch author for notification
    author_result = await db.execute(select(User).where(User.id == author_id))
    author = author_result.scalar_one()

    # 3. Finalize
    await db.commit()

    # 4. Handle side effects after commit
    await history_service.record_change(db, ticket.id, author_id, "created", None, None)
    await db.commit()

    from app.schemas.websocket import WSMessageType
    await notification_service.notify_ticket_created(db, ticket=ticket, actor=author)
    await notification_service.broadcast_global_event(
        type=WSMessageType.TICKET_CREATED,
        data={"id": str(ticket.id), "title": ticket.title},
        db=db
    )
    await db.commit()  # persist notification records created by the service
    await cache_service.cache_invalidate_prefix("tickets:")

    # 5. Background tasks
    asyncio.create_task(generate_ticket_embedding_task(ticket.id, title, description))
    if client_url:
        asyncio.create_task(scraping_service.scrape_and_index_url(ticket.id, client_url))
        
    # 5. Return decoupled schema
    return await get_ticket(db, ticket.id) # type: ignore


async def generate_ticket_embedding_task(ticket_id: uuid.UUID, title: str, description: Optional[str]) -> None:
    """
    Background task to generate and persist ticket embedding.
    
    Uses a dedicated session factory to ensure isolation from the request lifecycle.
    """
    embedding = await embedding_service.generate_ticket_embedding(title, description)
    if embedding is None:
        return

    try:
        from app.db.session import async_session_factory
        async with async_session_factory() as session:
            result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
            ticket = result.scalar_one_or_none()
            if ticket:
                ticket.embedding = embedding
                await session.commit()
                logging.getLogger(__name__).info(f"Ticket Service: Persistent embedding for ticket {ticket_id}")
    except Exception as exc:
        logging.getLogger(__name__).error(
            f"Ticket Service: Failed to persist embedding for {ticket_id}: {str(exc)}", 
            exc_info=True
        )


async def update_ticket(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    update_data: dict,
    actor: User,
) -> Optional[TicketOut]:
    """
    Generalized update for any ticket field.
    """
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        return None

    old_status = ticket.status
    old_assignee_id = ticket.assignee_id
    old_priority = ticket.priority
    old_title = ticket.title
    old_description = ticket.description
    old_client_url = ticket.client_url

    # Apply updates
    for key, value in update_data.items():
        if hasattr(ticket, key):
            setattr(ticket, key, value)

    await db.flush()

    # 5. Persist
    await db.commit()

    # 6. Side effects after commit: history, notifications, broadcast
    new_assignee: User | None = None
    if "assignee_id" in update_data and update_data["assignee_id"] != old_assignee_id:
        if update_data["assignee_id"]:
            res = await db.execute(select(User).where(User.id == update_data["assignee_id"]))
            new_assignee = res.scalar_one_or_none()

    # History — one entry per changed field
    if "status" in update_data and update_data["status"] != old_status:
        new_status_val = update_data["status"].value if hasattr(update_data["status"], "value") else str(update_data["status"])
        await history_service.record_change(db, ticket_id, actor.id, "status", old_status.value, new_status_val)

    if "priority" in update_data and update_data["priority"] != old_priority:
        new_priority_val = update_data["priority"].value if hasattr(update_data["priority"], "value") else str(update_data["priority"])
        await history_service.record_change(db, ticket_id, actor.id, "priority", old_priority.value, new_priority_val)

    if "title" in update_data and update_data["title"] != old_title:
        await history_service.record_change(db, ticket_id, actor.id, "title", old_title, update_data["title"])

    if "description" in update_data and update_data["description"] != old_description:
        await history_service.record_change(db, ticket_id, actor.id, "description", None, None)

    if "client_url" in update_data and update_data["client_url"] != old_client_url:
        await history_service.record_change(db, ticket_id, actor.id, "client_url", old_client_url, update_data["client_url"])

    if "assignee_id" in update_data and update_data["assignee_id"] != old_assignee_id:
        old_assignee_name: str | None = None
        if old_assignee_id:
            old_res = await db.execute(select(User).where(User.id == old_assignee_id))
            old_assignee_obj = old_res.scalar_one_or_none()
            old_assignee_name = old_assignee_obj.name if old_assignee_obj else None
        new_assignee_name = new_assignee.name if new_assignee else None
        await history_service.record_change(db, ticket_id, actor.id, "assignee", old_assignee_name, new_assignee_name)

    # Notifications
    if "status" in update_data and update_data["status"] != old_status:
        await notification_service.notify_status_changed(
            db, ticket=ticket, actor=actor, new_status=update_data["status"]
        )

    if "priority" in update_data and update_data["priority"] != old_priority:
        await notification_service.notify_priority_changed(
            db, ticket=ticket, actor=actor, new_priority=update_data["priority"]
        )

    if "assignee_id" in update_data and update_data["assignee_id"] != old_assignee_id:
        if new_assignee:
            await notification_service.notify_ticket_assigned(
                db, ticket=ticket, assignee=new_assignee, actor=actor
            )

    # Generic broadcast to trigger UI refreshes
    await notification_service.notify_ticket_updated(db, ticket=ticket, actor=actor)
    await db.commit()  # persist history + notification records
    await cache_service.cache_invalidate_prefix("tickets:")

    # --- Side effects (Background Tasks) ---
    if "title" in update_data or "description" in update_data:
        new_title = update_data.get("title", ticket.title)
        new_desc = update_data.get("description", ticket.description)
        asyncio.create_task(generate_ticket_embedding_task(ticket_id, new_title, new_desc))

    if "client_url" in update_data and update_data["client_url"]:
        asyncio.create_task(scraping_service.scrape_and_index_url(ticket_id, update_data["client_url"]))

    return await get_ticket(db, ticket_id)

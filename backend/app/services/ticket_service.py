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
from . import notification_service, embedding_service, scraping_service


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

    # 4. Handle side effects (Notifications) after commit
    await notification_service.notify_ticket_created(db, ticket=ticket, actor=author)
    await db.commit()  # persist notification records created by the service

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


async def change_status(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    new_status: TicketStatus,
    actor: User,
) -> Optional[TicketOut]:
    """
    Transitions a ticket to a new workflow status and triggers notifications.

    Args:
        db: Database session.
        ticket_id: UUID of the target ticket.
        new_status: The target TicketStatus enum value.
        actor: The user performing the action (for auditing and notifications).

    Returns:
        Optional[TicketOut]: The updated ticket schema, or None if not found.
    """
    # 1. Fetch the "live" model from the session
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        return None

    # 2. Apply business logic
    old_status = ticket.status
    ticket.status = new_status
    
    # 4. Persist changes
    await db.commit()
    
    # 5. Handle side effects (Notifications) after commit
    # This avoids race conditions where the frontend refreshes before the commit is finished
    if new_status != old_status:
        await notification_service.notify_status_changed(
            db, ticket=ticket, actor=actor, new_status=new_status.value
        )
        await notification_service.notify_ticket_updated(db, ticket=ticket, actor=actor)
        await db.commit()  # persist notification records

    # 6. Return a clean, decoupled Pydantic object
    return await get_ticket(db, ticket_id)


async def reassign(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    assignee_id: Optional[uuid.UUID],
    actor: User,
) -> Optional[TicketOut]:
    """
    Changes the assigned user for a ticket and notifies the new assignee.

    Args:
        db: Database session.
        ticket_id: UUID of the ticket.
        assignee_id: UUID of the new user, or None to unassign.
        actor: The user performing the change.

    Returns:
        Optional[TicketOut]: The updated ticket schema.
    """
    # 1. Fetch the model
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        return None

    # 2. Update field
    ticket.assignee_id = assignee_id

    # 4. Persist
    await db.commit()

    # 5. Notify after commit if a new assignee is provided
    if assignee_id:
        assignee_result = await db.execute(select(User).where(User.id == assignee_id))
        new_assignee = assignee_result.scalar_one_or_none()
        if new_assignee:
            await notification_service.notify_ticket_assigned(
                db, ticket=ticket, assignee=new_assignee, actor=actor
            )
        await db.commit()  # persist notification records

    # 6. Return decoupled schema
    return await get_ticket(db, ticket_id)


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

    # Apply updates
    for key, value in update_data.items():
        if hasattr(ticket, key):
            setattr(ticket, key, value)
    
    await db.flush()

    # 5. Persist
    await db.commit()

    # 6. Side effects (Notifications) after commit
    if "status" in update_data and update_data["status"] != old_status:
        await notification_service.notify_status_changed(
            db, ticket=ticket, actor=actor, new_status=update_data["status"]
        )

    if "assignee_id" in update_data and update_data["assignee_id"] != old_assignee_id:
        if update_data["assignee_id"]:
            res = await db.execute(select(User).where(User.id == update_data["assignee_id"]))
            new_assignee = res.scalar_one_or_none()
            if new_assignee:
                await notification_service.notify_ticket_assigned(
                    db, ticket=ticket, assignee=new_assignee, actor=actor
                )
        
    # Generic update notification to trigger UI refreshes
    await notification_service.notify_ticket_updated(db, ticket=ticket, actor=actor)
    await db.commit()  # persist notification records

    # --- Side effects (Background Tasks) ---
    if "title" in update_data or "description" in update_data:
        new_title = update_data.get("title", ticket.title)
        new_desc = update_data.get("description", ticket.description)
        asyncio.create_task(generate_ticket_embedding_task(ticket_id, new_title, new_desc))

    if "client_url" in update_data and update_data["client_url"]:
        asyncio.create_task(scraping_service.scrape_and_index_url(ticket_id, update_data["client_url"]))

    return await get_ticket(db, ticket_id)

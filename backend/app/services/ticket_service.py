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
from app.services import notification_service


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
    )
    db.add(ticket)
    await db.flush() # Get the ID for notifications
    
    # 2. Side effects
    # We fetch the author object to use their name in the notification
    author_result = await db.execute(select(User).where(User.id == author_id))
    author = author_result.scalar_one()
    
    await notification_service.notify_ticket_created(db, ticket=ticket, actor=author)
    
    # 3. Finalize
    await db.commit()
    
    # 4. Return decoupled schema
    return await get_ticket(db, ticket.id) # type: ignore


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
    
    # 3. Handle side effects (Notifications)
    if new_status != old_status:
        await notification_service.notify_status_changed(
            db, ticket=ticket, actor=actor, new_status=new_status.value
        )

    # 4. Persist changes
    await db.commit()
    
    # 5. Return a clean, decoupled Pydantic object
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
    
    # 3. Notify if a new assignee is provided
    if assignee_id:
        assignee_result = await db.execute(select(User).where(User.id == assignee_id))
        new_assignee = assignee_result.scalar_one_or_none()
        if new_assignee:
            await notification_service.notify_ticket_assigned(
                db, ticket=ticket, assignee=new_assignee, actor=actor
            )

    # 4. Persist
    await db.commit()
    
    # 5. Return decoupled schema
    return await get_ticket(db, ticket_id)

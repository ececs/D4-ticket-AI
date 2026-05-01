"""
Ticket service — reusable business logic for the AI agent.

The API routers handle HTTP concerns (parsing requests, returning responses).
This service layer encapsulates ticket operations that can be called from
both the HTTP router and the LangGraph AI agent tools.

This avoids duplicating database logic: the AI agent uses the same
validated, notification-aware functions as the REST API.

All functions receive an AsyncSession and the acting user, ensuring that
the AI agent can only perform actions the user is authorized to do.
"""

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.user import User
from app.services import notification_service


async def get_ticket(db: AsyncSession, ticket_id: uuid.UUID) -> Ticket | None:
    """Fetch a single ticket with its author and assignee relationships loaded."""
    result = await db.execute(
        select(Ticket)
        .options(
            selectinload(Ticket.author),   # type: ignore[attr-defined]
            selectinload(Ticket.assignee), # type: ignore[attr-defined]
        )
        .where(Ticket.id == ticket_id)
    )
    return result.scalar_one_or_none()


async def change_status(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    new_status: TicketStatus,
    actor: User,
) -> Ticket | None:
    """
    Change a ticket's status and notify relevant users.

    Used by both PATCH /tickets/{id} and the AI agent's change_status tool.

    Returns the updated ticket, or None if the ticket was not found.
    """
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        return None

    old_status = ticket.status
    ticket.status = new_status
    await db.flush()

    if new_status != old_status:
        await notification_service.notify_status_changed(
            db, ticket=ticket, actor=actor, new_status=new_status.value
        )

    await db.commit()
    return await get_ticket(db, ticket_id)


async def reassign(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    assignee_id: uuid.UUID | None,
    actor: User,
) -> Ticket | None:
    """
    Reassign a ticket to a different user (or unassign with assignee_id=None).

    Notifies the new assignee if one is set and it's not the actor themselves.
    Returns the updated ticket, or None if the ticket was not found.
    """
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        return None

    ticket.assignee_id = assignee_id
    await db.flush()

    if assignee_id:
        assignee_result = await db.execute(select(User).where(User.id == assignee_id))
        new_assignee = assignee_result.scalar_one_or_none()
        if new_assignee:
            await notification_service.notify_ticket_assigned(
                db, ticket=ticket, assignee=new_assignee, actor=actor
            )

    await db.commit()
    return await get_ticket(db, ticket_id)

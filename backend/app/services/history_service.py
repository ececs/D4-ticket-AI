"""
History service — append-only audit log for ticket changes.

Every write that goes through ticket_service calls record_change() here.
The service only appends rows; it never mutates or deletes them.
"""

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.ticket_history import TicketHistory
from app.schemas.ticket_history import TicketHistoryOut


async def record_change(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    actor_id: uuid.UUID,
    field: str,
    old_value: str | None,
    new_value: str | None,
) -> None:
    """Append one history entry. Caller is responsible for the final commit."""
    entry = TicketHistory(
        ticket_id=ticket_id,
        actor_id=actor_id,
        field=field,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(entry)
    await db.flush()


async def get_history(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    limit: int = 100,
) -> list[TicketHistoryOut]:
    result = await db.execute(
        select(TicketHistory)
        .options(selectinload(TicketHistory.actor))
        .where(TicketHistory.ticket_id == ticket_id)
        .order_by(TicketHistory.created_at.desc())
        .limit(limit)
    )
    return [TicketHistoryOut.model_validate(h) for h in result.scalars().all()]

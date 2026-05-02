"""
Ticket routes — CRUD + filtering + pagination + sorting + semantic search.

Search strategy:
  When a `search` query param is provided:
  1. Generate a vector embedding of the query (Google text-embedding-004).
  2. If embedding succeeds → semantic search: rank results by cosine similarity
     against stored ticket embeddings (requires pgvector migration to have run).
  3. If embedding fails (no API key, service down) → keyword fallback: ilike
     on title and description (same behavior as before pgvector).

  This means the API degrades gracefully in tests and local dev without an
  API key, while delivering semantic search in production.

Embedding side-effects on writes:
  - POST /tickets: embedding generated after commit (fire-and-forget).
  - PATCH /tickets/{id}: embedding regenerated if title or description changed.
  Both use asyncio.create_task so they don't add latency to the response.
"""

import asyncio
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.dependencies import CurrentUser, DB
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.models.user import User
from app.schemas.ticket import TicketCreate, TicketListResponse, TicketOut, TicketUpdate
from app.services import notification_service
from app.services.embedding_service import generate_embedding, generate_ticket_embedding

router = APIRouter(prefix="/tickets", tags=["Tickets"])

SORTABLE_COLUMNS = {
    "created_at": Ticket.created_at,
    "updated_at": Ticket.updated_at,
    "priority": Ticket.priority,
    "status": Ticket.status,
    "title": Ticket.title,
}


@router.get("", response_model=TicketListResponse, summary="List tickets with filters")
async def list_tickets(
    db: DB,
    current_user: CurrentUser,
    status: TicketStatus | None = Query(None),
    priority: TicketPriority | None = Query(None),
    assignee_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None, description="Semantic search (falls back to keyword)"),
    sort_by: str = Query("created_at"),
    order: Literal["asc", "desc"] = Query("desc"),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
):
    query = select(Ticket).options(
        selectinload(Ticket.author),    # type: ignore[attr-defined]
        selectinload(Ticket.assignee),  # type: ignore[attr-defined]
    )

    if status is not None:
        query = query.where(Ticket.status == status)
    if priority is not None:
        query = query.where(Ticket.priority == priority)
    if assignee_id is not None:
        query = query.where(Ticket.assignee_id == assignee_id)

    semantic = False
    if search:
        search_embedding = await generate_embedding(search, task_type="RETRIEVAL_QUERY")
        if search_embedding is not None:
            # Semantic: order by cosine distance to the query vector.
            # Only considers tickets that already have an embedding stored.
            query = query.where(Ticket.embedding.isnot(None))  # type: ignore[attr-defined]
            query = query.order_by(
                Ticket.embedding.cosine_distance(search_embedding)  # type: ignore[attr-defined]
            )
            semantic = True
        else:
            # Keyword fallback — ilike on title and description
            pattern = f"%{search}%"
            query = query.where(
                Ticket.title.ilike(pattern) | Ticket.description.ilike(pattern)
            )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    # When doing semantic search the ORDER BY is already set by cosine distance.
    # For regular queries apply the requested sort column.
    if not semantic:
        sort_column = SORTABLE_COLUMNS.get(sort_by, Ticket.created_at)
        query = query.order_by(sort_column.desc() if order == "desc" else sort_column.asc())

    offset = (page - 1) * size
    query = query.offset(offset).limit(size)

    result = await db.execute(query)
    tickets = result.scalars().all()

    return TicketListResponse(items=list(tickets), total=total, page=page, size=size)


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED, summary="Create a ticket")
async def create_ticket(body: TicketCreate, db: DB, current_user: CurrentUser):
    assignee: User | None = None
    if body.assignee_id:
        result = await db.execute(select(User).where(User.id == body.assignee_id))
        assignee = result.scalar_one_or_none()
        if not assignee:
            raise HTTPException(status_code=404, detail="Assignee not found")

    ticket = Ticket(
        title=body.title,
        description=body.description,
        priority=body.priority,
        author_id=current_user.id,
        assignee_id=body.assignee_id,
    )
    db.add(ticket)
    await db.flush()

    if assignee:
        await notification_service.notify_ticket_assigned(
            db, ticket=ticket, assignee=assignee, actor=current_user
        )

    await db.commit()
    await db.refresh(ticket)

    # Generate embedding asynchronously — doesn't block the response
    asyncio.create_task(_embed_ticket(ticket.id, body.title, body.description))

    return await _get_ticket_with_relations(db, ticket.id)


@router.get("/{ticket_id}", response_model=TicketOut, summary="Get a ticket by ID")
async def get_ticket(ticket_id: uuid.UUID, db: DB, current_user: CurrentUser):
    ticket = await _get_ticket_with_relations(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.patch("/{ticket_id}", response_model=TicketOut, summary="Update a ticket")
async def update_ticket(
    ticket_id: uuid.UUID,
    body: TicketUpdate,
    db: DB,
    current_user: CurrentUser,
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    old_status = ticket.status
    old_assignee_id = ticket.assignee_id

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ticket, field, value)

    await db.flush()

    if body.status is not None and body.status != old_status:
        await notification_service.notify_status_changed(
            db, ticket=ticket, actor=current_user, new_status=body.status.value
        )

    if body.assignee_id is not None and body.assignee_id != old_assignee_id:
        result = await db.execute(select(User).where(User.id == body.assignee_id))
        new_assignee = result.scalar_one_or_none()
        if new_assignee:
            await notification_service.notify_ticket_assigned(
                db, ticket=ticket, assignee=new_assignee, actor=current_user
            )

    await db.commit()

    # Regenerate embedding if searchable content changed
    text_changed = body.title is not None or body.description is not None
    if text_changed:
        new_title = body.title or ticket.title
        new_desc = body.description if body.description is not None else ticket.description
        asyncio.create_task(_embed_ticket(ticket_id, new_title, new_desc))

    return await _get_ticket_with_relations(db, ticket_id)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a ticket")
async def delete_ticket(ticket_id: uuid.UUID, db: DB, current_user: CurrentUser):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    await db.delete(ticket)
    await db.commit()


# ─── Private helpers ──────────────────────────────────────────────────────────

async def _get_ticket_with_relations(db: DB, ticket_id: uuid.UUID) -> TicketOut | None:
    result = await db.execute(
        select(Ticket)
        .options(
            selectinload(Ticket.author),    # type: ignore[attr-defined]
            selectinload(Ticket.assignee),  # type: ignore[attr-defined]
        )
        .where(Ticket.id == ticket_id)
    )
    return result.scalar_one_or_none()


async def _embed_ticket(ticket_id: uuid.UUID, title: str, description: str | None) -> None:
    """
    Background task: generate and persist a ticket's embedding.

    Opens its own DB session (independent of the request session which is
    already closed by the time this task runs).
    """
    embedding = await generate_ticket_embedding(title, description)
    if embedding is None:
        return

    try:
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
            ticket = result.scalar_one_or_none()
            if ticket:
                ticket.embedding = embedding
                await session.commit()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to persist embedding for %s: %s", ticket_id, exc)

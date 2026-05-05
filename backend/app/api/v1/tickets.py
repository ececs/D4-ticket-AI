"""
Ticket routes — CRUD + filtering + pagination + sorting + hybrid search.

Search strategy:
  When a `search` query param is provided:
  1. Generate a vector embedding of the query (Google text-embedding-004).
  2. If embedding succeeds → run hybrid search:
     - semantic ranking by cosine similarity against stored ticket embeddings
     - keyword ranking over title/description matches
     - fuse both rankings with Reciprocal Rank Fusion (RRF)
  3. If embedding fails (no API key, service down) → keyword fallback: ilike
     on title and description (same behavior as before pgvector).

  This means the API degrades gracefully in tests and local dev without an
  API key, while delivering hybrid semantic + keyword retrieval in production.

Embedding side-effects on writes:
  - POST /tickets: embedding generated after commit (fire-and-forget).
  - PATCH /tickets/{id}: embedding regenerated if title or description changed.
  Both use asyncio.create_task so they don't add latency to the response.
"""

import asyncio
import hashlib
import json
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import selectinload

from app.core.dependencies import CurrentUser, DB
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.models.user import User
from app.schemas.ticket import TicketCreate, TicketListResponse, TicketOut, TicketUpdate
from app.services.cache_service import cache_get, cache_set, cache_invalidate_prefix
from app.services.embedding_service import generate_embedding, generate_ticket_embedding
from app.services import ticket_service, notification_service, ai_copilot_service, scraping_service
from app.schemas.websocket import WSMessageType
from app.models.knowledge_chunk import KnowledgeChunk

CACHE_PREFIX = "tickets:"
CACHE_TTL = 60  # seconds

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
    search: str | None = Query(None, description="Hybrid semantic + keyword search (falls back to keyword)"),
    sort_by: str = Query("created_at"),
    order: Literal["asc", "desc"] = Query("desc"),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
):
    # Cache key = hash of all query params so each search/filter/page combination
    # is cached independently.
    cache_params = {
        "status": status.value if status else None,
        "priority": priority.value if priority else None,
        "assignee_id": str(assignee_id) if assignee_id else None,
        "search": search,
        "sort_by": sort_by,
        "order": order,
        "page": page,
        "size": size,
    }
    cache_key = CACHE_PREFIX + hashlib.md5(
        json.dumps(cache_params, sort_keys=True).encode()
    ).hexdigest()

    cached = await cache_get(cache_key)
    if cached is not None:
        return TicketListResponse(**cached)

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

    if search:
        search_embedding = await generate_embedding(search, task_type="RETRIEVAL_QUERY")
        if search_embedding is not None:
            # ── Hybrid search: RRF(semantic, keyword) ──────────────────────────
            # Fetch up to POOL candidates from each source, then fuse with
            # Reciprocal Rank Fusion: score = 1/(rank + K) summed across sources.
            # This surfaces exact-match titles AND conceptually similar tickets.
            POOL = 100
            K = 60  # standard RRF constant

            pattern = f"%{search}%"
            sem_q = (
                query.where(Ticket.embedding.isnot(None))  # type: ignore[attr-defined]
                .order_by(Ticket.embedding.cosine_distance(search_embedding))  # type: ignore[attr-defined]
                .limit(POOL)
            )
            keyword_rank = case(
                (func.lower(Ticket.title) == search.lower(), 0),
                (Ticket.title.ilike(pattern), 1),
                else_=2,
            )
            kw_q = (
                query.where(Ticket.title.ilike(pattern) | Ticket.description.ilike(pattern))
                .order_by(keyword_rank, Ticket.updated_at.desc())
                .limit(POOL)
            )

            sem_rows = (await db.execute(sem_q)).scalars().all()
            kw_rows = (await db.execute(kw_q)).scalars().all()

            rrf: dict = {}
            for i, t in enumerate(sem_rows):
                rrf[t.id] = rrf.get(t.id, 0.0) + 1.0 / (i + K)
            for i, t in enumerate(kw_rows):
                rrf[t.id] = rrf.get(t.id, 0.0) + 1.0 / (i + K)

            pool = {t.id: t for t in (*sem_rows, *kw_rows)}
            ranked = sorted(rrf, key=rrf.__getitem__, reverse=True)

            total = len(ranked)
            page_ids = ranked[(page - 1) * size: page * size]
            tickets = [pool[i] for i in page_ids]

            response = TicketListResponse(items=list(tickets), total=total, page=page, size=size)
            await cache_set(cache_key, response.model_dump(mode="json"), ttl=CACHE_TTL)
            return response
        else:
            # Embedding unavailable — keyword-only fallback (same as before)
            pattern = f"%{search}%"
            query = query.where(
                Ticket.title.ilike(pattern) | Ticket.description.ilike(pattern)
            )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    sort_column = SORTABLE_COLUMNS.get(sort_by, Ticket.created_at)
    query = query.order_by(sort_column.desc() if order == "desc" else sort_column.asc())

    offset = (page - 1) * size
    query = query.offset(offset).limit(size)

    result = await db.execute(query)
    tickets = result.scalars().all()

    response = TicketListResponse(items=list(tickets), total=total, page=page, size=size)
    await cache_set(cache_key, response.model_dump(mode="json"), ttl=CACHE_TTL)
    return response


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED, summary="Create a ticket")
async def create_ticket(body: TicketCreate, db: DB, current_user: CurrentUser):
    ticket = await ticket_service.create_ticket(
        db=db,
        title=body.title,
        description=body.description,
        priority=body.priority,
        author_id=current_user.id,
        assignee_id=body.assignee_id,
        client_url=body.client_url,
        client_summary=body.client_summary,
    )

    if body.client_url:
        asyncio.create_task(scraping_service.scrape_and_index_url(ticket.id, body.client_url))
    await cache_invalidate_prefix(CACHE_PREFIX)

    return ticket


@router.get("/{ticket_id}", response_model=TicketOut, summary="Get a ticket by ID")
async def get_ticket(ticket_id: uuid.UUID, db: DB, current_user: CurrentUser):
    ticket = await ticket_service.get_ticket(db, ticket_id)
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

    # --- Authorization Check ---
    # We allow any authenticated user to update the ticket for demo purposes.
    # (Previously restricted to author or assignee).

    update_data = body.model_dump(exclude_unset=True)
    updated_ticket = await ticket_service.update_ticket(
        db=db,
        ticket_id=ticket_id,
        update_data=update_data,
        actor=current_user,
    )

    await cache_invalidate_prefix(CACHE_PREFIX)

    return updated_ticket


@router.get("/{ticket_id}/history", summary="Get audit history for a ticket")
async def get_ticket_history(ticket_id: uuid.UUID, db: DB, current_user: CurrentUser):
    from app.services import history_service
    from app.schemas.ticket_history import TicketHistoryOut
    return await history_service.get_history(db, ticket_id)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a ticket")
async def delete_ticket(ticket_id: uuid.UUID, db: DB, current_user: CurrentUser):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el autor puede eliminar este ticket."
        )

    title = ticket.title

    await db.delete(ticket)
    await db.commit()

    # Notify after commit so the ticket_id FK is already gone
    await notification_service.notify_ticket_deleted(db, ticket_id, title, current_user)
    await db.commit()
    
    # Broadcast deletion for real-time UI sync (Global)
    await notification_service.broadcast_global_event(
        type=WSMessageType.TICKET_DELETED, 
        data={"id": str(ticket_id), "title": title},
        db=db
    )
    
    await cache_invalidate_prefix(CACHE_PREFIX)


from fastapi.responses import StreamingResponse

@router.get("/{ticket_id}/diagnosis")
async def get_diagnosis(
    ticket_id: uuid.UUID,
    db: DB,
    current_user: CurrentUser,
):
    """
    Generate an AI diagnosis and suggested solution for a ticket.
    Streams the response token-by-token.
    """
    return StreamingResponse(
        ai_copilot_service.stream_ticket_diagnosis(db, ticket_id),
        media_type="text/event-stream"
    )


@router.get("/{ticket_id}/web-context")
async def get_ticket_web_context(
    ticket_id: uuid.UUID,
    db: DB,
    current_user: CurrentUser,
):
    """
    Fetches the latest AI-extracted web context for this ticket.
    """
    # Use a more robust way to query JSON content in SQLAlchemy
    result = await db.execute(
        select(KnowledgeChunk)
        .where(func.json_extract_path_text(KnowledgeChunk.chunk_metadata, "ticket_id") == str(ticket_id))
        .order_by(KnowledgeChunk.created_at.desc())
        .limit(1)
    )
    chunk = result.scalar_one_or_none()
    return {"content": chunk.content if chunk else None}


@router.post("/{ticket_id}/web-scrape-refresh")
async def refresh_ticket_web_scrape(
    ticket_id: uuid.UUID,
    db: DB,
    current_user: CurrentUser,
):
    """
    Manually triggers a new web scrape for the ticket's URL.
    """
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket or not ticket.client_url:
        raise HTTPException(status_code=400, detail="Ticket has no URL to scrape.")
    
    # Trigger background task
    asyncio.create_task(scraping_service.scrape_and_index_url(ticket_id, ticket.client_url))
    return {"status": "scraping_started"}


# ─── Private helpers ──────────────────────────────────────────────────────────


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

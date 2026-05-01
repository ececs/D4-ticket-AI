"""
Ticket routes — CRUD + filtering + pagination + sorting.

This is the core resource of the API.

Filtering strategy:
  All filters are optional query parameters combined with AND logic.
  SQLAlchemy .where() chaining keeps queries safe from SQL injection —
  user input never touches raw SQL strings.

Sorting:
  Supports sorting by any ticket column. Direction is asc/desc.
  The sort_by parameter is validated against an allowlist to prevent
  injection via column names.

Pagination:
  Offset-based (page + size). Returns total count so the frontend
  can render "Page 1 of 5" style controls.

Notification side-effects:
  - On status change: notify author and assignee.
  - On assignee change: notify the new assignee.
  All notifications are created by notification_service to keep this
  router focused on HTTP concerns only.
"""

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

router = APIRouter(prefix="/tickets", tags=["Tickets"])

# Allowlist of sortable columns — prevents column-name injection attacks
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
    # --- Filters ---
    status: TicketStatus | None = Query(None, description="Filter by status"),
    priority: TicketPriority | None = Query(None, description="Filter by priority"),
    assignee_id: uuid.UUID | None = Query(None, description="Filter by assignee UUID"),
    search: str | None = Query(None, description="Search in title and description"),
    # --- Sorting ---
    sort_by: str = Query("created_at", description="Column to sort by"),
    order: Literal["asc", "desc"] = Query("desc", description="Sort direction"),
    # --- Pagination ---
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    size: int = Query(25, ge=1, le=100, description="Items per page"),
):
    """
    Return a paginated, filtered, sorted list of tickets.

    All filters are optional and combined with AND logic.
    Results include nested author and assignee User objects for display
    without additional API calls from the frontend.
    """
    # Base query with eager loading of related users
    # selectinload avoids N+1 queries: fetches all users in a single IN query
    query = select(Ticket).options(
        selectinload(Ticket.author),   # type: ignore[attr-defined]
        selectinload(Ticket.assignee), # type: ignore[attr-defined]
    )

    # Apply filters
    if status is not None:
        query = query.where(Ticket.status == status)
    if priority is not None:
        query = query.where(Ticket.priority == priority)
    if assignee_id is not None:
        query = query.where(Ticket.assignee_id == assignee_id)
    if search:
        # Case-insensitive search in title and description using PostgreSQL ilike
        pattern = f"%{search}%"
        query = query.where(
            Ticket.title.ilike(pattern) | Ticket.description.ilike(pattern)
        )

    # Count total matching rows (before pagination) for the frontend's page count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    # Apply sorting — use allowlist to prevent column injection
    sort_column = SORTABLE_COLUMNS.get(sort_by, Ticket.created_at)
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)

    result = await db.execute(query)
    tickets = result.scalars().all()

    return TicketListResponse(items=list(tickets), total=total, page=page, size=size)


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED, summary="Create a ticket")
async def create_ticket(body: TicketCreate, db: DB, current_user: CurrentUser):
    """
    Create a new ticket. The current user is set as the author.

    If an assignee_id is provided, the assignee is notified.
    """
    # Validate assignee exists (if provided) before creating the ticket
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
    await db.flush()  # Get the ticket id before notifications

    # Notify assignee if one was set
    if assignee:
        await notification_service.notify_ticket_assigned(
            db, ticket=ticket, assignee=assignee, actor=current_user
        )

    await db.commit()
    await db.refresh(ticket)

    # Load related users for the response
    return await _get_ticket_with_relations(db, ticket.id)


@router.get("/{ticket_id}", response_model=TicketOut, summary="Get a ticket by ID")
async def get_ticket(ticket_id: uuid.UUID, db: DB, current_user: CurrentUser):
    """Retrieve a single ticket with its author and assignee populated."""
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
    """
    Partially update a ticket. Only provided fields are changed (PATCH semantics).

    Side effects:
      - Status change → notify author and assignee.
      - Assignee change → notify the new assignee.
    """
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Track what changed to send the right notifications
    old_status = ticket.status
    old_assignee_id = ticket.assignee_id

    # Apply only the fields that were provided in the request body
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ticket, field, value)

    await db.flush()

    # --- Notification side-effects ---

    # Status changed
    if body.status is not None and body.status != old_status:
        await notification_service.notify_status_changed(
            db, ticket=ticket, actor=current_user, new_status=body.status.value
        )

    # Assignee changed to a different user
    if body.assignee_id is not None and body.assignee_id != old_assignee_id:
        result = await db.execute(select(User).where(User.id == body.assignee_id))
        new_assignee = result.scalar_one_or_none()
        if new_assignee:
            await notification_service.notify_ticket_assigned(
                db, ticket=ticket, assignee=new_assignee, actor=current_user
            )

    await db.commit()

    return await _get_ticket_with_relations(db, ticket_id)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a ticket")
async def delete_ticket(ticket_id: uuid.UUID, db: DB, current_user: CurrentUser):
    """
    Delete a ticket permanently.

    Cascade deletes: comments, attachments, and notifications are removed
    automatically via the FK ON DELETE CASCADE constraints set in the migration.

    Note: In a production system you might want to restrict deletion to the
    ticket author or an admin role. For this scope, any authenticated user can delete.
    """
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    await db.delete(ticket)
    await db.commit()


# ─── Private helpers ──────────────────────────────────────────────────────────

async def _get_ticket_with_relations(db: DB, ticket_id: uuid.UUID) -> TicketOut | None:
    """
    Fetch a ticket by ID with author and assignee eagerly loaded.

    Using selectinload avoids the N+1 query problem: SQLAlchemy fetches
    the related User rows in a single IN query rather than one per ticket.
    """
    result = await db.execute(
        select(Ticket)
        .options(
            selectinload(Ticket.author),   # type: ignore[attr-defined]
            selectinload(Ticket.assignee), # type: ignore[attr-defined]
        )
        .where(Ticket.id == ticket_id)
    )
    return result.scalar_one_or_none()

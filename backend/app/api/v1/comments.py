"""
Comment routes.

Comments are attached to a specific ticket and displayed chronologically
in the ticket detail view. All operations require authentication.

Side effects:
  - POST (create): automatically notifies the ticket author and assignee
    via notification_service (unless the commenter is the author/assignee).

Ordering:
  - GET returns comments sorted by created_at ascending (oldest first)
    so the conversation reads top-to-bottom like a chat.
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.dependencies import CurrentUser, DB
from app.models.comment import Comment
from app.models.ticket import Ticket
from app.schemas.comment import CommentCreate, CommentOut
from app.services import notification_service

# Prefix: /tickets/{ticket_id}/comments — nested under the ticket resource
router = APIRouter(prefix="/tickets", tags=["Comments"])


@router.get(
    "/{ticket_id}/comments",
    response_model=list[CommentOut],
    summary="List comments on a ticket",
)
async def list_comments(ticket_id: uuid.UUID, db: DB, current_user: CurrentUser):
    """
    Return all comments for a ticket, oldest first.

    Each comment includes the author's profile for display.
    """
    # Verify the ticket exists before listing its comments
    ticket_result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    if not ticket_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Ticket not found")

    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.author))  # type: ignore[attr-defined]
        .where(Comment.ticket_id == ticket_id)
        .order_by(Comment.created_at.asc())
    )
    return result.scalars().all()


@router.post(
    "/{ticket_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment to a ticket",
)
async def create_comment(
    ticket_id: uuid.UUID,
    body: CommentCreate,
    db: DB,
    current_user: CurrentUser,
):
    """
    Add a comment to a ticket and notify relevant users.

    The commenter's author profile is included in the response so the
    frontend can display the avatar and name without a second request.
    """
    # Verify ticket exists and load it for the notification
    ticket_result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = ticket_result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    comment = Comment(
        ticket_id=ticket_id,
        author_id=current_user.id,
        content=body.content,
    )
    db.add(comment)
    await db.flush()  # Get the comment id before notifications

    # Notify ticket author and assignee (notification_service handles deduplication)
    await notification_service.notify_comment_added(
        db, ticket=ticket, commenter=current_user
    )

    await db.commit()

    # Re-fetch with author relation for the response
    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.author))  # type: ignore[attr-defined]
        .where(Comment.id == comment.id)
    )
    return result.scalar_one()


@router.delete(
    "/{ticket_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment",
)
async def delete_comment(
    ticket_id: uuid.UUID,
    comment_id: uuid.UUID,
    db: DB,
    current_user: CurrentUser,
):
    """
    Delete a comment. Only the comment author can delete their own comments.

    Returns 403 if the current user did not write this comment.
    """
    result = await db.execute(
        select(Comment).where(Comment.id == comment_id, Comment.ticket_id == ticket_id)
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Authorization check: only the author can delete their own comment
    if comment.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comments",
        )

    await db.delete(comment)
    await db.commit()

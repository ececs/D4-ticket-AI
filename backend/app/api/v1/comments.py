"""
Comment routes — Nested under /api/v1/tickets/{ticket_id}/comments.
"""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status
from app.core.dependencies import CurrentUser, DB
from app.schemas.comment import CommentCreate, CommentOut
from app.services import comment_service

router = APIRouter(prefix="/tickets", tags=["Comments"])


@router.get(
    "/{ticket_id}/comments",
    response_model=List[CommentOut],
    summary="List comments on a ticket",
)
async def list_comments(ticket_id: uuid.UUID, db: DB, current_user: CurrentUser):
    """
    Returns all comments for a ticket, oldest first.
    """
    comments = await comment_service.list_comments(db, ticket_id)
    # The service returns an empty list if no comments, but we still need to 
    # check if the ticket exists to return a 404 (handled inside service or here)
    # For simplicity and to avoid extra queries, if comments is empty, 
    # we verify the ticket.
    if not comments:
        from sqlalchemy import select
        from app.models.ticket import Ticket
        ticket_exists = (await db.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one_or_none()
        if not ticket_exists:
            raise HTTPException(status_code=404, detail="Ticket not found")
            
    return comments


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
    """
    comment = await comment_service.create_comment(
        db, ticket_id=ticket_id, content=body.content, author=current_user
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    return comment


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
    Only the original author can delete their comment.
    """
    success = await comment_service.delete_comment(
        db, comment_id=comment_id, actor_id=current_user.id
    )
    if not success:
        # Note: 404/403 ambiguity is fine here for security (don't leak existence)
        # but the project requirements suggest a specific error.
        # Let's check for existence first to provide better error.
        from sqlalchemy import select
        from app.models.comment import Comment
        exists = (await db.execute(select(Comment).where(Comment.id == comment_id))).scalar_one_or_none()
        if not exists:
            raise HTTPException(status_code=404, detail="Comment not found")
        raise HTTPException(status_code=403, detail="You can only delete your own comments")

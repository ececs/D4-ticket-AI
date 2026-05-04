"""
Comment Service Module.

This service manages all business logic related to ticket comments.
By centralizing these operations, we ensure that notifications and 
validation are applied consistently regardless of whether the comment 
comes from the REST API or the AI Assistant.

Architecture (Senior Pattern):
- Decoupling: Returns Pydantic schemas (`CommentOut`) instead of models.
- Transactional: Ensures that comments and notifications are committed atomically.
"""

import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.comment import CommentOut
from app.services import notification_service


async def list_comments(db: AsyncSession, ticket_id: uuid.UUID) -> List[CommentOut]:
    """
    Retrieves all comments for a specific ticket, ordered by creation date.

    Args:
        db: Database session.
        ticket_id: UUID of the parent ticket.

    Returns:
        List[CommentOut]: Validated schemas for all comments found.
    """
    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.author))  # type: ignore[attr-defined]
        .where(Comment.ticket_id == ticket_id)
        .order_by(Comment.created_at.asc())
    )
    comments = result.scalars().all()
    return [CommentOut.model_validate(c) for c in comments]


async def create_comment(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    content: str,
    author: User,
) -> Optional[CommentOut]:
    """
    Adds a comment to a ticket and triggers notifications to author/assignee.

    Args:
        db: Database session.
        ticket_id: Parent ticket UUID.
        content: Comment body.
        author: The User object who wrote the comment.

    Returns:
        Optional[CommentOut]: The newly created comment, or None if ticket missing.
    """
    # 1. Verify ticket existence (needed for notification logic)
    ticket_result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = ticket_result.scalar_one_or_none()
    
    if not ticket:
        return None

    # 2. Create model
    comment = Comment(
        ticket_id=ticket_id,
        author_id=author.id,
        content=content,
    )
    db.add(comment)
    await db.flush()

    # 3. Trigger side effects
    await notification_service.notify_comment_added(
        db, ticket=ticket, commenter=author
    )
    # Broadcaster global update to refresh UI
    await notification_service.notify_ticket_updated(db, ticket=ticket, actor=author)

    # 4. Finalize
    await db.commit()
    
    # 5. Re-fetch with author relation for the schema
    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.author))  # type: ignore[attr-defined]
        .where(Comment.id == comment.id)
    )
    return CommentOut.model_validate(result.scalar_one())


async def delete_comment(
    db: AsyncSession,
    comment_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> bool:
    """
    Removes a comment if the actor is the original author.

    Args:
        db: Database session.
        comment_id: Target comment UUID.
        actor_id: UUID of the user attempting the deletion.

    Returns:
        bool: True if deleted, False if not found or unauthorized.
    """
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    
    if not comment or comment.author_id != actor_id:
        return False

    await db.delete(comment)
    await db.commit()
    return True

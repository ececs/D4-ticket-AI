"""
User routes.

Provides a list of all users in the system. This endpoint is used by the
frontend's assignee selector when creating or editing a ticket.

In a production system with thousands of users, this would be paginated
and searchable. For this scope, returning all users is acceptable.
"""

from fastapi import APIRouter
from sqlalchemy import select

from app.core.dependencies import CurrentUser, DB
from app.models.user import User
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=list[UserOut], summary="List all users")
async def list_users(current_user: CurrentUser, db: DB):
    """
    Return all registered users.

    Used by the frontend to populate the assignee dropdown when creating
    or editing a ticket. Requires authentication.
    """
    result = await db.execute(select(User).order_by(User.name))
    users = result.scalars().all()
    return users

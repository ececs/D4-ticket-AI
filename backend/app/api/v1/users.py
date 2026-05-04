"""
User routes.
"""

from typing import List
from fastapi import APIRouter
from app.core.dependencies import CurrentUser, DB
from app.schemas.user import UserOut
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=List[UserOut], summary="List all users")
async def list_users(current_user: CurrentUser, db: DB):
    """
    Return all registered users.
    """
    return await user_service.list_users(db)

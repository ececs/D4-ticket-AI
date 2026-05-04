"""
User Service Module.
"""

from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.schemas.user import UserOut

async def list_users(db: AsyncSession) -> List[UserOut]:
    """Retrieves all users ordered by name."""
    result = await db.execute(select(User).order_by(User.name))
    users = result.scalars().all()
    return [UserOut.model_validate(u) for u in users]

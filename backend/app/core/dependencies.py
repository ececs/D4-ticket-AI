"""
FastAPI dependency injection utilities.

Dependencies are reusable components that FastAPI resolves automatically
when listed as function parameters. This module provides:

  - get_current_user: extracts and validates the authenticated user from the request.
  - CurrentUser: type alias for use in route handlers.
  - DB: type alias for the database session dependency.

Token extraction strategy:
  1. Authorization: Bearer <token> header (for API clients, Swagger UI)
  2. access_token HttpOnly cookie (for Next.js browser sessions)

This dual approach means the API works for both browser-based sessions
and headless API clients (tools, scripts, AI agent).
"""

from fastapi import Depends, HTTPException, status, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated

from app.db.session import get_db
from app.core.security import decode_access_token
from app.models.user import User

# auto_error=False so we can also check the cookie as a fallback
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    access_token: Annotated[str | None, Cookie()] = None,
) -> User:
    """
    Resolve the authenticated user from an incoming request.

    Checks for a JWT in this order:
      1. Authorization: Bearer header (API clients, Swagger)
      2. access_token cookie (Next.js browser)

    Raises HTTP 401 if no token is present, invalid, or the user doesn't exist.
    """
    # Extract the token from whichever source is available
    token: str | None = None
    if credentials:
        token = credentials.credentials
    elif access_token:
        token = access_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode and verify the JWT signature and expiration
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Look up the user in the database to confirm they still exist
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


# Convenience type aliases — use these in route handlers for cleaner signatures:
#   async def my_route(user: CurrentUser, db: DB): ...
CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]

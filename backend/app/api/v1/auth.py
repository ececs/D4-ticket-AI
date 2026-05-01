"""
Authentication routes — Google OAuth 2.0 flow.

OAuth 2.0 Authorization Code Flow:
  1. Client calls GET /auth/google  →  redirected to Google's consent screen.
  2. User grants permission → Google redirects to GET /auth/callback?code=...
  3. Backend exchanges the code for a Google access token.
  4. Backend fetches the user's profile from Google (email, name, avatar).
  5. Backend upserts the user in our DB (create on first login, fetch on subsequent).
  6. Backend issues our own JWT and returns it to the frontend.

Why a backend-handled OAuth flow (not NextAuth.js on the frontend)?
  - Keeps Google credentials (client_secret) on the server — never exposed to browser.
  - The JWT is stored in an HttpOnly cookie, protecting against XSS attacks.
  - The FastAPI backend remains the single source of truth for auth.

Library: Authlib — the most complete OAuth2 library for Python.
"""

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.core.dependencies import CurrentUser, DB
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Configure Authlib OAuth client with Google's OIDC endpoints
oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    # server_metadata_url fetches Google's well-known OIDC config automatically
    # (authorization_endpoint, token_endpoint, userinfo_endpoint, etc.)
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile",  # Request basic profile + email from Google
    },
)


@router.get("/google", summary="Initiate Google OAuth login")
async def login_google(request: Request):
    """
    Redirect the user to Google's OAuth consent screen.

    The redirect_uri must match one of the URIs registered in Google Cloud Console.
    After the user grants permission, Google redirects back to /auth/callback.
    """
    redirect_uri = f"{settings.BACKEND_URL}/api/v1/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback", summary="Google OAuth callback")
async def auth_callback(request: Request, response: Response, db: DB):
    """
    Handle the OAuth callback from Google.

    Exchanges the authorization code for tokens, fetches the user profile,
    upserts the user in our database, and issues a JWT stored as an HttpOnly cookie.

    The HttpOnly flag prevents JavaScript from reading the cookie (XSS protection).
    Redirects the browser to the frontend dashboard after successful login.
    """
    # Exchange the authorization code for an access token + ID token
    token = await oauth.google.authorize_access_token(request)

    # Extract the user profile from the ID token (already verified by Authlib)
    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(status_code=400, detail="Could not retrieve user info from Google")

    email: str = user_info["email"]
    name: str = user_info.get("name", email)
    avatar_url: str | None = user_info.get("picture")

    # Upsert the user: fetch existing or create new on first login
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(email=email, name=name, avatar_url=avatar_url)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        # Update profile info in case the user changed their Google name or avatar
        user.name = name
        user.avatar_url = avatar_url
        await db.commit()

    # Issue our own JWT — from this point the app is independent of Google
    access_token = create_access_token(str(user.id))

    # Redirect to the frontend dashboard with the token set as an HttpOnly cookie
    redirect = RedirectResponse(url=f"{settings.FRONTEND_URL}/board")
    redirect.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,   # Not accessible via document.cookie — XSS protection
        secure=False,    # Set to True in production (requires HTTPS)
        samesite="lax",  # Protects against CSRF while allowing top-level navigation
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return redirect


@router.post("/logout", summary="Invalidate session")
async def logout(response: Response):
    """
    Clear the session cookie, effectively logging the user out.

    Note: JWTs are stateless — we can't truly "invalidate" them on the server.
    Clearing the cookie prevents the browser from sending the token in future requests.
    For stricter security, a token blocklist (Redis) could be added.
    """
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserOut, summary="Get current user profile")
async def get_me(current_user: CurrentUser):
    """
    Return the authenticated user's profile.

    Used by the frontend on page load to check if the session is still valid
    and to populate the user avatar/name in the header.
    """
    return current_user

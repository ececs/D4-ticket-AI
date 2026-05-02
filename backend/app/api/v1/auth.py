"""
Authentication routes — Google OAuth 2.0 flow (stateless, no server-side sessions).

OAuth 2.0 Authorization Code Flow:
  1. GET /auth/google  →  generates a signed state cookie + redirects to Google.
  2. User grants permission → Google redirects to GET /auth/callback?code=...&state=...
  3. Backend verifies state cookie, exchanges code for tokens via Google's token endpoint.
  4. Backend fetches user profile, upserts the user in our DB.
  5. Backend issues our JWT as an HttpOnly cookie and redirects to the frontend.

State management: instead of server-side sessions (which require SessionMiddleware and
sticky sessions), we store the OAuth state in a short-lived signed HttpOnly cookie.
The state is validated in the callback before the code exchange.
"""

import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import CurrentUser, DB
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserOut
from pydantic import BaseModel, Field

router = APIRouter(prefix="/auth", tags=["Authentication"])

class DemoLoginRequest(BaseModel):
    code: str = Field(..., description="The secret demo access code")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

_is_https = settings.BACKEND_URL.startswith("https")


@router.get("/google", summary="Initiate Google OAuth login")
async def login_google():
    """
    Redirect the user to Google's OAuth consent screen.

    Generates a random state token, sets it as a short-lived HttpOnly cookie
    (no server-side session required), and redirects to Google.
    """
    state = secrets.token_urlsafe(32)
    redirect_uri = f"{settings.BACKEND_URL}/api/v1/auth/callback"

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
    }

    redirect = RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{urlencode(params)}")
    redirect.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=_is_https,
        samesite="lax",
        max_age=300,  # 5 minutes — more than enough to complete the OAuth flow
    )
    return redirect


@router.get("/callback", summary="Google OAuth callback")
async def auth_callback(
    request: Request,
    db: DB,
    code: str,
    state: str,
    oauth_state: str | None = Cookie(default=None),
):
    """
    Handle the OAuth callback from Google.

    Verifies the state cookie, exchanges the authorization code for tokens,
    fetches the user profile, upserts the user, and issues our JWT as an
    HttpOnly cookie before redirecting to the frontend dashboard.
    """
    if not oauth_state or state != oauth_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state — possible CSRF attack")

    redirect_uri = f"{settings.BACKEND_URL}/api/v1/auth/callback"

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        })

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to obtain access token from Google")

    async with httpx.AsyncClient() as client:
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    user_info = userinfo_resp.json()
    email: str = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Could not retrieve email from Google")

    # --- Whitelist Check ---
    allowed = False
    if settings.ALLOWED_EMAILS == ["*"]:
        allowed = True
    else:
        for pattern in settings.ALLOWED_EMAILS:
            if pattern.startswith("@") and email.endswith(pattern):
                allowed = True
                break
            if email == pattern:
                allowed = True
                break

    if not allowed:
        logger.warning(f"Restricted access attempt by: {email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Acceso restringido. Tu correo o dominio no está en la lista de permitidos."
        )

    name: str = user_info.get("name", email)
    avatar_url: str | None = user_info.get("picture")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(email=email, name=name, avatar_url=avatar_url)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        user.name = name
        user.avatar_url = avatar_url
        await db.commit()

    jwt_token = create_access_token(str(user.id))

    # Redirect to the frontend's /api/auth/callback route which sets the cookie
    # on the frontend domain (necessary because backend and frontend are on different
    # domains — cookies set by the backend cannot be read by the frontend browser).
    redirect = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/api/auth/callback?token={jwt_token}"
    )
    redirect.delete_cookie("oauth_state")
    return redirect


@router.post("/logout", summary="Invalidate session")
async def logout(response: Response):
    """Clear the JWT cookie, logging the user out."""
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}


@router.post("/demo-login", summary="Login with a secret demo code")
async def demo_login(body: DemoLoginRequest, db: DB):
    """
    Allow access via a pre-configured secret code.
    Useful for evaluators who don't want to use Google OAuth.
    """
    if not settings.DEMO_ACCESS_CODE or body.code != settings.DEMO_ACCESS_CODE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código de acceso incorrecto o no configurado."
        )

    # Use a fixed email for the demo user
    demo_email = "evaluator@demo.local"
    result = await db.execute(select(User).where(User.email == demo_email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            email=demo_email,
            name="Evaluador Orbidi",
            avatar_url="https://api.dicebear.com/7.x/bottts/svg?seed=orbidi"
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    jwt_token = create_access_token(str(user.id))
    return {"token": jwt_token}


@router.get("/me", response_model=UserOut, summary="Get current user profile")
async def get_me(current_user: CurrentUser):
    """Return the authenticated user's profile."""
    return current_user

"""
JWT token utilities.

We use JSON Web Tokens (JWT) for stateless authentication.
After a successful Google OAuth login, we issue a JWT that the client stores
and sends with every request (either as a Bearer token or an HttpOnly cookie).

The token contains:
  - sub: the user's UUID (as string)
  - exp: expiration timestamp

We use HS256 (HMAC-SHA256) — symmetric signing. The SECRET_KEY must be kept secret.
"""

from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from .config import settings


def create_access_token(subject: str) -> str:
    """
    Create a signed JWT for the given subject (user ID).

    Args:
        subject: The user's UUID as a string. Used as the 'sub' claim.

    Returns:
        A signed JWT string valid for ACCESS_TOKEN_EXPIRE_MINUTES.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """
    Decode and verify a JWT, returning the subject (user ID) if valid.

    Args:
        token: The JWT string to verify.

    Returns:
        The 'sub' claim (user ID string) if the token is valid and not expired.
        None if the token is invalid, expired, or tampered with.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        # Covers: expired tokens, invalid signature, malformed tokens
        return None

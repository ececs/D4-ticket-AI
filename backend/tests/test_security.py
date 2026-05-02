from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token


def test_create_and_decode_token():
    token = create_access_token("user-123")
    assert decode_access_token(token) == "user-123"


def test_decode_invalid_token_returns_none():
    assert decode_access_token("not.a.valid.token") is None


def test_decode_empty_string_returns_none():
    assert decode_access_token("") is None


def test_decode_tampered_token_returns_none():
    token = create_access_token("user-123")
    tampered = token[:-5] + "XXXXX"
    assert decode_access_token(tampered) is None


def test_decode_expired_token_returns_none():
    expire = datetime.now(timezone.utc) - timedelta(minutes=1)
    payload = {"sub": "user-123", "exp": expire}
    expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    assert decode_access_token(expired_token) is None


def test_token_subject_is_preserved():
    subject = str("550e8400-e29b-41d4-a716-446655440000")
    token = create_access_token(subject)
    assert decode_access_token(token) == subject

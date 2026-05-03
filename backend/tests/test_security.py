"""
Security and validation tests.

Covers:
  - JWT creation, decoding, and tamper-resistance
  - Input validation (UUID format, enum values, out-of-range pagination)
  - Authentication guards across all core endpoints
"""

import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token
from httpx import AsyncClient


# ── JWT ───────────────────────────────────────────────────────────────────────

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


# ── UUID validation (tickets) ─────────────────────────────────────────────────

async def test_get_ticket_with_invalid_uuid_returns_422(client: AsyncClient):
    r = await client.get("/api/v1/tickets/not-a-uuid")
    assert r.status_code == 422


async def test_update_ticket_with_invalid_uuid_returns_422(client: AsyncClient):
    r = await client.patch("/api/v1/tickets/bad-uuid", json={"title": "X"})
    assert r.status_code == 422


async def test_delete_ticket_with_invalid_uuid_returns_422(client: AsyncClient):
    r = await client.delete("/api/v1/tickets/bad-uuid")
    assert r.status_code == 422


# ── Enum validation ───────────────────────────────────────────────────────────

async def test_update_ticket_invalid_status_returns_422(client: AsyncClient):
    """TicketUpdate.status is a TicketStatus enum — invalid values are rejected."""
    r = await client.post("/api/v1/tickets", json={"title": "T"})
    assert r.status_code == 201
    ticket_id = r.json()["id"]
    r = await client.patch(f"/api/v1/tickets/{ticket_id}", json={"status": "nonexistent_status"})
    assert r.status_code == 422


async def test_create_ticket_invalid_priority_returns_422(client: AsyncClient):
    r = await client.post("/api/v1/tickets", json={"title": "T", "priority": "ultra_high"})
    assert r.status_code == 422


async def test_list_tickets_invalid_status_filter_returns_422(client: AsyncClient):
    r = await client.get("/api/v1/tickets?status=invalid")
    assert r.status_code == 422


# ── Pagination bounds ─────────────────────────────────────────────────────────

async def test_list_tickets_page_zero_returns_422(client: AsyncClient):
    """Page must be >= 1."""
    r = await client.get("/api/v1/tickets?page=0")
    assert r.status_code == 422


async def test_list_tickets_size_above_max_returns_422(client: AsyncClient):
    """Page size must be <= 100."""
    r = await client.get("/api/v1/tickets?size=101")
    assert r.status_code == 422


async def test_list_tickets_negative_page_returns_422(client: AsyncClient):
    r = await client.get("/api/v1/tickets?page=-1")
    assert r.status_code == 422


# ── Auth guards ───────────────────────────────────────────────────────────────

async def test_tickets_require_auth(unauth_client: AsyncClient):
    r = await unauth_client.get("/api/v1/tickets")
    assert r.status_code == 401


async def test_create_ticket_requires_auth(unauth_client: AsyncClient):
    r = await unauth_client.post("/api/v1/tickets", json={"title": "T"})
    assert r.status_code == 401


async def test_notifications_require_auth(unauth_client: AsyncClient):
    r = await unauth_client.get("/api/v1/notifications")
    assert r.status_code == 401


async def test_users_require_auth(unauth_client: AsyncClient):
    r = await unauth_client.get("/api/v1/users")
    assert r.status_code == 401


async def test_knowledge_ingest_requires_auth(unauth_client: AsyncClient):
    r = await unauth_client.post("/api/v1/knowledge", json={"url": "https://example.com"})
    assert r.status_code == 401

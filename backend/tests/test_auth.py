"""
Tests for the Authentication API.

Orbidi spec requirement: Login via Google SSO (OAuth 2.0).
On first login, the user is automatically registered with name, email, and avatar.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.user import User


# ── Health ────────────────────────────────────────────────────────────────────

async def test_health_check(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


# ── /auth/me ──────────────────────────────────────────────────────────────────

async def test_me_returns_current_user(client: AsyncClient, test_user: User):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == test_user.email
    assert data["name"] == test_user.name
    assert data["id"] == str(test_user.id)


async def test_me_response_includes_required_fields(client: AsyncClient):
    """User schema: id, name, email, avatar_url — all required by Orbidi spec."""
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 200
    data = r.json()
    for field in ("id", "name", "email"):
        assert field in data, f"Missing field: {field}"
    # avatar_url is optional but must be present in the schema (can be None)
    assert "avatar_url" in data


async def test_me_without_token_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_with_invalid_token_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert r.status_code == 401


# ── /auth/google ──────────────────────────────────────────────────────────────

async def test_google_oauth_initiates_redirect(unauth_client: AsyncClient):
    """
    GET /auth/google must redirect to Google's OAuth consent screen.
    The state cookie must be set for CSRF protection.
    """
    r = await unauth_client.get("/api/v1/auth/google", follow_redirects=False)
    assert r.status_code in (302, 307)
    location = r.headers.get("location", "")
    assert "accounts.google.com" in location
    assert "client_id" in location
    assert "redirect_uri" in location
    assert "state" in location


async def test_google_oauth_sets_state_cookie(unauth_client: AsyncClient):
    """State cookie must be set to prevent CSRF in the OAuth flow."""
    r = await unauth_client.get("/api/v1/auth/google", follow_redirects=False)
    assert "oauth_state" in r.cookies


# ── /auth/logout ──────────────────────────────────────────────────────────────

async def test_logout_clears_auth_cookie(client: AsyncClient):
    """POST /auth/logout must clear the access_token cookie."""
    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 200
    # Cookie should be cleared (max-age=0 or expires in the past)
    set_cookie = r.headers.get("set-cookie", "")
    assert "access_token" in set_cookie


async def test_logout_is_idempotent_for_unauthenticated(unauth_client: AsyncClient):
    """Logout is a stateless cookie-clear operation; no auth required."""
    r = await unauth_client.post("/api/v1/auth/logout")
    assert r.status_code == 200


# ── /auth/demo-login ──────────────────────────────────────────────────────────

async def test_demo_login_valid_code_returns_token(unauth_client: AsyncClient):
    """Demo login with the correct code returns a JWT token."""
    with patch("app.core.config.settings.DEMO_ACCESS_CODE", "secret123"):
        with patch(
            "app.services.cache_service.is_rate_limited",
            new_callable=AsyncMock,
            return_value=False,
        ):
            r = await unauth_client.post(
                "/api/v1/auth/demo-login", json={"code": "secret123"}
            )
    assert r.status_code in (200, 201)
    data = r.json()
    assert "token" in data
    assert isinstance(data["token"], str)
    assert len(data["token"]) > 20


async def test_demo_login_invalid_code_returns_401(unauth_client: AsyncClient):
    with patch("app.core.config.settings.DEMO_ACCESS_CODE", "secret123"):
        with patch(
            "app.services.cache_service.is_rate_limited",
            new_callable=AsyncMock,
            return_value=False,
        ):
            r = await unauth_client.post(
                "/api/v1/auth/demo-login", json={"code": "wrong-code"}
            )
    assert r.status_code == 401


async def test_demo_login_missing_code_returns_422(unauth_client: AsyncClient):
    r = await unauth_client.post("/api/v1/auth/demo-login", json={})
    assert r.status_code == 422


async def test_demo_login_disabled_when_no_code_configured(unauth_client: AsyncClient):
    """If DEMO_ACCESS_CODE is empty, demo login must be disabled."""
    with patch("app.core.config.settings.DEMO_ACCESS_CODE", ""):
        r = await unauth_client.post(
            "/api/v1/auth/demo-login", json={"code": "anything"}
        )
    assert r.status_code in (400, 401, 404)


async def test_demo_login_rate_limited_returns_429(unauth_client: AsyncClient):
    """After 5 failed attempts in 15 minutes, further attempts must be blocked."""
    with patch("app.core.config.settings.DEMO_ACCESS_CODE", "secret123"):
        with patch(
            "app.services.cache_service.is_rate_limited",
            new_callable=AsyncMock,
            return_value=True,
        ):
            r = await unauth_client.post(
                "/api/v1/auth/demo-login", json={"code": "secret123"}
            )
    assert r.status_code == 429

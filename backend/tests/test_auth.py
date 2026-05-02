import pytest
from httpx import AsyncClient

from app.models.user import User


async def test_health_check(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_me_returns_current_user(client: AsyncClient, test_user: User):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == test_user.email
    assert data["name"] == test_user.name
    assert str(test_user.id) == data["id"]


async def test_me_without_token_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_with_invalid_token_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert r.status_code == 401

from httpx import AsyncClient

from app.models.user import User


async def test_list_users_returns_current_user(client: AsyncClient, test_user: User):
    r = await client.get("/api/v1/users")
    assert r.status_code == 200
    users = r.json()
    ids = [u["id"] for u in users]
    assert str(test_user.id) in ids


async def test_list_users_includes_all_users(
    client: AsyncClient,
    test_user: User,
    second_user: User,
):
    r = await client.get("/api/v1/users")
    assert r.status_code == 200
    ids = [u["id"] for u in r.json()]
    assert str(test_user.id) in ids
    assert str(second_user.id) in ids


async def test_list_users_without_auth_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.get("/api/v1/users")
    assert r.status_code == 401


async def test_list_users_response_shape(client: AsyncClient, test_user: User):
    r = await client.get("/api/v1/users")
    user = next(u for u in r.json() if u["id"] == str(test_user.id))
    assert "id" in user
    assert "name" in user
    assert "email" in user

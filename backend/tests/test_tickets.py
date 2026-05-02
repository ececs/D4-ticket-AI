import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


# ── helpers ──────────────────────────────────────────────────────────────────

async def _create_ticket(client: AsyncClient, **kwargs) -> dict:
    payload = {"title": "Default title", "priority": "medium", **kwargs}
    r = await client.post("/api/v1/tickets", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ── create ────────────────────────────────────────────────────────────────────

async def test_create_ticket_returns_201(client: AsyncClient):
    r = await client.post("/api/v1/tickets", json={"title": "My ticket", "priority": "high"})
    assert r.status_code == 201


async def test_create_ticket_defaults(client: AsyncClient, test_user: User):
    data = await _create_ticket(client, title="New ticket")
    assert data["title"] == "New ticket"
    assert data["status"] == "open"
    assert data["priority"] == "medium"
    assert data["author_id"] == str(test_user.id)
    assert data["assignee_id"] is None


async def test_create_ticket_with_description(client: AsyncClient):
    data = await _create_ticket(client, title="T", description="Some details")
    assert data["description"] == "Some details"


async def test_create_ticket_with_assignee(client: AsyncClient, test_user: User):
    data = await _create_ticket(client, title="T", assignee_id=str(test_user.id))
    assert data["assignee_id"] == str(test_user.id)


async def test_create_ticket_invalid_assignee_returns_404(client: AsyncClient):
    r = await client.post(
        "/api/v1/tickets",
        json={"title": "T", "assignee_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404


async def test_create_ticket_missing_title_returns_422(client: AsyncClient):
    r = await client.post("/api/v1/tickets", json={"priority": "low"})
    assert r.status_code == 422


# ── list ──────────────────────────────────────────────────────────────────────

async def test_list_tickets_empty(client: AsyncClient):
    r = await client.get("/api/v1/tickets")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0


async def test_list_tickets_returns_created(client: AsyncClient):
    await _create_ticket(client, title="Alpha")
    await _create_ticket(client, title="Beta")
    r = await client.get("/api/v1/tickets")
    assert r.json()["total"] == 2


async def test_list_tickets_filter_by_status(client: AsyncClient):
    t = await _create_ticket(client, title="Open one")
    await client.patch(f"/api/v1/tickets/{t['id']}", json={"status": "closed"})
    await _create_ticket(client, title="Still open")

    r = await client.get("/api/v1/tickets?status=open")
    items = r.json()["items"]
    assert all(i["status"] == "open" for i in items)
    assert len(items) == 1


async def test_list_tickets_filter_by_priority(client: AsyncClient):
    await _create_ticket(client, title="Low prio", priority="low")
    await _create_ticket(client, title="Critical prio", priority="critical")

    r = await client.get("/api/v1/tickets?priority=critical")
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["priority"] == "critical"


async def test_list_tickets_search_by_title(client: AsyncClient):
    await _create_ticket(client, title="Login bug fix")
    await _create_ticket(client, title="Performance improvement")

    r = await client.get("/api/v1/tickets?search=login")
    items = r.json()["items"]
    assert len(items) == 1
    assert "login" in items[0]["title"].lower()


async def test_list_tickets_search_by_description(client: AsyncClient):
    await _create_ticket(client, title="Issue A", description="database migration fails")
    await _create_ticket(client, title="Issue B", description="UI rendering glitch")

    r = await client.get("/api/v1/tickets?search=migration")
    assert r.json()["total"] == 1


async def test_list_tickets_pagination(client: AsyncClient):
    for i in range(5):
        await _create_ticket(client, title=f"Ticket {i}")

    r = await client.get("/api/v1/tickets?page=1&size=2")
    body = r.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["size"] == 2


async def test_list_tickets_pagination_last_page(client: AsyncClient):
    for i in range(5):
        await _create_ticket(client, title=f"T{i}")

    r = await client.get("/api/v1/tickets?page=3&size=2")
    assert len(r.json()["items"]) == 1


async def test_list_tickets_sort_asc(client: AsyncClient):
    await _create_ticket(client, title="Z ticket")
    await _create_ticket(client, title="A ticket")

    r = await client.get("/api/v1/tickets?sort_by=title&order=asc")
    titles = [i["title"] for i in r.json()["items"]]
    assert titles == sorted(titles)


async def test_list_tickets_filter_by_assignee(client: AsyncClient, test_user: User):
    await _create_ticket(client, title="Assigned", assignee_id=str(test_user.id))
    await _create_ticket(client, title="Unassigned")

    r = await client.get(f"/api/v1/tickets?assignee_id={test_user.id}")
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Assigned"


# ── get ───────────────────────────────────────────────────────────────────────

async def test_get_ticket_returns_200(client: AsyncClient):
    created = await _create_ticket(client, title="Detail ticket")
    r = await client.get(f"/api/v1/tickets/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


async def test_get_ticket_not_found_returns_404(client: AsyncClient):
    r = await client.get(f"/api/v1/tickets/{uuid.uuid4()}")
    assert r.status_code == 404


# ── update ────────────────────────────────────────────────────────────────────

async def test_update_ticket_title(client: AsyncClient):
    created = await _create_ticket(client, title="Original")
    r = await client.patch(f"/api/v1/tickets/{created['id']}", json={"title": "Updated"})
    assert r.status_code == 200
    assert r.json()["title"] == "Updated"


async def test_update_ticket_status(client: AsyncClient):
    created = await _create_ticket(client)
    r = await client.patch(f"/api/v1/tickets/{created['id']}", json={"status": "in_progress"})
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"


async def test_update_ticket_partial_only_changes_given_fields(client: AsyncClient):
    created = await _create_ticket(client, title="Keep me", priority="high")
    r = await client.patch(f"/api/v1/tickets/{created['id']}", json={"status": "closed"})
    data = r.json()
    assert data["title"] == "Keep me"
    assert data["priority"] == "high"
    assert data["status"] == "closed"


async def test_update_ticket_not_found_returns_404(client: AsyncClient):
    r = await client.patch(f"/api/v1/tickets/{uuid.uuid4()}", json={"title": "X"})
    assert r.status_code == 404


async def test_update_ticket_invalid_status_returns_422(client: AsyncClient):
    created = await _create_ticket(client)
    r = await client.patch(f"/api/v1/tickets/{created['id']}", json={"status": "nonexistent"})
    assert r.status_code == 422


# ── delete ────────────────────────────────────────────────────────────────────

async def test_delete_ticket_returns_204(client: AsyncClient):
    created = await _create_ticket(client)
    r = await client.delete(f"/api/v1/tickets/{created['id']}")
    assert r.status_code == 204


async def test_delete_ticket_removes_it(client: AsyncClient):
    created = await _create_ticket(client)
    await client.delete(f"/api/v1/tickets/{created['id']}")
    r = await client.get(f"/api/v1/tickets/{created['id']}")
    assert r.status_code == 404


async def test_delete_ticket_not_found_returns_404(client: AsyncClient):
    r = await client.delete(f"/api/v1/tickets/{uuid.uuid4()}")
    assert r.status_code == 404


# ── auth guard ────────────────────────────────────────────────────────────────

async def test_list_tickets_without_auth_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.get("/api/v1/tickets")
    assert r.status_code == 401


async def test_create_ticket_without_auth_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.post("/api/v1/tickets", json={"title": "T"})
    assert r.status_code == 401

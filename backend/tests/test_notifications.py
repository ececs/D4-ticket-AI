import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType
from app.models.user import User


async def _create_ticket(client: AsyncClient, **kwargs) -> dict:
    r = await client.post("/api/v1/tickets", json={"title": "T", **kwargs})
    assert r.status_code == 201
    return r.json()


# ── list ──────────────────────────────────────────────────────────────────────

async def test_list_notifications_empty(client: AsyncClient):
    r = await client.get("/api/v1/notifications")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_notifications_without_auth_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.get("/api/v1/notifications")
    assert r.status_code == 401


# ── event-driven creation ─────────────────────────────────────────────────────

async def test_status_change_creates_notification(client: AsyncClient, test_user: User):
    ticket = await _create_ticket(client, title="Status ticket")
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "in_progress"})

    r = await client.get("/api/v1/notifications")
    notifications = r.json()
    # Filter: look for the status_changed notification for the status transition (not ticket creation)
    status_notifs = [
        n for n in notifications
        if n["type"] == "status_changed" and "In Progress" in n["message"]
    ]
    assert len(status_notifs) == 1
    assert status_notifs[0]["ticket_id"] == ticket["id"]
    assert status_notifs[0]["read"] is False


async def test_comment_creates_notification(client: AsyncClient):
    ticket = await _create_ticket(client, title="Comment ticket")
    await client.post(
        f"/api/v1/tickets/{ticket['id']}/comments",
        json={"content": "First comment"},
    )

    r = await client.get("/api/v1/notifications")
    types = [n["type"] for n in r.json()]
    assert "commented" in types


async def test_assign_ticket_creates_notification(client: AsyncClient, test_user: User):
    ticket = await _create_ticket(client, title="Assign ticket")
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"assignee_id": str(test_user.id)})

    r = await client.get("/api/v1/notifications")
    types = [n["type"] for n in r.json()]
    assert "assigned" in types


async def test_multiple_events_create_multiple_notifications(client: AsyncClient):
    ticket = await _create_ticket(client, title="Multi-event")
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "in_progress"})
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "closed"})

    r = await client.get("/api/v1/notifications")
    # 1 from ticket creation + 2 from status changes
    assert len(r.json()) >= 2
    types = [n["type"] for n in r.json()]
    assert types.count("status_changed") >= 2


async def test_notifications_ordered_newest_first(client: AsyncClient):
    ticket = await _create_ticket(client, title="Order test")
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "in_progress"})
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "closed"})

    notifications = (await client.get("/api/v1/notifications")).json()
    # Most recent first: closed before in_progress
    assert notifications[0]["message"] != "" and notifications[1]["message"] != ""


# ── mark read ─────────────────────────────────────────────────────────────────

async def test_mark_notification_read(client: AsyncClient):
    ticket = await _create_ticket(client)
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "closed"})

    notifications = (await client.get("/api/v1/notifications")).json()
    notification_id = notifications[0]["id"]
    assert notifications[0]["read"] is False

    r = await client.patch(f"/api/v1/notifications/{notification_id}/read")
    assert r.status_code == 200

    updated = (await client.get("/api/v1/notifications")).json()
    target = next(n for n in updated if n["id"] == notification_id)
    assert target["read"] is True


async def test_mark_all_notifications_read(client: AsyncClient):
    ticket = await _create_ticket(client)
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "in_progress"})
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "closed"})

    r = await client.patch("/api/v1/notifications/read-all")
    assert r.status_code == 200

    notifications = (await client.get("/api/v1/notifications")).json()
    assert all(n["read"] is True for n in notifications)


async def test_mark_all_read_on_empty_is_ok(client: AsyncClient):
    r = await client.patch("/api/v1/notifications/read-all")
    assert r.status_code == 200


# ── seeded notifications ──────────────────────────────────────────────────────

async def test_notifications_limit_param(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    ticket = await _create_ticket(client)

    # Insert 10 notifications directly
    for i in range(10):
        n = Notification(
            user_id=test_user.id,
            type=NotificationType.status_changed,
            ticket_id=uuid.UUID(ticket["id"]),
            message=f"Notification {i}",
        )
        db_session.add(n)
    await db_session.commit()

    r = await client.get("/api/v1/notifications?limit=3")
    assert len(r.json()) == 3

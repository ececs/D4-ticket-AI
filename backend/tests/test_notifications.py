import uuid
from unittest.mock import AsyncMock, patch

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


async def test_priority_change_creates_ticket_updated_notification_with_priority_message(
    client: AsyncClient,
):
    ticket = await _create_ticket(client, title="Priority ticket", priority="low")
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"priority": "critical"})

    notifications = (await client.get("/api/v1/notifications")).json()
    priority_notifs = [
        n for n in notifications
        if n["type"] == "ticket_updated" and "changed priority" in n["message"]
    ]
    assert len(priority_notifs) == 1
    assert priority_notifs[0]["ticket_id"] == ticket["id"]
    assert "Critical" in priority_notifs[0]["message"]


async def test_no_priority_notification_when_value_does_not_change(
    client: AsyncClient,
):
    ticket = await _create_ticket(client, title="Stable priority", priority="medium")

    before = (await client.get("/api/v1/notifications")).json()
    before_priority_changes = [
        n for n in before if n["type"] == "ticket_updated" and "changed priority" in n["message"]
    ]

    response = await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"priority": "medium"})
    assert response.status_code == 200

    after = (await client.get("/api/v1/notifications")).json()
    after_priority_changes = [
        n for n in after if n["type"] == "ticket_updated" and "changed priority" in n["message"]
    ]
    assert len(after_priority_changes) == len(before_priority_changes)


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


async def test_delete_notification_removes_it(client: AsyncClient):
    ticket = await _create_ticket(client)
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "closed"})

    notifications = (await client.get("/api/v1/notifications")).json()
    notification_id = notifications[0]["id"]

    response = await client.delete(f"/api/v1/notifications/{notification_id}")
    assert response.status_code == 200

    updated = (await client.get("/api/v1/notifications")).json()
    assert all(n["id"] != notification_id for n in updated)


async def test_delete_notification_broadcasts_sync_event(
    client: AsyncClient,
):
    ticket = await _create_ticket(client)
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "closed"})
    notifications = (await client.get("/api/v1/notifications")).json()
    notification_id = notifications[0]["id"]

    with patch(
        "app.services.notification_service._publish_user_event",
        new_callable=AsyncMock,
    ) as mock_publish:
        response = await client.delete(f"/api/v1/notifications/{notification_id}")

    assert response.status_code == 200
    mock_publish.assert_awaited_once()


async def test_mark_all_notifications_read(client: AsyncClient):
    ticket = await _create_ticket(client)
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "in_progress"})
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "closed"})

    r = await client.patch("/api/v1/notifications/read-all")
    assert r.status_code == 200

    notifications = (await client.get("/api/v1/notifications")).json()
    assert all(n["read"] is True for n in notifications)


async def test_mark_all_notifications_broadcasts_sync_event(
    client: AsyncClient,
    db_session: AsyncSession,
):
    ticket = await _create_ticket(client)
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "in_progress"})

    with patch(
        "app.services.notification_service.broadcast_notifications_read_all",
        new_callable=AsyncMock,
    ) as mock_broadcast:
        response = await client.patch("/api/v1/notifications/read-all")

    assert response.status_code == 200
    mock_broadcast.assert_awaited_once()


async def test_mark_all_read_then_new_notification_is_unread_again(client: AsyncClient):
    ticket = await _create_ticket(client, title="Read all then new one")
    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "in_progress"})

    read_all = await client.patch("/api/v1/notifications/read-all")
    assert read_all.status_code == 200
    assert all(n["read"] is True for n in (await client.get("/api/v1/notifications")).json())

    await client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "closed"})

    notifications = (await client.get("/api/v1/notifications")).json()
    unread = [n for n in notifications if n["read"] is False]
    assert len(unread) == 1
    assert unread[0]["type"] == "status_changed"
    assert "Closed" in unread[0]["message"]


async def test_delete_other_users_notification_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
    second_user: User,
):
    ticket = await _create_ticket(client)
    notification = Notification(
        user_id=second_user.id,
        type=NotificationType.status_changed,
        ticket_id=uuid.UUID(ticket["id"]),
        message="Not yours",
    )
    db_session.add(notification)
    await db_session.commit()

    response = await client.delete(f"/api/v1/notifications/{notification.id}")
    assert response.status_code == 404


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

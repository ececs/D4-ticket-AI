import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy import select

from app.models.notification import Notification, NotificationType
from app.models.ticket import Ticket, TicketPriority


async def _create_ticket(client: AsyncClient, **kwargs) -> dict:
    payload = {"title": "Strict test ticket", "priority": "medium", **kwargs}
    response = await client.post("/api/v1/tickets", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _parse_sse_payloads(raw: str) -> list[dict]:
    events: list[dict] = []
    for line in raw.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if not payload:
            continue
        events.append(json.loads(payload))
    return events


class _StubAgent:
    def __init__(self, events=None, state=None, error: Exception | None = None):
        self._events = events or []
        self._state = state or {}
        self._error = error

    async def astream_events(self, initial_state, version="v2", config=None):
        if self._error is not None:
            raise self._error
        for event in self._events:
            yield event

    async def aget_state(self, config):
        return SimpleNamespace(values=self._state)


class _StubCheckpointer:
    def __init__(self, state):
        self._state = state

    async def aget(self, config):
        return self._state


async def test_create_ticket_blank_title_returns_422(client: AsyncClient):
    response = await client.post(
        "/api/v1/tickets",
        json={"title": "", "description": "Should not accept blank titles."},
    )
    assert response.status_code == 422


async def test_create_comment_blank_content_returns_422(client: AsyncClient):
    ticket = await _create_ticket(client)
    response = await client.post(
        f"/api/v1/tickets/{ticket['id']}/comments",
        json={"content": ""},
    )
    assert response.status_code == 422


async def test_delete_ticket_forbidden_for_non_author(
    second_client: AsyncClient,
    db_session,
    test_user,
):
    ticket = Ticket(
        title="Author-owned ticket",
        description="Only the author should be able to delete this.",
        priority=TicketPriority.medium,
        author_id=test_user.id,
    )
    db_session.add(ticket)
    await db_session.commit()

    response = await second_client.delete(f"/api/v1/tickets/{ticket.id}")
    assert response.status_code == 403


async def test_delete_ticket_preserves_a_history_notification_with_null_ticket_id(
    client: AsyncClient,
):
    ticket = await _create_ticket(client, title="Ticket to delete")

    response = await client.delete(f"/api/v1/tickets/{ticket['id']}")
    assert response.status_code == 204

    notifications = (await client.get("/api/v1/notifications")).json()
    deletion_notifs = [
        notification
        for notification in notifications
        if "eliminado" in notification["message"].lower()
    ]
    assert len(deletion_notifs) == 1
    assert deletion_notifs[0]["ticket_id"] is None
    assert "Ticket to delete" in deletion_notifs[0]["message"]


async def test_notifications_list_is_scoped_to_current_user(
    client: AsyncClient,
    db_session,
    test_user,
    second_user,
):
    ticket = Ticket(
        title="Notification scope ticket",
        description="Used to seed scoped notifications.",
        priority=TicketPriority.medium,
        author_id=test_user.id,
    )
    db_session.add(ticket)
    await db_session.commit()

    db_session.add_all(
        [
            Notification(
                user_id=test_user.id,
                type=NotificationType.status_changed,
                ticket_id=ticket.id,
                message="Visible to current user",
            ),
            Notification(
                user_id=second_user.id,
                type=NotificationType.status_changed,
                ticket_id=ticket.id,
                message="Must stay hidden",
            ),
        ]
    )
    await db_session.commit()

    payload = (await client.get("/api/v1/notifications")).json()
    messages = {item["message"] for item in payload}
    assert "Visible to current user" in messages
    assert "Must stay hidden" not in messages


async def test_mark_read_cannot_modify_another_users_notification(
    client: AsyncClient,
    db_session,
    test_user,
    second_user,
):
    ticket = Ticket(
        title="Other user's notification ticket",
        description="Seed for notification ownership.",
        priority=TicketPriority.medium,
        author_id=test_user.id,
    )
    db_session.add(ticket)
    await db_session.commit()

    notification = Notification(
        user_id=second_user.id,
        type=NotificationType.status_changed,
        ticket_id=ticket.id,
        message="Private notification",
    )
    db_session.add(notification)
    await db_session.commit()

    response = await client.patch(f"/api/v1/notifications/{notification.id}/read")
    assert response.status_code == 404

    refreshed = await db_session.execute(
        select(Notification).where(Notification.id == notification.id)
    )
    assert refreshed.scalar_one().read is False


async def test_mark_all_read_only_updates_current_users_notifications(
    client: AsyncClient,
    db_session,
    test_user,
    second_user,
):
    own_ticket = Ticket(
        title="Current user notification ticket",
        description="Seed current user notification.",
        priority=TicketPriority.medium,
        author_id=test_user.id,
    )
    other_ticket = Ticket(
        title="Other user notification ticket",
        description="Seed foreign notification.",
        priority=TicketPriority.medium,
        author_id=second_user.id,
    )
    db_session.add_all([own_ticket, other_ticket])
    await db_session.commit()

    current_user_notification = Notification(
        user_id=test_user.id,
        type=NotificationType.status_changed,
        ticket_id=own_ticket.id,
        message="Current user unread",
        read=False,
    )
    other_user_notification = Notification(
        user_id=second_user.id,
        type=NotificationType.status_changed,
        ticket_id=other_ticket.id,
        message="Other user unread",
        read=False,
    )
    db_session.add_all([current_user_notification, other_user_notification])
    await db_session.commit()

    response = await client.patch("/api/v1/notifications/read-all")
    assert response.status_code == 200
    assert response.json()["count"] >= 1

    current_user_view = (await client.get("/api/v1/notifications")).json()
    current_target = next(
        item for item in current_user_view if item["id"] == str(current_user_notification.id)
    )
    assert current_target["read"] is True

    other_refreshed = await db_session.execute(
        select(Notification).where(Notification.id == other_user_notification.id)
    )
    assert other_refreshed.scalar_one().read is False


async def test_notifications_are_ordered_newest_first_strictly(
    client: AsyncClient,
    db_session,
    test_user,
):
    ticket = Ticket(
        title="Notification ordering ticket",
        description="Used to seed notification ordering.",
        priority=TicketPriority.medium,
        author_id=test_user.id,
    )
    db_session.add(ticket)
    await db_session.commit()

    now = datetime.now(timezone.utc)
    older = Notification(
        user_id=test_user.id,
        type=NotificationType.status_changed,
        ticket_id=ticket.id,
        message="Older notification",
        created_at=now - timedelta(hours=2),
    )
    newer = Notification(
        user_id=test_user.id,
        type=NotificationType.status_changed,
        ticket_id=ticket.id,
        message="Newer notification",
        created_at=now,
    )
    db_session.add_all([older, newer])
    await db_session.commit()

    payload = (await client.get("/api/v1/notifications?limit=2")).json()
    assert [item["message"] for item in payload[:2]] == [
        "Newer notification",
        "Older notification",
    ]


async def test_comment_on_assigned_ticket_notifies_author_and_assignee(
    second_client: AsyncClient,
    db_session,
    test_user,
    second_user,
):
    ticket = Ticket(
        title="Assigned workflow ticket",
        description="Used to validate comment notifications.",
        priority=TicketPriority.medium,
        author_id=test_user.id,
        assignee_id=second_user.id,
    )
    db_session.add(ticket)
    await db_session.commit()

    comment_response = await second_client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json={"content": "Looking into this now."},
    )
    assert comment_response.status_code == 201

    result = await db_session.execute(
        select(Notification).where(
            Notification.type == NotificationType.commented,
            Notification.ticket_id == ticket.id,
        )
    )
    notifications = result.scalars().all()
    recipient_ids = {notification.user_id for notification in notifications}

    assert test_user.id in recipient_ids
    assert second_user.id in recipient_ids


async def test_ai_history_returns_only_human_and_ai_messages(client: AsyncClient):
    fake_state = SimpleNamespace(
        values={
            "messages": [
                SimpleNamespace(type="human", content="Hola"),
                SimpleNamespace(type="tool", content="ignored"),
                SimpleNamespace(type="ai", content="Respuesta"),
            ]
        }
    )

    with patch("app.ai.router.get_checkpointer", return_value=_StubCheckpointer(fake_state)):
        response = await client.get("/api/v1/ai/history/thread-123")

    assert response.status_code == 200
    assert response.json() == {
        "messages": [
            {"role": "user", "content": "Hola"},
            {"role": "assistant", "content": "Respuesta"},
        ]
    }


async def test_ai_chat_stream_emits_confirmation_required_for_delete_request(
    client: AsyncClient,
):
    agent = _StubAgent(
        events=[
            {
                "event": "on_tool_end",
                "name": "delete_ticket",
                "data": {"output": "__DELETE_REQUESTED__:abc-123:Broken ticket"},
            }
        ]
    )

    with (
        patch("app.ai.router.get_checkpointer", return_value=None),
        patch("app.ai.router.build_agent", return_value=agent),
    ):
        response = await client.post(
            "/api/v1/ai/chat",
            json={"messages": [{"role": "user", "content": "borra ese ticket"}]},
        )

    assert response.status_code == 200
    events = _parse_sse_payloads(response.text)
    assert any(event["type"] == "confirmation_required" for event in events)
    confirm_event = next(event for event in events if event["type"] == "confirmation_required")
    assert confirm_event["ticket_id"] == "abc-123"
    assert confirm_event["ticket_title"] == "Broken ticket"


async def test_ai_chat_stream_returns_friendly_quota_error(client: AsyncClient):
    agent = _StubAgent(error=RuntimeError("429 quota exceeded"))

    with (
        patch("app.ai.router.get_checkpointer", return_value=None),
        patch("app.ai.router.build_agent", return_value=agent),
    ):
        response = await client.post(
            "/api/v1/ai/chat",
            json={"messages": [{"role": "user", "content": "diagnostica este ticket"}]},
        )

    assert response.status_code == 200
    events = _parse_sse_payloads(response.text)
    error_event = next(event for event in events if event["type"] == "error")
    assert "Límite de uso de IA alcanzado" in error_event["content"]
    assert events[-1]["type"] == "done"

import uuid
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket_history import TicketHistory
from app.models.user import User


async def _create_ticket(client: AsyncClient, **kwargs) -> dict:
    payload = {"title": "History ticket", "priority": "medium", **kwargs}
    response = await client.post("/api/v1/tickets", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_ticket_records_created_history_entry(
    client: AsyncClient,
    test_user: User,
):
    ticket = await _create_ticket(client, title="History created")

    response = await client.get(f"/api/v1/tickets/{ticket['id']}/history")
    assert response.status_code == 200

    history = response.json()
    assert len(history) == 1
    assert history[0]["field"] == "created"
    assert history[0]["ticket_id"] == ticket["id"]
    assert history[0]["old_value"] is None
    assert history[0]["new_value"] is None
    assert history[0]["actor"]["id"] == str(test_user.id)


async def test_update_ticket_history_records_each_changed_field(
    client: AsyncClient,
    test_user: User,
    second_user: User,
):
    ticket = await _create_ticket(client, title="Original", priority="low")

    response = await client.patch(
        f"/api/v1/tickets/{ticket['id']}",
        json={
            "title": "Renamed",
            "description": "Added context",
            "status": "closed",
            "priority": "critical",
            "assignee_id": str(second_user.id),
            "client_url": "https://example.com/help",
        },
    )
    assert response.status_code == 200

    history = (await client.get(f"/api/v1/tickets/{ticket['id']}/history")).json()
    by_field = {item["field"]: item for item in history}

    assert {"created", "title", "description", "status", "priority", "assignee", "client_url"} <= set(by_field)

    assert by_field["title"]["old_value"] == "Original"
    assert by_field["title"]["new_value"] == "Renamed"
    assert by_field["status"]["old_value"] == "open"
    assert by_field["status"]["new_value"] == "closed"
    assert by_field["priority"]["old_value"] == "low"
    assert by_field["priority"]["new_value"] == "critical"
    assert by_field["assignee"]["old_value"] is None
    assert by_field["assignee"]["new_value"] == second_user.name
    assert by_field["client_url"]["old_value"] is None
    assert by_field["client_url"]["new_value"] == "https://example.com/help"
    assert by_field["description"]["actor"]["id"] == str(test_user.id)


async def test_update_ticket_history_skips_unchanged_values(client: AsyncClient):
    ticket = await _create_ticket(client, title="Stable title", priority="high")

    response = await client.patch(
        f"/api/v1/tickets/{ticket['id']}",
        json={"title": "Stable title", "priority": "high"},
    )
    assert response.status_code == 200

    history = (await client.get(f"/api/v1/tickets/{ticket['id']}/history")).json()
    assert [item["field"] for item in history] == ["created"]


async def test_delete_ticket_keeps_history_rows_with_null_ticket_id(
    client: AsyncClient,
    db_session: AsyncSession,
):
    ticket = await _create_ticket(client, title="History survives delete")
    ticket_uuid = uuid.UUID(ticket["id"])

    response = await client.delete(f"/api/v1/tickets/{ticket['id']}")
    assert response.status_code == 204

    result = await db_session.execute(
        select(TicketHistory).where(TicketHistory.field == "created")
    )
    rows = result.scalars().all()
    matching = [row for row in rows if row.actor_id is not None]
    assert matching
    created_row = next(row for row in matching if row.ticket_id is None or row.ticket_id == ticket_uuid)
    assert created_row.ticket_id is None


async def test_ticket_history_returns_newest_first(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    ticket = await _create_ticket(client, title="History order")
    ticket_uuid = uuid.UUID(ticket["id"])
    now = datetime.now(timezone.utc)

    created_entry = (
        await db_session.execute(
            select(TicketHistory).where(
                TicketHistory.ticket_id == ticket_uuid,
                TicketHistory.field == "created",
            )
        )
    ).scalar_one()
    created_entry.created_at = now - timedelta(hours=2)

    newest = TicketHistory(
        ticket_id=ticket_uuid,
        actor_id=test_user.id,
        field="status",
        old_value="open",
        new_value="closed",
        created_at=now,
    )
    middle = TicketHistory(
        ticket_id=ticket_uuid,
        actor_id=test_user.id,
        field="priority",
        old_value="medium",
        new_value="high",
        created_at=now - timedelta(hours=1),
    )
    db_session.add_all([newest, middle])
    await db_session.commit()

    history = (await client.get(f"/api/v1/tickets/{ticket['id']}/history")).json()
    assert [item["field"] for item in history[:3]] == ["status", "priority", "created"]


async def test_ticket_history_limit_is_enforced(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    ticket = await _create_ticket(client, title="History limit")
    ticket_uuid = uuid.UUID(ticket["id"])

    for index in range(120):
        db_session.add(
            TicketHistory(
                ticket_id=ticket_uuid,
                actor_id=test_user.id,
                field=f"extra_{index}",
                old_value=None,
                new_value=str(index),
            )
        )
    await db_session.commit()

    history = (await client.get(f"/api/v1/tickets/{ticket['id']}/history")).json()
    assert len(history) == 100

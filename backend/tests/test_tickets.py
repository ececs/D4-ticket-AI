"""
Tests for the Tickets API.

Orbidi spec requirements covered:
- Ticket fields: title, description, author, assignee, status, priority,
  created_at, updated_at
- Statuses: open, in_progress, in_review, closed
- List view: filters (status, priority, assignee), search, sort, pagination
- Reasignación: immediate DB reflection
- All CRUD operations with proper HTTP semantics
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.tickets import list_tickets
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.models.user import User


# ── helpers ───────────────────────────────────────────────────────────────────

async def _create_ticket(client: AsyncClient, **kwargs) -> dict:
    payload = {"title": "Default title", "priority": "medium", **kwargs}
    r = await client.post("/api/v1/tickets", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ── CREATE ────────────────────────────────────────────────────────────────────

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



async def test_create_ticket_missing_title_returns_422(client: AsyncClient):
    r = await client.post("/api/v1/tickets", json={"priority": "low"})
    assert r.status_code == 422


async def test_create_ticket_invalid_priority_returns_422(client: AsyncClient):
    r = await client.post("/api/v1/tickets", json={"title": "T", "priority": "urgent"})
    assert r.status_code == 422


async def test_create_ticket_response_includes_all_required_fields(
    client: AsyncClient, test_user: User
):
    """All Orbidi-mandated fields must appear in the response."""
    data = await _create_ticket(client, title="Full field check")
    required = {
        "id", "title", "description", "status", "priority",
        "author_id", "assignee_id", "created_at", "updated_at",
    }
    for field in required:
        assert field in data, f"Missing Orbidi-required field: {field}"


async def test_create_ticket_timestamps_are_set(client: AsyncClient):
    data = await _create_ticket(client)
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


async def test_create_ticket_with_client_url(client: AsyncClient):
    """client_url stores the customer-facing page for RAG context."""
    data = await _create_ticket(
        client, title="T", client_url="https://example.com/docs"
    )
    assert data.get("client_url") == "https://example.com/docs"


async def test_create_ticket_without_auth_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.post("/api/v1/tickets", json={"title": "T"})
    assert r.status_code == 401


# ── LIST ──────────────────────────────────────────────────────────────────────

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
    body = r.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


async def test_list_tickets_response_has_pagination_metadata(client: AsyncClient):
    """List response must include items, total, page, size."""
    r = await client.get("/api/v1/tickets")
    body = r.json()
    for key in ("items", "total", "page", "size"):
        assert key in body, f"Missing pagination field: {key}"


async def test_list_tickets_filter_by_status(client: AsyncClient):
    t = await _create_ticket(client, title="Open one")
    await client.patch(f"/api/v1/tickets/{t['id']}", json={"status": "closed"})
    await _create_ticket(client, title="Still open")

    r = await client.get("/api/v1/tickets?status=open")
    items = r.json()["items"]
    assert all(i["status"] == "open" for i in items)
    assert len(items) == 1


async def test_list_tickets_filter_by_priority(client: AsyncClient):
    await _create_ticket(client, title="Low", priority="low")
    await _create_ticket(client, title="Critical", priority="critical")

    r = await client.get("/api/v1/tickets?priority=critical")
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["priority"] == "critical"


async def test_list_tickets_filter_by_assignee(client: AsyncClient, test_user: User):
    await _create_ticket(client, title="Assigned", assignee_id=str(test_user.id))
    await _create_ticket(client, title="Unassigned")

    r = await client.get(f"/api/v1/tickets?assignee_id={test_user.id}")
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Assigned"


async def test_list_tickets_combined_filters(client: AsyncClient, test_user: User):
    """Filters must be composable (status AND priority)."""
    await _create_ticket(client, title="Match", priority="high", assignee_id=str(test_user.id))
    await _create_ticket(client, title="Wrong priority", priority="low", assignee_id=str(test_user.id))
    await _create_ticket(client, title="Wrong assignee", priority="high")

    r = await client.get(
        f"/api/v1/tickets?priority=high&assignee_id={test_user.id}"
    )
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Match"


async def test_list_tickets_search_by_title(client: AsyncClient):
    await _create_ticket(client, title="Login bug fix")
    await _create_ticket(client, title="Performance improvement")

    # Mock embedding to None to trigger ilike fallback (pgvector not in SQLite)
    with patch("app.api.v1.tickets.generate_embedding", new_callable=AsyncMock, return_value=None):
        r = await client.get("/api/v1/tickets?search=login")
    items = r.json()["items"]
    assert len(items) == 1
    assert "login" in items[0]["title"].lower()


async def test_list_tickets_search_by_description(client: AsyncClient):
    await _create_ticket(client, title="Issue A", description="database migration fails")
    await _create_ticket(client, title="Issue B", description="UI rendering glitch")

    with patch("app.api.v1.tickets.generate_embedding", new_callable=AsyncMock, return_value=None):
        r = await client.get("/api/v1/tickets?search=migration")
    assert r.json()["total"] == 1


async def test_list_tickets_search_no_match_returns_empty(client: AsyncClient):
    await _create_ticket(client, title="Unrelated title")

    with patch("app.api.v1.tickets.generate_embedding", new_callable=AsyncMock, return_value=None):
        r = await client.get("/api/v1/tickets?search=xyznonexistentquery")
    assert r.json()["total"] == 0


def _ticket_for_search(
    *,
    title: str,
    description: str | None = None,
    status: TicketStatus = TicketStatus.open,
    priority: TicketPriority = TicketPriority.medium,
) -> Ticket:
    now = datetime.now(timezone.utc)
    return Ticket(
        id=uuid.uuid4(),
        title=title,
        description=description,
        status=status,
        priority=priority,
        author_id=uuid.uuid4(),
        assignee_id=None,
        client_url=None,
        client_summary=None,
        created_at=now,
        updated_at=now,
    )


class _FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class _FakeSession:
    def __init__(self, results):
        self._results = list(results)
        self.queries = []

    async def execute(self, query):
        self.queries.append(query)
        return _FakeScalarResult(self._results.pop(0))


async def test_hybrid_search_rrf_promotes_ticket_present_in_both_rankings(test_user: User):
    both = _ticket_for_search(title="Login bug", description="Login fails after deploy")
    semantic_only = _ticket_for_search(title="Auth issue", description="Session bug")
    keyword_only = _ticket_for_search(title="Login UI copy", description="Minor text issue")
    fake_db = _FakeSession([[semantic_only, both], [both, keyword_only]])

    with (
        patch("app.api.v1.tickets.cache_get", new=AsyncMock(return_value=None)),
        patch("app.api.v1.tickets.cache_set", new=AsyncMock()),
        patch("app.api.v1.tickets.generate_embedding", new=AsyncMock(return_value=[0.1, 0.2])),
    ):
        response = await list_tickets(
            db=fake_db,
            current_user=test_user,
            status=None,
            priority=None,
            assignee_id=None,
            search="login",
            sort_by="created_at",
            order="desc",
            page=1,
            size=10,
        )

    assert response.total == 3
    assert [item.id for item in response.items] == [both.id, semantic_only.id, keyword_only.id]


async def test_hybrid_search_keeps_keyword_match_without_embedding(test_user: User):
    semantic_match = _ticket_for_search(title="Authentication problem", description="Conceptually related")
    no_embedding_keyword_match = _ticket_for_search(title="Login bug", description="Exact keyword match")
    fake_db = _FakeSession([[semantic_match], [no_embedding_keyword_match]])

    with (
        patch("app.api.v1.tickets.cache_get", new=AsyncMock(return_value=None)),
        patch("app.api.v1.tickets.cache_set", new=AsyncMock()),
        patch("app.api.v1.tickets.generate_embedding", new=AsyncMock(return_value=[0.1, 0.2])),
    ):
        response = await list_tickets(
            db=fake_db,
            current_user=test_user,
            status=None,
            priority=None,
            assignee_id=None,
            search="login",
            sort_by="created_at",
            order="desc",
            page=1,
            size=10,
        )

    ids = [item.id for item in response.items]
    assert semantic_match.id in ids
    assert no_embedding_keyword_match.id in ids


async def test_hybrid_search_pages_over_fused_rankings(test_user: User):
    tickets = [_ticket_for_search(title=f"Login result {i}") for i in range(4)]
    fake_db = _FakeSession([tickets, tickets])

    with (
        patch("app.api.v1.tickets.cache_get", new=AsyncMock(return_value=None)),
        patch("app.api.v1.tickets.cache_set", new=AsyncMock()),
        patch("app.api.v1.tickets.generate_embedding", new=AsyncMock(return_value=[0.1, 0.2])),
    ):
        response = await list_tickets(
            db=fake_db,
            current_user=test_user,
            status=None,
            priority=None,
            assignee_id=None,
            search="login",
            page=2,
            sort_by="created_at",
            order="desc",
            size=2,
        )

    assert response.total == 4
    assert len(response.items) == 2
    assert [item.id for item in response.items] == [tickets[2].id, tickets[3].id]


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


async def test_list_tickets_pagination_beyond_last_returns_empty(client: AsyncClient):
    await _create_ticket(client)
    r = await client.get("/api/v1/tickets?page=999&size=25")
    assert r.json()["items"] == []


async def test_list_tickets_sort_by_title_asc(client: AsyncClient):
    await _create_ticket(client, title="Z ticket")
    await _create_ticket(client, title="A ticket")

    r = await client.get("/api/v1/tickets?sort_by=title&order=asc")
    titles = [i["title"] for i in r.json()["items"]]
    assert titles == sorted(titles)


async def test_list_tickets_sort_by_title_desc(client: AsyncClient):
    await _create_ticket(client, title="A ticket")
    await _create_ticket(client, title="Z ticket")

    r = await client.get("/api/v1/tickets?sort_by=title&order=desc")
    titles = [i["title"] for i in r.json()["items"]]
    assert titles == sorted(titles, reverse=True)


async def test_list_tickets_sort_by_priority(client: AsyncClient):
    """Sorting by priority must not crash (enum ordering by DB value)."""
    await _create_ticket(client, priority="low")
    await _create_ticket(client, priority="critical")
    r = await client.get("/api/v1/tickets?sort_by=priority&order=asc")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2


async def test_list_tickets_sort_by_status(client: AsyncClient):
    await _create_ticket(client)
    r = await client.get("/api/v1/tickets?sort_by=status&order=asc")
    assert r.status_code == 200


async def test_list_tickets_sort_by_created_at(client: AsyncClient):
    await _create_ticket(client, title="First")
    await _create_ticket(client, title="Second")
    r = await client.get("/api/v1/tickets?sort_by=created_at&order=asc")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0]["title"] == "First"


async def test_list_tickets_invalid_page_returns_422(client: AsyncClient):
    r = await client.get("/api/v1/tickets?page=0")
    assert r.status_code == 422


async def test_list_tickets_size_too_large_returns_422(client: AsyncClient):
    r = await client.get("/api/v1/tickets?size=101")
    assert r.status_code == 422


async def test_list_tickets_without_auth_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.get("/api/v1/tickets")
    assert r.status_code == 401


# ── GET ───────────────────────────────────────────────────────────────────────

async def test_get_ticket_returns_200(client: AsyncClient):
    created = await _create_ticket(client, title="Detail ticket")
    r = await client.get(f"/api/v1/tickets/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


async def test_get_ticket_not_found_returns_404(client: AsyncClient):
    r = await client.get(f"/api/v1/tickets/{uuid.uuid4()}")
    assert r.status_code == 404


async def test_get_ticket_invalid_uuid_returns_422(client: AsyncClient):
    r = await client.get("/api/v1/tickets/not-a-uuid")
    assert r.status_code == 422


async def test_get_ticket_includes_author_object(client: AsyncClient, test_user: User):
    created = await _create_ticket(client)
    r = await client.get(f"/api/v1/tickets/{created['id']}")
    data = r.json()
    assert "author" in data
    assert data["author"]["id"] == str(test_user.id)
    assert "name" in data["author"]
    assert "email" in data["author"]


async def test_get_ticket_includes_assignee_object_when_set(
    client: AsyncClient, test_user: User
):
    created = await _create_ticket(client, assignee_id=str(test_user.id))
    r = await client.get(f"/api/v1/tickets/{created['id']}")
    data = r.json()
    assert data["assignee"] is not None
    assert data["assignee"]["id"] == str(test_user.id)


async def test_get_ticket_without_auth_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.get(f"/api/v1/tickets/{uuid.uuid4()}")
    assert r.status_code == 401


# ── ALL STATUSES (Orbidi spec: open, in_progress, in_review, closed) ──────────

async def test_all_orbidi_statuses_are_accepted(client: AsyncClient):
    """Every status defined in the spec must be settable via PATCH."""
    ticket = await _create_ticket(client)
    for status in ("in_progress", "in_review", "closed", "open"):
        r = await client.patch(
            f"/api/v1/tickets/{ticket['id']}", json={"status": status}
        )
        assert r.status_code == 200, f"Status '{status}' was rejected"
        assert r.json()["status"] == status


# ── UPDATE ────────────────────────────────────────────────────────────────────

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


async def test_update_ticket_priority(client: AsyncClient):
    created = await _create_ticket(client, priority="low")
    r = await client.patch(f"/api/v1/tickets/{created['id']}", json={"priority": "critical"})
    assert r.status_code == 200
    assert r.json()["priority"] == "critical"


async def test_update_ticket_description(client: AsyncClient):
    created = await _create_ticket(client)
    r = await client.patch(
        f"/api/v1/tickets/{created['id']}", json={"description": "New description"}
    )
    assert r.status_code == 200
    assert r.json()["description"] == "New description"


async def test_update_ticket_assignee(client: AsyncClient, test_user: User, second_user: User):
    """Reasignación: any authenticated user can reassign — immediate reflection."""
    created = await _create_ticket(client)
    r = await client.patch(
        f"/api/v1/tickets/{created['id']}", json={"assignee_id": str(second_user.id)}
    )
    assert r.status_code == 200
    assert r.json()["assignee_id"] == str(second_user.id)


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


async def test_update_ticket_invalid_priority_returns_422(client: AsyncClient):
    created = await _create_ticket(client)
    r = await client.patch(f"/api/v1/tickets/{created['id']}", json={"priority": "extreme"})
    assert r.status_code == 422


async def test_update_ticket_without_auth_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.patch(f"/api/v1/tickets/{uuid.uuid4()}", json={"title": "X"})
    assert r.status_code == 401


async def test_reasignacion_reflects_immediately_in_list(
    client: AsyncClient, test_user: User, second_user: User
):
    """Orbidi spec: reasignación debe reflejarse inmediatamente en la vista lista."""
    ticket = await _create_ticket(client)
    await client.patch(
        f"/api/v1/tickets/{ticket['id']}", json={"assignee_id": str(second_user.id)}
    )
    r = await client.get(f"/api/v1/tickets?assignee_id={second_user.id}")
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["assignee_id"] == str(second_user.id)


# ── DELETE ────────────────────────────────────────────────────────────────────

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


async def test_delete_ticket_without_auth_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.delete(f"/api/v1/tickets/{uuid.uuid4()}")
    assert r.status_code == 401


async def test_delete_ticket_cascades_to_comments(
    client: AsyncClient, db_session: AsyncSession
):
    """Deleting a ticket must remove associated comments (CASCADE)."""
    from app.models.comment import Comment
    from sqlalchemy import select

    ticket = await _create_ticket(client)
    await client.post(
        f"/api/v1/tickets/{ticket['id']}/comments", json={"content": "Will be deleted"}
    )
    await client.delete(f"/api/v1/tickets/{ticket['id']}")

    result = await db_session.execute(
        select(Comment).where(Comment.ticket_id == uuid.UUID(ticket["id"]))
    )
    assert result.scalars().all() == []

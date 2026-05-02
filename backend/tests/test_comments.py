import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.models.user import User


async def _create_ticket(client: AsyncClient, title: str = "Ticket") -> dict:
    r = await client.post("/api/v1/tickets", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _create_comment(client: AsyncClient, ticket_id: str, content: str = "A comment") -> dict:
    r = await client.post(f"/api/v1/tickets/{ticket_id}/comments", json={"content": content})
    assert r.status_code == 201
    return r.json()


# ── create ────────────────────────────────────────────────────────────────────

async def test_create_comment_returns_201(client: AsyncClient):
    ticket = await _create_ticket(client)
    r = await client.post(f"/api/v1/tickets/{ticket['id']}/comments", json={"content": "Hello"})
    assert r.status_code == 201


async def test_create_comment_contains_author(client: AsyncClient, test_user: User):
    ticket = await _create_ticket(client)
    data = await _create_comment(client, ticket["id"], "My comment")
    assert data["content"] == "My comment"
    assert data["author"]["id"] == str(test_user.id)


async def test_create_comment_on_nonexistent_ticket_returns_404(client: AsyncClient):
    r = await client.post(
        f"/api/v1/tickets/{uuid.uuid4()}/comments",
        json={"content": "Comment"},
    )
    assert r.status_code == 404



# ── list ──────────────────────────────────────────────────────────────────────

async def test_list_comments_empty(client: AsyncClient):
    ticket = await _create_ticket(client)
    r = await client.get(f"/api/v1/tickets/{ticket['id']}/comments")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_comments_returns_all(client: AsyncClient):
    ticket = await _create_ticket(client)
    await _create_comment(client, ticket["id"], "First")
    await _create_comment(client, ticket["id"], "Second")

    r = await client.get(f"/api/v1/tickets/{ticket['id']}/comments")
    assert len(r.json()) == 2


async def test_list_comments_ordered_oldest_first(client: AsyncClient):
    ticket = await _create_ticket(client)
    await _create_comment(client, ticket["id"], "First")
    await _create_comment(client, ticket["id"], "Second")

    comments = (await client.get(f"/api/v1/tickets/{ticket['id']}/comments")).json()
    assert comments[0]["content"] == "First"
    assert comments[1]["content"] == "Second"


async def test_list_comments_on_nonexistent_ticket_returns_404(client: AsyncClient):
    r = await client.get(f"/api/v1/tickets/{uuid.uuid4()}/comments")
    assert r.status_code == 404


# ── delete ────────────────────────────────────────────────────────────────────

async def test_delete_own_comment_returns_204(client: AsyncClient):
    ticket = await _create_ticket(client)
    comment = await _create_comment(client, ticket["id"])
    r = await client.delete(f"/api/v1/tickets/{ticket['id']}/comments/{comment['id']}")
    assert r.status_code == 204


async def test_delete_comment_removes_it(client: AsyncClient):
    ticket = await _create_ticket(client)
    comment = await _create_comment(client, ticket["id"])
    await client.delete(f"/api/v1/tickets/{ticket['id']}/comments/{comment['id']}")

    comments = (await client.get(f"/api/v1/tickets/{ticket['id']}/comments")).json()
    assert all(c["id"] != comment["id"] for c in comments)


async def test_delete_other_users_comment_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    second_user: User,
):
    ticket = await _create_ticket(client)

    # Create a comment directly in DB as second_user (bypassing the HTTP client)
    comment = Comment(
        ticket_id=uuid.UUID(ticket["id"]),
        author_id=second_user.id,
        content="Written by other user",
    )
    db_session.add(comment)
    await db_session.commit()

    # test_user (the client) tries to delete second_user's comment → 403
    r = await client.delete(f"/api/v1/tickets/{ticket['id']}/comments/{comment.id}")
    assert r.status_code == 403


async def test_delete_nonexistent_comment_returns_404(client: AsyncClient):
    ticket = await _create_ticket(client)
    r = await client.delete(f"/api/v1/tickets/{ticket['id']}/comments/{uuid.uuid4()}")
    assert r.status_code == 404

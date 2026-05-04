"""
Tests for the Attachments API.

Orbidi spec requirement:
  - File attachments per ticket (10 MB limit)
  - Upload, list, delete operations
  - Uploader-only deletion
"""

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment
from app.models.user import User
from app.services import storage_service


async def _create_ticket(client: AsyncClient, title: str = "Ticket with attachments") -> dict:
    r = await client.post("/api/v1/tickets", json={"title": title})
    assert r.status_code == 201
    return r.json()


def _make_file(
    content: bytes = b"fake file content",
    filename: str = "test.png",
    content_type: str = "image/png",
):
    return {"file": (filename, io.BytesIO(content), content_type)}


# ── list ──────────────────────────────────────────────────────────────────────

async def test_list_attachments_empty(client: AsyncClient, mock_storage):
    ticket = await _create_ticket(client)
    r = await client.get(f"/api/v1/tickets/{ticket['id']}/attachments")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_attachments_without_auth_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.get(f"/api/v1/tickets/{uuid.uuid4()}/attachments")
    assert r.status_code == 401


# ── upload ────────────────────────────────────────────────────────────────────

async def test_upload_image_returns_201(client: AsyncClient, mock_storage):
    ticket = await _create_ticket(client)
    r = await client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments",
        files=_make_file(b"png bytes", "photo.png", "image/png"),
    )
    assert r.status_code == 201
    data = r.json()
    assert data["filename"] == "photo.png"
    assert data["mime_type"] == "image/png"


async def test_upload_pdf_returns_201(client: AsyncClient, mock_storage):
    ticket = await _create_ticket(client)
    r = await client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments",
        files=_make_file(b"%PDF-content", "report.pdf", "application/pdf"),
    )
    assert r.status_code == 201


async def test_upload_appears_in_list(client: AsyncClient, mock_storage):
    ticket = await _create_ticket(client)
    await client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments",
        files=_make_file(b"data", "doc.png", "image/png"),
    )
    r = await client.get(f"/api/v1/tickets/{ticket['id']}/attachments")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["filename"] == "doc.png"


async def test_upload_response_has_required_fields(client: AsyncClient, mock_storage):
    """Attachment schema: id, filename, mime_type, download_url (presigned), created_at."""
    ticket = await _create_ticket(client)
    r = await client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments",
        files=_make_file(b"data", "file.png", "image/png"),
    )
    data = r.json()
    for field in ("id", "filename", "mime_type", "download_url", "created_at"):
        assert field in data, f"Missing field: {field}"


async def test_upload_multiple_attachments(client: AsyncClient, mock_storage):
    ticket = await _create_ticket(client)
    for i in range(3):
        r = await client.post(
            f"/api/v1/tickets/{ticket['id']}/attachments",
            files=_make_file(b"data", f"file{i}.png", "image/png"),
        )
        assert r.status_code == 201

    r = await client.get(f"/api/v1/tickets/{ticket['id']}/attachments")
    assert len(r.json()) == 3


async def test_upload_to_nonexistent_ticket_returns_404(client: AsyncClient, mock_storage):
    r = await client.post(
        f"/api/v1/tickets/{uuid.uuid4()}/attachments",
        files=_make_file(b"data", "file.png", "image/png"),
    )
    assert r.status_code == 404


async def test_upload_without_auth_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.post(
        f"/api/v1/tickets/{uuid.uuid4()}/attachments",
        files=_make_file(b"data", "file.png", "image/png"),
    )
    assert r.status_code == 401


# ── size limit (Orbidi spec: 10 MB) ──────────────────────────────────────────

async def test_upload_oversized_file_returns_413(client: AsyncClient, mock_storage):
    """Files above the 10 MB limit must be rejected with 413."""
    ticket = await _create_ticket(client)
    oversized = b"x" * (11 * 1024 * 1024)  # 11 MB
    r = await client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments",
        files=_make_file(oversized, "huge.png", "image/png"),
    )
    assert r.status_code == 413


# ── MIME validation ───────────────────────────────────────────────────────────

async def test_upload_disallowed_mime_returns_415(client: AsyncClient, mock_storage):
    """Executables and other disallowed types must be rejected with 415."""
    ticket = await _create_ticket(client)
    r = await client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments",
        files=_make_file(b"MZ...", "malware.exe", "application/x-msdownload"),
    )
    assert r.status_code == 415


async def test_upload_zip_returns_415(client: AsyncClient, mock_storage):
    ticket = await _create_ticket(client)
    r = await client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments",
        files=_make_file(b"PK...", "archive.zip", "application/zip"),
    )
    assert r.status_code == 415


# ── delete ────────────────────────────────────────────────────────────────────

async def test_delete_own_attachment_returns_204(client: AsyncClient, mock_storage):
    ticket = await _create_ticket(client)
    attachment = (
        await client.post(
            f"/api/v1/tickets/{ticket['id']}/attachments",
            files=_make_file(b"data", "to_delete.png", "image/png"),
        )
    ).json()

    r = await client.delete(f"/api/v1/tickets/{ticket['id']}/attachments/{attachment['id']}")
    assert r.status_code == 204


async def test_delete_removes_attachment_from_list(client: AsyncClient, mock_storage):
    ticket = await _create_ticket(client)
    attachment = (
        await client.post(
            f"/api/v1/tickets/{ticket['id']}/attachments",
            files=_make_file(b"data", "remove_me.png", "image/png"),
        )
    ).json()

    await client.delete(f"/api/v1/tickets/{ticket['id']}/attachments/{attachment['id']}")

    r = await client.get(f"/api/v1/tickets/{ticket['id']}/attachments")
    assert all(a["id"] != attachment["id"] for a in r.json())


async def test_delete_other_users_attachment_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    second_user: User,
    mock_storage,
):
    """Only the uploader can delete an attachment — Orbidi spec."""
    from unittest.mock import patch, AsyncMock

    ticket = await _create_ticket(client)

    # Insert an attachment owned by second_user directly in DB (bypass HTTP)
    attachment = Attachment(
        ticket_id=uuid.UUID(ticket["id"]),
        uploader_id=second_user.id,
        filename="owned_by_other.png",
        mime_type="image/png",
        storage_key=f"tickets/test/{uuid.uuid4()}/owned.png",
        size_bytes=100,
    )
    db_session.add(attachment)
    await db_session.commit()

    # test_user (the authenticated client) tries to delete second_user's file → 403
    r = await client.delete(
        f"/api/v1/tickets/{ticket['id']}/attachments/{attachment.id}"
    )
    assert r.status_code == 403


async def test_delete_nonexistent_attachment_returns_404(client: AsyncClient, mock_storage):
    ticket = await _create_ticket(client)
    r = await client.delete(f"/api/v1/tickets/{ticket['id']}/attachments/{uuid.uuid4()}")
    assert r.status_code == 404


async def test_delete_attachment_without_auth_returns_401(unauth_client: AsyncClient):
    r = await unauth_client.delete(
        f"/api/v1/tickets/{uuid.uuid4()}/attachments/{uuid.uuid4()}"
    )
    assert r.status_code == 401

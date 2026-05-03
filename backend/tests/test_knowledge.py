"""
Tests for the Knowledge Base API (RAG — Task #4).

Covers:
  - POST /knowledge: scrape + embed + store URL content
  - Idempotent re-index (same URL twice replaces old chunks)
  - Auth guard
  - Graceful error when URL cannot be scraped (422)
  - _chunk_text unit tests (pure function, no I/O)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.knowledge_service import _chunk_text


# ── _chunk_text unit tests (pure, no DB/network) ──────────────────────────────

def test_chunk_text_single_short_paragraph():
    text = "Hello world."
    chunks = _chunk_text(text)
    assert chunks == ["Hello world."]


def test_chunk_text_empty_string():
    chunks = _chunk_text("")
    assert chunks == []


def test_chunk_text_splits_long_text():
    # 600 chars should produce at least 2 chunks (CHUNK_SIZE = 500)
    text = "A" * 600
    chunks = _chunk_text(text)
    assert len(chunks) >= 2
    assert all(len(c) <= 500 for c in chunks)


def test_chunk_text_merges_short_paragraphs():
    # Two short paragraphs should be merged into one chunk
    text = "Short paragraph one.\n\nShort paragraph two."
    chunks = _chunk_text(text)
    assert len(chunks) == 1
    assert "Short paragraph one." in chunks[0]
    assert "Short paragraph two." in chunks[0]


def test_chunk_text_splits_on_paragraph_boundaries():
    para_a = "A" * 300
    para_b = "B" * 300
    text = f"{para_a}\n\n{para_b}"
    chunks = _chunk_text(text)
    # Combined length (600+2) > CHUNK_SIZE (500), so must be in separate chunks
    assert len(chunks) == 2


def test_chunk_text_overlap_preserved():
    # A paragraph that exceeds CHUNK_SIZE should produce overlapping chunks
    long_para = "X" * 1100
    chunks = _chunk_text(long_para)
    assert len(chunks) >= 2
    # Overlap: last chars of chunk[0] should appear at start of chunk[1]
    assert chunks[0][-50:] == chunks[1][:50]


# ── POST /knowledge ───────────────────────────────────────────────────────────

_FAKE_TEXT = "This is a paragraph.\n\nThis is another paragraph."
_FAKE_EMBEDDING = [0.1] * 768


def _patch_ingest():
    """Context managers that prevent real HTTP calls and AI API usage."""
    return (
        patch(
            "app.services.knowledge_service.asyncio.to_thread",
            new_callable=MagicMock,
        ),
        patch(
            "app.services.knowledge_service.generate_embedding",
            new_callable=AsyncMock,
            return_value=_FAKE_EMBEDDING,
        ),
    )


async def test_ingest_url_returns_201(client: AsyncClient):
    """Happy path: valid URL that trafilatura can scrape."""
    with (
        patch(
            "app.services.knowledge_service.asyncio.to_thread",
            side_effect=[_FAKE_TEXT, _FAKE_TEXT],  # fetch_url, then extract
        ),
        patch(
            "app.services.knowledge_service.generate_embedding",
            new_callable=AsyncMock,
            return_value=_FAKE_EMBEDDING,
        ),
    ):
        r = await client.post("/api/v1/knowledge", json={"url": "https://example.com/docs"})
    assert r.status_code == 201
    data = r.json()
    assert data["url"] == "https://example.com/docs"
    assert data["chunks_created"] >= 1


async def test_ingest_url_response_shape(client: AsyncClient):
    """IngestResponse must include url and chunks_created."""
    with (
        patch(
            "app.services.knowledge_service.asyncio.to_thread",
            side_effect=[_FAKE_TEXT, _FAKE_TEXT],
        ),
        patch(
            "app.services.knowledge_service.generate_embedding",
            new_callable=AsyncMock,
            return_value=_FAKE_EMBEDDING,
        ),
    ):
        r = await client.post("/api/v1/knowledge", json={"url": "https://example.com"})
    assert r.status_code == 201
    data = r.json()
    assert "url" in data
    assert "chunks_created" in data
    assert isinstance(data["chunks_created"], int)
    assert data["chunks_created"] > 0


async def test_ingest_url_idempotent(client: AsyncClient, db_session: AsyncSession):
    """Re-ingesting the same URL must replace old chunks, not duplicate them."""
    from sqlalchemy import select, func
    from app.models.knowledge_chunk import KnowledgeChunk

    url = "https://example.com/page"

    for _ in range(2):
        with (
            patch(
                "app.services.knowledge_service.asyncio.to_thread",
                side_effect=[_FAKE_TEXT, _FAKE_TEXT],
            ),
            patch(
                "app.services.knowledge_service.generate_embedding",
                new_callable=AsyncMock,
                return_value=_FAKE_EMBEDDING,
            ),
        ):
            r = await client.post("/api/v1/knowledge", json={"url": url})
        assert r.status_code == 201
        first_count = r.json()["chunks_created"]

    # After two ingestions the DB should contain exactly one set of chunks
    result = await db_session.execute(
        select(func.count()).select_from(KnowledgeChunk).where(KnowledgeChunk.url == url)
    )
    db_count = result.scalar_one()
    assert db_count == first_count


async def test_ingest_url_failed_fetch_returns_422(client: AsyncClient):
    """If trafilatura cannot fetch the URL, the endpoint must return 422."""
    with patch(
        "app.services.knowledge_service.asyncio.to_thread",
        side_effect=[None, None],  # fetch_url returns None
    ):
        r = await client.post("/api/v1/knowledge", json={"url": "https://unreachable.invalid"})
    assert r.status_code == 422


async def test_ingest_url_failed_extract_returns_422(client: AsyncClient):
    """If trafilatura fetches but cannot extract text, return 422."""
    with patch(
        "app.services.knowledge_service.asyncio.to_thread",
        side_effect=["<html/>", None],  # fetch succeeds, extract fails
    ):
        r = await client.post("/api/v1/knowledge", json={"url": "https://empty-page.example"})
    assert r.status_code == 422


async def test_ingest_url_invalid_url_returns_422(client: AsyncClient):
    """Pydantic must reject non-URL strings before they reach the service."""
    r = await client.post("/api/v1/knowledge", json={"url": "not-a-url"})
    assert r.status_code == 422


async def test_ingest_url_missing_body_returns_422(client: AsyncClient):
    r = await client.post("/api/v1/knowledge", json={})
    assert r.status_code == 422


async def test_ingest_url_requires_auth(unauth_client: AsyncClient):
    r = await unauth_client.post("/api/v1/knowledge", json={"url": "https://example.com"})
    assert r.status_code == 401


async def test_ingest_url_stores_chunks_in_db(client: AsyncClient, db_session: AsyncSession):
    """Verify chunks actually land in knowledge_chunks table."""
    from sqlalchemy import select
    from app.models.knowledge_chunk import KnowledgeChunk

    url = "https://example.com/stored"
    with (
        patch(
            "app.services.knowledge_service.asyncio.to_thread",
            side_effect=[_FAKE_TEXT, _FAKE_TEXT],
        ),
        patch(
            "app.services.knowledge_service.generate_embedding",
            new_callable=AsyncMock,
            return_value=_FAKE_EMBEDDING,
        ),
    ):
        r = await client.post("/api/v1/knowledge", json={"url": url})
    assert r.status_code == 201

    result = await db_session.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.url == url)
    )
    rows = result.scalars().all()
    assert len(rows) == r.json()["chunks_created"]
    assert rows[0].content != ""

"""
RAG knowledge service — scrape, chunk, embed, store, and retrieve.

Flow:
  ingest_url()  — fetch a URL with trafilatura, split into ~500-char chunks,
                  generate embeddings, delete old chunks for the same URL,
                  bulk-insert new ones.
  search()      — embed a query and return the top-k most similar chunks.
                  Falls back to full-text ILIKE if no API key is available.
"""

import asyncio
import logging
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_chunk import KnowledgeChunk
from app.services.embedding_service import generate_embedding

logger = logging.getLogger(__name__)

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def _chunk_text(text: str) -> list[str]:
    """
    Split text into overlapping chunks of ~CHUNK_SIZE chars.

    Splits on paragraph boundaries first, then merges short paragraphs
    until the target size is reached.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= CHUNK_SIZE:
            current = f"{current}\n\n{para}".strip() if current else para
        else:
            if current:
                chunks.append(current)
            # Para itself longer than CHUNK_SIZE — hard-split it
            while len(para) > CHUNK_SIZE:
                chunks.append(para[:CHUNK_SIZE])
                para = para[CHUNK_SIZE - CHUNK_OVERLAP:]
            current = para

    if current:
        chunks.append(current)

    return chunks


async def ingest_url(db: AsyncSession, url: str) -> dict:
    """
    Scrape a URL, chunk, embed, and persist to knowledge_chunks.

    Idempotent: deletes any existing chunks for the URL before inserting.

    Returns:
        {"url": str, "chunks_created": int}

    Raises:
        ValueError if the URL could not be scraped or yields no text.
    """
    import trafilatura

    raw_html = await asyncio.to_thread(trafilatura.fetch_url, url)
    if not raw_html:
        raise ValueError(f"Could not fetch URL: {url}")

    text = await asyncio.to_thread(
        trafilatura.extract,
        raw_html,
        include_comments=False,
        include_tables=True,
    )
    if not text:
        raise ValueError(f"Could not extract text from URL: {url}")

    chunks = _chunk_text(text)
    if not chunks:
        raise ValueError("No content found after chunking")

    # Embed all chunks concurrently
    embeddings: list[Optional[list[float]]] = await asyncio.gather(
        *[generate_embedding(c, task_type="RETRIEVAL_DOCUMENT") for c in chunks]
    )

    # Remove stale chunks for this URL (idempotent re-index)
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.url == url))

    rows = [
        KnowledgeChunk(
            url=url,
            chunk_index=i,
            content=chunk,
            embedding=emb,
        )
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]
    db.add_all(rows)
    await db.commit()

    logger.info("Ingested %d chunks from %s", len(rows), url)
    return {"url": url, "chunks_created": len(rows)}


async def search(db: AsyncSession, query: str, k: int = 5) -> list[str]:
    """
    Return the top-k knowledge chunks most relevant to `query`.

    Uses cosine similarity if embeddings are available; falls back to
    ILIKE substring match otherwise.
    """
    query_embedding = await generate_embedding(query, task_type="RETRIEVAL_QUERY")

    if query_embedding is not None:
        stmt = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.embedding.isnot(None))  # type: ignore[attr-defined]
            .order_by(KnowledgeChunk.embedding.cosine_distance(query_embedding))  # type: ignore[attr-defined]
            .limit(k)
        )
    else:
        pattern = f"%{query}%"
        stmt = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.content.ilike(pattern))
            .limit(k)
        )

    result = await db.execute(stmt)
    return [row.content for row in result.scalars().all()]

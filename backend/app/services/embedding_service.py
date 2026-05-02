"""
Embedding service — generates vector representations of text using Google's
gemini-embedding-001 model (3072 dimensions) via direct HTTP API call.

Used for:
  - Indexing tickets: embedding generated on create/update and stored in the
    `embedding` column for later retrieval.
  - Semantic search: the search query is embedded at query time and compared
    against stored ticket embeddings using cosine similarity.

Graceful degradation:
  Returns None if GOOGLE_API_KEY is not set or the API call fails.
  The caller falls back to ilike (keyword search) in that case.

Why gemini-embedding-001?
  The API key available supports the Gemini embedding model family.
  3072 dimensions — rich semantic representation with strong multilingual support.
  Task type RETRIEVAL_DOCUMENT for indexing, RETRIEVAL_QUERY for search.
"""

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 3072
_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"


async def generate_embedding(
    text: str,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> Optional[list[float]]:
    """
    Generate a 3072-dim embedding for the given text.

    Args:
        text: The text to embed (truncated to 2000 chars to stay within limits).
        task_type: "RETRIEVAL_DOCUMENT" for indexing, "RETRIEVAL_QUERY" for search.

    Returns:
        List of 3072 floats, or None if generation failed.
    """
    from app.core.config import settings

    if not settings.GOOGLE_API_KEY:
        return None

    url = _EMBED_URL.format(model=EMBEDDING_MODEL)
    payload = {
        "model": f"models/{EMBEDDING_MODEL}",
        "content": {"parts": [{"text": text[:2000]}]},
        "taskType": task_type,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                json=payload,
                params={"key": settings.GOOGLE_API_KEY},
            )
            resp.raise_for_status()
            return resp.json()["embedding"]["values"]

    except Exception as exc:
        logger.warning("Embedding generation failed: %s", exc)
        return None


async def generate_ticket_embedding(title: str, description: Optional[str] = None) -> Optional[list[float]]:
    """Embed a ticket's title and description combined."""
    text = title
    if description:
        text = f"{title}\n\n{description}"
    return await generate_embedding(text, task_type="RETRIEVAL_DOCUMENT")

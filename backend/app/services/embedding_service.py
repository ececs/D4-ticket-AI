"""
Embedding service — generates vector representations of text using Google's
text-embedding-004 model (768 dimensions) via the google-genai SDK.

Used for:
  - Indexing tickets: embedding generated on create/update and stored in the
    `embedding` column for later retrieval.
  - Semantic search: the search query is embedded at query time and compared
    against stored ticket embeddings using cosine similarity.

Graceful degradation:
  Returns None if GOOGLE_API_KEY is not set or the API call fails.
  The caller falls back to ilike (keyword search) in that case.

Why text-embedding-004?
  768 dimensions — compact enough for fast HNSW search but rich enough for
  nuanced similarity. Native support in Google AI Studio and the genai SDK.
  Task type RETRIEVAL_DOCUMENT for indexing, RETRIEVAL_QUERY for search.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIM = 768


async def generate_embedding(
    text: str,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> Optional[list[float]]:
    """
    Generate a 768-dim embedding for the given text.

    Args:
        text: The text to embed (truncated to 2000 chars to stay within limits).
        task_type: "RETRIEVAL_DOCUMENT" for indexing, "RETRIEVAL_QUERY" for search.

    Returns:
        List of 768 floats, or None if generation failed.
    """
    from app.core.config import settings

    if not settings.GOOGLE_API_KEY:
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.GOOGLE_API_KEY)

        result = await asyncio.to_thread(
            genai.embed_content,
            model=f"models/{EMBEDDING_MODEL}",
            content=text[:2000],
            task_type=task_type,
        )
        return result["embedding"]

    except Exception as exc:
        logger.warning("Embedding generation failed: %s", exc)
        return None


async def generate_ticket_embedding(title: str, description: Optional[str] = None) -> Optional[list[float]]:
    """Embed a ticket's title and description combined."""
    text = title
    if description:
        text = f"{title}\n\n{description}"
    return await generate_embedding(text, task_type="RETRIEVAL_DOCUMENT")

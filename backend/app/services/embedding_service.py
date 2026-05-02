"""
Embedding Service Module.

This service manages the generation of high-dimensional vector representations
for text data using Google's Gemini Embedding API. It is a core component of the
D4-Ticket AI semantic search engine, enabling Retrieval-Augmented Generation (RAG)
and similarity-based ticket grouping.

Key Features:
- Model: gemini-embedding-2 (2026 Standard).
- Dimensionality: Optimized to 768 via Matryoshka Representation Learning.
- Scalability: Asynchronous HTTP requests with automatic truncation.
- Reliability: Graceful degradation to keyword search on API failures.

Workflow:
1. Receives raw text (Ticket, Knowledge, or Query).
2. Truncates content to comply with context window limits.
3. Calls Google API with appropriate taskType (DOCUMENT vs QUERY).
4. Returns a normalized vector for persistent storage or real-time comparison.
"""

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# In 2026, gemini-embedding-2 is the GA (General Availability) standard.
# It is multimodal and supports Matryoshka truncation for optimized dimensions.
# Standardized to 768 to optimize semantic search performance.
EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIM = 768
_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"


async def generate_embedding(
    text: str,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> Optional[list[float]]:
    """
    Generates a high-dimensional vector embedding for the provided text.

    Communicates with the Google Generative AI API using the gemini-embedding-2 
    model. The output dimensionality is strictly controlled at 768 to ensure 
    PostgreSQL HNSW index efficiency and consistent RAM usage.

    Args:
        text: The source text to transform into a vector.
        task_type: The intended use of the embedding. 
            Options: "RETRIEVAL_DOCUMENT" (default) or "RETRIEVAL_QUERY".

    Returns:
        Optional[list[float]]: A list of 768 floating-point values representing 
             the semantic content of the text, or None if the process fails.
    """
    from app.core.config import settings

    if not settings.GOOGLE_API_KEY:
        return None

    url = _EMBED_URL.format(model=EMBEDDING_MODEL)
    payload = {
        "model": f"models/{EMBEDDING_MODEL}",
        "content": {"parts": [{"text": text[:2000]}]},
        "taskType": task_type,
        "outputDimensionality": EMBEDDING_DIM,
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
    """
    Specialized wrapper to generate embeddings for Ticket entities.

    Combines the title and description fields into a single semantic context 
    string before performing the embedding generation.

    Args:
        title: The summary or primary title of the ticket.
        description: The extended details of the ticket. Defaults to None.

    Returns:
        Optional[list[float]]: The 768-dimension vector for the combined ticket text.
    """
    text = title
    if description:
        text = f"{title}\n\n{description}"
    return await generate_embedding(text, task_type="RETRIEVAL_DOCUMENT")

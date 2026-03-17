"""
Vector embeddings for semantic RAG search (Phase 4).

Uses Gemini text-embedding-004 (768 dims) via REST API.
Graceful degradation: no GEMINI_API_KEY = no embeddings = regex fallback everywhere.
"""

import logging
import os
from typing import List, Optional

import httpx
import numpy as np

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBEDDING_MODEL}:embedContent"
EMBEDDING_DIMS = 768


def is_available() -> bool:
    """Check if embedding generation is available (API key configured)."""
    return bool(GEMINI_API_KEY)


async def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Generate a 768-dim embedding via Gemini text-embedding-004.

    Returns None on any failure (missing key, API error, timeout).
    """
    if not GEMINI_API_KEY:
        return None

    if not text or not text.strip():
        return None

    # Truncate to ~8000 chars to stay within model token limits
    truncated = text[:8000]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                EMBEDDING_URL,
                params={"key": GEMINI_API_KEY},
                json={
                    "model": f"models/{EMBEDDING_MODEL}",
                    "content": {"parts": [{"text": truncated}]},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            values = data.get("embedding", {}).get("values")
            if values and len(values) == EMBEDDING_DIMS:
                return values
            logger.warning(f"Unexpected embedding response shape: {len(values) if values else 'None'}")
            return None
    except Exception as e:
        logger.warning(f"Embedding generation failed: {e}")
        return None


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors using numpy."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    dot = np.dot(va, vb)
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    if norm == 0:
        return 0.0
    return float(dot / norm)


async def find_similar(
    query: str,
    collection,
    doc_type: str,
    limit: int = 5,
    min_score: float = 0.3,
) -> List[dict]:
    """
    Semantic similarity search against a MongoDB collection.

    1. Generate embedding for query text
    2. Fetch all docs that have an 'embedding' field (projection: id + embedding only)
    3. Compute cosine similarity for each
    4. Return top-N sorted by score

    Args:
        query: Search text
        collection: pymongo Collection
        doc_type: "todo" or "lesson" (determines which fields to return)
        limit: Max results
        min_score: Minimum similarity threshold

    Returns:
        List of docs with 'similarity_score' attached, sorted descending
    """
    query_embedding = await generate_embedding(query)
    if query_embedding is None:
        return []

    # Fetch only docs that have embeddings — project just id + embedding for speed
    cursor = collection.find(
        {"embedding": {"$exists": True}},
        {"_id": 0, "id": 1, "embedding": 1},
    )

    scored = []
    for doc in cursor:
        doc_embedding = doc.get("embedding")
        if not doc_embedding or len(doc_embedding) != EMBEDDING_DIMS:
            continue
        score = cosine_similarity(query_embedding, doc_embedding)
        if score >= min_score:
            scored.append((doc["id"], score))

    # Sort by score descending, take top N
    scored.sort(key=lambda x: x[1], reverse=True)
    top_ids = scored[:limit]

    if not top_ids:
        return []

    # Fetch full docs for the top matches
    id_list = [item[0] for item in top_ids]
    score_map = {item[0]: item[1] for item in top_ids}

    if doc_type == "todo":
        projection = {"_id": 0, "id": 1, "description": 1, "priority": 1, "status": 1, "project": 1, "created_at": 1}
    else:
        projection = {"_id": 0, "id": 1, "topic": 1, "language": 1, "tags": 1, "lesson_learned": 1}

    results = list(collection.find({"id": {"$in": id_list}}, projection))

    # Attach scores and sort
    for doc in results:
        doc["similarity_score"] = round(score_map.get(doc["id"], 0.0), 4)
    results.sort(key=lambda d: d.get("similarity_score", 0), reverse=True)

    return results


def embedding_text_for_todo(todo: dict) -> str:
    """Combine todo fields into a single string for embedding."""
    parts = []
    if todo.get("description"):
        parts.append(todo["description"])
    if todo.get("notes"):
        parts.append(todo["notes"])
    if todo.get("project"):
        parts.append(f"project: {todo['project']}")
    tags = todo.get("metadata", {}).get("tags", [])
    if tags:
        parts.append(f"tags: {', '.join(str(t) for t in tags)}")
    return " | ".join(parts)


def embedding_text_for_lesson(lesson: dict) -> str:
    """Combine lesson fields into a single string for embedding."""
    parts = []
    if lesson.get("topic"):
        parts.append(lesson["topic"])
    if lesson.get("lesson_learned"):
        parts.append(lesson["lesson_learned"])
    if lesson.get("language"):
        parts.append(f"language: {lesson['language']}")
    tags = lesson.get("tags", [])
    if tags:
        parts.append(f"tags: {', '.join(str(t) for t in tags)}")
    return " | ".join(parts)

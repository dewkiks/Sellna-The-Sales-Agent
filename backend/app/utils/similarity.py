"""Cosine similarity and other vector utility functions.

Used when the vector store is unavailable or when agents need a quick
in-process ranking without a round-trip to Qdrant/FAISS.

Cosine similarity formula:
    cos(θ) = (A · B) / (||A|| * ||B||)

Result is in [-1, 1]; 1 means identical direction, 0 means orthogonal,
-1 means opposite.  For unit-normalised embedding vectors (as produced by
most embedding models), the result is equivalent to the dot product.
"""

from __future__ import annotations

import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two dense vectors.

    Returns 0.0 when either vector is a zero vector (no direction) rather
    than dividing by zero.
    """
    if len(a) != len(b):
        raise ValueError(f"Vector dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))    # A · B
    norm_a = math.sqrt(sum(x * x for x in a)) # ||A||
    norm_b = math.sqrt(sum(x * x for x in b)) # ||B||
    if norm_a == 0 or norm_b == 0:
        # Zero vector has no meaningful direction; similarity is undefined — return 0.
        return 0.0
    return dot / (norm_a * norm_b)


def top_k_similar(
    query: list[float],
    candidates: list[tuple[str, list[float]]],
    k: int = 5,
) -> list[tuple[str, float]]:
    """Return top-k (id, score) pairs sorted by cosine similarity (highest first).

    Args:
        query:      Query embedding vector.
        candidates: List of (id, vector) tuples to rank.
        k:          Number of results to return.
    """
    scored = [(cid, cosine_similarity(query, vec)) for cid, vec in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)  # descending — most similar first
    return scored[:k]

"""Vector store abstraction — supports Qdrant and FAISS.

This module provides a backend-agnostic interface (``VectorStore``) for
storing and searching dense vector embeddings.  It is the foundation of the
RAG (Retrieval-Augmented Generation) layer: competitor web content, cleaned
company data, and persona profiles are embedded and stored here so that
agents can retrieve the most relevant chunks before sending prompts to the LLM.

Two concrete implementations are provided:
  - ``QdrantVectorStore``: production-grade, uses the remote Qdrant service;
    recommended for any real deployment.
  - ``FAISSVectorStore``: purely in-memory flat index; useful for local dev
    and unit tests when a running Qdrant instance is unavailable.

The active backend is selected via the ``VECTOR_STORE`` setting ("qdrant" or
"faiss") and returned as a process-wide singleton via ``get_vector_store()``.

Usage:
    from app.db.vector_store import get_vector_store
    vs = get_vector_store()
    await vs.upsert("collection", id, embedding, payload)
    results = await vs.search("collection", query_embedding, top_k=5)
"""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
_settings = get_settings()


# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------


class VectorSearchResult:
    """A single result returned by a vector similarity search.

    Attributes:
        id:      Document identifier (the ``doc_id`` passed to ``upsert``).
        score:   Similarity score; higher is more similar (cosine distance for
                 Qdrant, inner-product ≈ cosine for normalised FAISS vectors).
        payload: Arbitrary metadata stored alongside the vector at upsert time,
                 e.g. {"text": "...", "competitor_id": "..."}.
    """

    def __init__(self, id: str, score: float, payload: dict[str, Any]):
        self.id = id
        self.score = score
        self.payload = payload


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class VectorStore(ABC):
    """Abstract base class that every vector-store backend must implement.

    Using an ABC here lets the rest of the codebase depend on this interface
    rather than on a specific vendor, making it easy to swap Qdrant for FAISS
    (or any future backend) without touching agent code.
    """

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        doc_id: str,
        embedding: list[float],
        payload: dict[str, Any],
    ) -> None:
        """Insert or update a vector+payload in the named collection."""
        ...

    @abstractmethod
    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> list[VectorSearchResult]:
        """Return the top-k most similar documents above the score threshold."""
        ...

    @abstractmethod
    async def delete(self, collection: str, doc_id: str) -> None:
        """Remove a single document from a collection by its ID."""
        ...

    @abstractmethod
    async def delete_collection(self, collection: str) -> None:
        """Drop an entire collection and all its vectors."""
        ...

    @abstractmethod
    async def delete_all_collections(self) -> int:
        """Drop every collection. Returns the number removed."""
        ...


# ---------------------------------------------------------------------------
# Qdrant implementation
# ---------------------------------------------------------------------------


class QdrantVectorStore(VectorStore):
    """Production vector store backed by Qdrant (remote service).

    Qdrant stores vectors in named *collections*, each configured with a fixed
    dimension and a distance metric.  All operations are fully async via the
    official ``AsyncQdrantClient``.
    """

    def __init__(self) -> None:
        from qdrant_client import AsyncQdrantClient
        from qdrant_client.models import Distance, VectorParams

        # Lazily imported to avoid hard dependency when FAISS backend is chosen.
        self._client = AsyncQdrantClient(
            url=_settings.qdrant_url,
            api_key=_settings.qdrant_api_key,
        )
        self._Distance = Distance
        self._VectorParams = VectorParams
        self._dim = _settings.embedding_dimension  # must match embedding model output size

    async def _ensure_collection(self, collection: str) -> None:
        """Create the collection if it does not exist; ignore 409 Conflict.

        HTTP 409 means the collection already exists — that is fine. Any other
        error (wrong API key, network failure, dimension mismatch) is re-raised.
        """
        from qdrant_client.http.exceptions import UnexpectedResponse
        from qdrant_client.models import Distance, VectorParams
        try:
            await self._client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=self._dim, distance=Distance.COSINE),
            )
        except UnexpectedResponse as e:
            if e.status_code != 409:  # 409 = already exists — safe to ignore
                raise

    async def upsert(
        self,
        collection: str,
        doc_id: str,
        embedding: list[float],
        payload: dict[str, Any],
    ) -> None:
        """Store or overwrite one vector+payload point in Qdrant."""
        from qdrant_client.models import PointStruct
        await self._ensure_collection(collection)
        point = PointStruct(id=doc_id, vector=embedding, payload=payload)
        # Qdrant "upsert" replaces the point if doc_id already exists.
        await self._client.upsert(collection_name=collection, points=[point])

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> list[VectorSearchResult]:
        """Nearest-neighbour search; returns up to top_k results above threshold."""
        await self._ensure_collection(collection)
        hits = await self._client.query_points(
            collection_name=collection,
            query=query_embedding,
            limit=top_k,
            score_threshold=score_threshold,
        )
        return [
            VectorSearchResult(id=str(hit.id), score=hit.score, payload=hit.payload or {})
            for hit in hits.points
        ]

    async def delete(self, collection: str, doc_id: str) -> None:
        from qdrant_client.models import PointIdsList
        await self._client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=[doc_id]),
        )

    async def delete_collection(self, collection: str) -> None:
        """Drop an entire collection. No-op if it doesn't exist."""
        try:
            await self._client.delete_collection(collection_name=collection)
        except Exception as e:  # noqa: BLE001 — missing collection is fine
            logger.warning("vector_store.delete_collection.failed", collection=collection, error=str(e))

    async def delete_all_collections(self) -> int:
        """Drop every Qdrant collection. Returns the number removed."""
        collections = (await self._client.get_collections()).collections
        for c in collections:
            try:
                await self._client.delete_collection(collection_name=c.name)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "vector_store.delete_collection.failed", collection=c.name, error=str(e)
                )
        return len(collections)


# ---------------------------------------------------------------------------
# FAISS implementation (sync, run in executor)
# ---------------------------------------------------------------------------


class FAISSVectorStore(VectorStore):
    """Lightweight local FAISS store. Not recommended for production scale."""

    def __init__(self) -> None:
        import faiss  # type: ignore
        import numpy as np

        self._faiss = faiss
        self._np = np
        self._dim = _settings.embedding_dimension
        self._index_path = Path(_settings.faiss_index_path)
        self._index_path.mkdir(parents=True, exist_ok=True)
        self._indices: dict[str, Any] = {}
        self._payloads: dict[str, dict[str, Any]] = {}  # collection -> {id: payload}
        self._ids: dict[str, list[str]] = {}  # collection -> [id, ...]

    def _get_index(self, collection: str):
        """Return (or lazily create) a flat inner-product index for a collection.

        ``IndexFlatIP`` computes exact inner-product similarity. When vectors
        are L2-normalised (unit length), inner product equals cosine similarity,
        so results are directly comparable to the Qdrant cosine backend.
        """
        if collection not in self._indices:
            idx = self._faiss.IndexFlatIP(self._dim)  # inner product ≈ cosine if normalized
            self._indices[collection] = idx
            self._payloads[collection] = {}
            self._ids[collection] = []
        return self._indices[collection]

    async def upsert(
        self,
        collection: str,
        doc_id: str,
        embedding: list[float],
        payload: dict[str, Any],
    ) -> None:
        """Async wrapper: delegates the sync FAISS call to a thread-pool executor.

        FAISS is a C++ library with no async support; ``run_in_executor`` moves
        the blocking call off the event-loop thread so it doesn't stall other
        coroutines.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._upsert_sync, collection, doc_id, embedding, payload)

    def _upsert_sync(self, collection: str, doc_id: str, embedding: list[float], payload: dict) -> None:
        import numpy as np
        idx = self._get_index(collection)
        vec = np.array([embedding], dtype="float32")
        # L2 normalise so inner product == cosine similarity during search.
        self._faiss.normalize_L2(vec)
        idx.add(vec)
        # Parallel lists: self._ids tracks insertion order so we can map FAISS
        # integer indices back to string doc_ids after a search.
        self._ids[collection].append(doc_id)
        self._payloads[collection][doc_id] = payload

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> list[VectorSearchResult]:
        """Async wrapper: delegates the sync FAISS search to a thread-pool executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._search_sync, collection, query_embedding, top_k, score_threshold
        )

    def _search_sync(
        self, collection: str, query_embedding: list[float], top_k: int, threshold: float
    ) -> list[VectorSearchResult]:
        import numpy as np
        idx = self._get_index(collection)
        if idx.ntotal == 0:
            return []
        vec = np.array([query_embedding], dtype="float32")
        self._faiss.normalize_L2(vec)
        # idx.search returns (scores, indices) arrays shaped (1, top_k).
        scores, indices = idx.search(vec, min(top_k, idx.ntotal))
        results = []
        ids = self._ids[collection]
        payloads = self._payloads[collection]
        for score, i in zip(scores[0], indices[0]):
            # FAISS returns -1 for padded slots when fewer than top_k vectors exist.
            if i < 0 or score < threshold:
                continue
            doc_id = ids[i]
            results.append(VectorSearchResult(id=doc_id, score=float(score), payload=payloads.get(doc_id, {})))
        return results

    async def delete(self, collection: str, doc_id: str) -> None:
        # FAISS flat index doesn't support per-point deletion; we drop the
        # payload so the doc is excluded from results on the application side.
        if collection in self._payloads:
            self._payloads[collection].pop(doc_id, None)

    async def delete_collection(self, collection: str) -> None:
        """Drop an in-memory collection entirely."""
        self._indices.pop(collection, None)
        self._payloads.pop(collection, None)
        self._ids.pop(collection, None)

    async def delete_all_collections(self) -> int:
        """Drop every in-memory collection. Returns the number removed."""
        count = len(self._indices)
        self._indices.clear()
        self._payloads.clear()
        self._ids.clear()
        return count


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    """Return the process-wide vector store singleton.

    ``lru_cache(maxsize=1)`` ensures only one instance is ever created,
    regardless of how many agents or routes call this function.  The backend
    is chosen from the ``VECTOR_STORE`` env setting ("qdrant" | "faiss").
    """
    backend = _settings.vector_store
    logger.info("vector_store.init", backend=backend)
    if backend == "qdrant":
        return QdrantVectorStore()
    return FAISSVectorStore()

"""Embedding Service — async text-to-vector conversion.

Role in architecture
--------------------
RAGService (rag_service.py) calls this module to convert both *documents*
(at index time) and *queries* (at retrieve time) into dense floating-point
vectors.  Those vectors are stored in / searched against Qdrant
(app/db/vector_store.py).

Supports two backends — chosen automatically based on LLM_PROVIDER:

- **SentenceTransformers** (local, free, default when LLM_PROVIDER=groq/grok)
    → model: ``all-MiniLM-L6-v2``  (384 dims, ~90 MB, runs on CPU)
    → SentenceTransformer.encode() is CPU-bound, so it is offloaded to a
      thread pool via ``loop.run_in_executor`` to keep the async event loop
      unblocked.

- **OpenAI** (only when LLM_PROVIDER=openai)
    → model: ``text-embedding-3-small`` (1536 dims)
    → xAI/Grok does NOT offer an embedding API, so the service falls back
      to SentenceTransformers automatically in that case.

Key dependencies
----------------
- ``sentence-transformers`` (optional, installed for local usage)
- ``openai`` AsyncOpenAI client
- ``app.config.get_settings()`` — reads ``active_embedding_backend``,
  ``embedding_model``, ``sentence_transformer_model``
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Sequence

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
_settings = get_settings()


class EmbeddingService:
    """Async text-to-vector service used by RAGService for indexing and retrieval.

    The backend (OpenAI or SentenceTransformers) is selected once at
    construction time based on ``settings.active_embedding_backend`` and
    never changes for the lifetime of the process.
    """

    def __init__(self) -> None:
        # active_embedding_backend auto-forces sentence_transformers when provider=grok
        self._backend = _settings.active_embedding_backend
        logger.info(
            "embedding_service.init",
            backend=self._backend,
            llm_provider=_settings.llm_provider,
        )
        if self._backend == "sentence_transformers":
            self._init_st()
        else:
            self._init_openai()

    def _init_openai(self) -> None:
        """Set up the OpenAI async client for remote embedding calls.

        A separate ``openai_api_key`` is used so the embedding backend can
        remain OpenAI even if the LLM provider is switched to Groq/Ollama.
        """
        from openai import AsyncOpenAI

        # Use OpenAI key specifically for embeddings (separate from LLM provider)
        self._client = AsyncOpenAI(
            api_key=_settings.openai_api_key or "sk-placeholder",
            base_url=_settings.openai_base_url,
        )
        self._model = _settings.embedding_model

    def _init_st(self) -> None:
        """Load the SentenceTransformer model into memory (once, at startup)."""
        from sentence_transformers import SentenceTransformer  # type: ignore

        self._st_model = SentenceTransformer(_settings.sentence_transformer_model)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def embed_one(self, text: str) -> list[float]:
        """Embed a single string. Convenience wrapper around embed_batch."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of strings, dispatching to the active backend.

        Args:
            texts: Non-empty list of strings to embed.

        Returns:
            Parallel list of float vectors (one per input string).
        """
        if not texts:
            return []
        if self._backend == "sentence_transformers":
            return await self._embed_st(texts)
        return await self._embed_openai(texts)

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    async def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        """Call the OpenAI Embeddings API and return the vectors."""
        try:
            response = await self._client.embeddings.create(
                model=self._model, input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as exc:
            logger.error("embedding.openai.error", error=str(exc))
            raise

    async def _embed_st(self, texts: list[str]) -> list[list[float]]:
        """Run SentenceTransformer.encode() in a thread pool.

        encode() is synchronous and CPU-bound; offloading it via
        run_in_executor prevents it from blocking the asyncio event loop
        (which would stall all other concurrent pipeline coroutines).
        ``normalize_embeddings=True`` ensures cosine-similarity scores are
        in [0, 1] without further normalisation at retrieval time.
        """
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(
            None, lambda: self._st_model.encode(texts, normalize_embeddings=True).tolist()
        )
        return embeddings


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Return the process-wide singleton EmbeddingService instance.

    ``lru_cache(maxsize=1)`` ensures the model is loaded exactly once,
    regardless of how many agents call this function concurrently.
    """
    return EmbeddingService()

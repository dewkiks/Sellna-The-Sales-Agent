"""RAG Service — Retrieval-Augmented Generation.

Role in architecture
--------------------
Three pipeline stages use RAG to ground their LLM calls in factual,
project-specific data instead of relying purely on model weights:

- **GapAnalysisAgent** (Stage 5): indexes cleaned competitor profiles,
  retrieves the most relevant chunks, then asks the LLM to identify gaps.
- **PersonaAgent** (Stage 7): retrieves gap-analysis context to build
  data-grounded buyer personas for each ICP.
- **OutreachAgent** (Stage 8): retrieves persona + gap context to write
  personalised outreach copy for each buyer persona.

RAG pipeline (custom, no LangChain dependency)
----------------------------------------------
1. **Index**   — ``index_documents(collection, docs)``:
   embed each document with EmbeddingService → upsert into Qdrant collection.

2. **Retrieve** — ``retrieve(collection, query)``:
   embed the query → cosine similarity search in Qdrant → return top-k text
   chunks whose score exceeds ``score_threshold``.

3. **Generate** — ``query(collection, question)``:
   build a system + user message where the retrieved chunks are injected as
   ``Context:`` → call LLMService.chat() → return the answer string.

The convenience method ``index_and_query`` runs all three steps in sequence.

Key dependencies
----------------
- ``app.db.vector_store`` (Qdrant wrapper) — stores and searches embeddings
- ``app.services.embedding_service`` — converts text to vectors
- ``app.services.llm_service`` — generates the final answer

Named collections
-----------------
Each pipeline run scopes its data to a collection named after the company
(e.g. ``gap_<company_id>``), preventing data leakage between companies.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.config import get_settings
from app.core.logging import get_logger
from app.db.vector_store import get_vector_store
from app.services.embedding_service import get_embedding_service
from app.services.llm_service import get_llm_service

logger = get_logger(__name__)
_settings = get_settings()


class RAGService:
    """Retrieval-Augmented Generation over a named Qdrant collection.

    Instantiate directly (not a singleton) — agents that use RAG create
    their own instance but the underlying service singletons
    (vector_store, embedding_service, llm_service) are shared.
    """

    def __init__(self) -> None:
        # All three dependencies are process-wide singletons — no I/O at init.
        self._vs = get_vector_store()
        self._embed = get_embedding_service()
        self._llm = get_llm_service()

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    async def index_documents(
        self,
        collection: str,
        documents: list[str],
        payloads: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        """Embed and upsert documents into a Qdrant collection (RAG Step 1).

        Each document gets a fresh UUID as its point ID.  The raw text is
        stored in the Qdrant payload under the key ``"text"`` so it can be
        retrieved later without a separate database lookup.

        Args:
            collection: Qdrant collection name (e.g. ``"gap_<company_id>"``).
            documents:  Plaintext chunks to index.
            payloads:   Optional parallel list of extra metadata dicts to
                        merge into each document's Qdrant payload.

        Returns:
            List of UUID strings assigned to the upserted points.
        """
        if not documents:
            return []

        # Batch-embed all documents in one API/model call for efficiency.
        embeddings = await self._embed.embed_batch(documents)
        ids: list[str] = []

        for i, (doc, emb) in enumerate(zip(documents, embeddings)):
            doc_id = str(uuid.uuid4())
            # Always store the raw text so retrieve() can return it directly.
            payload: dict[str, Any] = {"text": doc}
            if payloads and i < len(payloads):
                payload.update(payloads[i])
            await self._vs.upsert(collection, doc_id, emb, payload)
            ids.append(doc_id)

        logger.info("rag.indexed", collection=collection, count=len(ids))
        return ids

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        collection: str,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.3,
    ) -> list[str]:
        """Find the most semantically similar document chunks (RAG Step 2).

        Embeds ``query`` with EmbeddingService, runs a cosine-similarity search
        in Qdrant, and filters results below ``score_threshold`` to avoid
        injecting irrelevant noise into the LLM context.

        Args:
            collection:      Qdrant collection to search.
            query:           Natural-language question or task description.
            top_k:           Maximum number of chunks to return.
            score_threshold: Minimum cosine similarity (0–1) to include a hit.

        Returns:
            List of raw text strings (from the Qdrant payload ``"text"`` field).
        """
        query_emb = await self._embed.embed_one(query)
        hits = await self._vs.search(collection, query_emb, top_k=top_k, score_threshold=score_threshold)
        return [hit.payload.get("text", "") for hit in hits]

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    async def query(
        self,
        collection: str,
        question: str,
        system_prompt: str = "",
        top_k: int = 5,
        json_mode: bool = False,
    ) -> str:
        """Execute the full RAG cycle: retrieve → augment → generate (Steps 2 + 3).

        Retrieved chunks are concatenated with ``---`` separators and injected
        into the user message as ``Context:``.  This grounds the LLM in real
        data from the collection (e.g. cleaned competitor profiles) rather than
        having it hallucinate answers.

        Args:
            collection:   Qdrant collection to retrieve from.
            question:     The task or question to answer.
            system_prompt: Override the default sales-expert persona if needed.
            top_k:        Maximum number of retrieved chunks to inject.
            json_mode:    If True, the LLM is instructed to return JSON only.

        Returns:
            The LLM's answer as a string (may be JSON if ``json_mode=True``).
        """
        chunks = await self.retrieve(collection, question, top_k=top_k)

        if not system_prompt:
            system_prompt = (
                "You are a strategic sales intelligence expert. "
                "Answer the question using ONLY the provided context. "
                "Be specific and actionable."
            )

        # Separate chunks visually so the LLM sees them as distinct sources.
        context = "\n\n---\n\n".join(chunks) if chunks else "No context available."

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Context:\n{context}\n\n"
                    f"Task:\nIdentify the key insights relevant to:\n{question}\n\n"
                    f"Return concise JSON."
                ),
            },
        ]

        answer = await self._llm.chat(messages, json_mode=json_mode)
        logger.info("rag.query.complete", collection=collection, chunks_used=len(chunks))
        return answer

    # ------------------------------------------------------------------
    # Convenience: index + query in one call
    # ------------------------------------------------------------------

    async def index_and_query(
        self,
        collection: str,
        documents: list[str],
        question: str,
        system_prompt: str = "",
        top_k: int = 5,
        json_mode: bool = False,
    ) -> str:
        """One-shot helper: index documents then immediately query them.

        Useful when an agent builds a temporary collection for a single query
        (e.g. GapAnalysisAgent populating and querying ``gap_<company_id>``
        in the same request).  Equivalent to calling ``index_documents`` then
        ``query`` sequentially.
        """
        await self.index_documents(collection, documents)
        return await self.query(collection, question, system_prompt=system_prompt, top_k=top_k, json_mode=json_mode)

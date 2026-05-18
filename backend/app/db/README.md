# app/db — Database Layer

The `db` package is the single source of truth for all persistent storage in Sellna.ai.
It covers two distinct storage systems: a relational PostgreSQL database (via SQLAlchemy 2.x async ORM)
for structured entity data, and a vector store (Qdrant in production, FAISS locally) for dense
embedding search that powers the RAG (Retrieval-Augmented Generation) layer used by agents.

## Files

| File | Description |
|---|---|
| `__init__.py` | Package marker; consumers import directly from sub-modules. |
| `postgres.py` | Async SQLAlchemy engine, session factory, all ORM models, and DB lifecycle helpers (`create_all_tables`, `dispose_engine`). |
| `vector_store.py` | Backend-agnostic `VectorStore` ABC with Qdrant and FAISS implementations; singleton factory `get_vector_store()`. |
| `repositories/__init__.py` | Repository classes — one per entity — each wrapping typed CRUD operations over the ORM models. |

## Architecture fit

```
FastAPI route / pipeline stage
        |
        v
 Repository class          <-- app/db/repositories/
 (session injected)
        |
        v
 SQLAlchemy ORM model      <-- app/db/postgres.py
 (asyncpg → PostgreSQL)
```

Agents also call `get_vector_store()` directly to embed and search competitor
text for RAG context:

```
Agent
  |-- embed text ---------> VectorStore.upsert(collection, id, vector, payload)
  |-- semantic search ----> VectorStore.search(collection, query_vector, top_k)
```

The repository pattern keeps all database access in one place: agents and
routes call repository methods rather than writing raw SQL, which makes it
easier to test, audit, and swap the underlying store.

`flush()` is used inside repositories instead of `commit()` so the calling
service or route handler controls the transaction boundary.

## Likely exam questions

**Q: What is the repository pattern and why does this project use it?**
A: The repository pattern wraps all database access in dedicated classes with entity-specific methods (create, get, update, delete). Agents call repository methods rather than writing SQL directly, keeping business logic separate from persistence logic and making the DB layer easy to test or swap.

**Q: How does the vector store enable RAG?**
A: Competitor and company text is converted to dense embedding vectors and stored in Qdrant (or FAISS). When an agent needs context, it embeds its query and calls `VectorStore.search()` to retrieve the most semantically similar chunks — these are then injected into the LLM prompt as grounding evidence.

**Q: Why are Qdrant and FAISS both supported?**
A: Qdrant is the production backend (persistent, scalable, remote service). FAISS is an in-memory fallback for local development and unit tests where a running Qdrant instance is inconvenient. The `VectorStore` ABC means the rest of the code doesn't need to know which is active.

**Q: Why does `async_session_factory` use `expire_on_commit=False`?**
A: In async SQLAlchemy, accessing an attribute after a commit would normally trigger a lazy SELECT — which requires the session to be open. `expire_on_commit=False` disables this expiry so attributes remain readable without an extra round-trip, which is critical in async code where the session may already be closed.

**Q: Why use JSONB columns instead of fully normalised tables for agent output?**
A: Agent outputs (ICP profiles, personas, market gaps, outreach content) are complex nested documents that vary in structure and evolve as the LLM prompts change. Storing them as JSONB avoids frequent schema migrations while still allowing indexed queries in PostgreSQL.

**Q: What does `_ensure_collection` do in `QdrantVectorStore`, and why is a 409 ignored?**
A: It creates the Qdrant collection on first use. HTTP 409 Conflict means the collection already exists, which is harmless — so only that status code is silently swallowed; any other error (wrong API key, dimension mismatch) is re-raised.

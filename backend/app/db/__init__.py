# sales_agentic_ai/app/db/__init__.py
"""Database package initializer.

Re-exports nothing by itself; consumers import directly from
``app.db.postgres`` (ORM models, engine, session factory) or
``app.db.vector_store`` (Qdrant/FAISS abstraction).
"""

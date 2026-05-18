# sales_agentic_ai/app/services/__init__.py
"""
Services package — shared infrastructure used by every agent in the pipeline.

This package provides four cross-cutting capabilities:

- ``llm_service``       — provider-agnostic async LLM client (OpenAI SDK protocol)
- ``embedding_service`` — text → dense vector conversion (OpenAI or SentenceTransformers)
- ``rag_service``       — Retrieval-Augmented Generation: index / retrieve / generate
- ``scraping_service``  — high-level async web scraper that wraps the project-level
                          ``scrapper_module`` (httpx + Playwright + social scrapers)

All services are singletons obtained via ``lru_cache`` factory functions
(e.g. ``get_llm_service()``) so they are constructed once per process and
shared across concurrent agent coroutines.
"""

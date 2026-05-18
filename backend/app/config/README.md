# app/config — Application Configuration

This package is the single source of truth for every externally configurable value in the Sellna.ai backend. It uses Pydantic Settings to read values from environment variables and a `.env` file, validate them at startup, and expose them as a typed, cached `Settings` singleton that any module can import with `from app.config import get_settings`.

## Files

| File | Description |
|---|---|
| `__init__.py` | Re-exports `Settings` and `get_settings` for convenient top-level import |
| `settings.py` | `Settings` class (Pydantic BaseSettings) and `get_settings()` cached factory |

## Key Settings groups

| Group | Key fields |
|---|---|
| App | `app_name`, `environment`, `debug` |
| Security | `secret_key`, `jwt_algorithm`, `jwt_expire_minutes`, `cors_origins` |
| Database | `database_url`, `db_pool_size` |
| Redis / Celery | `redis_url`, `celery_broker_url`, `celery_result_backend` |
| LLM provider | `llm_provider` (chooses among openai/groq/grok/ollama/nvidia/gemini/openrouter/custom), per-provider key/url/model |
| Embeddings | `embedding_backend`, `sentence_transformer_model`, `embedding_dimension` |
| Scraping | `max_concurrent_requests`, `request_timeout`, `browser_headless` |
| Logging | `log_level`, `log_format` ("json" or "console") |
| Pipeline | `pipeline_timeout_seconds` |

## How this folder fits the architecture

`get_settings()` is called at module import time in `app/core/logging.py`, `app/core/security.py`, `app/workers/celery_app.py`, and `app/services/llm_service.py`. Because it is decorated with `@lru_cache(maxsize=1)`, the `.env` file is parsed exactly once per process. In tests, `get_settings.cache_clear()` can reset the singleton between test runs if needed.

The three provider-dispatch properties (`llm_model`, `llm_base_url`, `llm_api_key`) mean that `LLMService` never branches on the provider name — it always reads `settings.llm_model` and `settings.llm_base_url`, and the Settings object handles the dispatch internally.

## Likely exam questions

**Q: How is configuration loaded, and where does it come from?**
A: `Settings` extends `pydantic_settings.BaseSettings`. On construction it reads from (in priority order): environment variables, the `.env` file at the project root, then the field defaults defined in the class. `get_settings()` is decorated with `@lru_cache(maxsize=1)` so this happens only once per process.

**Q: How do you switch from Groq to OpenAI without changing code?**
A: Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY=sk-...` in `.env`. The `llm_model`, `llm_base_url`, and `llm_api_key` properties dispatch on `llm_provider` and return the corresponding `openai_*` fields. All call sites use `settings.llm_model` etc., so no code changes are needed.

**Q: What happens if you set `LLM_PROVIDER=groq` but forget to set `GROQ_API_KEY`?**
A: The `@model_validator(mode="after")` `validate_active_provider_key` method runs at startup and raises a `ValueError` if the active provider's API key is empty or still contains the placeholder "YOUR_". Pydantic surfaces this as a clear error before the server accepts any requests.

**Q: Why are `llm_model`, `llm_base_url`, etc. `@property` methods rather than plain fields?**
A: They depend on the value of `llm_provider`, which is only known after all fields are populated. Properties are computed on demand, so they always reflect the current `llm_provider` without needing a validator to copy values around.

**Q: What does `active_embedding_backend` do and why does it exist?**
A: Some providers (Grok, Groq, OpenRouter, NVIDIA) do not offer an embedding API. If a user sets `EMBEDDING_BACKEND=openai` while using one of these providers, the property silently falls back to `sentence_transformers` (a local model), preventing a runtime authentication error when the vector store tries to embed text.

**Q: What does `CORS_ORIGINS` control and how is it parsed?**
A: It is a comma-separated string of allowed browser origins (e.g. `http://localhost:3000`). The `cors_origins_list` property splits it into a Python list that FastAPI's `CORSMiddleware` can consume. Storing it as a string is necessary because Pydantic Settings cannot split comma-separated values from `.env` files into lists automatically.

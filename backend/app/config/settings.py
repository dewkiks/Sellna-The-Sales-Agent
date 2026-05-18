"""Application configuration via Pydantic Settings.

All externally configurable values live here.  Populate via environment
variables or a ``.env`` file at the project root.

How configuration is loaded
---------------------------
``Settings`` extends ``pydantic_settings.BaseSettings``.  On instantiation,
Pydantic reads values from (in priority order):
  1. Environment variables (highest priority — useful in Docker/CI)
  2. The .env file at the project root (convenient for local dev)
  3. The field defaults defined in this class (lowest priority)

Field names are case-insensitive (``DATABASE_URL`` and ``database_url`` both
map to ``Settings.database_url``).  Extra fields in .env are silently ignored.

``get_settings()`` is decorated with ``@lru_cache(maxsize=1)`` so the file is
parsed exactly once per process, regardless of how many modules call it.

Key design patterns
-------------------
- ``llm_model``, ``llm_base_url``, ``llm_api_key`` are computed ``@property``
  values that dispatch on ``llm_provider``, returning the matching per-provider
  fields.  This keeps call-sites provider-agnostic.
- ``llm_extra_body`` returns a provider-specific dict (e.g. NVIDIA thinking
  mode) that gets passed as ``extra_body`` to the OpenAI SDK.
- ``active_embedding_backend`` falls back to sentence_transformers for
  providers (Grok, Groq, OpenRouter, NVIDIA) that have no embedding API.
- A ``@model_validator`` runs after all fields are populated to ensure the
  selected LLM provider has a real API key before the app starts.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised configuration object for the entire Sellna.ai backend.

    Instantiate via ``get_settings()`` (never directly) to ensure the
    @lru_cache singleton guarantee and avoid re-reading the .env file.
    """

    # SettingsConfigDict tells Pydantic how to load from the environment.
    model_config = SettingsConfigDict(
        env_file=".env",           # path relative to the process working directory
        env_file_encoding="utf-8",
        case_sensitive=False,      # DATABASE_URL == database_url
        extra="ignore",            # unknown .env keys don't raise an error
    )

    # ------------------------------------------------------------------
    # App
    # ------------------------------------------------------------------
    app_name: str = "Sales Agentic AI"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # ------------------------------------------------------------------
    # API / Security
    # ------------------------------------------------------------------
    secret_key: str = Field(
        default="CHANGE_ME_IN_PRODUCTION_USE_A_LONG_RANDOM_STRING",
        description="JWT signing secret — MUST be overridden in production",
    )
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 hours

    # Comma-separated list of allowed CORS origins
    cors_origins: str = "http://localhost:3000,http://localhost:8000,http://localhost:8080,http://127.0.0.1:8080"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse the comma-separated CORS_ORIGINS string into a list.

        Pydantic Settings doesn't natively split comma-separated strings into
        lists when reading from a .env file, so we store the raw string and
        expose a property for FastAPI's CORSMiddleware.
        """
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ------------------------------------------------------------------
    # Database — PostgreSQL
    # ------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/sales_ai",
        description="Async SQLAlchemy connection URL",
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False  # flip to True to log SQL

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ------------------------------------------------------------------
    # Vector Store
    # ------------------------------------------------------------------
    vector_store: Literal["qdrant", "faiss"] = "qdrant"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "sales_ai_embeddings"

    # FAISS (local fallback)
    faiss_index_path: str = "./data/faiss_index"

    # ------------------------------------------------------------------
    # LLM Provider — switch between openai | grok | groq | openrouter
    #                            | nvidia | gemini | ollama | custom
    # ------------------------------------------------------------------
    llm_provider: Literal[
        "openai", "grok", "groq", "openrouter", "nvidia", "gemini", "ollama", "custom"
    ] = "groq"

    # --- xAI / Grok ---
    grok_api_key: str = Field(default="", description="xAI API key (format: xai-...)")
    grok_base_url: str = "https://api.x.ai/v1"
    grok_model: str = "grok-3-beta"   # or grok-2-1212, grok-beta

    # --- OpenAI (set llm_provider=openai to use) ---
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # --- Ollama (local, set llm_provider=ollama) ---
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3"
    ollama_api_key: str = "ollama"   # Ollama ignores this but SDK requires it

    # --- Groq (set llm_provider=groq) ---
    groq_api_key: str = Field(default="", description="Groq API key (format: gsk_...)")
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"  # fast + capable; alt: mixtral-8x7b-32768

    # --- OpenRouter (set llm_provider=openrouter) ---
    openrouter_api_key: str = Field(default="", description="OpenRouter API key (format: sk-or-...)")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"

    # --- NVIDIA (set llm_provider=nvidia) — OpenAI-compatible NIM endpoint ---
    nvidia_api_key: str = Field(default="", description="NVIDIA API key (format: nvapi-...)")
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "deepseek-ai/deepseek-v4-flash"
    nvidia_thinking: bool = True  # send chat_template_kwargs={"thinking": ...} (reasoning models)
    # reasoning_effort for reasoning models — "" disables it (not all models accept it)
    nvidia_reasoning_effort: Literal["", "low", "medium", "high"] = "high"

    # --- Google Gemini (set llm_provider=gemini) — OpenAI-compatible endpoint ---
    gemini_api_key: str = Field(default="", description="Google AI Studio key (format: AIza...)")
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_model: str = "gemini-2.0-flash"

    # --- Custom / Any other OpenAI-compatible endpoint ---
    custom_base_url: str = ""
    custom_api_key: str = ""
    custom_model: str = ""

    # --- Shared LLM settings ---
    llm_temperature: float = 0.2
    llm_max_tokens: int = 400

    @property
    def llm_model(self) -> str:
        """Active model name based on selected provider.

        LLMService uses this so it never needs to branch on llm_provider itself.
        To switch providers, change LLM_PROVIDER in .env — everything else
        follows automatically.
        """
        return {
            "grok": self.grok_model,
            "openai": self.openai_model,
            "ollama": self.ollama_model,
            "groq": self.groq_model,
            "openrouter": self.openrouter_model,
            "nvidia": self.nvidia_model,
            "gemini": self.gemini_model,
            "custom": self.custom_model,
        }[self.llm_provider]

    @property
    def llm_base_url(self) -> str:
        """Active OpenAI-compatible base URL based on selected provider.

        All supported providers expose an OpenAI-compatible REST API, so a
        single LLMService can talk to any of them by changing only the
        base_url and api_key.
        """
        return {
            "grok": self.grok_base_url,
            "openai": self.openai_base_url,
            "ollama": self.ollama_base_url,
            "groq": self.groq_base_url,
            "openrouter": self.openrouter_base_url,
            "nvidia": self.nvidia_base_url,
            "gemini": self.gemini_base_url,
            "custom": self.custom_base_url,
        }[self.llm_provider]

    @property
    def llm_api_key(self) -> str:
        """Active API key based on selected provider.

        Ollama uses a dummy value ("ollama") because the local server does not
        require authentication, but the OpenAI SDK requires a non-empty string.
        """
        return {
            "grok": self.grok_api_key,
            "openai": self.openai_api_key,
            "ollama": self.ollama_api_key,
            "groq": self.groq_api_key,
            "openrouter": self.openrouter_api_key,
            "nvidia": self.nvidia_api_key,
            "gemini": self.gemini_api_key,
            "custom": self.custom_api_key,
        }[self.llm_provider]

    @property
    def llm_extra_body(self) -> dict:
        """Provider-specific extra request-body fields (non-OpenAI-standard params).

        NVIDIA NIM reasoning models (e.g. Kimi) accept ``chat_template_kwargs``
        to toggle thinking mode — passed via the OpenAI SDK's ``extra_body``.
        """
        if self.llm_provider == "nvidia":
            kwargs: dict = {"thinking": self.nvidia_thinking}
            if self.nvidia_reasoning_effort:
                kwargs["reasoning_effort"] = self.nvidia_reasoning_effort
            return {"chat_template_kwargs": kwargs}
        return {}

    @model_validator(mode="after")
    def validate_active_provider_key(self) -> Settings:
        """Fail fast if the active LLM provider has no real API key.

        mode="after" means this validator runs once all fields are already
        assigned, so llm_api_key (a property) is safe to call.  Raising
        ValueError here causes Pydantic to surface it as a clear startup error
        rather than an obscure authentication failure at runtime.
        """
        # Ollama is a local server — no real API key needed.
        if self.llm_provider == "ollama":
            return self

        key = self.llm_api_key
        # Reject empty strings and placeholder values like "YOUR_GROQ_API_KEY".
        if not key or "YOUR_" in key.upper():
            raise ValueError(
                f"Missing or invalid API key for active provider '{self.llm_provider}'. "
                f"Please update {self.llm_provider.upper()}_API_KEY in your .env file."
            )
        return self
        

    # ------------------------------------------------------------------
    # Embeddings
    # NOTE: xAI/Grok does NOT offer an embedding API.
    #   When llm_provider=grok, embedding_backend auto-defaults to
    #   sentence_transformers (local, free, no API key needed).
    # ------------------------------------------------------------------
    embedding_backend: Literal["openai", "sentence_transformers"] = "sentence_transformers"
    embedding_model: str = "text-embedding-3-small"   # used only when backend=openai
    embedding_dimension: int = 384   # 384 for all-MiniLM-L6-v2, 1536 for OpenAI
    sentence_transformer_model: str = "all-MiniLM-L6-v2"

    @property
    def active_embedding_backend(self) -> str:
        """Resolve which embedding backend to actually use.

        Some LLM providers (Grok, Groq, OpenRouter, NVIDIA) do not expose an
        embedding API compatible with the OpenAI ``/embeddings`` endpoint.  If
        the user sets ``EMBEDDING_BACKEND=openai`` while also using one of these
        providers, this property silently falls back to sentence_transformers
        (a local model, no API key required) to avoid a runtime error.
        """
        if self.llm_provider in ("grok", "groq", "openrouter", "nvidia") and self.embedding_backend == "openai":
            return "sentence_transformers"
        return self.embedding_backend

    # ------------------------------------------------------------------
    # Scraping (inherited from existing module)
    # ------------------------------------------------------------------
    max_concurrent_requests: int = 5
    request_timeout: int = 30
    retry_times: int = 3
    browser_headless: bool = True

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------
    prometheus_enabled: bool = True
    prometheus_path: str = "/metrics"

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------
    pipeline_timeout_seconds: int = 300  # per-stage timeout


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance.

    The @lru_cache decorator ensures the .env file is parsed and all
    validators run exactly once for the lifetime of the process.  Subsequent
    calls return the same object instantly.  If you need to reload settings
    in tests, call ``get_settings.cache_clear()`` first.
    """
    return Settings()

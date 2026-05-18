"""LLM Service — pluggable provider-aware async client.

Role in architecture
--------------------
Every agent in the pipeline (DomainAgent, CompetitorAgent, GapAnalysisAgent,
ICPAgent, PersonaAgent, OutreachAgent, …) calls ``get_llm_service().chat()``
to interact with the language model.  RAGService also uses this service for
the *generate* step of its RAG cycle.

All providers use the **OpenAI Python SDK** — only ``base_url`` and ``api_key``
change per provider.  This means switching from Groq to Ollama to NVIDIA is
a single ``.env`` change with no code modifications.

Supported providers
-------------------
- Groq          → LLM_PROVIDER=groq        + GROQ_API_KEY=gsk_...
- Grok (xAI)    → LLM_PROVIDER=grok        + GROK_API_KEY=xai-...
- OpenAI        → LLM_PROVIDER=openai      + OPENAI_API_KEY=sk-...
- OpenRouter    → LLM_PROVIDER=openrouter  + OPENROUTER_API_KEY=sk-or-...
- NVIDIA        → LLM_PROVIDER=nvidia      + NVIDIA_API_KEY=nvapi-...
- Gemini        → LLM_PROVIDER=gemini      + GEMINI_API_KEY=AIza...
- Ollama        → LLM_PROVIDER=ollama      (no key needed, local server)
- Custom        → LLM_PROVIDER=custom      + CUSTOM_BASE_URL + CUSTOM_API_KEY

Key features
------------
- **Streaming**: pass ``on_token`` to receive content deltas in real time
  (used by the pipeline to push live output to the frontend via SSE).
- **Reasoning model support**: ``on_reasoning`` receives thinking-chain deltas
  (``delta.reasoning_content`` / ``delta.reasoning``) separately from the
  final answer content.
- **Retry with backoff**: up to 4 attempts on HTTP 429 rate-limit responses,
  with exponential waits of 3 s, 6 s, and 12 s.
- **JSON mode**: ``json_mode=True`` instructs the model to output valid JSON
  (with an Ollama-specific workaround that injects an instruction into the
  system prompt, since Ollama doesn't honour ``response_format`` cleanly).

Key dependencies
----------------
- ``openai`` AsyncOpenAI (used for ALL providers via base_url routing)
- ``app.config.get_settings()`` — ``llm_provider``, ``llm_model``,
  ``llm_base_url``, ``llm_api_key``, ``llm_temperature``, ``llm_max_tokens``,
  ``llm_extra_body``
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
_settings = get_settings()


class LLMService:
    """Async LLM wrapper — provider is selected at construction from settings.

    One instance is shared across all agents via ``get_llm_service()``.
    The underlying ``AsyncOpenAI`` client is thread-safe and reuses its
    internal ``httpx.AsyncClient`` connection pool across calls.
    """

    def __init__(self) -> None:
        from openai import AsyncOpenAI

        provider = _settings.llm_provider
        api_key = _settings.llm_api_key or "placeholder"   # Ollama/local don't need a real key
        base_url = _settings.llm_base_url

        logger.info(
            "llm_service.init",
            provider=provider,
            model=_settings.llm_model,
            base_url=base_url,
        )

        # A single AsyncOpenAI client handles ALL providers — the provider's
        # API endpoint is expressed purely via base_url (e.g. Groq uses
        # https://api.groq.com/openai/v1, Ollama uses http://localhost:11434/v1).
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._provider = provider

    def _build_kwargs(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        extra_kwargs: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Assemble the keyword-arguments dict for a chat completion call.

        Handles:
        - Standard chat parameters (model, messages, temperature, max_tokens).
        - JSON mode: injects ``response_format`` and, for Ollama, an extra
          system-prompt instruction (Ollama ignores ``response_format`` alone).
        - ``llm_extra_body``: provider-specific body fields (e.g. NVIDIA's
          ``thinking`` flag for reasoning mode) merged in last so they can
          override defaults if needed.

        Args:
            messages:      OpenAI-format message list.
            model:         Model identifier string.
            temperature:   Sampling temperature (0 = deterministic).
            max_tokens:    Upper bound on response length.
            json_mode:     Whether to request structured JSON output.
            extra_kwargs:  Caller-supplied overrides applied after all else.

        Returns:
            Dict ready to be unpacked into ``client.chat.completions.create(**)``.
        """
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": 0.8,
        }
        if json_mode:
            if self._provider == "ollama":
                # Ollama does not reliably honour response_format alone; augment
                # the system prompt to guarantee JSON-only output.
                msgs = list(messages)
                if msgs and msgs[0]["role"] == "system":
                    msgs[0] = {
                        "role": "system",
                        "content": msgs[0]["content"] + "\n\nIMPORTANT: You MUST respond with ONLY valid JSON. No markdown, no explanation, no code fences.",
                    }
                else:
                    msgs.insert(0, {
                        "role": "system",
                        "content": "You MUST respond with ONLY valid JSON. No markdown, no explanation, no code fences.",
                    })
                kwargs["messages"] = msgs
                kwargs["response_format"] = {"type": "json_object"}
            else:
                kwargs["response_format"] = {"type": "json_object"}
        # Provider-specific non-standard body fields (e.g. NVIDIA thinking mode).
        provider_extra_body = _settings.llm_extra_body
        if provider_extra_body:
            kwargs["extra_body"] = {**provider_extra_body, **(kwargs.get("extra_body") or {})}
        if extra_kwargs:
            kwargs.update(extra_kwargs)
        return kwargs

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
        on_token: Callable[[str], None] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> str:
        """Send a chat request and return the assistant reply as a string.

        If ``on_token`` or ``on_reasoning`` is provided the request uses
        streaming mode. ``on_token`` receives answer-content deltas; the
        returned string is built only from these. ``on_reasoning`` receives
        the reasoning-model thinking deltas (``delta.reasoning_content`` /
        ``delta.reasoning``) and is never folded into the return value.
        """
        model = model or _settings.llm_model
        temperature = temperature if temperature is not None else _settings.llm_temperature
        max_tokens = max_tokens or _settings.llm_max_tokens

        kwargs = self._build_kwargs(messages, model, temperature, max_tokens, json_mode, extra_kwargs)

        t0 = time.perf_counter()
        last_exc: Exception | None = None
        # Up to 4 attempts total (initial + 3 retries on rate-limit).
        for attempt in range(4):
            try:
                if on_token is not None or on_reasoning is not None:
                    # ── Streaming path ──────────────────────────────────────
                    # ``stream=True`` makes the SDK return an async generator
                    # of SSE chunks instead of waiting for the full response.
                    # Each chunk contains a delta for either the reasoning
                    # chain or the final answer content.
                    kwargs["stream"] = True
                    stream = await self._client.chat.completions.create(**kwargs)
                    content = ""
                    async for chunk in stream:
                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta
                        # Reasoning models (e.g. DeepSeek-R1, NVIDIA Llama-3 Nemotron)
                        # emit thinking on a non-standard field.  We check both
                        # field names for cross-provider compatibility.
                        reasoning = (
                            getattr(delta, "reasoning_content", None)
                            or getattr(delta, "reasoning", None)
                        )
                        if reasoning and on_reasoning is not None:
                            on_reasoning(reasoning)
                        text = delta.content or ""
                        if text:
                            # Fire the caller's token callback (e.g. for SSE push)
                            # and accumulate the full reply to return at the end.
                            if on_token is not None:
                                on_token(text)
                            content += text
                    elapsed = time.perf_counter() - t0
                    logger.info(
                        "llm.chat.stream.complete",
                        provider=self._provider,
                        model=model,
                        elapsed_ms=round(elapsed * 1000),
                        chars=len(content),
                    )
                    return content
                else:
                    # ── Non-streaming path ───────────────────────────────────
                    # Used when the caller only needs the final string and does
                    # not need live token delivery (e.g. JSON-mode calls).
                    response = await self._client.chat.completions.create(**kwargs)
                    elapsed = time.perf_counter() - t0
                    content = response.choices[0].message.content or ""
                    logger.info(
                        "llm.chat.complete",
                        provider=self._provider,
                        model=model,
                        elapsed_ms=round(elapsed * 1000),
                        prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                        completion_tokens=response.usage.completion_tokens if response.usage else 0,
                    )
                    return content
            except Exception as exc:
                # Retry on 429 rate-limit with exponential backoff.
                # Non-rate-limit errors are re-raised immediately.
                is_rate_limit = "429" in str(exc) or "rate_limit" in str(exc).lower()
                if is_rate_limit and attempt < 3:
                    wait = 2 ** attempt * 3  # 3 s → 6 s → 12 s
                    logger.warning(
                        "llm.chat.rate_limit_retry",
                        attempt=attempt + 1,
                        wait_seconds=wait,
                        model=model,
                    )
                    await asyncio.sleep(wait)
                    last_exc = exc
                    continue
                logger.error("llm.chat.error", provider=self._provider, error=str(exc), model=model)
                raise
        raise last_exc  # type: ignore[misc]

    async def classify(self, text: str, categories: list[str], context: str = "") -> str:
        """Single-turn zero-shot text classifier.

        Sends one prompt asking the model to pick the single best category,
        then validates the response against the allowed list.

        Args:
            text:       The text to classify.
            categories: Exhaustive list of allowed category strings.
            context:    Optional extra context prepended to the user message.

        Returns:
            The matched category string, or ``categories[0]`` as a safe
            default when the model returns an unrecognised value.
        """
        system = (
            f"You are a precise classifier. Given text, choose the SINGLE best category from: "
            f"{', '.join(categories)}. Respond with ONLY the category name, no explanation."
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"{context}\n\nText: {text}"},
        ]
        # temperature=0 → deterministic; max_tokens=50 → category name only
        result = await self.chat(messages, temperature=0.0, max_tokens=50)
        result = result.strip().strip('"').strip("'")
        return result if result in categories else categories[0]


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    """Return the process-wide singleton LLMService instance.

    ``lru_cache(maxsize=1)`` constructs the client (and loads provider config)
    exactly once regardless of how many agents call this concurrently.
    """
    return LLMService()

"""Outreach Agent — pipeline stage 9 (final stage, RAG-powered).

Generates personalized, multi-channel outreach copy for every BuyerPersona
produced by PersonaAgent.  This is the last stage in the sequential
pipeline and the one with the highest creativity requirement.

Channel types supported:
  - ``cold_email``  — subject line, 150–250 word body, CTA, personalization tokens
  - ``linkedin``    — connection-request note + follow-up message
  - ``call_opener`` — 30-second script with pattern-interrupt opener

RAG flow (when a rag_collection is provided):
  - Query the existing gap collection (built by GapAnalysisAgent in stage 6)
    with a persona-specific query ("messaging for <title> dealing with <pains>").
  - Inject the top-3 competitor intelligence chunks into every channel prompt
    so the copy references real market differentiators, not generic claims.

Concurrency: all channel prompts for a given persona are issued in parallel
via ``asyncio.gather``, so three LLM calls happen simultaneously.  A failed
channel is skipped (returns None, filtered out) so one bad LLM response
never blocks the others.

Temperature 0.6: highest in the pipeline — outreach copy must sound human
and varied, not robotic or repetitive across similar personas.

Pipeline position: final stage — consumes BuyerPersona + CompanyAnalysis,
produces OutreachAsset list persisted to the DB by the pipeline orchestrator.

Key dependencies:
  - app.services.llm_service — shared async LLM client
  - app.services.rag_service — Qdrant retrieval (optional, if collection given)
  - app.utils.json_parse — LLM JSON repair
  - app.schemas.outreach — OutreachAsset Pydantic model
  - app.schemas.persona — BuyerPersona Pydantic model
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from uuid import UUID

from app.core.logging import get_logger
from app.schemas.company import CompanyAnalysis
from app.schemas.outreach import OutreachAsset
from app.schemas.persona import BuyerPersona
from app.services.llm_service import get_llm_service
from app.services.rag_service import RAGService
from app.utils.json_parse import parse_llm_json

logger = get_logger(__name__)

_CHANNEL_PROMPTS = {
    "cold_email": """Generate a personalized cold email for this persona.
Return JSON:
{
  "subject": "compelling subject line (max 60 chars)",
  "body": "full email body (150-250 words, plain text)",
  "call_to_action": "specific CTA",
  "personalization_tokens": {"{{pain_point}}": "value", "{{trigger}}": "value"}
}""",
    "linkedin": """Generate a personalized LinkedIn connection request + follow-up message.
Return JSON:
{
  "subject": "LinkedIn connection request note (max 300 chars)",
  "body": "LinkedIn follow-up message after connecting (100-150 words)",
  "call_to_action": "specific low-friction CTA",
  "personalization_tokens": {}
}""",
    "call_opener": """Generate a cold call opener script (30-second pitch).
Return JSON:
{
  "subject": "Pattern interrupt opener line",
  "body": "Full 30-second call opener script (conversational, not salesy)",
  "call_to_action": "Specific ask (meeting, demo, etc.)",
  "personalization_tokens": {"{{company}}": "their company name"}
}""",
}


class OutreachAgent:
    """Generates personalized multi-channel outreach content.

    Called once per BuyerPersona, typically via asyncio.gather in the pipeline
    orchestrator so multiple personas are processed concurrently.
    """

    def __init__(self) -> None:
        self._llm = get_llm_service()
        self._rag = RAGService()

    async def run(
        self,
        persona: BuyerPersona,
        analysis: CompanyAnalysis,
        channels: list[str] | None = None,
        rag_collection: str | None = None,
        stream_cb: Callable[[dict], None] | None = None,
    ) -> list[OutreachAsset]:
        """Generate outreach assets for a single buyer persona.

        Args:
            persona: BuyerPersona from PersonaAgent — title, pain points,
                     goals, objections, tone preference, buying triggers.
            analysis: CompanyAnalysis from DomainAgent — product context.
            channels: Which channels to generate copy for.  Defaults to all
                      three: ["cold_email", "linkedin", "call_opener"].
            rag_collection: Qdrant collection name to retrieve competitor
                            intelligence chunks from.  Pass None to skip RAG
                            (e.g. first-run before GapAnalysisAgent has indexed).
            stream_cb: Optional SSE event callback for frontend progress.

        Returns:
            List of OutreachAsset objects — one per successfully generated
            channel.  Failed channel calls are excluded rather than raising.
        """
        if channels is None:
            channels = ["cold_email", "linkedin", "call_opener"]

        t0 = time.perf_counter()
        logger.info(
            "outreach_agent.start",
            module_name="OutreachAgent",
            persona=persona.title,
            channels=channels,
        )
        if stream_cb:
            stream_cb({"type": "agent_start", "label": f"Crafting outreach for {persona.title}..."})

        # ---- RAG: retrieve competitor context once, share across channels ----
        # One retrieval call feeds all channel prompts — avoids N×Qdrant
        # round-trips for the same persona and keeps latency predictable.
        rag_context = ""
        if rag_collection:
            query = f"messaging for {persona.title} dealing with {', '.join(persona.pain_points[:2])}"
            chunks = await self._rag.retrieve(rag_collection, query, top_k=3)
            rag_context = "\n\nCompetitor intelligence context:\n" + "\n".join(chunks)

        # ---- Concurrent channel generation ----
        # All three channel LLM calls run in parallel; gather collects results
        # in order.  Each call is wrapped in a try/except so one failure
        # returns None rather than propagating and cancelling the others.
        tasks = [
            self._generate_for_channel(persona, analysis, channel, rag_context, stream_cb=stream_cb)
            for channel in channels
        ]
        results = await asyncio.gather(*tasks)
        assets: list[OutreachAsset] = [a for a in results if a is not None]

        elapsed = time.perf_counter() - t0
        logger.info(
            "outreach_agent.complete",
            module_name="OutreachAgent",
            execution_time=round(elapsed, 3),
            output_summary=f"assets={len(assets)} for {persona.title}",
        )
        if stream_cb:
            stream_cb({
                "type": "agent_done",
                "summary": f"{len(assets)} assets · {', '.join(a.channel for a in assets)}",
                "result": {
                    "persona": persona.title,
                    "assets": [
                        {
                            "channel": a.channel,
                            "subject": a.subject,
                            "body_preview": a.body[:180] if a.body else "",
                            "call_to_action": a.call_to_action,
                        }
                        for a in assets
                    ],
                },
            })
        return assets

    async def _generate_for_channel(
        self,
        persona: BuyerPersona,
        analysis: CompanyAnalysis,
        channel: str,
        rag_context: str,
        stream_cb: Callable[[dict], None] | None = None,
    ) -> OutreachAsset | None:
        """Generate a single OutreachAsset for one channel.

        The channel-specific instruction (format, length, tone) is looked up
        from ``_CHANNEL_PROMPTS``; an unknown channel name falls back to the
        cold-email format so the pipeline never hard-errors on a bad input.

        Args:
            persona: Target buyer persona.
            analysis: Company and product context.
            channel: One of "cold_email", "linkedin", "call_opener".
            rag_context: Pre-retrieved competitor intelligence text (may be
                         empty string if RAG was skipped).
            stream_cb: SSE event callback (may be None).

        Returns:
            OutreachAsset on success, None if the LLM call or parsing fails.
        """
        channel_instruction = _CHANNEL_PROMPTS.get(channel, _CHANNEL_PROMPTS["cold_email"])
        prompt = self._build_prompt(persona, analysis, channel_instruction, rag_context)

        _SYSTEM_PROMPT = """You are an expert B2B sales copywriter generating personalized outreach content.
Write compelling, specific, and human-sounding messages tailored to the persona and company context.
Rules:
- Use ONLY the information provided in the prompt.
- Return ONLY valid JSON — no markdown, no commentary.
- Match the tone and format specified in the channel instructions exactly.
- Do not truncate — complete every JSON field fully."""

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        def on_token(t: str) -> None:
            if stream_cb:
                stream_cb({"type": "token", "content": t})

        def on_reasoning(t: str) -> None:
            if stream_cb:
                stream_cb({"type": "reasoning", "content": t})

        try:
            # temperature=0.6: highest in the pipeline — copy must feel
            # natural and unique per persona, not templated.
            raw = await self._llm.chat(
                messages, json_mode=True, temperature=0.6,
                on_token=on_token, on_reasoning=on_reasoning,
            )
            data = parse_llm_json(raw)
            return OutreachAsset(
                persona_id=persona.persona_id,
                company_id=persona.company_id,
                channel=channel,
                subject=data.get("subject", ""),
                body=data.get("body", ""),
                call_to_action=data.get("call_to_action", ""),
                # personalization_tokens values must be plain scalars for
                # the DB schema; non-scalar values (nested dicts/lists) are
                # JSON-serialized to strings as a safe fallback.
                personalization_tokens={
                    str(k): (v if isinstance(v, (str, int, float, bool)) else json.dumps(v))
                    for k, v in data.get("personalization_tokens", {}).items()
                } if isinstance(data.get("personalization_tokens"), dict) else {},
            )
        except Exception as e:
            # Returning None here rather than re-raising lets asyncio.gather
            # continue the other channel tasks even when one fails.
            logger.warning("outreach_agent.channel_error", channel=channel, error=str(e))
            return None

    @staticmethod
    def _build_prompt(
        persona: BuyerPersona,
        analysis: CompanyAnalysis,
        channel_instruction: str,
        rag_context: str,
    ) -> str:
        """Assemble the full LLM user-turn prompt for one channel.

        The prompt structure is:
          1. Selling company + product context (shared across channels)
          2. Persona details (title, tone, pain points, objections, triggers)
          3. RAG-retrieved competitor intelligence (optional)
          4. Channel-specific format instruction from ``_CHANNEL_PROMPTS``

        Args:
            persona: BuyerPersona defining the target.
            analysis: CompanyAnalysis for seller context.
            channel_instruction: Per-channel format spec from _CHANNEL_PROMPTS.
            rag_context: Pre-fetched competitor chunks (empty string if none).

        Returns:
            Full user-turn prompt string.
        """
        return (
            f"Company selling: {analysis.company_name}\n"
            f"Product: {analysis.raw_input.product_description[:200]}\n"
            f"Core Problem Solved: {analysis.raw_input.core_problem_solved}\n\n"
            f"Target Persona:\n"
            f"  Title: {persona.title}\n"
            f"  Seniority: {persona.seniority}\n"
            f"  Goals: {', '.join(persona.goals[:3])}\n"
            f"  Pain Points: {', '.join(persona.pain_points[:3])}\n"
            f"  Objections: {', '.join(persona.objections[:2])}\n"
            f"  Buying Triggers: {', '.join(persona.buying_triggers[:2])}\n"
            f"  Preferred Tone: {persona.messaging_tone}\n"
            f"{rag_context}\n\n"
            f"{channel_instruction}"
        )

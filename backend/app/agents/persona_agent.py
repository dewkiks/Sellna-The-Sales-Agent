"""Persona Generator Agent — pipeline stage 8 (RAG-powered).

Generates detailed BuyerPersona objects for each ICPProfile produced by
ICPAgent.  Personas answer the question "Who, specifically, will evaluate
and sign off on a purchase from this ICP company?"

RAG flow (when rag_collection is provided):
  - For each ICP, query the gap collection (built in stage 6) with
    "buyer personas for <industry> <buyer_authority>".
  - Inject the top-3 chunks into the persona prompt so the model references
    actual competitor messaging gaps when describing buyer pain points,
    objections, and preferred channels.

Concurrency: one asyncio task is spawned per ICP and all run in parallel
via asyncio.gather.  For three ICPs × 2 personas each, this means 3
concurrent LLM calls instead of 3 sequential ones.

Error isolation: if generate_for_icp fails for one ICP, it returns [] and
logs the error — the other ICPs are not affected.

Pipeline position: receives CompanyAnalysis + ICPProfile list (stage 7),
produces BuyerPersona list consumed by OutreachAgent (stage 9).

Key dependencies:
  - app.services.llm_service — shared async LLM client
  - app.services.rag_service — Qdrant retrieval
  - app.utils.json_parse — LLM JSON repair
  - app.schemas.persona — BuyerPersona Pydantic model
  - app.schemas.icp — ICPProfile Pydantic model
"""

import asyncio
import time
from collections.abc import Callable
from uuid import UUID

from app.core.logging import get_logger
from app.schemas.company import CompanyAnalysis
from app.schemas.icp import ICPProfile
from app.schemas.persona import BuyerPersona
from app.services.llm_service import get_llm_service
from app.services.rag_service import RAGService
from app.utils.json_parse import parse_llm_json

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are a B2B buyer-psychology expert.
Given an Ideal Customer Profile, create detailed, realistic buyer personas for
the people who would evaluate and purchase this product. Draw on your knowledge
of B2B roles, decision-making, and communication preferences to make each
persona concrete — you are expected to infer details that are not spelled out
in the input.

Create detailed buyer personas for each ICP and return JSON:
{
  "personas": [
    {
      "title": "Exact job title",
      "seniority": "C-Level | VP | Director | Manager | IC",
      "goals": ["goal1", "goal2", "goal3"],
      "pain_points": ["pain1", "pain2", "pain3"],
      "objections": ["objection1", "objection2"],
      "buying_triggers": ["trigger1", "trigger2"],
      "preferred_channels": ["email", "linkedin", "phone"],
      "messaging_tone": "professional | friendly | technical | consultative",
      "content_preferences": ["case_studies", "whitepapers", "demos"]
    }
  ]
}
Respond with ONLY valid JSON — no markdown, no code fences, no explanation."""


class PersonaAgent:
    """Generates buyer personas from ICPs using LLM + optional RAG context.

    The RAG collection is the same one built by GapAnalysisAgent, so persona
    prompts are grounded in the same competitor intelligence that drove the
    gap and ICP decisions.
    """

    def __init__(self) -> None:
        self._llm = get_llm_service()
        self._rag = RAGService()

    async def run(
        self,
        company_analysis: CompanyAnalysis,
        icps: list[ICPProfile],
        num_personas_per_icp: int = 2,
        rag_collection: str | None = None,
        stream_cb: Callable[[dict], None] | None = None,
    ) -> list[BuyerPersona]:
        """Generate buyer personas for all ICPs in parallel.

        Args:
            company_analysis: CompanyAnalysis from DomainAgent — company name
                              and product context passed into each prompt.
            icps: ICPProfile list from ICPAgent — one asyncio task per ICP.
            num_personas_per_icp: How many personas to request per ICP.
                                  Total output = len(icps) × this value (minus failures).
            rag_collection: Qdrant collection name for competitor context.
                            None disables RAG (e.g. when collection is not yet built).
            stream_cb: Optional SSE event callback for frontend progress.

        Returns:
            Flat list of all BuyerPersona objects across all ICPs.
        """
        t0 = time.perf_counter()
        logger.info(
            "persona_agent.start",
            module_name="PersonaAgent",
            company=company_analysis.company_name,
            input_summary=f"icps={len(icps)}, personas_per_icp={num_personas_per_icp}",
        )
        if stream_cb:
            stream_cb({"type": "agent_start", "label": f"Building buyer personas for {len(icps)} ICPs..."})

        all_personas: list[BuyerPersona] = []
        tasks = []
        for icp in icps:
            tasks.append(self.generate_for_icp(company_analysis, icp, num_personas_per_icp, rag_collection, stream_cb=stream_cb))

        results = await asyncio.gather(*tasks)
        for persona_list in results:
            all_personas.extend(persona_list)

        elapsed = time.perf_counter() - t0
        logger.info(
            "persona_agent.complete",
            module_name="PersonaAgent",
            execution_time=round(elapsed, 3),
            output_summary=f"personas={len(all_personas)}",
        )
        if stream_cb:
            titles = ", ".join(p.title for p in all_personas[:3])
            stream_cb({
                "type": "agent_done",
                "summary": f"{len(all_personas)} personas · {titles}",
                "result": {
                    "personas": [
                        {
                            "title": p.title,
                            "seniority": p.seniority,
                            "messaging_tone": p.messaging_tone,
                            "pain_points": p.pain_points[:3],
                            "buying_triggers": p.buying_triggers[:2],
                            "preferred_channels": p.preferred_channels[:3],
                        }
                        for p in all_personas
                    ]
                },
            })
        return all_personas

    async def _get_rag_context(self, icp: ICPProfile, rag_collection: str) -> str:
        """Retrieve competitor intelligence relevant to a specific ICP.

        The query is formed from the ICP's industry + buyer authority so the
        vector search surfaces competitor content that targets the same role,
        not generic market copy.

        Args:
            icp: The ICP for which to retrieve context.
            rag_collection: Qdrant collection to query.

        Returns:
            Formatted context block ready to append to the persona prompt,
            or an empty string if retrieval returns nothing.
        """
        query = f"buyer personas for {icp.industry} {icp.buyer_authority}"
        results = await self._rag.retrieve(rag_collection, query, top_k=3)
        return "\n\nRelevant context from competitor intelligence:\n" + "\n".join(results)

    async def generate_for_icp(
        self,
        analysis: CompanyAnalysis,
        icp: ICPProfile,
        n: int,
        rag_collection: str | None,
        stream_cb: Callable[[dict], None] | None = None,
    ) -> list[BuyerPersona]:
        """Generate buyer personas for a single ICP.

        Public (not prefixed _) so the pipeline orchestrator can call it
        directly for ad-hoc per-ICP persona generation if needed.

        Args:
            analysis: CompanyAnalysis with seller context.
            icp: One ICPProfile to generate personas for.
            n: Number of personas to request from the LLM.
            rag_collection: Qdrant collection (None → skip RAG).
            stream_cb: SSE event callback.

        Returns:
            List of BuyerPersona objects (up to n).  Returns empty list on
            LLM or parsing failure — never raises to the caller.
        """
        rag_context = ""
        if rag_collection:
            rag_context = await self._get_rag_context(icp, rag_collection)

        prompt = self._build_prompt(analysis, icp, n, rag_context)
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
            # temperature=0.4: between DomainAgent (0.2) and OutreachAgent
            # (0.6) — personas should be realistic and differentiated but
            # still grounded in B2B norms.
            raw = await self._llm.chat(
                messages, json_mode=True, temperature=0.4,
                on_token=on_token, on_reasoning=on_reasoning,
            )
            data = parse_llm_json(raw)
            
            personas = []
            for item in data.get("personas", []):
                try:
                    persona = BuyerPersona(
                        icp_id=icp.icp_id,
                        company_id=analysis.company_id,
                        title=item.get("title", ""),
                        seniority=item.get("seniority", "Director"),
                        goals=item.get("goals", []),
                        pain_points=item.get("pain_points", []),
                        objections=item.get("objections", []),
                        buying_triggers=item.get("buying_triggers", []),
                        preferred_channels=item.get("preferred_channels", ["email"]),
                        messaging_tone=item.get("messaging_tone", "professional"),
                        content_preferences=item.get("content_preferences", []),
                    )
                    personas.append(persona)
                except Exception as e:
                    logger.warning("persona_agent.parse_error", error=str(e))
            return personas
        except Exception as e:
            logger.error("persona_agent.generate_error", error=str(e))
            return []

    @staticmethod
    def _build_prompt(
        analysis: CompanyAnalysis,
        icp: ICPProfile,
        n: int,
        rag_context: str,
    ) -> str:
        """Build the LLM user-turn prompt for persona generation.

        Args:
            analysis: Seller company context.
            icp: The ICP this set of personas must fit.
            n: How many personas to request.
            rag_context: Competitor intelligence text to append (may be empty).

        Returns:
            Formatted prompt string for the LLM user message.
        """
        return (
            f"Company: {analysis.company_name}\n"
            f"Product: {analysis.raw_input.product_description[:300]}\n"
            f"Core Problem: {analysis.raw_input.core_problem_solved}\n\n"
            f"ICP:\n"
            f"  Industry: {icp.industry}\n"
            f"  Size: {icp.company_size}\n"
            f"  Revenue: {icp.revenue_range}\n"
            f"  Buyer Authority: {icp.buyer_authority}\n"
            f"  Pain Points: {', '.join(icp.pain_points[:4])}\n"
            f"  Buying Signals: {', '.join(icp.buying_signals[:3])}\n"
            f"{rag_context}\n\n"
            f"Generate {n} detailed personas for this ICP."
        )

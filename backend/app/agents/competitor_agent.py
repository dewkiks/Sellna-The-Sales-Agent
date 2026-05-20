"""Competitor Discovery Agent — pipeline stage 2.

Uses LLM world-knowledge to identify real, named competitors for the
analyzed company.  No search engine is called; the LLM is prompted to
draw on its own pre-training knowledge of the market derived from
DomainAgent's CompanyAnalysis.

Responsibilities:
- Build a structured prompt from the CompanyAnalysis (category, segments,
  buyer roles, geography, positioning).
- Call the LLM in JSON mode at low temperature (0.3) to encourage factual,
  consistent recall over creative generation.
- Parse and validate each competitor object, logging and skipping any
  malformed entries so a single bad item never aborts the whole run.
- Return a ranked list of CompetitorDiscovered objects ready for WebAgent
  to scrape.

Pipeline position: receives CompanyAnalysis from DomainAgent (stage 1),
produces CompetitorDiscovered list consumed by WebAgent (stage 3).

Key dependencies:
  - app.services.llm_service — shared async LLM client (OpenAI-compatible)
  - app.utils.json_parse — robust LLM JSON extraction / repair
  - app.schemas.competitor — CompetitorDiscovered Pydantic model
"""

from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID

from app.core.logging import get_logger
from app.schemas.company import CompanyAnalysis
from app.schemas.competitor import CompetitorDiscovered
from app.services.llm_service import get_llm_service
from app.utils.json_parse import parse_llm_json

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are a B2B competitive-intelligence analyst.

Given a company's details, identify its top real-world competitors. Use the
company details to understand which market it operates in, then draw on your
own knowledge of actual companies in that space to name competitors. The
competitors will NOT be listed in the input — you are expected to know them.

Return structured JSON ONLY:
{
  "competitors": [
    {
      "name": "Competitor Name",
      "website": "https://example.com",
      "category": "Direct | Indirect | Alternative",
      "positioning": "One sentence on how they position themselves",
      "relevance_score": 0.0
    }
  ]
}

Rules:
- Identify 3-5 real, named companies that genuinely exist — never placeholders
- category: "Direct" = head-to-head, "Indirect" = partial overlap, "Alternative" = adjacent substitute
- relevance_score: 1.0 = head-to-head competitor, 0.5 = partial overlap, 0.3 = adjacent
- Respond with ONLY valid JSON — no markdown, no code fences, no explanation."""


class CompetitorAgent:
    """Discovers competitors using LLM reasoning from domain analysis.

    Stateless: the LLM service is injected once at construction via
    get_llm_service() and shared safely across concurrent calls.
    """

    def __init__(self) -> None:
        self._llm = get_llm_service()

    async def run(
        self,
        analysis: CompanyAnalysis,
        stream_cb: Callable[[dict], None] | None = None,
    ) -> list[CompetitorDiscovered]:
        """Identify real competitors for the analyzed company.

        Args:
            analysis: Output of DomainAgent — company name, category,
                      segments, buyer roles, positioning, geography.
            stream_cb: Optional callback receiving SSE-style event dicts
                (types: "token", "reasoning") so the frontend's Token
                output panel can show the LLM thinking in real time.

        Returns:
            List of CompetitorDiscovered objects (typically 3–5), each with
            a name, website, category (Direct/Indirect/Alternative),
            one-line positioning, and a relevance_score in [0.3, 1.0].
            Malformed LLM entries are skipped with a warning log.
        """
        t0 = time.perf_counter()
        logger.info(
            "competitor_agent.start",
            module_name="CompetitorAgent",
            company=analysis.company_name,
            input_summary=f"category={analysis.product_category}, segments={len(analysis.target_segments)}",
        )

        def emit(line: str) -> None:
            if stream_cb:
                stream_cb({"type": "token", "content": line})

        emit(
            f"→ Analysing {analysis.company_name} in the "
            f"{analysis.product_category or 'B2B'} market\n"
            f"→ {len(analysis.target_segments)} segments · "
            f"{len(analysis.buyer_roles)} buyer roles\n"
            f"→ Asking model for 3–5 real competitors...\n\n"
        )

        user_prompt = self._build_prompt(analysis)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        def on_token(t: str) -> None:
            if stream_cb:
                stream_cb({"type": "token", "content": t})

        def on_reasoning(t: str) -> None:
            if stream_cb:
                stream_cb({"type": "reasoning", "content": t})

        # temperature=0.3: low enough for factual recall, high enough to avoid
        # the model always returning the same top-3 names for every company.
        raw = await self._llm.chat(
            messages, json_mode=True, temperature=0.3,
            on_token=on_token, on_reasoning=on_reasoning,
        )
        data = parse_llm_json(raw)

        competitors: list[CompetitorDiscovered] = []
        for item in data.get("competitors", []):
            try:
                comp = CompetitorDiscovered(
                    name=item["name"],
                    website=item.get("website", ""),
                    category=item.get("category", "Direct"),
                    positioning=item.get("positioning", ""),
                    relevance_score=float(item.get("relevance_score", 0.5)),
                    # Tag every competitor as LLM-sourced so downstream code
                    # can distinguish from human-curated or search-engine results.
                    discovery_source="llm_reasoning",
                )
                competitors.append(comp)
            except Exception as e:
                # Pydantic validation or missing required key — skip this item
                # rather than failing the whole agent call.
                logger.warning("competitor_agent.parse_error", error=str(e), item=item)

        if competitors:
            emit("\n\nParsed competitors:\n")
            for c in competitors:
                emit(
                    f"  • {c.name} ({c.category}, score {c.relevance_score:.2f}) "
                    f"— {c.website}\n"
                )

        elapsed = time.perf_counter() - t0
        logger.info(
            "competitor_agent.complete",
            module_name="CompetitorAgent",
            execution_time=round(elapsed, 3),
            output_summary=f"discovered={len(competitors)} competitors",
        )
        return competitors

    @staticmethod
    def _build_prompt(analysis: CompanyAnalysis) -> str:
        """Build the user-turn prompt from a CompanyAnalysis.

        Caps lists at 5 items each so the context stays focused — the LLM
        does not need exhaustive lists to identify competitors.

        Args:
            analysis: DomainAgent output with market metadata.

        Returns:
            Formatted string ready to be sent as the user message.
        """
        segments = ", ".join(analysis.target_segments[:5])
        buyer_roles = ", ".join(analysis.buyer_roles[:5])
        return (
            f"Company: {analysis.company_name}\n"
            f"Product Category: {analysis.product_category}\n"
            f"Market Type: {getattr(analysis.market_type, 'value', analysis.market_type)}\n"
            f"Target Segments: {segments}\n"
            f"Buyer Roles: {buyer_roles}\n"
            f"Positioning: {analysis.competitive_positioning}\n"
            f"Geography: {analysis.raw_input.target_geography}"
        )

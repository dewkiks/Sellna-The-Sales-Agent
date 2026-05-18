"""ICP Generator Agent — pipeline stage 7.

Generates structured Ideal Customer Profiles (ICPs) using two inputs:
  - CompanyAnalysis (stage 1) for market type, buyer roles, target segments.
  - MarketGap list (stage 6) so the ICPs are anchored in real competitive
    opportunities rather than generic industry averages.

The LLM is prompted to infer concrete company demographics — size, revenue,
tech stack, geography — that are not spelled out in the inputs.  This is an
intentional design choice: the model's world-knowledge about B2B buyer
segments supplements the sparse structured inputs.

Streaming support: emits agent_start, token, reasoning, and agent_done events
so the frontend can show real-time progress (same protocol as DomainAgent).

Pipeline position: receives CompanyAnalysis + MarketGap list, produces
ICPProfile list consumed by PersonaAgent (stage 8).

Key dependencies:
  - app.services.llm_service — shared async LLM client
  - app.utils.json_parse — LLM JSON repair
  - app.schemas.icp — ICPProfile Pydantic model
  - app.schemas.gap_analysis — MarketGap Pydantic model
"""

from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID

from app.core.logging import get_logger
from app.schemas.company import CompanyAnalysis
from app.schemas.gap_analysis import MarketGap
from app.schemas.icp import ICPProfile
from app.services.llm_service import get_llm_service
from app.utils.json_parse import parse_llm_json

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are a B2B go-to-market strategist.
Given a company's profile and the market gaps it can exploit, design specific,
realistic Ideal Customer Profiles (ICPs). Draw on your knowledge of B2B buyers,
company demographics, and technology adoption to make each ICP concrete and
actionable — most of these details will NOT be in the input, you are expected
to infer them.

Generate Ideal Customer Profiles and return a JSON object:
{
  "icps": [
    {
      "industry": "specific industry vertical",
      "company_size": "e.g. 50-200 employees",
      "revenue_range": "e.g. $5M-$20M ARR",
      "tech_stack": ["tool1", "tool2"],
      "buyer_authority": "specific title",
      "geography": "region",
      "pain_points": ["pain1", "pain2"],
      "buying_signals": ["signal1", "signal2"],
      "exclusion_criteria": ["exclude1"],
      "fit_score_rationale": "why this is a perfect fit"
    }
  ]
}
Respond with ONLY valid JSON — no markdown, no code fences, no explanation."""


class ICPAgent:
    """Generates Ideal Customer Profiles using domain analysis + gap intelligence.

    No RAG in this stage: the LLM system prompt explicitly instructs the model
    to draw on its own knowledge of B2B buyer demographics, supplementing the
    structured inputs.  RAG is deferred to PersonaAgent (stage 8) where
    competitor-specific messaging context adds more value.
    """

    def __init__(self) -> None:
        self._llm = get_llm_service()

    async def run(
        self,
        analysis: CompanyAnalysis,
        gaps: list[MarketGap],
        num_profiles: int = 3,
        stream_cb: Callable[[dict], None] | None = None,
    ) -> list[ICPProfile]:
        """Generate ICP profiles for the analyzed company.

        Args:
            analysis: CompanyAnalysis from DomainAgent.
            gaps: Market gaps from GapAnalysisAgent — top 6 are included in
                  the prompt to anchor ICPs in identified opportunities.
            num_profiles: How many ICPs to request from the LLM (default 3).
                          The returned list is sliced to this count even if
                          the LLM produces more.
            stream_cb: Optional SSE-style event callback for frontend progress.

        Returns:
            Up to ``num_profiles`` ICPProfile objects.  Malformed items are
            silently skipped with a warning log entry.
        """
        t0 = time.perf_counter()
        logger.info(
            "icp_agent.start",
            module_name="ICPAgent",
            company=analysis.company_name,
            input_summary=f"gaps={len(gaps)}, requested={num_profiles}",
        )
        if stream_cb:
            stream_cb({"type": "agent_start", "label": f"Generating {num_profiles} Ideal Customer Profiles..."})

        user_prompt = self._build_prompt(analysis, gaps, num_profiles)
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

        # temperature=0.3: slightly more creative than DomainAgent so the
        # model generates distinct ICPs rather than near-duplicates, while
        # still staying grounded in the provided context.
        raw = await self._llm.chat(
            messages, json_mode=True, temperature=0.3,
            on_token=on_token, on_reasoning=on_reasoning,
        )
        data = parse_llm_json(raw)

        profiles: list[ICPProfile] = []
        for item in data.get("icps", []):
            try:
                icp = ICPProfile(
                    company_id=analysis.company_id,
                    industry=item.get("industry", ""),
                    company_size=item.get("company_size", ""),
                    revenue_range=item.get("revenue_range", ""),
                    tech_stack=item.get("tech_stack", []),
                    buyer_authority=item.get("buyer_authority", ""),
                    # Fall back to the user-supplied geography if the LLM omits it.
                    geography=item.get("geography", analysis.raw_input.target_geography),
                    pain_points=item.get("pain_points", []),
                    buying_signals=item.get("buying_signals", []),
                    exclusion_criteria=item.get("exclusion_criteria", []),
                    fit_score_rationale=item.get("fit_score_rationale", ""),
                )
                profiles.append(icp)
            except Exception as e:
                logger.warning("icp_agent.parse_error", error=str(e))

        elapsed = time.perf_counter() - t0
        logger.info(
            "icp_agent.complete",
            module_name="ICPAgent",
            execution_time=round(elapsed, 3),
            output_summary=f"icps={len(profiles)}",
        )
        if stream_cb:
            industries = ", ".join(p.industry for p in profiles[:3])
            stream_cb({
                "type": "agent_done",
                "summary": f"{len(profiles)} ICPs · {industries}",
                "result": {
                    "icps": [
                        {
                            "industry": p.industry,
                            "company_size": p.company_size,
                            "revenue_range": p.revenue_range,
                            "buyer_authority": p.buyer_authority,
                            "geography": p.geography,
                            "pain_points": p.pain_points[:3],
                            "buying_signals": p.buying_signals[:2],
                        }
                        for p in profiles[:num_profiles]
                    ]
                },
            })
        return profiles[:num_profiles]

    @staticmethod
    def _build_prompt(analysis: CompanyAnalysis, gaps: list[MarketGap], n: int) -> str:
        """Build the LLM user-turn prompt for ICP generation.

        Gaps are formatted as one line each (type + description + opportunity)
        so the model can quickly scan and connect them to specific ICP choices
        without reading dense paragraphs.

        Args:
            analysis: DomainAgent output.
            gaps: GapAnalysisAgent output (up to 6 used).
            n: Number of ICPs to request.

        Returns:
            Formatted multi-line string for the LLM user message.
        """
        gap_summaries = "\n".join(
            f"- [{g.gap_type}] {g.description} → {g.opportunity}"
            for g in gaps[:6]
        )
        return (
            f"Company: {analysis.company_name}\n"
            f"Product Category: {analysis.product_category}\n"
            f"Target Geography: {analysis.raw_input.target_geography}\n"
            f"Customer Type: {getattr(analysis.raw_input.customer_type, 'value', analysis.raw_input.customer_type)}\n"
            f"Pricing Model: {getattr(analysis.raw_input.pricing_model, 'value', analysis.raw_input.pricing_model)}\n"
            f"Buyer Roles: {', '.join(analysis.buyer_roles[:5])}\n"
            f"Market Segments: {', '.join(analysis.target_segments[:5])}\n"
            f"Market Gaps:\n{gap_summaries}\n\n"
            f"Generate {n} highly specific ICPs."
        )

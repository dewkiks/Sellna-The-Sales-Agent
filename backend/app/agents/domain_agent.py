"""Domain Intelligence Agent — pipeline stage 1.

The entry point of the entire pipeline.  Accepts raw user-supplied
CompanyInput and produces a CompanyAnalysis that every downstream agent
depends on.

Responsibilities:
- Build a structured prompt from CompanyInput fields (name, description,
  industry, geography, pricing model, customer type, features, tech stack).
- Call the LLM at very low temperature (0.2) to get stable, deterministic
  market classification rather than creative output.
- Parse the returned JSON into a typed CompanyAnalysis (market_type,
  target_segments, pain_points, buyer_roles, product_category,
  competitive_positioning, strengths, weaknesses).
- Optionally emit streaming events (agent_start, token, reasoning,
  agent_done) so the frontend can render real-time progress via SSE.

Pipeline position: first stage — its CompanyAnalysis is the shared context
object passed through every subsequent agent.

Key dependencies:
  - app.services.llm_service — shared async LLM client (OpenAI-compatible)
  - app.utils.json_parse — robust LLM JSON extraction / repair
  - app.schemas.company — CompanyInput, CompanyAnalysis, MarketType
  - app.config — settings (e.g. model name, timeout)
"""

from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID

from app.config import get_settings
from app.core.logging import get_logger
from app.schemas.company import (
    CompanyAnalysis,
    CompanyInput,
    MarketType,
)
from app.services.llm_service import get_llm_service
from app.utils.json_parse import parse_llm_json

logger = get_logger(__name__)
_settings = get_settings()

_SYSTEM_PROMPT = """You are a B2B market analyst inside a sales intelligence pipeline.
Analyze the company described by the user and produce a concise market analysis.
Ground the analysis in the provided company details, applying your knowledge of
B2B markets to classify the market and infer segments, buyers, and positioning.

Return a structured JSON object with:
{
  "market_type": one of ["horizontal", "vertical", "niche", "enterprise"],
  "target_segments": [list of 3-5 specific market segments],
  "pain_points": [list of 4-6 pain points the product addresses],
  "buyer_roles": [list of 3-5 specific job titles who buy this],
  "product_category": "single category string",
  "competitive_positioning": "1-2 sentence positioning statement",
  "strengths": [list of 3-5 product strengths],
  "weaknesses": [list of 2-3 potential weaknesses or gaps]
}
Respond with ONLY valid JSON — no markdown, no code fences, no explanation."""


class DomainAgent:
    """Stateless agent — takes CompanyInput, returns CompanyAnalysis.

    Stateless means no per-run state is stored on the instance; every call
    to ``run`` is independent.  The LLM service is a shared singleton so
    the same HTTP connection pool is reused across pipeline runs.
    """

    def __init__(self) -> None:
        self._llm = get_llm_service()

    async def run(
        self,
        company_input: CompanyInput,
        stream_cb: Callable[[dict], None] | None = None,
    ) -> CompanyAnalysis:
        """Run domain analysis for a company and return a CompanyAnalysis.

        Args:
            company_input: Validated user-supplied company description.
            stream_cb: Optional callback invoked with SSE-style event dicts
                (types: "agent_start", "token", "reasoning", "agent_done").
                Pass None when streaming is not needed (e.g. batch mode).

        Returns:
            CompanyAnalysis with LLM-classified market metadata.  All list
            fields (segments, buyer roles, etc.) are non-empty because the
            LLM prompt explicitly requests them; the schema provides empty-list
            defaults as a safety net for malformed responses.
        """
        t0 = time.perf_counter()
        logger.info(
            "domain_agent.start",
            module_name="DomainAgent",
            company=company_input.company_name,
            input_summary=f"industry={company_input.industry}, type={company_input.customer_type}",
        )
        if stream_cb:
            stream_cb({"type": "agent_start", "label": f"Analyzing {company_input.company_name}..."})

        user_prompt = self._build_prompt(company_input)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Wrap the stream_cb in closures accepted by the LLM service.
        # These are no-ops when stream_cb is None, keeping the hot path clean.
        def on_token(t: str) -> None:
            if stream_cb:
                stream_cb({"type": "token", "content": t})

        def on_reasoning(t: str) -> None:
            # Emitted by reasoning-capable models (e.g. o1, deepseek-r1)
            # so the frontend can display chain-of-thought separately.
            if stream_cb:
                stream_cb({"type": "reasoning", "content": t})

        # temperature=0.2: market classification should be stable and
        # consistent — not a creative task.
        raw = await self._llm.chat(
            messages, json_mode=True, temperature=0.2,
            on_token=on_token, on_reasoning=on_reasoning,
        )
        # parse_llm_json handles markdown fences, partial JSON, and minor
        # formatting errors that LLMs occasionally produce despite JSON mode.
        data = parse_llm_json(raw)

        # Default "horizontal" is the safest fallback: it is the broadest
        # market type and will not incorrectly narrow downstream targeting.
        analysis = CompanyAnalysis(
            company_name=company_input.company_name,
            market_type=MarketType(data.get("market_type", "horizontal")),
            target_segments=data.get("target_segments", []),
            pain_points=data.get("pain_points", []),
            buyer_roles=data.get("buyer_roles", []),
            product_category=data.get("product_category", ""),
            competitive_positioning=data.get("competitive_positioning", ""),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            raw_input=company_input,
        )

        elapsed = time.perf_counter() - t0
        logger.info(
            "domain_agent.complete",
            module_name="DomainAgent",
            execution_time=round(elapsed, 3),
            output_summary=(
                f"market_type={analysis.market_type}, "
                f"segments={len(analysis.target_segments)}, "
                f"buyer_roles={len(analysis.buyer_roles)}"
            ),
        )
        if stream_cb:
            stream_cb({
                "type": "agent_done",
                "summary": f"{analysis.market_type.value} market · {len(analysis.target_segments)} segments · {len(analysis.buyer_roles)} buyer roles",
                "result": {
                    "market_type": analysis.market_type.value,
                    "product_category": analysis.product_category,
                    "competitive_positioning": analysis.competitive_positioning,
                    "target_segments": analysis.target_segments[:5],
                    "buyer_roles": analysis.buyer_roles[:5],
                    "pain_points": analysis.pain_points[:4],
                    "strengths": analysis.strengths[:3],
                    "weaknesses": analysis.weaknesses[:2],
                },
            })
        return analysis

    @staticmethod
    def _build_prompt(inp: CompanyInput) -> str:
        """Serialize a CompanyInput into a dense LLM user-turn prompt.

        Lists are capped at 10 items each to stay within practical token
        budgets.  Optional fields fall back to "Not provided" rather than
        empty strings so the LLM sees clear signal that data is absent.

        Args:
            inp: Raw company input from the API request.

        Returns:
            Multi-line string passed as the user message to the LLM.
        """
        features = ", ".join(inp.product_features[:10]) if inp.product_features else "Not provided"
        tech = ", ".join(inp.tech_stack[:10]) if inp.tech_stack else "Not provided"
        return (
            f"Company: {inp.company_name}\n"
            f"Product: {inp.product_description}\n"
            f"Industry: {inp.industry}\n"
            f"Target Geography: {inp.target_geography}\n"
            f"Pricing Model: {getattr(inp.pricing_model, 'value', inp.pricing_model)}\n"
            f"Customer Type: {getattr(inp.customer_type, 'value', inp.customer_type)}\n"
            f"Core Problem: {inp.core_problem_solved}\n"
            f"Features: {features}\n"
            f"Tech Stack: {tech}\n"
            f"Website: {inp.website or 'Not provided'}"
        )

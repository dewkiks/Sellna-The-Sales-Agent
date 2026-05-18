"""Optimization Agent — post-pipeline feedback loop.

Unlike the nine core pipeline stages, this agent runs *after* outreach
assets have been deployed and engagement data has been collected.  It is
called on-demand (via the API) rather than as part of the sequential
sales pipeline.

Responsibilities:
- Join OutreachAsset records with their matching OutreachFeedback by
  asset_id, filling zeros for assets with no feedback yet.
- Build a compact performance table (channel, subject, open/reply/conversion
  rates) and pass it to the LLM.
- Return a structured dict with an overall performance score and prioritized
  recommendations for targeting, messaging, and A/B tests.

Design note: no RAG here — the feedback metrics are the sole evidence base.
The LLM applies its own knowledge of outreach best practices to interpret
the numbers; it does not need competitor context at this stage.

Key dependencies:
  - app.services.llm_service — shared async LLM client
  - app.utils.json_parse — LLM JSON repair
  - app.schemas.outreach — OutreachAsset, OutreachFeedback
"""

from __future__ import annotations

import time
from uuid import UUID

from app.core.logging import get_logger
from app.schemas.outreach import OutreachAsset, OutreachFeedback
from app.services.llm_service import get_llm_service
from app.utils.json_parse import parse_llm_json

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are a B2B sales performance analyst.
Analyze the outreach engagement metrics provided and apply your knowledge of
outreach best practices to produce specific, actionable recommendations.

Analyze engagement metrics and provide specific optimization recommendations.
Return JSON:
{
  "overall_score": 0.0-10.0,
  "performance_summary": "brief assessment",
  "targeting_recommendations": ["rec1", "rec2", "rec3"],
  "messaging_recommendations": ["rec1", "rec2"],
  "a_b_test_ideas": ["test1", "test2"],
  "priority_actions": ["action1", "action2"]
}
Respond with ONLY valid JSON — no markdown, no code fences, no explanation."""


class OptimizationAgent:
    """Analyzes engagement feedback signals and generates optimization recommendations.

    Operates outside the sequential pipeline — called when engagement data is
    available, not as part of the initial analysis run.
    """

    def __init__(self) -> None:
        self._llm = get_llm_service()

    async def run(
        self,
        assets: list[OutreachAsset],
        feedback_list: list[OutreachFeedback],
    ) -> dict:
        """Analyze outreach performance and return improvement recommendations.

        Args:
            assets: OutreachAsset records for a given company (all channels).
            feedback_list: Engagement metrics collected for those assets.
                           Assets with no matching feedback are treated as
                           having 0% open, reply, and conversion rates.

        Returns:
            Dict with keys: overall_score (float 0–10), performance_summary,
            targeting_recommendations, messaging_recommendations,
            a_b_test_ideas, and priority_actions.  Returns the raw parsed
            LLM output — the caller is responsible for validation.
        """
        t0 = time.perf_counter()
        logger.info(
            "optimization_agent.start",
            module_name="OptimizationAgent",
            input_summary=f"assets={len(assets)}, feedback={len(feedback_list)}",
        )

        # ---- Merge: join assets with feedback by asset_id ----
        # Build a dict keyed by asset_id string so the lookup is O(1)
        # regardless of how many assets exist.
        feedback_map = {str(fb.asset_id): fb for fb in feedback_list}
        merged = []
        for asset in assets:
            fb = feedback_map.get(str(asset.asset_id))
            merged.append({
                "channel": asset.channel,
                "subject": asset.subject[:80],
                "open_rate": fb.open_rate if fb else 0.0,
                "reply_rate": fb.reply_rate if fb else 0.0,
                "conversion_rate": fb.conversion_rate if fb else 0.0,
                "notes": fb.notes if fb else "",
            })

        user_prompt = self._build_prompt(merged)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # temperature=0.2: recommendations should be analytical and repeatable,
        # not creative — low temperature reduces hallucinated "best practices".
        raw = await self._llm.chat(messages, json_mode=True, temperature=0.2)
        result = parse_llm_json(raw)

        elapsed = time.perf_counter() - t0
        logger.info(
            "optimization_agent.complete",
            module_name="OptimizationAgent",
            execution_time=round(elapsed, 3),
            output_summary=f"score={result.get('overall_score', 'N/A')}",
        )
        return result

    @staticmethod
    def _build_prompt(merged: list[dict]) -> str:
        """Format the merged asset+feedback data as a compact performance table.

        Each row is one line: ``[channel] open=X% reply=Y% conv=Z% | subject``.
        The subject is truncated at 80 chars (already done at merge time) so
        the LLM can identify what was tested without reading full email bodies.

        Args:
            merged: List of dicts produced by the run() merge step.

        Returns:
            Formatted prompt string for the LLM user message.
        """
        rows = "\n".join(
            f"[{m['channel']}] open={m['open_rate']:.0%} reply={m['reply_rate']:.0%} "
            f"conv={m['conversion_rate']:.0%} | {m['subject']}"
            for m in merged
        )
        return (
            f"Outreach performance data:\n{rows}\n\n"
            "Provide detailed optimization recommendations to improve targeting and messaging."
        )

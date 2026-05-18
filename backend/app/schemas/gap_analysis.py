"""Gap analysis schemas — market intelligence output.

The Gap Analysis Agent compares the target company's profile against scraped
competitor data to surface unmet needs and positioning weaknesses.  Each
finding is a ``MarketGap``, which is persisted in the ``market_gaps`` table
and surfaced in the frontend as an actionable opportunity.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MarketGap(BaseModel):
    """A discovered market gap or competitive opportunity.

    ``gap_type``: category of the finding —
        "missing_feature"       — competitors lack a capability the company has or could build.
        "underserved_segment"   — a customer segment no one is targeting well.
        "messaging_weakness"    — a competitor's positioning is unclear or off-message.
    ``supporting_evidence``: list of quoted or paraphrased facts from scraped
        competitor data that back the claim; used for credibility in the UI.
    ``confidence_score``: 0–1 LLM self-assessed confidence; drives sort order in the UI.
    ``recommended_action``: optional concrete next step (e.g. "Add SSO to feature page").
    """

    gap_id: UUID = Field(default_factory=uuid4)
    company_id: UUID
    gap_type: str  # "missing_feature" | "underserved_segment" | "messaging_weakness"
    description: str
    opportunity: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[str] = Field(default_factory=list)
    recommended_action: str = ""

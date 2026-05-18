"""Pydantic schemas for Ideal Customer Profiles (ICPs).

An ICP describes a *company* (not an individual) that is the best fit for the
product.  The ICP Agent generates several profiles per analysis run so the
pipeline can produce tailored personas and outreach for each segment.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ICPProfile(BaseModel):
    """Output of ICP Agent — one ideal target-company profile.

    ``buyer_authority``: titles of the people who sign off on purchase decisions
    within a company that fits this ICP (e.g. "VP of Sales, Head of Growth").
    ``buying_signals``: observable events that indicate a company is ready to buy
    (e.g. "recently raised Series A", "job postings for SDRs").
    ``exclusion_criteria``: hard disqualifiers (e.g. "fewer than 10 employees").
    ``fit_score_rationale``: free-text explanation of why this profile was chosen.
    """

    icp_id: UUID = Field(default_factory=uuid4)
    company_id: UUID
    industry: str
    company_size: str     # e.g. "50-200 employees"
    revenue_range: str    # e.g. "$5M-$20M ARR"
    tech_stack: list[str] = Field(default_factory=list)
    buyer_authority: str  # e.g. "VP of Sales, Head of Growth"
    geography: str
    pain_points: list[str] = Field(default_factory=list)
    buying_signals: list[str] = Field(default_factory=list)
    exclusion_criteria: list[str] = Field(default_factory=list)
    fit_score_rationale: str = ""


class ICPGenerateRequest(BaseModel):
    """API request body to trigger ICP generation.

    ``num_profiles``: how many distinct ICP profiles to produce (1–10).
    Capped at 10 to prevent runaway LLM token spend.
    """

    company_id: UUID
    num_profiles: int = Field(default=3, ge=1, le=10)

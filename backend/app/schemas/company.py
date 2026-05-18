"""Pydantic schemas for Company Intelligence (Module 1 — Domain Agent).

``CompanyInput`` is the user-facing entry point: the frontend posts this JSON
to kick off the pipeline.  Every downstream agent receives a copy of it so
they understand the context (what the company does, who it sells to, etc.).

``CompanyAnalysis`` is what the Domain Agent writes back — a structured
interpretation of the input that later agents (ICP, Persona, Gap Analysis)
consume for their own prompts.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class PricingModel(str, Enum):
    """Allowed values for how the product is monetised.

    Stored as a string so JSON serialisation is trivial (no extra .value call).
    """

    freemium = "freemium"
    subscription = "subscription"
    usage_based = "usage_based"
    enterprise = "enterprise"
    one_time = "one_time"
    other = "other"


class CustomerType(str, Enum):
    """Allowed values for the primary customer segment.

    Agents use this to tailor ICP / persona assumptions (e.g. B2B → focus on
    company size and buying committees; B2C → focus on individual motivations).
    """

    b2b = "B2B"
    b2c = "B2C"
    b2b2c = "B2B2C"
    government = "Government"
    marketplace = "Marketplace"


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


class CompanyInput(BaseModel):
    """Complete company context required before any pipeline stage runs."""

    company_name: str = Field(..., min_length=1, max_length=200)
    product_description: str = Field(..., min_length=10)
    industry: str = Field(..., description="e.g. 'SaaS', 'FinTech', 'Healthcare'")
    target_geography: str = Field(..., description="e.g. 'North America', 'Global'")
    pricing_model: PricingModel
    customer_type: CustomerType
    core_problem_solved: str = Field(..., min_length=10)
    product_features: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    website: Optional[str] = Field(default=None)


# ---------------------------------------------------------------------------
# Output / Analysis
# ---------------------------------------------------------------------------


class MarketType(str, Enum):
    """Classification of the market the product competes in.

    horizontal = general-purpose tool (e.g. CRM); vertical = industry-specific
    (e.g. dental practice management); niche = narrow sub-segment; enterprise =
    large-organisation focus.
    """

    horizontal = "horizontal"
    vertical = "vertical"
    niche = "niche"
    enterprise = "enterprise"


class CompanyAnalysis(BaseModel):
    """Domain Intelligence Agent output — structured market intelligence about the company.

    ``company_id``: generated here (not from the DB) so the analysis object
    can be passed between agents before being persisted.
    ``raw_input``: the original CompanyInput is embedded so downstream agents
    always have full context in a single object.
    ``strengths`` / ``weaknesses``: LLM-inferred SWOT elements used by the
    Gap Analysis and Outreach agents.
    """

    company_id: UUID = Field(default_factory=uuid4)
    company_name: str
    market_type: MarketType
    target_segments: list[str]
    pain_points: list[str]
    buyer_roles: list[str]
    product_category: str
    competitive_positioning: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    raw_input: CompanyInput  # full original input, kept for agent context

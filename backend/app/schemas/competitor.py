"""Pydantic schemas for competitor discovery and web intelligence.

Three models correspond to three pipeline stages for each competitor:
  1. ``CompetitorDiscovered`` — LLM identifies a rival (name, website, category).
  2. ``CompetitorWebData``    — Web Agent scrapes the rival's site for features,
                                pricing, marketing copy, etc.
  3. ``CompetitorCleanData``  — Cleaning Agent normalises the raw scraped data
                                into structured, deduplicated fields.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CompetitorBase(BaseModel):
    """Shared fields present in both the discovered and enriched competitor schemas."""

    name: str
    website: str
    category: str       # broad product category, e.g. "CRM" or "Email Automation"
    positioning: str    # brief description of the competitor's market angle


class CompetitorDiscovered(CompetitorBase):
    """Output of Competitor Discovery Agent."""

    competitor_id: UUID = Field(default_factory=uuid4)
    relevance_score: float = Field(ge=0.0, le=1.0, default=0.5)
    discovery_source: str = "llm_search"


class CompetitorWebData(BaseModel):
    """Output of Web Intelligence Agent for a single competitor.

    ``raw_headings``: page URL → list of heading texts; used to build context
    for the Cleaning Agent without losing source attribution.
    ``scrape_success``: False means the scraper hit an error; ``error`` holds
    the reason.  Downstream agents must handle partial data gracefully.
    """

    competitor_id: UUID
    website: str
    features: list[str] = Field(default_factory=list)
    pricing_tiers: list[str] = Field(default_factory=list)
    marketing_copy: str = ""
    value_proposition: str = ""
    target_audience: str = ""
    raw_headings: dict[str, list[str]] = Field(default_factory=dict)  # page_url -> headings
    raw_paragraphs: list[str] = Field(default_factory=list)
    scrape_success: bool = False
    error: Optional[str] = None


class CompetitorCleanData(BaseModel):
    """Output of Cleaning Agent for a single competitor.

    ``normalized_text``: a single merged, whitespace-normalised string built
    from all cleaned fields.  This is what gets embedded into the vector store
    so the RAG layer can retrieve relevant competitor content by semantic search.
    """

    competitor_id: UUID
    clean_features: list[str] = Field(default_factory=list)
    clean_pricing: str = ""
    clean_positioning: str = ""
    clean_value_proposition: str = ""
    normalized_text: str = ""  # combined text for vector embedding

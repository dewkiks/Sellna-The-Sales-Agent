"""Pydantic schemas for Buyer Personas.

Where an ICP describes a *company*, a persona describes the *individual* inside
that company who influences or makes the buying decision.  The Persona Agent
generates 1–5 personas per ICP, each representing a different role or seniority
level (e.g. "VP of Sales" vs "Sales Ops Manager").
"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BuyerPersona(BaseModel):
    """Output of Persona Agent — one human buyer within an ICP-matching company.

    ``icp_id``: links back to the ICPProfile this persona was derived from.
    ``seniority``: e.g. "C-Level", "Director", "Manager" — affects messaging tone.
    ``objections``: anticipated sales objections for this role (e.g. "too expensive").
    ``buying_triggers``: events that make this person start evaluating a solution.
    ``messaging_tone``: "professional" | "friendly" | "technical" — instructs the
        Outreach Agent on the register to use.
    ``content_preferences``: e.g. ["case studies", "ROI calculators"] — used to
        tailor which supporting materials to reference in outreach.
    """

    persona_id: UUID = Field(default_factory=uuid4)
    icp_id: UUID
    company_id: UUID
    title: str        # e.g. "VP of Sales"
    seniority: str    # e.g. "C-Level", "Director", "Manager"
    goals: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    buying_triggers: list[str] = Field(default_factory=list)
    preferred_channels: list[str] = Field(default_factory=list)
    messaging_tone: str = "professional"  # "professional" | "friendly" | "technical"
    content_preferences: list[str] = Field(default_factory=list)


class PersonaGenerateRequest(BaseModel):
    """API request body to trigger persona generation.

    ``icp_id``: optional — if omitted, the agent generates personas for all
    ICPs belonging to the company.
    ``num_personas``: how many personas per ICP (1–5).
    """

    icp_id: UUID | None = None
    company_id: UUID
    num_personas: int = Field(default=2, ge=1, le=5)

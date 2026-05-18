"""Pydantic schemas for Outreach content generation.

The Outreach Agent produces one ``OutreachAsset`` per channel per persona.
Channels are: "cold_email", "linkedin", "call_opener".

Feedback is written back via ``OutreachFeedback`` when real engagement data
arrives (open/reply/conversion rates).  This closes the loop for future
optimisation runs.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class OutreachAsset(BaseModel):
    """A single piece of generated outreach content, tailored to one persona.

    ``channel``: "cold_email" | "linkedin" | "call_opener".
    ``subject``: email subject line; empty string for non-email channels.
    ``personalization_tokens``: placeholder key→value pairs the salesperson
    can substitute before sending (e.g. {"first_name": "{{first_name}}"}).
    """

    asset_id: UUID = Field(default_factory=uuid4)
    persona_id: UUID
    company_id: UUID
    channel: str  # "cold_email" | "linkedin" | "call_opener"
    subject: str = ""   # email subject line; blank for non-email channels
    body: str
    call_to_action: str = ""
    personalization_tokens: dict[str, Any] = Field(default_factory=dict)


class OutreachGenerateRequest(BaseModel):
    """API request body to trigger outreach generation for a persona.

    ``channels``: which outreach formats to produce; defaults to all three.
    """

    persona_id: UUID
    company_id: UUID
    channels: list[str] = Field(
        default=["cold_email", "linkedin", "call_opener"],
        description="List of channels to generate content for",
    )


class OutreachUpdateRequest(BaseModel):
    """Partial edit of a generated outreach asset — only sent fields are changed."""

    subject: str | None = None
    body: str | None = None
    call_to_action: str | None = None


class OutreachFeedback(BaseModel):
    """Engagement signal for a sent outreach asset.

    All rate fields are constrained to [0.0, 1.0] (Pydantic validators enforce
    this so invalid API payloads are rejected before hitting the DB).
    ``notes``: free-text salesperson commentary (e.g. "bounced — bad email").
    """

    asset_id: UUID
    open_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    reply_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    conversion_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    notes: str = ""

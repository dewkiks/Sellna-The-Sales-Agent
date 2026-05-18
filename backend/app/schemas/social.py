"""Pydantic schemas for the Social Intelligence stage.

The Social Agent discovers, from a company's (or competitor's) website:
  - social accounts (LinkedIn / Instagram org pages),
  - team members (real people — name, title, LinkedIn),
  - contact emails and phone numbers.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SocialProfileData(BaseModel):
    """A single discovered social account (organization-level).

    ``platform``: e.g. "LinkedIn" | "Instagram".
    ``success``: False if the Social Agent failed to scrape this profile.
    ``source``: the page URL where the social link was found.
    ``data``: raw platform-specific scraped content (follower count, bio, etc.).
    """

    platform: str  # "LinkedIn" | "Instagram" | ...
    profile_type: str = "organization"
    url: str
    success: bool = False
    error: Optional[str] = None
    source: Optional[str] = None  # page URL where the social link was found
    data: dict[str, Any] = Field(default_factory=dict)  # raw scraped platform data


class PersonContact(BaseModel):
    """A real person discovered on a team / leadership / about page."""

    name: str
    title: str = ""
    linkedin_url: str = ""
    source: str = ""  # page URL the person was found on


class SubjectSocials(BaseModel):
    """Everything found for one subject (the target company or a competitor).

    ``subject_type``: "company" — the user's own company; "competitor" — a rival.
    ``subject_id``: the competitor's UUID when subject_type == "competitor";
                    None for the company itself.
    One ``SocialIntelligenceOutput`` holds a list of these, one per subject.
    """

    subject_type: str  # "company" | "competitor"
    subject_id: Optional[UUID] = None  # None for the company; competitor UUID otherwise
    subject_name: str = ""
    website: str = ""
    profiles: list[SocialProfileData] = Field(default_factory=list)
    people: list[PersonContact] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)


class SocialIntelligenceOutput(BaseModel):
    """Aggregate output of the Social Intelligence pipeline stage.

    Wraps all subjects (company + competitors) so the pipeline can pass a
    single object to downstream consumers.

    ``total_profiles``: convenience property — counts scrapped social profiles
    across all subjects; useful for logging and validation.
    """

    subjects: list[SubjectSocials] = Field(default_factory=list)

    @property
    def total_profiles(self) -> int:
        """Total number of social profiles found across all subjects."""
        return sum(len(s.profiles) for s in self.subjects)

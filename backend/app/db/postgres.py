"""Async PostgreSQL setup via SQLAlchemy 2.x + asyncpg.

This module is the single source of truth for the relational data layer.
It defines:
  - The async engine and session factory used throughout the app.
  - All SQLAlchemy ORM models (one per database table).
  - Lifecycle helpers called at FastAPI startup/shutdown.

All heavy JSON payloads (LLM output, scraped data) are stored as JSONB
columns rather than normalised tables, which keeps schema migrations simple
while still allowing indexed queries in PostgreSQL.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import get_settings

_settings = get_settings()

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

engine = create_async_engine(
    _settings.database_url,  # asyncpg:// DSN from config
    pool_size=_settings.db_pool_size,      # max persistent connections in pool
    max_overflow=_settings.db_max_overflow, # extra connections allowed above pool_size
    echo=_settings.db_echo,                # set True in dev to log all SQL
    future=True,                           # use SQLAlchemy 2.x "future" API
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    # expire_on_commit=False: attributes remain accessible after commit without
    # triggering an extra SELECT — important in async code where lazy loads fail.
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------


class Base(AsyncAttrs, DeclarativeBase):
    """Shared ORM base with async attribute support."""
    pass


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------


class UserRecord(Base):
    """A registered application user — the identity behind JWT auth.

    Authentication is local (email + password). ``hashed_password`` stores a
    bcrypt hash, never the plaintext. ``email`` is unique and case-normalised
    by the auth layer before insert/lookup.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="admin", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CompanyRecord(Base):
    """Root entity — the user-submitted company being analysed.

    ``input_data``: the raw CompanyInput JSON as received from the API.
    ``analysis``: the CompanyAnalysis JSON produced by the Domain Agent;
                  null until that agent completes.
    ``updated_at``: automatically refreshed by the DB on every UPDATE.
    """

    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    industry: Mapped[str] = mapped_column(String(100))
    input_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CompetitorRecord(Base):
    """A competitor discovered by the Competitor Agent for a given company.

    ``relevance_score``: 0–1 relevance to the target company (LLM-assigned).
    ``web_data``: raw CompetitorWebData JSON after the Web Agent scrapes the competitor's site.
    ``clean_data``: normalised CompetitorCleanData JSON after the Cleaning Agent runs.
    Both JSON fields start null and are filled by later pipeline stages.
    """

    __tablename__ = "competitors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200))
    website: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(200))
    positioning: Mapped[str] = mapped_column(Text, default="")
    relevance_score: Mapped[float] = mapped_column(Float, default=0.5)
    web_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    clean_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ICPRecord(Base):
    """An Ideal Customer Profile generated by the ICP Agent.

    ``profile_data``: full ICPProfile JSON — industry, company size, revenue
    range, pain points, buying signals, etc.  One company may have several ICPs.
    """

    __tablename__ = "icps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    profile_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PersonaRecord(Base):
    """A buyer persona generated by the Persona Agent.

    ``icp_id``: links back to the ICPRecord this persona refines.
    ``persona_data``: full BuyerPersona JSON — title, goals, pain points,
    objections, preferred channels, messaging tone, etc.
    """

    __tablename__ = "personas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    icp_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    persona_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutreachRecord(Base):
    """A generated outreach asset (email, LinkedIn message, call opener) for a persona.

    ``channel``: one of "cold_email" | "linkedin" | "call_opener".
    ``content``: OutreachAsset JSON — subject, body, CTA, personalisation tokens.
    ``open_rate`` / ``reply_rate`` / ``conversion_rate``: engagement metrics
    written back via OutreachFeedback; default 0.0 until real data arrives.
    """

    __tablename__ = "outreach_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(50))
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    open_rate: Mapped[float] = mapped_column(Float, default=0.0)
    reply_rate: Mapped[float] = mapped_column(Float, default=0.0)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketGapRecord(Base):
    """A market gap or competitive opportunity found by the Gap Analysis Agent.

    ``gap_type``: category — "missing_feature" | "underserved_segment" | "messaging_weakness".
    ``gap_data``: full MarketGap JSON including description, opportunity, evidence.
    ``confidence_score``: 0–1 LLM confidence in the finding.
    """

    __tablename__ = "market_gaps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    gap_type: Mapped[str] = mapped_column(String(100))
    gap_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialProfileRecord(Base):
    """A social profile discovered & scraped during the Social Intelligence stage.

    Covers both organization accounts and individual team-member profiles, for
    the analyzed company and for each competitor.
    """

    __tablename__ = "social_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # "company" — the analyzed company itself; "competitor" — a discovered rival.
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # competitor id when subject_type == "competitor"; null for the company itself.
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    subject_name: Mapped[str] = mapped_column(String(200), default="")
    platform: Mapped[str] = mapped_column(String(50))
    # "organization" — a brand account; "person" — an individual team member.
    profile_type: Mapped[str] = mapped_column(String(20), default="organization")
    url: Mapped[str] = mapped_column(String(700))
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialContactRecord(Base):
    """A contact discovered during the Social Intelligence stage —
    an email address, a phone number, or a real team member."""

    __tablename__ = "social_contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    subject_name: Mapped[str] = mapped_column(String(200), default="")
    # "email" | "phone" | "person"
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[str] = mapped_column(String(300))  # the email / phone / person name
    title: Mapped[str] = mapped_column(String(200), default="")  # job title (persons)
    url: Mapped[str] = mapped_column(String(700), default="")  # LinkedIn URL (persons)
    source_page: Mapped[str] = mapped_column(String(700), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# DB Lifecycle helpers
# ---------------------------------------------------------------------------


async def create_all_tables() -> None:
    """Create all ORM-mapped tables if they do not already exist (idempotent).

    Called once at FastAPI startup (lifespan handler). Uses ``run_sync`` to
    execute the synchronous ``metadata.create_all`` inside the async engine's
    connection context.
    """
    async with engine.begin() as conn:
        # run_sync bridges the gap: metadata.create_all is sync-only
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    """Gracefully close all pooled connections on app shutdown."""
    await engine.dispose()

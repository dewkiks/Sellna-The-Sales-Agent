"""Repository layer — typed CRUD wrappers over SQLAlchemy ORM models.

The *repository pattern* isolates all database access in one place.  Every
entity has its own repository class that accepts an ``AsyncSession`` and
exposes a small, entity-specific API (create / get / update / delete).

Benefits for this codebase:
  - Agents call repositories rather than writing raw SQL, so the agent logic
    stays focused on business rules.
  - All DB interactions are in one file, making them easy to audit, test, and
    swap (e.g. replace PostgreSQL with a different store later).
  - ``flush()`` is used instead of ``commit()`` so that the calling service
    or route handler controls the transaction boundary.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import (
    CompanyRecord,
    CompetitorRecord,
    ICPRecord,
    MarketGapRecord,
    OutreachRecord,
    PersonaRecord,
    PipelineRunRecord,
    SocialContactRecord,
    SocialProfileRecord,
)


# ---------------------------------------------------------------------------
# Company Repository
# ---------------------------------------------------------------------------


class CompanyRepository:
    """CRUD interface for the ``companies`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def create(self, name: str, industry: str, input_data: dict) -> CompanyRecord:
        """Insert a new company row and return it (ID assigned by DB)."""
        record = CompanyRecord(name=name, industry=industry, input_data=input_data)
        self._db.add(record)
        # flush sends the INSERT to the DB within the current transaction so
        # the auto-generated UUID is available immediately on the record object.
        await self._db.flush()
        return record

    async def get_by_id(self, company_id: uuid.UUID) -> Optional[CompanyRecord]:
        """Fetch a company by primary key; returns None if not found."""
        result = await self._db.execute(select(CompanyRecord).where(CompanyRecord.id == company_id))
        return result.scalar_one_or_none()

    async def update_analysis(self, company_id: uuid.UUID, analysis: dict) -> None:
        """Write the Domain Agent's analysis JSON into the company row."""
        record = await self.get_by_id(company_id)
        if record:
            record.analysis = analysis
            await self._db.flush()

    async def list_all(self) -> list[CompanyRecord]:
        """Return all companies ordered newest-first."""
        result = await self._db.execute(select(CompanyRecord).order_by(CompanyRecord.created_at.desc()))
        return list(result.scalars().all())

    async def delete(self, company_id: uuid.UUID) -> bool:
        """Delete a company and every record that belongs to it.

        Related tables key off ``company_id`` without DB-level cascades, so each
        child table is cleared explicitly before removing the company row.
        Returns False if the company doesn't exist.
        """
        record = await self.get_by_id(company_id)
        if record is None:
            return False
        # Delete children in dependency order (outreach depends on persona,
        # persona depends on ICP, etc.) to respect logical foreign keys.
        for model in (
            OutreachRecord,
            PersonaRecord,
            ICPRecord,
            MarketGapRecord,
            CompetitorRecord,
            SocialContactRecord,
            SocialProfileRecord,
        ):
            await self._db.execute(
                sa_delete(model).where(model.company_id == company_id)
            )
        await self._db.execute(
            sa_delete(CompanyRecord).where(CompanyRecord.id == company_id)
        )
        await self._db.flush()
        return True

    async def delete_all(self) -> None:
        """Wipe every row from every application table."""
        for model in (
            OutreachRecord,
            PersonaRecord,
            ICPRecord,
            MarketGapRecord,
            CompetitorRecord,
            SocialContactRecord,
            SocialProfileRecord,
            CompanyRecord,
        ):
            await self._db.execute(sa_delete(model))
        await self._db.flush()


# ---------------------------------------------------------------------------
# Competitor Repository
# ---------------------------------------------------------------------------


class CompetitorRepository:
    """CRUD interface for the ``competitors`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def bulk_create(self, company_id: uuid.UUID, competitors: list[dict]) -> list[CompetitorRecord]:
        """Insert all discovered competitors for a company in one flush.

        ``add_all`` queues every record together; a single flush sends them as
        one batch to the DB, which is more efficient than N individual flushes.
        """
        records = [CompetitorRecord(company_id=company_id, **c) for c in competitors]
        self._db.add_all(records)
        await self._db.flush()
        return records

    async def get_by_company(self, company_id: uuid.UUID) -> list[CompetitorRecord]:
        """Return all competitors discovered for a given company."""
        result = await self._db.execute(
            select(CompetitorRecord).where(CompetitorRecord.company_id == company_id)
        )
        return list(result.scalars().all())

    async def update_web_data(self, competitor_id: uuid.UUID, web_data: dict) -> None:
        """Write raw scraped web content (CompetitorWebData JSON) onto a competitor row."""
        result = await self._db.execute(
            select(CompetitorRecord).where(CompetitorRecord.id == competitor_id)
        )
        record = result.scalar_one_or_none()
        if record:
            record.web_data = web_data
            await self._db.flush()

    async def update_clean_data(self, competitor_id: uuid.UUID, clean_data: dict) -> None:
        """Write normalised data (CompetitorCleanData JSON) after the Cleaning Agent runs."""
        result = await self._db.execute(
            select(CompetitorRecord).where(CompetitorRecord.id == competitor_id)
        )
        record = result.scalar_one_or_none()
        if record:
            record.clean_data = clean_data
            await self._db.flush()


# ---------------------------------------------------------------------------
# ICP Repository
# ---------------------------------------------------------------------------


class ICPRepository:
    """CRUD interface for the ``icps`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def create(self, company_id: uuid.UUID, profile_data: dict) -> ICPRecord:
        """Persist one ICP profile (ICPProfile JSON) for a company."""
        record = ICPRecord(company_id=company_id, profile_data=profile_data)
        self._db.add(record)
        await self._db.flush()
        return record

    async def get_by_company(self, company_id: uuid.UUID) -> list[ICPRecord]:
        """Return all ICP profiles generated for a company (typically 1–5)."""
        result = await self._db.execute(
            select(ICPRecord).where(ICPRecord.company_id == company_id)
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Persona Repository
# ---------------------------------------------------------------------------


class PersonaRepository:
    """CRUD interface for the ``personas`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def create(self, icp_id: uuid.UUID, company_id: uuid.UUID, persona_data: dict) -> PersonaRecord:
        """Persist one buyer persona (BuyerPersona JSON) linked to an ICP."""
        record = PersonaRecord(icp_id=icp_id, company_id=company_id, persona_data=persona_data)
        self._db.add(record)
        await self._db.flush()
        return record

    async def get_by_company(self, company_id: uuid.UUID) -> list[PersonaRecord]:
        """Return all personas for a company across all its ICPs."""
        result = await self._db.execute(
            select(PersonaRecord).where(PersonaRecord.company_id == company_id)
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Outreach Repository
# ---------------------------------------------------------------------------


class OutreachRepository:
    """CRUD interface for the ``outreach_assets`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def create(
        self,
        persona_id: uuid.UUID,
        company_id: uuid.UUID,
        channel: str,
        content: dict,
    ) -> OutreachRecord:
        """Persist a new outreach asset (email / LinkedIn / call opener)."""
        record = OutreachRecord(
            persona_id=persona_id, company_id=company_id, channel=channel, content=content
        )
        self._db.add(record)
        await self._db.flush()
        return record

    async def update_content(
        self,
        asset_id: uuid.UUID,
        fields: dict,
    ) -> OutreachRecord | None:
        """Merge ``fields`` into an asset's content JSON. Returns the record, or None if absent.

        A new dict is constructed via ``{**old, **fields}`` so SQLAlchemy's
        change-tracking detects the JSONB column as modified — mutating the
        existing dict in-place would be invisible to the ORM.
        """
        result = await self._db.execute(
            select(OutreachRecord).where(OutreachRecord.id == asset_id)
        )
        record = result.scalar_one_or_none()
        if record:
            # Reassign a new dict so SQLAlchemy detects the JSON column change.
            record.content = {**(record.content or {}), **fields}
            await self._db.flush()
        return record

    async def update_feedback(
        self,
        asset_id: uuid.UUID,
        open_rate: float,
        reply_rate: float,
        conversion_rate: float,
    ) -> None:
        """Write real engagement metrics back onto a sent outreach asset."""
        result = await self._db.execute(
            select(OutreachRecord).where(OutreachRecord.id == asset_id)
        )
        record = result.scalar_one_or_none()
        if record:
            record.open_rate = open_rate
            record.reply_rate = reply_rate
            record.conversion_rate = conversion_rate
            await self._db.flush()

    async def get_by_company(self, company_id: uuid.UUID) -> list[OutreachRecord]:
        """Return all outreach assets created for a company (all channels, all personas)."""
        result = await self._db.execute(
            select(OutreachRecord).where(OutreachRecord.company_id == company_id)
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Market Gap Repository
# ---------------------------------------------------------------------------


class MarketGapRepository:
    """CRUD interface for the ``market_gaps`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def create(self, company_id: uuid.UUID, gap_type: str, gap_data: dict, confidence: float) -> MarketGapRecord:
        """Persist one market gap finding (MarketGap JSON) with its confidence score."""
        record = MarketGapRecord(
            company_id=company_id, gap_type=gap_type, gap_data=gap_data, confidence_score=confidence
        )
        self._db.add(record)
        await self._db.flush()
        return record

    async def get_by_company(self, company_id: uuid.UUID) -> list[MarketGapRecord]:
        """Return all market gaps identified for a company."""
        result = await self._db.execute(
            select(MarketGapRecord).where(MarketGapRecord.company_id == company_id)
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Social Profile Repository
# ---------------------------------------------------------------------------


class SocialProfileRepository:
    """CRUD interface for the ``social_profiles`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def bulk_create(
        self, company_id: uuid.UUID, profiles: list[dict]
    ) -> list[SocialProfileRecord]:
        """Persist a batch of scraped social profiles for a company.

        Uses ``add_all`` + a single ``flush`` for efficiency — same pattern
        as ``CompetitorRepository.bulk_create``.
        """
        records = [SocialProfileRecord(company_id=company_id, **p) for p in profiles]
        self._db.add_all(records)
        await self._db.flush()
        return records

    async def get_by_company(self, company_id: uuid.UUID) -> list[SocialProfileRecord]:
        """Return all social profiles for a company, newest first."""
        result = await self._db.execute(
            select(SocialProfileRecord)
            .where(SocialProfileRecord.company_id == company_id)
            .order_by(SocialProfileRecord.created_at.desc())
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Social Contact Repository
# ---------------------------------------------------------------------------


class SocialContactRepository:
    """CRUD interface for the ``social_contacts`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def bulk_create(
        self, company_id: uuid.UUID, contacts: list[dict]
    ) -> list[SocialContactRecord]:
        """Persist a batch of discovered emails / phones / people."""
        records = [SocialContactRecord(company_id=company_id, **c) for c in contacts]
        self._db.add_all(records)
        await self._db.flush()
        return records

    async def get_by_company(self, company_id: uuid.UUID) -> list[SocialContactRecord]:
        """Return all contacts discovered for a company, newest first."""
        result = await self._db.execute(
            select(SocialContactRecord)
            .where(SocialContactRecord.company_id == company_id)
            .order_by(SocialContactRecord.created_at.desc())
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Pipeline Run Repository
# ---------------------------------------------------------------------------


class PipelineRunRepository:
    """CRUD interface for the ``pipeline_runs`` table — durable run snapshots.

    Stores the aggregated agent-stream state for a pipeline run so the live-run
    view can be restored after a browser refresh.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def upsert(
        self,
        job_id: str,
        company_id: uuid.UUID | None,
        agents: list,
        active_agent: Optional[str],
        done: bool,
    ) -> PipelineRunRecord:
        """Insert or update the snapshot for a job (one row per ``job_id``)."""
        record = (
            await self._db.execute(
                select(PipelineRunRecord).where(PipelineRunRecord.job_id == job_id)
            )
        ).scalar_one_or_none()
        if record is None:
            record = PipelineRunRecord(job_id=job_id)
            self._db.add(record)
        record.company_id = company_id
        record.agents = agents
        record.active_agent = active_agent
        record.done = done
        await self._db.flush()
        return record

    async def get(self, job_id: str) -> Optional[PipelineRunRecord]:
        """Fetch a run snapshot by job id; returns None if absent."""
        result = await self._db.execute(
            select(PipelineRunRecord).where(PipelineRunRecord.job_id == job_id)
        )
        return result.scalar_one_or_none()

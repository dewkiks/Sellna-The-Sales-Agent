"""Sales Pipeline Orchestrator — the central coordinator of the Sellna.ai backend.

Role in architecture
--------------------
``SalesPipeline.run()`` is the single entry point that transforms a
``CompanyInput`` (domain + company name) into a full ``PipelineResult``
containing competitors, market gaps, ICPs, buyer personas, and outreach copy.

It is called by the FastAPI route in ``app/api/v1/pipeline.py``.

Pipeline stages and data flow
------------------------------

  CompanyInput (user input)
      │
  Stage 1 — DomainAgent         → CompanyAnalysis
      │         (LLM: SERP + company intelligence)
      │
  Stage 2 — CompetitorAgent     → [CompetitorDiscovered]
      │         (LLM: identifies competitors from company analysis)
      │
  Stage 3 — WebAgent            → [CompetitorWebData]        ← scrapping_module
      │         (scrapes each competitor site IN PARALLEL via asyncio.as_completed)
      │
  Stage 3.5 — SocialAgent       → [SubjectSocials]           ← scrapping_module social
      │         (discovers LinkedIn/Instagram for company + competitors IN PARALLEL)
      │
  Stage 4 — CleaningAgent       → [CompetitorCleanData]
      │         (LLM: normalises raw web data into structured profiles)
      │
  Stage 5 — GapAnalysisAgent    → [MarketGap]                ← RAG
      │         (indexes clean profiles → retrieves → LLM identifies gaps)
      │
  Stage 6 — ICPAgent            → [ICPProfile]
      │         (LLM: builds Ideal Customer Profiles from gaps + analysis)
      │
  Stage 7 — PersonaAgent        → [BuyerPersona]             ← RAG, PARALLEL per ICP
      │         (retrieves gap context → LLM generates personas for each ICP)
      │
  Stage 8 — OutreachAgent       → [OutreachAsset]            ← RAG, PARALLEL per persona
              (retrieves persona+gap context → LLM writes personalised outreach)

Parallelism strategy
--------------------
- **Web scraping (Stage 3)** and **Social scraping (Stage 3.5)** use
  ``asyncio.as_completed()`` — results are persisted to the DB *as each URL
  finishes*, so a slow site doesn't block faster ones from being saved.
- **Persona generation (Stage 7)** uses ``asyncio.as_completed()`` — one
  coroutine per ICP; personas are saved incrementally.
- **Outreach generation (Stage 8)** uses ``asyncio.gather()`` — all persona
  outreach tasks are launched simultaneously; gather collects them all at the
  end (exceptions are caught per-batch rather than aborting the whole stage).

Error handling
--------------
``_run_stage()`` wraps every sequential stage in a timeout
(``settings.pipeline_timeout_seconds``) and a bare Exception catch.
Failures append to ``errors: list[str]`` and return ``None``, so later stages
receive empty inputs and emit warnings rather than crashing the whole run.

Live progress (streaming callbacks)
------------------------------------
The constructor accepts two callbacks:
- ``on_progress(status, progress, company_id)`` — coarse integer percentage;
  used by the HTTP polling endpoint.
- ``stream_cb(event: dict)`` — fine-grained SSE events with per-agent typing
  (``agent_start``, ``scrape_tick``, ``agent_done``, ``done``).  ``_make_agent_cb``
  wraps ``stream_cb`` to automatically inject the agent name so the frontend
  can render per-agent thinking panels.

Persistence
-----------
Every stage persists its output to PostgreSQL via repository classes
(``CompanyRepository``, ``CompetitorRepository``, …) before proceeding.
``await self._db.commit()`` is called after each persist so partial results
are visible even if the pipeline fails mid-run.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import (
    CleaningAgent,
    CompetitorAgent,
    DomainAgent,
    GapAnalysisAgent,
    ICPAgent,
    OutreachAgent,
    PersonaAgent,
    SocialAgent,
    WebAgent,
)
from app.config import get_settings
from app.core.logging import get_logger
from app.db.repositories import (
    CompanyRepository,
    CompetitorRepository,
    ICPRepository,
    MarketGapRepository,
    OutreachRepository,
    PersonaRepository,
    SocialContactRepository,
    SocialProfileRepository,
)
from app.schemas.company import CompanyAnalysis, CompanyInput
from app.schemas.competitor import CompetitorCleanData, CompetitorDiscovered, CompetitorWebData
from app.schemas.gap_analysis import MarketGap
from app.schemas.icp import ICPProfile
from app.schemas.outreach import OutreachAsset
from app.schemas.persona import BuyerPersona
from app.schemas.social import SubjectSocials

logger = get_logger(__name__)
_settings = get_settings()


# ---------------------------------------------------------------------------
# Pipeline output contract
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """Complete enterprise output produced by one full pipeline run.

    Returned directly by ``SalesPipeline.run()`` and serialised to JSON
    by the FastAPI route via ``to_dict()``.  All list fields default to
    empty so callers can safely iterate even when a stage produced nothing.
    """

    company_id: UUID
    company_analysis: CompanyAnalysis
    competitors: list[CompetitorDiscovered] = field(default_factory=list)
    social_profiles: list[SubjectSocials] = field(default_factory=list)
    market_gaps: list[MarketGap] = field(default_factory=list)
    icps: list[ICPProfile] = field(default_factory=list)
    personas: list[BuyerPersona] = field(default_factory=list)
    outreach_assets: list[OutreachAsset] = field(default_factory=list)
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise all Pydantic schema objects to plain dicts for JSON response."""
        return {
            "company_id": str(self.company_id),
            "icps": [icp.model_dump() for icp in self.icps],
            "personas": [p.model_dump() for p in self.personas],
            "outreach_assets": [a.model_dump() for a in self.outreach_assets],
            "market_gaps": [g.model_dump() for g in self.market_gaps],
            "competitors": [c.model_dump() for c in self.competitors],
            # mode="json" ensures UUID/datetime fields are JSON-serialisable strings.
            "social_profiles": [s.model_dump(mode="json") for s in self.social_profiles],
            "duration_seconds": round(self.duration_seconds, 2),
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class SalesPipeline:
    """Async pipeline orchestrator. Stateless — creates new agents per run.

    One ``SalesPipeline`` instance handles exactly one ``run()`` call.
    Do not reuse an instance across requests.
    """

    def __init__(
        self,
        db: AsyncSession,
        proxy: str | None = None,
        render_js: bool = False,
        num_icps: int = 1,
        num_personas_per_icp: int = 1,
        on_progress: Callable | None = None,
        stream_cb: Callable | None = None,
    ) -> None:
        """
        Args:
            db:                  SQLAlchemy async session (injected by FastAPI dependency).
            proxy:               Optional HTTP/SOCKS proxy forwarded to ScrapingService.
            render_js:           Enable Playwright JS rendering for scraping.
            num_icps:            How many Ideal Customer Profiles to generate.
            num_personas_per_icp: Buyer personas generated per ICP.
            on_progress:         Coarse callback ``(status, progress, company_id)``
                                 for HTTP polling.
            stream_cb:           Fine-grained SSE event callback ``(event: dict)``.
                                 Receives agent-tagged dicts; see ``_make_agent_cb``.
        """
        self._db = db
        self._proxy = proxy
        self._render_js = render_js
        self._num_icps = num_icps
        self._num_personas = num_personas_per_icp
        self._on_progress = on_progress
        self._stream_cb = stream_cb
        # Populated after Stage 1 persists the company record to the DB.
        self._company_id: UUID | None = None

    async def run(self, company_input: CompanyInput) -> PipelineResult:
        """Execute the full 9-stage sales intelligence pipeline.

        Args:
            company_input: User-provided company name, domain, and optional
                           metadata (industry, website, description).

        Returns:
            ``PipelineResult`` containing all generated intelligence.
            Even on partial failure the result is returned — check
            ``result.errors`` and ``result.warnings`` for diagnostics.
        """
        t0 = time.perf_counter()
        errors: list[str] = []
        warnings: list[str] = []

        logger.info(
            "pipeline.start",
            company=company_input.company_name,
            stages="domain→competitor→web→social→clean→gap→icp→persona→outreach",
        )

        # ------------------------------------------------------------------
        # Stage 1: Domain Intelligence
        company_analysis = await self._run_stage(
            "domain_intelligence",
            lambda inp: DomainAgent().run(inp, stream_cb=self._make_agent_cb("DomainAgent")),
            company_input,
            errors,
        )
        if company_analysis is None:
            return PipelineResult(
                company_id=uuid.uuid4(),
                company_analysis=None,  # type: ignore
                errors=errors,
                warnings=warnings,
                duration_seconds=time.perf_counter() - t0,
            )

        company_id = getattr(company_analysis, "company_id", None)

        # Persist company
        repo = CompanyRepository(self._db)
        company_record = await repo.create(
            name=company_input.company_name,
            industry=company_input.industry,
            input_data=company_input.model_dump(mode="json"),
        )
        await repo.update_analysis(company_record.id, company_analysis.model_dump(mode="json"))
        await self._db.commit()
        self._company_id = company_record.id
        if self._on_progress:
            self._on_progress(status="Company analyzed", progress=self._get_stage_progress("domain_intelligence"), company_id=str(self._company_id))

        # ------------------------------------------------------------------
        # Stage 2: Competitor Discovery
        # ------------------------------------------------------------------
        _comp_cb = self._make_agent_cb("CompetitorAgent")
        if _comp_cb:
            _comp_cb({"type": "agent_start", "label": "Discovering competitors..."})
        competitors: list[CompetitorDiscovered] = await self._run_stage(
            "competitor_discovery",
            lambda inp: CompetitorAgent().run(inp, stream_cb=_comp_cb),
            company_analysis,
            errors,
        ) or []
        if _comp_cb:
            names = ", ".join(c.name for c in competitors[:3])
            _comp_cb({
                "type": "agent_done",
                "summary": f"{len(competitors)} competitors · {names}",
                "result": {
                    "competitors": [
                        {"name": c.name, "website": c.website, "category": c.category, "score": c.relevance_score}
                        for c in competitors
                    ]
                },
            })

        if not competitors:
            warnings.append(
                "Competitor discovery produced 0 competitors — "
                "web scraping and gap analysis will have no competitor data."
            )

        # Persist competitors.
        # bulk_create lets the DB assign each row's id (auto-increment / UUID gen).
        # We then realign each in-memory CompetitorDiscovered object's competitor_id
        # to match its corresponding DB row.  Without this realignment, later stages
        # (WebAgent, SocialAgent, CleaningAgent) would call update_*_data() with a
        # stale in-memory uuid4, silently match no DB row, and lose all scraped data.
        comp_repo = CompetitorRepository(self._db)
        if competitors:
            created = await comp_repo.bulk_create(
                company_id=company_record.id,
                competitors=[
                    {
                        "name": c.name,
                        "website": c.website,
                        "category": c.category,
                        "positioning": c.positioning,
                        "relevance_score": c.relevance_score,
                    }
                    for c in competitors
                ],
            )
            for comp, record in zip(competitors, created):
                comp.competitor_id = record.id
            await self._db.commit()

        # Stage 3: Web Intelligence
        # ------------------------------------------------------------------
        _web_cb = self._make_agent_cb("WebAgent")
        if _web_cb:
            _web_cb({"type": "agent_start", "label": f"Scraping {len(competitors)} competitor websites..."})
            _web_cb({
                "type": "token",
                "content": (
                    f"→ Launching {len(competitors)} parallel scrapes\n"
                    f"  render_js={self._render_js}\n"
                    f"  targets:\n"
                    + "".join(f"   - {c.name} ({c.website})\n" for c in competitors)
                    + "\n"
                ),
            })
        web_agent = WebAgent(proxy=self._proxy, render_js=self._render_js)
        web_data: list[CompetitorWebData] = []
        scraped_count = 0

        if competitors:
            logger.info("pipeline.web_intel.start", count=len(competitors))
            # Launch one scrape coroutine per competitor simultaneously.
            # asyncio.as_completed() yields futures as they resolve, so we
            # persist each result immediately rather than waiting for the
            # slowest site.  A failed scrape raises → caught below → added
            # to errors, pipeline continues with remaining competitors.
            tasks = [web_agent.scrape_one(c) for c in competitors]
            for future in asyncio.as_completed(tasks):
                try:
                    wd = await future
                    web_data.append(wd)
                    scraped_count += 1
                    await comp_repo.update_web_data(wd.competitor_id, wd.model_dump(mode="json"))
                    await self._db.commit()
                    if _web_cb:
                        _web_cb({"type": "scrape_tick", "url": wd.website, "count": scraped_count, "total": len(competitors)})
                        if wd.scrape_success:
                            _web_cb({
                                "type": "token",
                                "content": (
                                    f"[{scraped_count}/{len(competitors)}] ✓ {wd.website}\n"
                                    f"    features={len(wd.features or [])} · "
                                    f"pricing_tiers={len(wd.pricing_tiers or [])} · "
                                    f"paragraphs={len(wd.raw_paragraphs or [])}\n"
                                    f"    value_prop: {(wd.value_proposition or '')[:120]}\n"
                                ),
                            })
                        else:
                            _web_cb({
                                "type": "token",
                                "content": (
                                    f"[{scraped_count}/{len(competitors)}] ✗ {wd.website}\n"
                                    f"    error: {wd.error or 'unknown'}\n"
                                ),
                            })
                    if self._on_progress:
                        self._on_progress(status=f"Scraped {wd.website}", progress=self._get_stage_progress("web_intelligence"), company_id=str(self._company_id))
                except Exception as e:
                    logger.error("pipeline.web_intel.error", error=str(e))
                    errors.append(f"Scrape failed: {e}")
                    if _web_cb:
                        _web_cb({"type": "token", "content": f"[!] scrape error: {e}\n"})
        if _web_cb:
            _web_cb({
                "type": "agent_done",
                "summary": f"{scraped_count}/{len(competitors)} pages scraped",
                "result": {
                    "sites": [
                        {
                            "website": wd.website,
                            "success": wd.scrape_success,
                            "value_proposition": (wd.value_proposition or "")[:120],
                            "features": (wd.features or [])[:5],
                            "pricing_found": bool(wd.pricing_tiers),
                            "error": wd.error if not wd.scrape_success else None,
                        }
                        for wd in web_data
                    ]
                },
            })

        # ------------------------------------------------------------------
        # Stage 3.5: Social Intelligence
        # Discovers + scrapes social accounts and team-member profiles for the
        # company itself and every discovered competitor.
        # ------------------------------------------------------------------
        _social_cb = self._make_agent_cb("SocialAgent")
        social_subjects: list[SubjectSocials] = []
        social_repo = SocialProfileRepository(self._db)
        contact_repo = SocialContactRepository(self._db)

        # Build the list of subjects to scrape: the analysed company itself
        # + every discovered competitor.  The tuple is (type, db_id, name, url).
        social_targets: list[tuple[str, UUID | None, str, str]] = []
        company_site = (company_input.website or "").strip()
        if company_site:
            social_targets.append(
                ("company", None, company_input.company_name, company_site)
            )
        for c in competitors:
            if c.website:
                social_targets.append(
                    ("competitor", c.competitor_id, c.name, c.website)
                )

        if _social_cb:
            _social_cb({
                "type": "agent_start",
                "label": f"Discovering social profiles across {len(social_targets)} subjects...",
            })
            _social_cb({
                "type": "token",
                "content": (
                    f"→ {len(social_targets)} subjects queued\n"
                    + "".join(
                        f"   - {sn} ({st}) — {sw}\n"
                        for st, _sid, sn, sw in social_targets
                    )
                    + "→ Crawling homepage + team/about/contact pages for each\n\n"
                ),
            })

        if social_targets:
            logger.info("pipeline.social_intel.start", subjects=len(social_targets))
            social_agent = SocialAgent(proxy=self._proxy, render_js=self._render_js)
            # Same concurrency pattern as web scraping: one coroutine per subject,
            # results persisted incrementally via asyncio.as_completed().
            social_tasks = [
                social_agent.run(
                    subject_type=st, subject_id=sid, subject_name=sn, website=sw
                )
                for st, sid, sn, sw in social_targets
            ]
            for future in asyncio.as_completed(social_tasks):
                try:
                    subj = await future
                    social_subjects.append(subj)
                    rows = [
                        {
                            "subject_type": subj.subject_type,
                            "subject_id": subj.subject_id,
                            "subject_name": subj.subject_name,
                            "platform": p.platform,
                            "profile_type": p.profile_type,
                            "url": p.url,
                            "success": p.success,
                            "data": p.data,
                        }
                        for p in subj.profiles
                    ]
                    # Emails, phones and people all land in social_contacts.
                    base = {
                        "subject_type": subj.subject_type,
                        "subject_id": subj.subject_id,
                        "subject_name": subj.subject_name,
                    }
                    contact_rows = (
                        [
                            {**base, "kind": "email", "value": e}
                            for e in subj.emails
                        ]
                        + [
                            {**base, "kind": "phone", "value": p}
                            for p in subj.phones
                        ]
                        + [
                            {
                                **base,
                                "kind": "person",
                                "value": person.name,
                                "title": person.title,
                                "url": person.linkedin_url,
                                "source_page": person.source,
                            }
                            for person in subj.people
                        ]
                    )
                    if rows:
                        await social_repo.bulk_create(company_record.id, rows)
                    if contact_rows:
                        await contact_repo.bulk_create(
                            company_record.id, contact_rows
                        )
                    if rows or contact_rows:
                        await self._db.commit()
                    if _social_cb:
                        _social_cb({
                            "type": "scrape_tick",
                            "url": subj.website,
                            "count": len(subj.profiles)
                            + len(subj.people)
                            + len(subj.emails),
                        })
                        _social_cb({
                            "type": "token",
                            "content": (
                                f"✓ {subj.subject_name} ({subj.subject_type})\n"
                                f"    accounts={len(subj.profiles)} · "
                                f"people={len(subj.people)} · "
                                f"emails={len(subj.emails)} · "
                                f"phones={len(subj.phones)}\n"
                            ),
                        })
                    if self._on_progress:
                        self._on_progress(
                            status=f"Social profiles for {subj.subject_name}",
                            progress=self._get_stage_progress("social_intelligence"),
                            company_id=str(self._company_id),
                        )
                except Exception as e:
                    logger.error("pipeline.social_intel.error", error=str(e))
                    errors.append(f"Social intelligence failed: {e}")
                    if _social_cb:
                        _social_cb({"type": "token", "content": f"[!] social fetch error: {e}\n"})

        total_accounts = sum(len(s.profiles) for s in social_subjects)
        total_people = sum(len(s.people) for s in social_subjects)
        total_emails = sum(len(s.emails) for s in social_subjects)
        if _social_cb:
            _social_cb({
                "type": "agent_done",
                "summary": (
                    f"{total_accounts} accounts · {total_people} people · "
                    f"{total_emails} emails across {len(social_subjects)} subjects"
                ),
                "result": {
                    "subjects": [
                        {
                            "subject": s.subject_name,
                            "type": s.subject_type,
                            "accounts": [
                                {
                                    "platform": p.platform,
                                    "url": p.url,
                                }
                                for p in s.profiles
                            ],
                            "people": [
                                {"name": pe.name, "title": pe.title}
                                for pe in s.people
                            ],
                            "emails": s.emails,
                        }
                        for s in social_subjects
                    ]
                },
            })

        # ------------------------------------------------------------------
        # Stage 4: Data Cleaning
        # ------------------------------------------------------------------
        _clean_cb = self._make_agent_cb("CleaningAgent")
        if _clean_cb:
            _clean_cb({"type": "agent_start", "label": "Cleaning and structuring web data..."})
        clean_data: list[CompetitorCleanData] = await self._run_stage(
            "data_cleaning",
            lambda inp: CleaningAgent().run(inp, stream_cb=_clean_cb),
            web_data,
            errors,
        ) or []
        if _clean_cb:
            _clean_cb({"type": "agent_done", "summary": f"{len(clean_data)} competitor profiles structured"})

        # Persist clean data
        for cd in clean_data:
            await comp_repo.update_clean_data(cd.competitor_id, cd.model_dump(mode="json"))
        await self._db.commit()

        # ------------------------------------------------------------------
        # Stage 5: Gap Analysis (RAG)
        # ------------------------------------------------------------------
        _gap_cb = self._make_agent_cb("GapAnalysisAgent")
        if _gap_cb:
            _gap_cb({"type": "agent_start", "label": "Analyzing market gaps from competitor data..."})
        gaps: list[MarketGap] = await self._run_stage(
            "gap_analysis",
            lambda: GapAnalysisAgent().run(company_analysis, clean_data, stream_cb=_gap_cb),
            None,
            errors,
            no_arg=True,
        ) or []
        if _gap_cb:
            _gap_cb({
                "type": "agent_done",
                "summary": f"{len(gaps)} market gaps identified",
                "result": {
                    "gaps": [
                        {"type": g.gap_type, "description": g.description[:100], "confidence": round(g.confidence_score, 2)}
                        for g in gaps[:5]
                    ]
                },
            })

        # Persist gaps
        gap_repo = MarketGapRepository(self._db)
        for gap in gaps:
            await gap_repo.create(
                company_id=company_record.id,
                gap_type=gap.gap_type,
                gap_data=gap.model_dump(mode="json"),
                confidence=gap.confidence_score,
            )
        await self._db.commit()

        # ------------------------------------------------------------------
        # Stage 6: ICP Generation
        # ------------------------------------------------------------------
        icps: list[ICPProfile] = await self._run_stage(
            "icp_generation",
            lambda: ICPAgent().run(company_analysis, gaps, self._num_icps, stream_cb=self._make_agent_cb("ICPAgent")),
            None,
            errors,
            no_arg=True,
        ) or []

        if not icps:
            warnings.append(
                "ICP generation produced 0 profiles — "
                "persona and outreach generation were skipped."
            )

        # Persist ICPs
        icp_repo = ICPRepository(self._db)
        for icp in icps:
            await icp_repo.create(
                company_id=company_record.id,
                profile_data=icp.model_dump(mode="json"),
            )
        await self._db.commit()

        # Stage 7: Persona Generation (RAG-enriched)
        # ------------------------------------------------------------------
        # The RAG collection name is scoped to this company's run so data
        # from one company never leaks into another company's retrieval.
        rag_collection = f"gap_{company_id}"
        persona_agent = PersonaAgent()
        persona_repo = PersonaRepository(self._db)
        personas: list[BuyerPersona] = []

        # Emit agent_start/done at the pipeline level — the parallel
        # generate_for_icp() invocations do not, so without this PersonaAgent
        # never appears in the live UI and its tokens would be dropped.
        _persona_cb = self._make_agent_cb("PersonaAgent")
        if _persona_cb and icps:
            _persona_cb({
                "type": "agent_start",
                "label": f"Building {self._num_personas} personas for each of {len(icps)} ICPs...",
            })
            _persona_cb({
                "type": "token",
                "content": (
                    f"→ {len(icps)} ICPs queued · {self._num_personas} personas each\n"
                    + "".join(
                        f"   - {icp.industry or 'ICP'} · {icp.buyer_authority or '?'}\n"
                        for icp in icps
                    )
                    + f"→ RAG collection: {rag_collection}\n\n"
                ),
            })

        if icps:
            logger.info("pipeline.persona_gen.start", count=len(icps))
            # One coroutine per ICP, all run concurrently.  asyncio.as_completed
            # saves each ICP's personas to the DB as soon as they are ready.
            persona_tasks = [persona_agent.generate_for_icp(company_analysis, icp, self._num_personas, rag_collection, stream_cb=_persona_cb) for icp in icps]
            for future in asyncio.as_completed(persona_tasks):
                try:
                    p_list = await future
                    for p in p_list:
                        personas.append(p)
                        await persona_repo.create(
                            icp_id=p.icp_id,
                            company_id=company_record.id,
                            persona_data=p.model_dump(mode="json"),
                        )
                    await self._db.commit()
                    if _persona_cb and p_list:
                        titles = ", ".join(p.title for p in p_list)
                        _persona_cb({
                            "type": "token",
                            "content": f"✓ ICP done · {len(p_list)} personas: {titles}\n",
                        })
                    if self._on_progress:
                        self._on_progress(status=f"Generated {len(p_list)} personas", progress=self._get_stage_progress("persona_generation"), company_id=str(self._company_id))
                except Exception as e:
                    logger.error("pipeline.persona_gen.error", error=str(e))
                    errors.append(f"Persona generation failed: {e}")
                    if _persona_cb:
                        _persona_cb({"type": "token", "content": f"[!] persona error: {e}\n"})

        if _persona_cb and icps:
            titles = ", ".join(p.title for p in personas[:3])
            _persona_cb({
                "type": "agent_done",
                "summary": f"{len(personas)} personas · {titles}",
                "result": {
                    "personas": [
                        {
                            "title": p.title,
                            "seniority": p.seniority,
                            "messaging_tone": p.messaging_tone,
                            "pain_points": p.pain_points[:3],
                            "buying_triggers": p.buying_triggers[:2],
                            "preferred_channels": p.preferred_channels[:3],
                        }
                        for p in personas
                    ]
                },
            })

        if icps and not personas:
            warnings.append(
                "Persona generation produced 0 personas — outreach generation was skipped."
            )

        # ------------------------------------------------------------------
        # Stage 8: Outreach Generation (RAG-enriched, parallel per persona)
        # ------------------------------------------------------------------
        if self._on_progress:
            self._on_progress(status="Generating outreach assets...", progress=self._get_stage_progress("outreach_generation"), company_id=str(self._company_id))

        outreach_assets: list[OutreachAsset] = []
        outreach_agent = OutreachAgent()
        outreach_repo = OutreachRepository(self._db)

        async def gen_outreach(persona: BuyerPersona) -> list[OutreachAsset]:
            assets = await outreach_agent.run(
                persona=persona,
                analysis=company_analysis,
                rag_collection=rag_collection,
                stream_cb=self._make_agent_cb("OutreachAgent"),
            )
            for a in assets:
                await outreach_repo.create(
                    persona_id=persona.persona_id,
                    company_id=company_record.id,
                    channel=a.channel,
                    content=a.model_dump(mode="json"),
                )
            return assets

        outreach_tasks = [gen_outreach(p) for p in personas]
        # asyncio.gather with return_exceptions=True: all tasks run in parallel;
        # a failure in one persona's outreach doesn't cancel the others.
        # We distinguish Exception results from list results below.
        outreach_batches = await asyncio.gather(*outreach_tasks, return_exceptions=True)
        for batch in outreach_batches:
            if isinstance(batch, list):
                outreach_assets.extend(batch)
            elif isinstance(batch, Exception):
                msg = f"Outreach error: {batch}"
                logger.error("pipeline.outreach.error", error=str(batch))
                errors.append(msg)
        
        await self._db.commit()

        if personas and not outreach_assets:
            warnings.append("Outreach generation produced 0 assets.")

        # ------------------------------------------------------------------
        # Done
        # ------------------------------------------------------------------
        duration = time.perf_counter() - t0
        logger.info(
            "pipeline.complete",
            company=company_input.company_name,
            competitors=len(competitors),
            gaps=len(gaps),
            icps=len(icps),
            personas=len(personas),
            outreach_assets=len(outreach_assets),
            duration_seconds=round(duration, 2),
            errors=len(errors),
            warnings=len(warnings),
        )

        # Signal the frontend that the entire pipeline has finished.
        if self._stream_cb:
            self._stream_cb({"type": "done", "agent": "pipeline"})

        return PipelineResult(
            company_id=company_record.id,
            company_analysis=company_analysis,
            competitors=competitors,
            social_profiles=social_subjects,
            market_gaps=gaps,
            icps=icps,
            personas=personas,
            outreach_assets=outreach_assets,
            duration_seconds=duration,
            errors=errors,
            warnings=warnings,
        )

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    async def _run_stage(
        self,
        stage_name: str,
        fn,  # callable
        arg,
        errors: list[str],
        *,
        no_arg: bool = False,
    ):
        """Execute a sequential pipeline stage with timeout and error recovery.

        Wraps the agent call in ``asyncio.wait_for`` so a hung LLM or network
        call cannot stall the entire pipeline indefinitely.  On timeout or any
        exception the error is appended to ``errors`` and ``None`` is returned
        — callers fall back to empty lists so downstream stages receive no input
        rather than crashing.

        Args:
            stage_name: Human-readable name used for logging and progress tracking.
            fn:         Async callable to invoke.
            arg:        Single positional argument passed to ``fn`` (ignored when
                        ``no_arg=True``).
            errors:     Mutable list; failure messages are appended here.
            no_arg:     Pass ``True`` when ``fn`` takes no arguments (e.g. lambdas
                        that have already closed over their inputs).

        Returns:
            The return value of ``fn``, or ``None`` on failure/timeout.
        """
        try:
            logger.info("pipeline.stage.start", stage=stage_name)
            if self._on_progress:
                pct = self._get_stage_progress(stage_name)
                self._on_progress(
                    status=f"Executing {stage_name}...",
                    progress=pct,
                    company_id=str(self._company_id) if self._company_id else None
                )

            t = time.perf_counter()
            if no_arg:
                result = await asyncio.wait_for(fn(), timeout=_settings.pipeline_timeout_seconds)
            else:
                result = await asyncio.wait_for(fn(arg), timeout=_settings.pipeline_timeout_seconds)
            logger.info(
                "pipeline.stage.done",
                stage=stage_name,
                elapsed=round(time.perf_counter() - t, 2),
            )
            return result
        except asyncio.TimeoutError:
            msg = f"Stage '{stage_name}' timed out after {_settings.pipeline_timeout_seconds}s"
            logger.error("pipeline.stage.timeout", stage=stage_name)
            errors.append(msg)
            return None
        except Exception as exc:
            msg = f"Stage '{stage_name}' failed: {exc}"
            logger.error("pipeline.stage.error", stage=stage_name, error=str(exc))
            errors.append(msg)
            return None

    def _make_agent_cb(self, agent_name: str) -> Callable | None:
        """Create a stream callback pre-tagged with an agent name.

        Wraps the pipeline-level ``stream_cb`` so each agent's events arrive
        at the frontend with an ``"agent"`` key identifying their source.
        Returns ``None`` when no ``stream_cb`` was provided, letting agents
        skip callback calls cheaply via ``if cb: cb(...)`` guards.

        Example event produced:
            ``{"type": "agent_start", "label": "...", "agent": "WebAgent"}``
        """
        if not self._stream_cb:
            return None

        def cb(event: dict) -> None:
            # Merge agent name into every event dict (spread + override).
            self._stream_cb({**event, "agent": agent_name})

        return cb

    def _get_stage_progress(self, stage_name: str) -> int:
        """Map a stage name to an integer completion percentage (0–100).

        The 10 stages are evenly distributed across 100 %, so each stage
        represents ~10 % of total progress.  Unknown stage names return 0.
        """
        stages = [
            "domain_intelligence",
            "competitor_discovery",
            "web_intelligence",
            "social_intelligence",
            "data_cleaning",
            "gap_analysis",
            "icp_generation",
            "persona_generation",
            "outreach_generation",
            "optimization"
        ]
        try:
            idx = stages.index(stage_name)
            return int(((idx + 1) / len(stages)) * 100)
        except ValueError:
            return 0

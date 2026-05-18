"""Companion Chat API — a conversational agent over pipeline data + app FAQs.

`POST /api/v1/chat` streams an LLM answer (plain-text chunks). The assistant is
grounded with: a static app FAQ, the list of analyzed companies, and — when a
`company_id` is supplied — that company's analysis, competitors, ICPs,
personas, gaps and discovered contacts.
"""

from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.dependencies import DbSession
from app.core.logging import get_logger
from app.db.repositories import (
    CompanyRepository,
    CompetitorRepository,
    ICPRepository,
    MarketGapRepository,
    PersonaRepository,
    SocialContactRepository,
)
from app.services.llm_service import get_llm_service

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = get_logger(__name__)

_FAQ = """\
Sellna is an AI sales-intelligence platform. One 9-agent pipeline turns a
company website into go-to-market intelligence. Pipeline stages, in order:
  1. Domain Resolver   — verifies & enriches the domain
  2. Company Profiler  — industry, market type, positioning
  3. Competitor Hunter — finds direct & adjacent rivals
  4. Web Scraper       — scrapes competitor websites for features & pricing
  5. Social Intelligence — finds social accounts, team members and emails
                           for the company and each competitor
  6. Data Cleaning     — structures the scraped data
  7. Gap Analyst       — maps unmet positioning gaps (RAG)
  8. ICP Generator     — fit-scored ideal customer profiles
  9. Persona Builder + Outreach Composer — buyer personas and outreach copy

Standalone tools: the Web Scraper and Social Scraper pages scrape any URL on
demand. Start a run with the "New analysis" button; live agent logs stream on
the dashboard. Results appear on the Competitors, ICP, Personas and Outreach
pages for the selected company.
"""


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's question")
    history: list[ChatMessage] = Field(default_factory=list)
    company_id: str | None = Field(
        default=None, description="Active company to ground answers in"
    )


async def _build_context(db, company_id: str | None) -> str:
    """Assemble a compact live-data snapshot for the system prompt."""
    parts: list[str] = []
    companies = await CompanyRepository(db).list_all()
    if companies:
        parts.append(
            f"Companies analyzed ({len(companies)}): "
            + ", ".join(c.name for c in companies[:25])
        )
    else:
        parts.append("No companies have been analyzed yet.")

    cid: uuid.UUID | None = None
    if company_id:
        try:
            cid = uuid.UUID(company_id)
        except ValueError:
            cid = None

    if cid:
        company = await CompanyRepository(db).get_by_id(cid)
        if company:
            parts.append(
                f"\nActive company: {company.name} — industry {company.industry}."
            )
            if company.analysis:
                a = company.analysis
                slim = {
                    k: a.get(k)
                    for k in (
                        "market_type",
                        "product_category",
                        "competitive_positioning",
                        "target_segments",
                        "pain_points",
                    )
                    if a.get(k)
                }
                parts.append("Analysis: " + json.dumps(slim, default=str)[:1200])

            comps = await CompetitorRepository(db).get_by_company(cid)
            if comps:
                parts.append(
                    f"Competitors ({len(comps)}): "
                    + ", ".join(c.name for c in comps[:20])
                )
            icps = await ICPRepository(db).get_by_company(cid)
            personas = await PersonaRepository(db).get_by_company(cid)
            gaps = await MarketGapRepository(db).get_by_company(cid)
            parts.append(
                f"ICPs: {len(icps)} · personas: {len(personas)} · "
                f"market gaps: {len(gaps)}."
            )
            contacts = await SocialContactRepository(db).get_by_company(cid)
            emails = [c.value for c in contacts if c.kind == "email"]
            people = [c.value for c in contacts if c.kind == "person"]
            if emails or people:
                parts.append(
                    f"Discovered contacts: {len(emails)} emails, "
                    f"{len(people)} people"
                    + (f" ({', '.join(people[:8])})" if people else "")
                )

    return "\n".join(parts)


@router.post("", summary="Ask the Sellna companion a question (streamed reply)")
async def chat(payload: ChatRequest, db: DbSession) -> StreamingResponse:
    """Stream an LLM answer grounded in app FAQs + live pipeline data."""
    context = await _build_context(db, payload.company_id)
    system = (
        "You are Sellna's companion — a concise, friendly sales-intelligence "
        "assistant inside the Sellna app. Answer questions about the user's "
        "analyzed companies, competitors, the agent pipeline, the scrapers, and "
        "how to use the app. Ground answers in the live data below; if the data "
        "doesn't cover it, say so plainly. Keep replies short and practical — "
        "a few sentences or a tight list.\n\n"
        f"=== APP FAQ ===\n{_FAQ}\n\n=== LIVE DATA ===\n{context}"
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for m in payload.history[-8:]:
        if m.role in ("user", "assistant") and m.content:
            messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": payload.message})

    logger.info("chat.request", company_id=payload.company_id, history=len(messages))
    llm = get_llm_service()

    async def token_stream():
        queue: asyncio.Queue = asyncio.Queue()
        sentinel = object()

        def on_token(tok: str) -> None:
            queue.put_nowait(tok)

        async def run() -> None:
            try:
                await llm.chat(messages, on_token=on_token, max_tokens=700)
            except Exception as exc:  # surface a readable message to the client
                logger.error("chat.error", error=str(exc))
                queue.put_nowait(f"\n\n_Sorry — the assistant hit an error: {exc}_")
            finally:
                queue.put_nowait(sentinel)

        task = asyncio.create_task(run())
        try:
            while True:
                item = await queue.get()
                if item is sentinel:
                    break
                yield item
        finally:
            await task

    return StreamingResponse(
        token_stream(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

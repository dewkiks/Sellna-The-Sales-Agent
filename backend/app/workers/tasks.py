"""Celery tasks — long-running Sales AI operations.

Why asyncio.run() is needed
---------------------------
Celery worker processes are purely synchronous — they do not run an event loop.
The Sales AI pipeline, however, is entirely built on async/await (SQLAlchemy
async sessions, async HTTP calls, async LLM streaming).

The bridge is ``asyncio.run(_run())``: this call blocks the synchronous Celery
worker thread, creates a fresh event loop, runs the async pipeline to
completion, tears down the loop, and returns the result to Celery.  This means
each Celery task slot can run one full pipeline at a time.

Session handling inside tasks
------------------------------
The FastAPI ``get_db`` dependency cannot be used here because there is no
HTTP request context.  Instead, ``_get_session()`` creates a fresh async engine
and session factory local to the worker process.  The async ``with`` block in
each ``_run()`` closure ensures the session is always closed even on error.

Task state reporting
---------------------
``self.update_state(state="RUNNING", meta={...})`` writes progress metadata
into Redis.  The FastAPI endpoint ``/pipeline/status/{job_id}`` calls
``AsyncResult(job_id).info`` to surface this metadata to the frontend.

Tasks:
  run_pipeline_task   — full 9-agent pipeline (domain → outreach)
  run_outreach_task   — generate outreach copy for a single persona

Results are stored in Redis (via the Celery result backend) and retrievable
by job_id from the /pipeline/status/{job_id} endpoint.
"""

from __future__ import annotations

import asyncio
import traceback

from celery import current_task
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)
_s = get_settings()


def _get_session() -> AsyncSession:
    """Create a fresh async DB session inside the Celery worker process.

    Each task invocation creates its own engine and session factory rather than
    sharing a global pool.  This is intentional: Celery workers may be on
    different machines, and SQLAlchemy connection pools are not fork-safe.
    ``pool_pre_ping=True`` discards stale connections left over from a fork.
    ``expire_on_commit=False`` keeps ORM objects accessible after commit
    without triggering lazy-load errors.

    Returns:
        An open AsyncSession that must be used as an async context manager.
    """
    engine = create_async_engine(_s.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return factory()


# ---------------------------------------------------------------------------
# Task: Full Pipeline
# ---------------------------------------------------------------------------


@celery_app.task(
    name="sales_ai.run_pipeline",
    bind=True,          # ``bind=True`` gives the task access to ``self`` (current task instance)
    max_retries=1,      # override the global task_max_retries=2 — pipeline is expensive
    soft_time_limit=3600,  # 60-min SIGTERM warning (gives code a chance to clean up)
    time_limit=3800,       # hard SIGKILL — absolute ceiling
)
def run_pipeline_task(
    self,
    company_input_dict: dict,
    render_js: bool = False,
    num_icps: int = 1,
    num_personas_per_icp: int = 1,
) -> dict:
    """Run the full Sales AI pipeline as a background Celery task.

    Celery serialises the CompanyInput as a plain dict (``company_input_dict``)
    because complex Python objects cannot cross the Redis message boundary.
    Inside ``_run()`` it is re-hydrated into a ``CompanyInput`` Pydantic model.

    Args:
        company_input_dict:   Serialised CompanyInput (from ``.model_dump()``).
        render_js:            Whether to use Playwright for JS-heavy pages.
        num_icps:             Number of Ideal Customer Profiles to generate.
        num_personas_per_icp: Personas to generate per ICP.

    Returns:
        A dict representation of ``PipelineResult`` stored in Redis.
        Retrieve it via ``AsyncResult(task_id).result``.
    """
    # Import here (not at module top) to avoid loading the pipeline at worker
    # startup time — keeps worker boot fast and avoids circular imports.
    from app.pipelines.sales_pipeline import SalesPipeline
    from app.schemas.company import CompanyInput

    logger.info("celery.pipeline.start", task_id=self.request.id)

    # Signal the broker that the task has started (visible via /pipeline/status)
    self.update_state(state="RUNNING", meta={"status": "Pipeline started", "progress": 0})

    async def _run():
        def on_prog(status, progress, company_id=None):
            """Progress callback passed into SalesPipeline.

            The pipeline calls this after each agent stage completes,
            allowing Celery to update the task state in Redis so the
            API can relay progress to the frontend.
            """
            logger.info("pipeline.progress", status=status, progress=progress, company_id=company_id)
            meta = {"status": status, "progress": progress}
            if company_id:
                meta["company_id"] = company_id
            # Write progress into Redis — polled by the status endpoint.
            self.update_state(state="RUNNING", meta=meta)

        async with _get_session() as session:
            try:
                payload = CompanyInput(**company_input_dict)
                pipeline = SalesPipeline(
                    db=session,
                    render_js=render_js,
                    num_icps=num_icps,
                    num_personas_per_icp=num_personas_per_icp,
                    on_progress=on_prog,
                )
                res = await pipeline.run(payload)
                await session.commit()
                return res
            except Exception as e:
                await session.rollback()
                logger.error(f"Pipeline DB session failed: {e}")
                raise

    try:
        # asyncio.run() is the bridge between sync Celery and the async pipeline.
        result = asyncio.run(_run())
        logger.info(
            "celery.pipeline.complete",
            task_id=self.request.id,
            duration=result.duration_seconds,
            errors=len(result.errors),
        )
        return result.to_dict()  # Pydantic model → plain dict for Redis storage
    except Exception as exc:
        logger.error(
            "celery.pipeline.failed",
            task_id=self.request.id,
            error=str(exc),
            traceback=traceback.format_exc(),
        )
        # self.retry() re-raises a Retry exception that Celery intercepts;
        # the task is re-queued with a 30-second delay before the next attempt.
        raise self.retry(exc=exc, countdown=30)  # retry once after 30s


# ---------------------------------------------------------------------------
# Task: Single Outreach Generation
# ---------------------------------------------------------------------------


@celery_app.task(
    name="sales_ai.run_outreach",
    bind=True,
    max_retries=2,          # outreach is cheaper — up to 2 retries are acceptable
    soft_time_limit=1800,   # 30-min soft kill
    time_limit=2000,        # hard kill
)
def run_outreach_task(
    self,
    company_id: str,
    persona_id: str,
    channels: list[str] | None = None,
) -> dict:
    """Generate outreach copy for a single buyer persona as a background task.

    Rather than re-running the whole pipeline, this task fetches an existing
    company record and persona from the DB and runs only the OutreachAgent.

    Args:
        company_id: UUID of the company record in PostgreSQL.
        persona_id: UUID of the target BuyerPersona record.
        channels:   Optional list of channels to generate copy for
                    (e.g. ["email", "linkedin"]).  Defaults to all channels
                    if None.

    Returns:
        A dict with key "assets" containing a list of serialised OutreachAsset
        dicts, stored in Redis under this task's ID.
    """
    # Lazy imports keep worker startup fast and avoid circular references.
    from app.agents import OutreachAgent
    from app.db.repositories import CompanyRepository, PersonaRepository
    from app.schemas.company import CompanyAnalysis, CompanyInput
    from app.schemas.persona import BuyerPersona

    logger.info("celery.outreach.start", task_id=self.request.id, persona_id=persona_id)

    async def _run():
        async with _get_session() as session:
            # Reconstruct CompanyInput and CompanyAnalysis from stored JSON.
            company_repo = CompanyRepository(session)
            record = await company_repo.get_by_id(company_id)
            inp = CompanyInput(**record.input_data)
            analysis = CompanyAnalysis(**{**record.analysis, "raw_input": inp})

            # Locate the target persona among all personas for this company.
            persona_repo = PersonaRepository(session)
            persona_records = await persona_repo.get_by_company(company_id)
            target = next((r for r in persona_records if str(r.id) == persona_id), None)
            if not target:
                raise ValueError(f"Persona {persona_id} not found")

            persona = BuyerPersona(**target.persona_data)
            agent = OutreachAgent()
            assets = await agent.run(
                persona=persona,
                analysis=analysis,
                channels=channels,
                rag_collection=f"gap_{company_id}",  # Qdrant collection for RAG context
            )
            # Serialise Pydantic models to plain dicts so Celery can JSON-encode them.
            return {"assets": [a.model_dump(mode="json") for a in assets]}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("celery.outreach.failed", task_id=self.request.id, error=str(exc))
        raise self.retry(exc=exc, countdown=10)  # retry with a 10-second delay

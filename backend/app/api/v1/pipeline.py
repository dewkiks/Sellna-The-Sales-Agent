"""Pipeline Orchestration API — async-queued and synchronous execution modes.

This is the primary entry point used by the React frontend.  A single POST
to /pipeline/run kicks off the full 9-agent pipeline and returns a job_id
immediately so the UI can begin polling / streaming without blocking.

Endpoints:
  POST /pipeline/run           — submit pipeline (Celery if available,
                                 else FastAPI BackgroundTasks fallback).
                                 Returns job_id immediately (HTTP 202).
  GET  /pipeline/status/{id}   — poll job state + progress percentage.
  GET  /pipeline/stream/{id}   — Server-Sent Events (SSE) stream of
                                 token-by-token LLM output and agent
                                 lifecycle events.
  GET  /pipeline/result/{id}   — fetch the full result of a SUCCESS job.
  POST /pipeline/abort/{id}    — cancel a running or queued job.

Execution mode decision (POST /run):
  1. If a live Celery worker is detected (via inspect().ping()), the job
     is dispatched to the Celery queue and the Celery task id is used as
     the job_id.
  2. If no worker is reachable, FastAPI's BackgroundTasks are used instead.
     Job state lives in the module-level `_LOCAL_JOBS` dict and the SSE
     stream queue is managed by `stream_manager`.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

from app.core.logging import get_logger
from app.core.stream_manager import stream_manager
from app.schemas.company import CompanyInput

router = APIRouter(prefix="/pipeline", tags=["Pipeline Orchestration"])
logger = get_logger(__name__)

# ---- In-memory job registry (BackgroundTasks fallback only) ----
# When Celery is unavailable, job state (state, progress, result, error)
# is stored here keyed by job_id (UUID string).  This dict is intentionally
# NOT shared across processes or restarts — it is a development convenience,
# not a production-grade store.  In production, Celery + Redis/RabbitMQ
# store task state durably and this dict is never written.
_LOCAL_JOBS: Dict[str, Dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Async (Internal Background Task) — modified for dual celery/fallback use
# ---------------------------------------------------------------------------


@router.post(
    "/run",
    summary="Submit pipeline to Celery queue (async)",
    description=(
        "Submits the full 8-agent pipeline as a background Celery task. "
        "Returns a **job_id** immediately. Poll `/pipeline/status/{job_id}` to track progress."
    ),
    status_code=202,
)
async def run_pipeline_async(
    payload: CompanyInput,
    background_tasks: BackgroundTasks,
    render_js: bool = False,
    num_icps: int = 3,
    num_personas_per_icp: int = 2,
) -> dict:
    """POST /pipeline/run — primary pipeline submission endpoint.

    Accepts a CompanyInput payload and returns HTTP 202 Accepted with a
    `job_id` immediately.  The pipeline runs asynchronously; the caller
    must poll GET /pipeline/status/{job_id} or subscribe to the SSE
    stream at GET /pipeline/stream/{job_id} for progress.

    Query params:
      render_js           (bool, default False) — use Playwright for scraping.
      num_icps            (int,  default 3)     — ICPs to generate.
      num_personas_per_icp (int, default 2)     — personas per ICP.

    Execution path (chosen at runtime, transparent to the caller):
      - Celery path  : job dispatched to a worker queue; job_id = Celery task id.
      - Fallback path: job runs in a FastAPI BackgroundTask; job_id = local UUID.
                       SSE stream and _LOCAL_JOBS are both pre-created before
                       returning so the frontend can connect the EventSource
                       without a race condition.
    """
    job_id = str(uuid.uuid4())

    # ---- Detect Celery worker availability ----
    # We do NOT just call apply_async blindly because that always succeeds —
    # tasks silently queue forever with no worker to consume them.
    # inspect().ping() asks live workers to respond; an empty dict means
    # no workers are running.  timeout=1 keeps the request fast.
    _celery_worker_available = False
    try:
        from app.workers.celery_app import celery_app as _celery_app
        # Returns {worker_id: {"ok": "pong"}} for each live worker
        active = _celery_app.control.inspect(timeout=1).ping() or {}
        _celery_worker_available = bool(active)
    except Exception:
        # Celery broker not reachable at all — fall through to BackgroundTasks
        _celery_worker_available = False

    # ---- Path 1: Celery worker is alive ----
    if _celery_worker_available:
        try:
            from app.workers.tasks import run_pipeline_task
            task = run_pipeline_task.apply_async(
                kwargs=dict(
                    company_input_dict=payload.model_dump(mode="json"),
                    render_js=render_js,
                    num_icps=num_icps,
                    num_personas_per_icp=num_personas_per_icp,
                )
            )
            job_id = task.id
            logger.info("api.pipeline.queued", company=payload.company_name, job_id=job_id)
            return {
                "job_id": job_id,
                "status": "queued",
                "company": payload.company_name,
                "poll_url": f"/api/v1/pipeline/status/{job_id}",
                "message": "Pipeline submitted. Poll poll_url for updates.",
            }
        except Exception as exc:
            logger.warning(f"Celery task dispatch failed ({exc}), falling back.")

    # ---- Path 2: BackgroundTasks fallback ----
    logger.warning("No Celery worker detected — using in-memory BackgroundTasks fallback.")

    # IMPORTANT: Register the job AND create the stream queue BEFORE adding
    # the background task.  The frontend opens the EventSource immediately
    # after receiving the job_id in the 202 response.  If the asyncio queue
    # in stream_manager doesn't exist yet when subscribe() is called, it
    # returns an error event and the SSE connection closes — meaning the UI
    # misses every agent event.  Pre-creating both prevents this race.
    _LOCAL_JOBS[job_id] = {
        "state": "RUNNING",
        "progress": 2,
        "status_msg": "Starting pipeline...",
        "result": None,
        "error": None,
        "company_id": None,
    }
    stream_manager.create(job_id)

    # Progress callback — SalesPipeline calls this after each agent stage
    # to update the shared job dict; GET /status reads from that same dict.
    def make_progress_cb(jid: str):
        def on_progress(status: str, progress: int, company_id: str | None = None):
            _LOCAL_JOBS[jid]["status_msg"] = status
            _LOCAL_JOBS[jid]["progress"] = progress
            if company_id:
                _LOCAL_JOBS[jid]["company_id"] = company_id
        return on_progress

    # background_runner is the coroutine FastAPI's BackgroundTasks will execute
    # after the HTTP 202 response has been sent to the client.
    async def background_runner(jid: str, data: CompanyInput):

        # stream_cb bridges SalesPipeline's event emitter to stream_manager,
        # which fans out events to all active SSE subscribers for this job.
        def pipeline_stream_cb(event: dict) -> None:
            stream_manager.publish(jid, event)

        try:
            from app.pipelines.sales_pipeline import SalesPipeline
            from app.db.postgres import async_session_factory

            async with async_session_factory() as session:
                _LOCAL_JOBS[jid]["status_msg"] = "Processing stages..."
                pipeline = SalesPipeline(
                    db=session,
                    render_js=render_js,
                    num_icps=num_icps,
                    num_personas_per_icp=num_personas_per_icp,
                    on_progress=make_progress_cb(jid),
                    stream_cb=pipeline_stream_cb,
                )
                res = await pipeline.run(data)
                await session.commit()

                _LOCAL_JOBS[jid]["state"] = "SUCCESS"
                _LOCAL_JOBS[jid]["progress"] = 100
                _LOCAL_JOBS[jid]["result"] = res.to_dict()
                _LOCAL_JOBS[jid]["status_msg"] = "Done"
                if not _LOCAL_JOBS[jid]["company_id"] and res.company_id:
                    _LOCAL_JOBS[jid]["company_id"] = str(res.company_id)
        except Exception as e:
            _LOCAL_JOBS[jid]["state"] = "FAILURE"
            _LOCAL_JOBS[jid]["error"] = str(e)
            _LOCAL_JOBS[jid]["status_msg"] = "Failed"
            stream_manager.publish(jid, {"type": "done", "agent": "pipeline"})
            logger.error(f"Fallback pipeline failed: {e}")

    # Fire background task
    background_tasks.add_task(background_runner, job_id, payload)

    return {
        "job_id": job_id,
        "status": "queued",
        "company": payload.company_name,
        "poll_url": f"/api/v1/pipeline/status/{job_id}",
        "message": "Pipeline submitted. Poll poll_url for updates.",
    }




@router.get(
    "/status/{job_id}",
    summary="Check pipeline job status",
)
async def pipeline_status(job_id: str) -> dict:
    """GET /pipeline/status/{job_id} — Poll job state and progress.

    Checks both backends in order:
      1. _LOCAL_JOBS (BackgroundTasks fallback) — checked first because
         local job_ids never collide with Celery task ids (different UUID
         sources), so a miss here is definitive for local jobs.
      2. Celery AsyncResult — used when Celery dispatched the job.

    Response shape varies by state:
      RUNNING : includes `progress` (0–100) and `status_msg`.
      SUCCESS : includes `result_url` pointing to GET /pipeline/result.
      FAILURE : includes `error` string.
      PENDING : job is queued but not yet picked up by a worker.

    Raises 503 if the Celery backend is unreachable (only when falling
    back to Celery and the broker is down).
    """
    # ---- Check local in-memory jobs first ----
    if job_id in _LOCAL_JOBS:
        local_job = _LOCAL_JOBS[job_id]
        state = local_job["state"]
        response: dict = {"job_id": job_id, "state": state}

        if state == "SUCCESS":
            response["result_url"] = f"/api/v1/pipeline/result/{job_id}"
            response["message"] = "Pipeline complete. Fetch result at result_url."
            response["progress"] = 100
            if local_job.get("company_id"):
                response["company_id"] = local_job["company_id"]
        elif state == "FAILURE":
            response["error"] = local_job.get("error")
        else:
            response["progress"] = local_job.get("progress", 2)
            response["status_msg"] = local_job.get("status_msg", "Processing...")
            if local_job.get("company_id"):
                response["company_id"] = local_job["company_id"]

        return response

    # ---- Fallback: query Celery task state ----
    try:
        from app.workers.celery_app import celery_app

        task = celery_app.AsyncResult(job_id)
        state = task.state  # PENDING | STARTED | PROGRESS | SUCCESS | FAILURE | RETRY
        logger.info("api.pipeline.status", job_id=job_id, state=state, info=str(task.info)[:200])

        response: dict = {"job_id": job_id, "state": state}

        if state == "SUCCESS":
            response["result_url"] = f"/api/v1/pipeline/result/{job_id}"
            response["message"] = "Pipeline complete. Fetch result at result_url."
        elif state == "FAILURE":
            response["error"] = str(task.result)
        elif state in ("RUNNING", "STARTED", "PROGRESS"):
            meta = task.info or {}
            response["progress"] = meta.get("progress", 0)
            response["status_msg"] = meta.get("status", "Processing...")
            if "company_id" in meta:
                response["company_id"] = meta["company_id"]
        elif state == "PENDING":
            response["message"] = "Job is queued, waiting for a worker."

        return response
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Cannot connect to job backend: {exc}")


@router.post(
    "/abort/{job_id}",
    summary="Abort a running pipeline job",
)
async def abort_pipeline(job_id: str) -> dict:
    """POST /pipeline/abort/{job_id}

    Cancels a running or queued pipeline job.

    Local jobs (_LOCAL_JOBS): marked FAILURE immediately; the background
    coroutine is NOT forcefully killed (Python async tasks can't be
    externally cancelled this way), but the state change prevents result
    consumers from acting on any output.

    Celery jobs: revoke() + terminate=True sends SIGTERM to the worker
    process running the task.
    """
    if job_id in _LOCAL_JOBS:
        _LOCAL_JOBS[job_id]["state"] = "FAILURE"
        _LOCAL_JOBS[job_id]["error"] = "Aborted by user"
        return {"status": "success", "message": f"Local job {job_id} marked as failed"}

    try:
        from app.workers.celery_app import celery_app
        task = celery_app.AsyncResult(job_id)
        task.revoke(terminate=True)
        logger.info("api.pipeline.abort", job_id=job_id)
        return {"status": "success", "message": f"Job {job_id} revoked"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to abort job: {exc}")


@router.get(
    "/stream/{job_id}",
    summary="SSE stream of LLM tokens and agent events for a pipeline run",
)
async def stream_pipeline(job_id: str):
    """GET /pipeline/stream/{job_id} — Server-Sent Events (SSE) endpoint.

    Opens a persistent HTTP connection that pushes events as they are
    produced by the running pipeline.  The React frontend uses this to
    animate the "agent thinking" UI in real time.

    Event format (each chunk):
      data: {"type": "token"|"start"|"done", "agent": "<name>", ...}\\n\\n

    How it works:
      - stream_manager.subscribe(job_id) returns an async generator that
        yields events from an asyncio.Queue dedicated to this job.
      - SalesPipeline calls pipeline_stream_cb (set up in background_runner)
        which calls stream_manager.publish(job_id, event) to enqueue events.
      - Each published event is JSON-serialised and sent as an SSE data line.

    Response headers:
      Cache-Control: no-cache  — prevent proxies from buffering the stream.
      X-Accel-Buffering: no    — disable Nginx proxy buffering for SSE.

    The stream ends when the pipeline publishes a {"type": "done"} event or
    when the client disconnects.
    """

    async def event_generator():
        # Consume events from the in-memory asyncio queue for this job
        async for event in stream_manager.subscribe(job_id):
            # SSE wire format: "data: <json>\\n\\n"
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",    # don't let proxies cache the stream
            "X-Accel-Buffering": "no",      # disable Nginx buffering
        },
    )


@router.get(
    "/result/{job_id}",
    summary="Fetch completed pipeline result",
)
async def pipeline_result(job_id: str) -> dict:
    """GET /pipeline/result/{job_id}

    Returns the full pipeline output once the job has reached SUCCESS state.
    Raises 404 if the job is still running, failed, or not found.
    Raises 503 if the Celery backend is unreachable.

    The caller should only call this after GET /pipeline/status returns
    state == "SUCCESS" and provides a `result_url`.
    """
    # ---- Check local in-memory jobs first ----
    if job_id in _LOCAL_JOBS:
        local_job = _LOCAL_JOBS[job_id]
        if local_job["state"] != "SUCCESS":
            raise HTTPException(
                status_code=404,
                detail=f"Result not ready. Current state: {local_job['state']}",
            )
        return local_job["result"]
        
    # ---- Fallback: retrieve from Celery result backend ----
    try:
        from app.workers.celery_app import celery_app

        task = celery_app.AsyncResult(job_id)
        if task.state != "SUCCESS":
            raise HTTPException(
                status_code=404,
                detail=f"Result not ready. Current state: {task.state}",
            )
        return task.result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

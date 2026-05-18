"""Per-job streaming event manager using asyncio queues.

How live pipeline progress reaches the browser
-----------------------------------------------
Sellna.ai streams pipeline progress to the frontend via Server-Sent Events
(SSE).  The flow is:

  1. The pipeline API endpoint creates a job (job_id = UUID) and calls
     ``stream_manager.create(job_id)`` to allocate a dedicated asyncio.Queue.
  2. Each of the 9 AI agents receives a callback (built by ``make_stream_cb``)
     that calls ``stream_manager.publish(job_id, event)`` whenever the LLM
     produces a token or an agent completes a stage.
  3. The SSE endpoint opens an HTTP response that stays open (EventSource on
     the browser side) and calls ``stream_manager.subscribe(job_id)``.  This
     async generator pulls events off the queue one by one and formats them as
     SSE ``data:`` lines.
  4. When the pipeline finishes it publishes ``{"type": "done"}``; the
     generator sees this, stops yielding, and the HTTP response closes.
  5. ``stream_manager.cleanup(job_id)`` removes the queue from memory.

Design choices:
  - asyncio.Queue (not threading.Queue) because the whole server is async.
  - maxsize=4000 prevents unbounded memory use if the client disconnects.
  - QueueFull events are silently dropped — the client missing a token is
    better than crashing the agent.
  - A 25-second timeout on ``q.get()`` sends a ``{"type": "heartbeat"}``
    to keep the HTTP connection alive through proxies that close idle connections.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator


class StreamManager:
    """Singleton that holds one asyncio.Queue per active pipeline job.

    The class-level dict ``_queues`` is shared across all instances, making
    this effectively a singleton — any code that imports ``stream_manager``
    (the module-level instance below) shares the same underlying dict.

    Thread-safety note: asyncio.Queue is designed for use within a single
    event loop.  Do NOT call publish() from a different thread (e.g. a Celery
    worker); use a thread-safe bridge (asyncio.run_coroutine_threadsafe) if
    needed.
    """

    # Class-level dict: job_id (str UUID) → asyncio.Queue
    _queues: dict[str, asyncio.Queue] = {}

    def create(self, job_id: str) -> None:
        """Allocate a new bounded queue for a pipeline job.

        Args:
            job_id: Unique identifier (UUID string) for the pipeline run.
                    Must be called before any agents publish events.
        """
        # maxsize=4000 caps memory use; events beyond this limit are dropped.
        self._queues[job_id] = asyncio.Queue(maxsize=4000)

    def publish(self, job_id: str, event: dict) -> None:
        """Push an event dict into the job's queue without blocking.

        Called by agent callbacks from within an async context.  Uses
        put_nowait() (non-blocking) so agent execution is never stalled by
        a slow or disconnected SSE client.

        Args:
            job_id: The pipeline run whose queue should receive the event.
            event:  Arbitrary dict — e.g. {"type": "token", "text": "Hello"}.
        """
        q = self._queues.get(job_id)
        if q:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # drop silently — client is too slow; prefer throughput over completeness

    async def subscribe(self, job_id: str) -> AsyncGenerator[dict, None]:
        """Async generator consumed by the SSE endpoint.

        Yields event dicts one at a time.  Sends a heartbeat every 25 seconds
        if no event arrives, to prevent proxies from closing the idle connection.
        Stops automatically when it yields a ``{"type": "done"}`` event.

        Args:
            job_id: The pipeline run to listen to.

        Yields:
            Event dicts pushed by agents, or ``{"type": "heartbeat"}`` pings.
        """
        q = self._queues.get(job_id)
        if not q:
            # Job unknown — this can happen if the client connects after cleanup.
            yield {"type": "error", "message": "Job not found or already finished"}
            return

        while True:
            try:
                # Block until an event is available, but time out after 25 s.
                event = await asyncio.wait_for(q.get(), timeout=25.0)
                yield event
                if event.get("type") == "done":
                    break  # pipeline finished — close the generator
            except asyncio.TimeoutError:
                # No event in 25 s — send a no-op ping to keep the TCP connection alive.
                yield {"type": "heartbeat"}

    def cleanup(self, job_id: str) -> None:
        """Remove the queue for a completed or cancelled job.

        Should be called after the SSE subscription ends to avoid memory leaks.

        Args:
            job_id: The job whose queue should be discarded.
        """
        self._queues.pop(job_id, None)


# Module-level singleton — import and use this object everywhere.
# Because _queues is a class-level attribute, all imports share the same state.
stream_manager = StreamManager()


def make_stream_cb(job_id: str, agent_name: str):
    """Build a synchronous callback that stamps events with the agent name.

    The pipeline passes this callback into each agent so agents don't need
    to know about job_id or StreamManager directly.  Agents simply call
    ``cb({"type": "token", "text": chunk})`` and the callback handles routing.

    Args:
        job_id:     The pipeline run this callback belongs to.
        agent_name: Name of the agent (e.g. "DomainAgent") to tag each event.

    Returns:
        A synchronous callable ``cb(event: dict) -> None``.
    """

    def cb(event: dict) -> None:
        # Merge the incoming event with the agent tag, then enqueue non-blocking.
        stream_manager.publish(job_id, {**event, "agent": agent_name})

    return cb

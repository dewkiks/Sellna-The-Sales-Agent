"""Server-side accumulator for a pipeline run's live agent stream.

During a run the pipeline emits stream events one at a time — ``agent_start``,
``token``, ``reasoning``, ``scrape_tick``, ``agent_done`` and a final ``done``.
``RunRecorder`` folds those events into an aggregated per-agent snapshot — the
same shape the frontend renders — so the live-run view can be persisted to the
database and restored after a page refresh.

This mirrors the frontend store's ``applyStreamEvent`` reducer; keep the two in
sync if the stream-event schema changes. The heavy per-agent ``result`` payload
is intentionally NOT recorded — it is not shown in the run view and would only
bloat the stored snapshot.
"""

from __future__ import annotations

from typing import Any


class RunRecorder:
    """Folds pipeline stream events into a persistable per-agent snapshot."""

    def __init__(self) -> None:
        self.agents: list[dict[str, Any]] = []
        self.active_agent: str | None = None
        self.done: bool = False

    def _agent(self, name: str) -> dict[str, Any] | None:
        """Return the accumulated record for ``name``, or None if unseen."""
        for agent in self.agents:
            if agent["name"] == name:
                return agent
        return None

    def _ensure(self, name: str, label: str | None) -> dict[str, Any]:
        """Return the record for ``name``, creating a blank one if needed."""
        record = self._agent(name)
        if record is None:
            record = {
                "name": name,
                "label": label or name,
                "status": "thinking",
                "tokens": "",
                "reasoning": "",
            }
            self.agents.append(record)
        return record

    def apply(self, event: dict) -> None:
        """Fold one stream event into the accumulated state."""
        etype = event.get("type")

        # The pipeline-level "done" event closes the run.
        if etype == "done":
            self.done = True
            self.active_agent = None
            return

        agent = event.get("agent")
        # Heartbeats and the pipeline-level tag carry no per-agent data.
        if not agent or agent == "pipeline":
            return

        if etype == "agent_start":
            self.active_agent = agent
            self._ensure(agent, event.get("label"))
            return

        # token / reasoning / scrape_tick / agent_done — create the record
        # lazily in case an event arrives before its agent_start.
        record = self._ensure(agent, event.get("label"))

        if etype == "token":
            record["tokens"] += event.get("content") or ""
        elif etype == "reasoning":
            record["reasoning"] += event.get("content") or ""
        elif etype == "scrape_tick":
            record["scrapeCount"] = event.get("count")
            record["scrapeTotal"] = event.get("total")
            url = event.get("url")
            if url:
                sites = record.setdefault("scrapeSites", [])
                if url not in sites:
                    sites.append(url)
        elif etype == "agent_done":
            record["status"] = "done"
            if event.get("summary") is not None:
                record["summary"] = event.get("summary")
            self.active_agent = None

    def snapshot(self) -> dict[str, Any]:
        """Return the current accumulated state as a plain JSON-able dict."""
        return {
            "agents": self.agents,
            "active_agent": self.active_agent,
            "done": self.done,
        }

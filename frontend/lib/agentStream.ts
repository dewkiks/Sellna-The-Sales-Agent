
/**
 * Persistent agent-stream session.
 *
 * The pipeline's live execution logs are streamed over SSE. Previously the
 * EventSource lived inside a React hook, so navigating away (or refreshing)
 * unmounted the hook, closed the socket and discarded every captured log.
 *
 * This module owns the EventSource as a module-level singleton — it is NOT
 * tied to any component lifecycle. Captured events are written into the
 * Zustand pipeline store, which persists them to localStorage. Result:
 *   - navigating between sections keeps the socket open and the logs intact;
 *   - refreshing the page restores the logs and reconnects if the run is
 *     still in progress.
 */

import { API_ROOT } from "@/lib/api";
import { usePipelineStore } from "@/store/pipelineStore";

export type StreamEventType =
  | "agent_start"
  | "agent_done"
  | "token"
  | "reasoning"
  | "scrape_tick"
  | "heartbeat"
  | "done"
  | "error";

export interface StreamEvent {
  type: StreamEventType;
  agent?: string;
  label?: string;
  summary?: string;
  content?: string;
  message?: string;
  url?: string;
  count?: number;
  total?: number;
  result?: unknown;
}

export interface AgentState {
  name: string;
  label: string;
  status: "thinking" | "done";
  summary?: string;
  result?: unknown;
  tokens: string;
  reasoning: string;
  scrapeCount?: number;
  scrapeTotal?: number;
  scrapeUrl?: string;
  /** Every site URL the scraper has finished, in completion order. */
  scrapeSites?: string[];
}

/* ---- singleton socket state (module scope, survives component unmounts) ---- */
let es: EventSource | null = null;
let connectedJobId: string | null = null;

function closeSocket() {
  if (es) {
    es.close();
    es = null;
  }
  connectedJobId = null;
}

export const agentStream = {
  /**
   * Make sure the live SSE socket is open for `jobId`. Safe to call on every
   * render of the live-run page — it is a no-op when already connected.
   */
  ensureConnected(jobId: string | null) {
    if (typeof window === "undefined") return;

    if (!jobId) {
      closeSocket();
      return;
    }
    if (connectedJobId === jobId && es) return; // already streaming this job

    const store = usePipelineStore.getState();

    if (store.streamJobId !== jobId) {
      // A different (new) run — start the log slice fresh.
      store.streamReset(jobId);
    } else if (store.streamDone) {
      // This job already finished; the persisted logs are complete.
      return;
    }

    closeSocket();
    connectedJobId = jobId;

    const source = new EventSource(`${API_ROOT}/pipeline/stream/${jobId}`);
    es = source;

    source.onmessage = (ev) => {
      let event: StreamEvent;
      try {
        event = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (event.type === "heartbeat") return;

      const s = usePipelineStore.getState();
      if (event.type === "done") {
        s.setStreamDone(true);
        closeSocket();
        return;
      }
      if (event.type === "error") {
        // Job not found / already cleaned up — keep whatever was captured.
        closeSocket();
        return;
      }
      s.applyStreamEvent(event);
    };

    source.onerror = () => {
      // The browser auto-reconnects EventSource on transient failures; only
      // tear down once it has permanently given up.
      if (source.readyState === EventSource.CLOSED && es === source) {
        closeSocket();
      }
    };
  },

  /** Explicitly drop the socket (e.g. when a run is aborted). */
  disconnect() {
    closeSocket();
  },
};

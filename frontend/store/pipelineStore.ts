import { create } from "zustand";
import { persist, createJSONStorage, type StateStorage } from "zustand/middleware";
import type {
  PipelineResultResponse,
  PipelineStatusResponse,
  PipelinePayload,
  SocialScrapeResult,
  WebScrapeResult,
} from "@/lib/api";
import type { AgentState, StreamEvent } from "@/lib/agentStream";

interface PipelineStore {
  jobId: string | null;
  setJobId: (id: string | null) => void;

  companyId: string | null;
  setCompanyId: (id: string | null) => void;

  companyName: string | null;
  setCompanyName: (name: string | null) => void;

  /** Form draft carried between the company wizard steps. */
  draft: Partial<PipelinePayload> & { website?: string };
  setDraft: (d: Partial<PipelinePayload> & { website?: string }) => void;

  result: PipelineResultResponse | null;
  setResult: (result: PipelineResultResponse | null) => void;

  status: PipelineStatusResponse | null;
  setStatus: (status: PipelineStatusResponse | null) => void;

  isRunning: boolean;
  setIsRunning: (running: boolean) => void;

  /* ---- live agent-stream session (persisted so logs survive nav/refresh) ---- */
  /** Which job the captured logs below belong to. */
  streamJobId: string | null;
  /** Per-agent captured execution logs (tokens, reasoning, scrape progress). */
  streamAgents: AgentState[];
  /** Name of the agent currently streaming, if any. */
  streamActiveAgent: string | null;
  /** True once the run has finished streaming. */
  streamDone: boolean;
  /** Begin a fresh capture for a new run. */
  streamReset: (jobId: string) => void;
  /** Fold one SSE event into the captured logs. */
  applyStreamEvent: (event: StreamEvent) => void;
  /** Mark the stream finished (also clears the active agent). */
  setStreamDone: (done: boolean) => void;
  /** Restore the captured stream from a server-persisted snapshot. */
  hydrateStream: (
    jobId: string,
    agents: AgentState[],
    activeAgent: string | null,
    done: boolean,
  ) => void;

  /* ---- scraper-tool results — persisted so they survive navigation/refresh ---- */
  socialScrape: { url: string; result: SocialScrapeResult | null };
  setSocialScrape: (s: { url: string; result: SocialScrapeResult | null }) => void;
  webScrape: { url: string; result: WebScrapeResult | null };
  setWebScrape: (s: { url: string; result: WebScrapeResult | null }) => void;

  clearStore: () => void;
}

/**
 * localStorage wrapper that throttles writes. Token events fire many times a
 * second; without throttling every keystroke of streamed output would
 * re-serialize and re-write the whole persisted blob. Writes are coalesced to
 * at most one per second (trailing edge) and flushed before the tab unloads.
 */
function throttledLocalStorage(): StateStorage {
  const DELAY = 1000;
  let pending: { name: string; value: string } | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let lastWrite = 0;

  const flush = () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    if (!pending) return;
    try {
      localStorage.setItem(pending.name, pending.value);
    } catch {
      /* quota / private mode — ignore */
    }
    pending = null;
    lastWrite = Date.now();
  };

  if (typeof window !== "undefined") {
    window.addEventListener("beforeunload", flush);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") flush();
    });
  }

  return {
    getItem: (name) => {
      try {
        return localStorage.getItem(name);
      } catch {
        return null;
      }
    },
    setItem: (name, value) => {
      pending = { name, value };
      const since = Date.now() - lastWrite;
      if (since >= DELAY) {
        flush();
      } else if (!timer) {
        timer = setTimeout(flush, DELAY - since);
      }
    },
    removeItem: (name) => {
      try {
        localStorage.removeItem(name);
      } catch {
        /* ignore */
      }
    },
  };
}

export const usePipelineStore = create<PipelineStore>()(
  persist(
    (set, get) => ({
      jobId: null,
      setJobId: (id) => set({ jobId: id }),

      companyId: null,
      setCompanyId: (id) => set({ companyId: id }),

      companyName: null,
      setCompanyName: (name) => set({ companyName: name }),

      draft: {},
      setDraft: (d) => set((s) => ({ draft: { ...s.draft, ...d } })),

      result: null,
      setResult: (result) => set({ result }),

      status: null,
      setStatus: (status) => set({ status }),

      isRunning: false,
      setIsRunning: (running) => set({ isRunning: running }),

      streamJobId: null,
      streamAgents: [],
      streamActiveAgent: null,
      streamDone: false,

      streamReset: (jobId) =>
        set({
          streamJobId: jobId,
          streamAgents: [],
          streamActiveAgent: null,
          streamDone: false,
        }),

      setStreamDone: (done) =>
        set(done ? { streamDone: true, streamActiveAgent: null } : { streamDone: false }),

      hydrateStream: (jobId, agents, activeAgent, done) =>
        set({
          streamJobId: jobId,
          streamAgents: agents,
          streamActiveAgent: activeAgent,
          streamDone: done,
        }),

      socialScrape: { url: "", result: null },
      setSocialScrape: (s) => set({ socialScrape: s }),
      webScrape: { url: "", result: null },
      setWebScrape: (s) => set({ webScrape: s }),

      applyStreamEvent: (event) => {
        const agents = get().streamAgents;

        if (event.type === "agent_start" && event.agent) {
          const exists = agents.some((a) => a.name === event.agent);
          set({
            streamActiveAgent: event.agent,
            streamAgents: exists
              ? agents
              : [
                  ...agents,
                  {
                    name: event.agent,
                    label: event.label ?? event.agent,
                    status: "thinking",
                    tokens: "",
                    reasoning: "",
                  },
                ],
          });
          return;
        }

        if (event.type === "scrape_tick" && event.agent) {
          set({
            streamAgents: agents.map((a) =>
              a.name === event.agent
                ? {
                    ...a,
                    scrapeCount: event.count,
                    scrapeTotal: event.total,
                    scrapeUrl: event.url,
                    // Accumulate each finished site so the run view can show
                    // the real list with proper completion check-marks.
                    scrapeSites:
                      event.url && !(a.scrapeSites || []).includes(event.url)
                        ? [...(a.scrapeSites || []), event.url]
                        : a.scrapeSites || [],
                  }
                : a,
            ),
          });
          return;
        }

        if (event.type === "token" && event.agent && event.content) {
          set({
            streamAgents: agents.map((a) =>
              a.name === event.agent
                ? { ...a, tokens: a.tokens + event.content }
                : a,
            ),
          });
          return;
        }

        if (event.type === "reasoning" && event.agent && event.content) {
          set({
            streamAgents: agents.map((a) =>
              a.name === event.agent
                ? { ...a, reasoning: a.reasoning + event.content }
                : a,
            ),
          });
          return;
        }

        if (event.type === "agent_done" && event.agent) {
          set({
            streamActiveAgent: null,
            streamAgents: agents.map((a) =>
              a.name === event.agent
                ? {
                    ...a,
                    status: "done",
                    summary: event.summary,
                    result: event.result,
                  }
                : a,
            ),
          });
          return;
        }
      },

      clearStore: () =>
        set({
          jobId: null,
          companyId: null,
          result: null,
          status: null,
          isRunning: false,
          streamJobId: null,
          streamAgents: [],
          streamActiveAgent: null,
          streamDone: false,
        }),
    }),
    {
      name: "pipeline-storage",
      storage: createJSONStorage(() =>
        typeof window !== "undefined"
          ? throttledLocalStorage()
          : (undefined as unknown as StateStorage),
      ),
      partialize: (state) => ({
        jobId: state.jobId,
        companyId: state.companyId,
        companyName: state.companyName,
        draft: state.draft,
        isRunning: state.isRunning,
        streamJobId: state.streamJobId,
        streamAgents: state.streamAgents,
        streamActiveAgent: state.streamActiveAgent,
        streamDone: state.streamDone,
        socialScrape: state.socialScrape,
        webScrape: state.webScrape,
      }),
    },
  ),
);

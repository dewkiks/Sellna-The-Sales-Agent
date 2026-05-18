"use client";

import { useEffect } from "react";
import { agentStream } from "@/lib/agentStream";
import type { AgentState } from "@/lib/agentStream";
import { usePipelineStore } from "@/store/pipelineStore";

export type { StreamEvent, StreamEventType, AgentState } from "@/lib/agentStream";

/**
 * Subscribe to a pipeline run's live execution logs.
 *
 * The actual SSE socket and the captured logs live outside React (see
 * `@/lib/agentStream` + the pipeline store), so the logs persist across
 * navigation and page refreshes. This hook just keeps the socket connected
 * for `jobId` and reads the captured state.
 */
export function useAgentStream(jobId: string | null) {
  const streamJobId = usePipelineStore((s) => s.streamJobId);
  const agents = usePipelineStore((s) => s.streamAgents);
  const activeAgent = usePipelineStore((s) => s.streamActiveAgent);
  const isDone = usePipelineStore((s) => s.streamDone);

  useEffect(() => {
    agentStream.ensureConnected(jobId);
    // Intentionally no cleanup: the socket is a singleton that must survive
    // this component unmounting (navigating to another section).
  }, [jobId]);

  // The captured slice belongs to a different job — don't surface stale logs.
  if (jobId && streamJobId && streamJobId !== jobId) {
    return {
      agents: [] as AgentState[],
      activeAgent: null as string | null,
      isDone: false,
    };
  }

  return { agents, activeAgent, isDone };
}

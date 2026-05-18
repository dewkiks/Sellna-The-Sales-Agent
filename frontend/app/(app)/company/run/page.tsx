"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useTopBarSlot } from "@/components/AppShell";
import { Ico } from "@/components/icons";
import { Card, AGENTS, AgentRow, type AgentStatus } from "@/components/primitives";
import { useAgentStream } from "@/hooks/useAgentStream";
import { agentStream } from "@/lib/agentStream";
import { pipelineApi } from "@/lib/api";
import { usePipelineStore } from "@/store/pipelineStore";
import { toast } from "@/lib/toast";

/* a streamed text panel — fixed height, scrolls instead of stretching */
const panelStyle = (mono: boolean): React.CSSProperties => ({
  background: "var(--bg-soft)",
  border: "1px solid var(--border)",
  borderRadius: 10,
  padding: "12px 14px",
  font: mono ? "12.5px/1.6 var(--font-mono)" : "12px/1.55 var(--font-sans)",
  color: mono ? "var(--ink-2)" : "var(--ink-3)",
  height: 248,
  overflowY: "auto",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
});

export default function LiveRunPage() {
  const router = useRouter();
  const {
    jobId,
    companyName,
    draft,
    setCompanyId,
    setIsRunning,
    setStreamDone,
    clearStore,
  } = usePipelineStore();
  const runTarget = companyName || draft?.website || "Your domain";
  const { agents, activeAgent, isDone } = useAgentStream(jobId);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  const { data: status } = useQuery({
    queryKey: ["pipelineStatus", jobId],
    queryFn: () => pipelineApi.getPipelineStatus(jobId as string),
    enabled: !!jobId,
    refetchInterval: (q) =>
      ["SUCCESS", "FAILURE"].includes((q.state.data?.state as string) || "")
        ? false
        : 3000,
    retry: false,
  });

  useEffect(() => {
    if (status?.state === "SUCCESS") {
      if (status.company_id) setCompanyId(status.company_id);
      setIsRunning(false);
      setStreamDone(true);
      toast.success("Pipeline complete — intelligence ready");
    }
    if (status?.state === "FAILURE") {
      setIsRunning(false);
      setStreamDone(true);
    }
  }, [status?.state, status?.company_id, setCompanyId, setIsRunning, setStreamDone]);

  const doneCount = agents.filter((a) => a.status === "done").length;
  const live = !!jobId && agents.length > 0;
  const failed = status?.state === "FAILURE";
  const completedCount = live ? (isDone ? AGENTS.length : doneCount) : 0;

  const agentStatus = (i: number): AgentStatus => {
    if (isDone) return "completed";
    if (!live || failed) return i < completedCount ? "completed" : "pending";
    return i < completedCount
      ? "completed"
      : i === completedCount
        ? "running"
        : "pending";
  };

  /* ---- the agent currently being previewed ---- */
  const autoIndex = live ? Math.min(completedCount, AGENTS.length - 1) : 0;
  const focusIndex = selectedIdx ?? autoIndex;
  const focusMeta = AGENTS[focusIndex];
  // streamed agents arrive in pipeline order, so index lines up with AGENTS
  const focusAgent = agents[focusIndex];
  const focusLabel = focusAgent?.label || focusMeta.name;
  const focusStarted = !!focusAgent;
  const focusStreaming = focusStarted && focusAgent.status !== "done" && !isDone;
  const tokenText = focusAgent?.tokens || "";
  const reasoningText = focusAgent?.reasoning || "";

  /* ---- scrape progress — real Web Scraper stream data only ---- */
  const scraper =
    agents.find(
      (a) => (a.scrapeSites?.length ?? 0) > 0 || typeof a.scrapeTotal === "number",
    ) || null;
  const scrapeSites = scraper?.scrapeSites ?? [];
  const scrapeCount = scrapeSites.length;
  const scrapeTotal = scraper?.scrapeTotal ?? scrapeCount;
  const scraperRunning = !!scraper && scraper.status !== "done" && !isDone;
  const scrapePct =
    scrapeTotal > 0 ? Math.round((scrapeCount / scrapeTotal) * 100) : 0;
  const scrapePending = Math.max(
    0,
    scrapeTotal - scrapeCount - (scraperRunning && scrapeCount < scrapeTotal ? 1 : 0),
  );

  useTopBarSlot(
    <span className="pill live">
      <span className="dot" />
      {isDone ? "Complete" : "Streaming"} · {completedCount} of {AGENTS.length}
    </span>,
    [isDone, completedCount],
  );

  return (
    <>
      <div className="page-h">
        <div>
          <div className="section-h">
            {isDone
              ? "Completed"
              : live
                ? `Running${status?.status_msg ? ` · ${status.status_msg}` : ""}`
                : "Waiting to start"}
          </div>
          <h1>{runTarget} → full GTM intelligence</h1>
          <p>
            Watch the pipeline think. Click any agent on the left to inspect its
            streamed output and reasoning.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="btn"
            onClick={async () => {
              if (jobId && !isDone) {
                try {
                  await pipelineApi.abortPipeline(jobId);
                } catch {
                  /* ignore */
                }
              }
              clearStore();
              agentStream.disconnect();
              router.push("/app");
            }}
          >
            <Ico.x style={{ width: 13, height: 13 }} /> Abort run
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 14 }}>
        <Card title="Agents" subtitle="9 specialists · click to preview">
          <div style={{ display: "grid", gap: 6 }}>
            {AGENTS.map((a, i) => (
              <div
                key={a.id}
                onClick={() => setSelectedIdx(i)}
                style={{
                  cursor: "pointer",
                  borderRadius: 10,
                  outline:
                    i === focusIndex ? "2px solid var(--blue-glow)" : "none",
                  outlineOffset: -2,
                }}
              >
                <AgentRow agent={a} status={agentStatus(i)} />
              </div>
            ))}
          </div>
        </Card>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Card
            title={`Agent ${String(focusIndex + 1).padStart(2, "0")} · ${focusLabel}`}
            subtitle={
              focusStarted
                ? focusAgent.status === "done"
                  ? "Completed"
                  : "Streaming live"
                : "Not started yet"
            }
            right={
              <span className={"pill " + (focusStreaming ? "blue" : "")}>
                <span
                  className="dot"
                  style={{
                    background: focusStreaming ? "var(--blue)" : "var(--ink-4)",
                  }}
                />
                {focusStarted
                  ? focusAgent.status === "done"
                    ? "done"
                    : "thinking"
                  : "idle"}
              </span>
            }
          >
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <div className="section-h" style={{ marginBottom: 8 }}>
                  Token output
                </div>
                <div style={panelStyle(true)}>
                  {tokenText ? (
                    <>
                      {tokenText}
                      {focusStreaming && <span className="ai-caret" />}
                    </>
                  ) : (
                    <span style={{ color: "var(--ink-4)" }}>
                      {focusStarted
                        ? "This agent produced no streamed text."
                        : "This agent hasn't started yet."}
                    </span>
                  )}
                </div>
              </div>
              <div>
                <div className="section-h" style={{ marginBottom: 8 }}>
                  Reasoning trace
                </div>
                <div style={panelStyle(false)}>
                  {reasoningText ? (
                    reasoningText
                  ) : (
                    <span style={{ color: "var(--ink-4)" }}>
                      {focusStarted
                        ? "No reasoning trace for this agent."
                        : "This agent hasn't started yet."}
                    </span>
                  )}
                </div>
              </div>
            </div>
            {focusStarted && focusAgent.summary && (
              <div
                style={{
                  marginTop: 12,
                  paddingTop: 12,
                  borderTop: "1px solid var(--border)",
                  fontSize: 12,
                  color: "var(--ink-2)",
                }}
              >
                <strong style={{ color: "var(--ink)" }}>Summary · </strong>
                {focusAgent.summary}
              </div>
            )}
          </Card>

          <Card
            title="Scrape progress"
            subtitle={
              scraper
                ? `Web Scraper — ${scrapeCount} of ${scrapeTotal} sites`
                : "Web Scraper"
            }
          >
            {!scraper ? (
              <div style={{ fontSize: 12, color: "var(--ink-3)", padding: "4px 2px" }}>
                Scrape progress appears here once the Web Scraper agent starts.
              </div>
            ) : (
              <>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    marginBottom: 10,
                  }}
                >
                  <div
                    style={{
                      flex: 1,
                      height: 6,
                      borderRadius: 3,
                      background: "var(--bg-muted)",
                      overflow: "hidden",
                      position: "relative",
                    }}
                  >
                    <div
                      style={{
                        position: "absolute",
                        inset: 0,
                        width: `${scrapePct}%`,
                        background:
                          "linear-gradient(90deg,var(--blue-glow),var(--blue))",
                        borderRadius: 3,
                      }}
                    />
                  </div>
                  <div
                    style={{
                      fontSize: 11.5,
                      fontFamily: "var(--font-mono)",
                      color: "var(--ink-3)",
                    }}
                  >
                    {scrapeCount}/{scrapeTotal}
                  </div>
                </div>
                <div style={{ display: "grid", gap: 6, maxHeight: 200, overflowY: "auto" }}>
                  {scrapeSites.map((u, i) => (
                    <div
                      key={u + i}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        padding: "6px 10px",
                      }}
                    >
                      <Ico.check
                        style={{ width: 13, height: 13, color: "var(--green)" }}
                      />
                      <span
                        style={{
                          font: "12px var(--font-mono)",
                          color: "var(--ink-2)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          minWidth: 0,
                        }}
                      >
                        {u}
                      </span>
                      <span
                        style={{
                          marginLeft: "auto",
                          fontSize: 10.5,
                          color: "var(--green)",
                          fontWeight: 600,
                          flexShrink: 0,
                        }}
                      >
                        done
                      </span>
                    </div>
                  ))}
                  {scraperRunning && scrapeCount < scrapeTotal && (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        padding: "6px 10px",
                        background: "var(--blue-soft)",
                        borderRadius: 8,
                      }}
                    >
                      <span className="spin" />
                      <span
                        style={{
                          font: "12px var(--font-mono)",
                          color: "var(--blue-deep)",
                        }}
                      >
                        scraping next site…
                      </span>
                    </div>
                  )}
                  {scrapePending > 0 && (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        padding: "6px 10px",
                      }}
                    >
                      <span
                        style={{
                          width: 13,
                          height: 13,
                          borderRadius: "50%",
                          border: "1.5px dashed var(--ink-4)",
                        }}
                      />
                      <span style={{ font: "12px var(--font-mono)", color: "var(--ink-4)" }}>
                        +{scrapePending} more queued
                      </span>
                    </div>
                  )}
                </div>
              </>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}

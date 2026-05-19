
import { useEffect, useRef, useState } from "react";
import { Ico } from "./icons";
import { AGENTS, AgentRow } from "./primitives";
import { useAgentStream, type AgentState } from "@/hooks/useAgentStream";
import { usePipelineStore } from "@/store/pipelineStore";

/* ---------- status glyph ---------- */

function StatusDot({
  status,
  active,
}: {
  status: AgentState["status"];
  active: boolean;
}) {
  if (status === "done")
    return (
      <span
        style={{
          width: 18,
          height: 18,
          borderRadius: "50%",
          background: "var(--green)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <Ico.check style={{ width: 11, height: 11, color: "#fff" }} />
      </span>
    );
  if (active) return <span className="spin" style={{ width: 16, height: 16 }} />;
  return (
    <span
      style={{
        width: 16,
        height: 16,
        borderRadius: "50%",
        border: "1.6px dashed var(--ink-4)",
        flexShrink: 0,
      }}
    />
  );
}

/* ---------- collapsible reasoning trace (AI-Elements "Reasoning") ---------- */

function Reasoning({ text, active }: { text: string; active: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginBottom: 8 }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: 0,
          fontSize: 11.5,
        }}
      >
        <Ico.brain style={{ width: 13, height: 13, color: "var(--violet)" }} />
        {active ? (
          <span className="ai-thinking">Reasoning…</span>
        ) : (
          <span style={{ color: "var(--ink-3)", fontWeight: 600 }}>
            Reasoning
          </span>
        )}
        <Ico.chev
          style={{
            width: 12,
            height: 12,
            color: "var(--ink-4)",
            transform: open ? "rotate(180deg)" : "none",
            transition: "transform .2s",
          }}
        />
      </button>
      {open && (
        <div
          style={{
            marginTop: 6,
            padding: "8px 10px",
            background: "var(--bg-soft)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            font: "11.5px/1.55 var(--font-sans)",
            color: "var(--ink-3)",
            whiteSpace: "pre-wrap",
            maxHeight: 160,
            overflowY: "auto",
          }}
        >
          {text}
        </div>
      )}
    </div>
  );
}

/* ---------- streaming token output (AI-Elements "Response") ---------- */

function Response({ text, streaming }: { text: string; streaming: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [text]);
  return (
    <div
      ref={ref}
      style={{
        background: "var(--bg-soft)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: "10px 12px",
        font: "12px/1.6 var(--font-mono)",
        color: "var(--ink-2)",
        whiteSpace: "pre-wrap",
        maxHeight: 200,
        overflowY: "auto",
        minHeight: 52,
      }}
    >
      {text || <span style={{ color: "var(--ink-4)" }}>Waiting for output…</span>}
      {streaming && <span className="ai-caret" />}
    </div>
  );
}

/* ---------- one agent's expandable live log ---------- */

function AgentLog({
  a,
  active,
  open,
  onToggle,
}: {
  a: AgentState;
  active: boolean;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div className={"ai-task" + (active ? " active" : "")}>
      <button
        onClick={onToggle}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "9px 11px",
          background: "none",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <StatusDot status={a.status} active={active} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ink)" }}>
            {a.label}
          </div>
          {active ? (
            <span className="ai-thinking" style={{ fontSize: 11 }}>
              streaming…
            </span>
          ) : a.summary ? (
            <div
              style={{
                fontSize: 11,
                color: "var(--ink-3)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {a.summary}
            </div>
          ) : a.status === "done" ? (
            <div style={{ fontSize: 11, color: "var(--ink-4)" }}>done</div>
          ) : null}
        </div>
        <Ico.chev
          style={{
            width: 13,
            height: 13,
            color: "var(--ink-4)",
            flexShrink: 0,
            transform: open ? "rotate(180deg)" : "none",
            transition: "transform .2s",
          }}
        />
      </button>
      {open && (
        <div style={{ padding: "10px 11px 11px", borderTop: "1px solid var(--border)" }}>
          {(a.reasoning || active) && (
            <Reasoning
              text={a.reasoning || "Waiting for the reasoning trace…"}
              active={active}
            />
          )}
          <Response text={a.tokens} streaming={active} />
          {typeof a.scrapeTotal === "number" && (
            <div
              style={{
                marginTop: 8,
                fontSize: 11,
                color: "var(--ink-3)",
                fontFamily: "var(--font-mono)",
              }}
            >
              scraped {a.scrapeSites?.length ?? a.scrapeCount ?? 0} /{" "}
              {a.scrapeTotal} sites
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ---------- panel ---------- */

/**
 * Live pipeline execution logs — subscribes to the running job's SSE stream
 * and renders each agent's reasoning + streamed output, AI-Elements style.
 */
export function LiveLogs() {
  const jobId = usePipelineStore((s) => s.jobId);
  const { agents, activeAgent, isDone } = useAgentStream(jobId);
  const [openName, setOpenName] = useState<string | null>(null);
  const live = agents.length > 0;

  const effectiveOpen =
    openName ?? activeAgent ?? (live ? agents[agents.length - 1].name : null);

  if (!live) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 6,
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
        }}
      >
        <div style={{ fontSize: 11.5, color: "var(--ink-3)", marginBottom: 2 }}>
          No run streaming. Start a new analysis to watch all 9 agents think
          live.
        </div>
        {AGENTS.map((a) => (
          <AgentRow key={a.id} agent={a} status="pending" />
        ))}
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 7,
        flex: 1,
        minHeight: 0,
        overflowY: "auto",
        paddingRight: 2,
      }}
    >
      {agents.map((a) => {
        const active = a.name === activeAgent && !isDone;
        return (
          <AgentLog
            key={a.name}
            a={a}
            active={active}
            open={a.name === effectiveOpen}
            onToggle={() =>
              setOpenName((o) => (o === a.name ? "__none__" : a.name))
            }
          />
        );
      })}
      {isDone && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 11.5,
            color: "var(--green)",
            fontWeight: 600,
            padding: "4px 2px",
          }}
        >
          <Ico.check style={{ width: 13, height: 13 }} /> Pipeline complete —
          all agents finished.
        </div>
      )}
    </div>
  );
}

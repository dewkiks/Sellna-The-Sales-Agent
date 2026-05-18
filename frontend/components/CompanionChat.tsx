"use client";

import { useEffect, useRef, useState } from "react";
import { Ico, BrandGlyph } from "./icons";
import { SplineAvatar } from "./SplineAvatar";
import { API_ROOT } from "@/lib/api";
import { usePipelineStore } from "@/store/pipelineStore";

interface Msg {
  role: "user" | "assistant";
  content: string;
}

const SUGGESTIONS = [
  "What does the pipeline do?",
  "Summarize my active company",
  "Which competitors were found?",
  "How does the social scraper work?",
];

/**
 * Floating Sellna companion. The 3D avatar is the launcher — clicking it opens
 * a chat agent that answers questions about analyzed companies, the pipeline
 * and app FAQs (streamed from `POST /api/v1/chat`).
 */
export function CompanionChat() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const companyId = usePipelineStore((s) => s.companyId);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, open]);

  const send = async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    const history = messages;
    setMessages([
      ...messages,
      { role: "user", content: q },
      { role: "assistant", content: "" },
    ]);
    setBusy(true);
    try {
      const res = await fetch(`${API_ROOT}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: q,
          history: history.map((m) => ({ role: m.role, content: m.content })),
          company_id: companyId,
        }),
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let acc = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        acc += dec.decode(value, { stream: true });
        setMessages((m) => {
          const copy = m.slice();
          copy[copy.length - 1] = { role: "assistant", content: acc };
          return copy;
        });
      }
    } catch {
      setMessages((m) => {
        const copy = m.slice();
        copy[copy.length - 1] = {
          role: "assistant",
          content:
            "Sorry — I couldn't reach the assistant. Make sure the backend is running.",
        };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  };

  /* ---- launcher (avatar) ---- */
  if (!open) {
    return (
      <div
        className="avatar-dock"
        aria-label="Open Sellna companion"
        role="button"
        tabIndex={0}
        onClick={() => setOpen(true)}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setOpen(true)}
        style={{ cursor: "pointer" }}
      >
        <div className="bubble">Ask me anything ↘</div>
        {/* viewer ignores pointer events so the dock receives the click */}
        <div style={{ pointerEvents: "none" }}>
          <SplineAvatar size={132} />
        </div>
      </div>
    );
  }

  const last = messages[messages.length - 1];
  const waitingFirstToken =
    busy && last?.role === "assistant" && last.content === "";

  /* ---- chat panel ---- */
  return (
    <div className="companion-panel" aria-label="Sellna companion chat">
      <div className="companion-head">
        <div className="brand-mark" style={{ width: 30, height: 30, borderRadius: 9 }}>
          <BrandGlyph size={15} />
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: "-0.01em" }}>
            Sellna Companion
          </div>
          <div style={{ fontSize: 11, color: "var(--ink-3)" }}>
            Ask about companies, pipelines & how things work
          </div>
        </div>
        <button
          className="btn ghost"
          style={{ padding: 6 }}
          onClick={() => setOpen(false)}
          aria-label="Close"
        >
          <Ico.x style={{ width: 15, height: 15 }} />
        </button>
      </div>

      <div ref={scrollRef} className="companion-body">
        {messages.length === 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div
              style={{
                fontSize: 12.5,
                color: "var(--ink-2)",
                lineHeight: 1.55,
              }}
            >
              Hi — I&apos;m your Sellna companion. Ask me about an analyzed
              company, a pipeline run, the scrapers, or how anything here works.
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  className="companion-chip"
                  onClick={() => send(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {messages.map((m, i) => {
              const isUser = m.role === "user";
              const isLast = i === messages.length - 1;
              return (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    justifyContent: isUser ? "flex-end" : "flex-start",
                  }}
                >
                  <div
                    className={"companion-msg " + (isUser ? "user" : "bot")}
                  >
                    {!isUser && isLast && waitingFirstToken ? (
                      <span className="ai-thinking">Thinking…</span>
                    ) : (
                      <>
                        {m.content}
                        {!isUser && isLast && busy && m.content !== "" && (
                          <span className="ai-caret" />
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="companion-input">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
          placeholder="Ask the companion…"
          disabled={busy}
        />
        <button
          className="btn primary"
          style={{ padding: "8px 10px" }}
          onClick={() => send(input)}
          disabled={busy || !input.trim()}
          aria-label="Send"
        >
          {busy ? (
            <span className="spin" style={{ width: 13, height: 13 }} />
          ) : (
            <Ico.send style={{ width: 14, height: 14 }} />
          )}
        </button>
      </div>
    </div>
  );
}

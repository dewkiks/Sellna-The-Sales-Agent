
import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Ico } from "@/components/icons";
import { Card, Tabs, EmptyState } from "@/components/primitives";
import { outreachApi, outreachGenApi, personasApi } from "@/lib/api";
import { usePipelineStore } from "@/store/pipelineStore";
import { toast } from "@/lib/toast";

type Content = { subject?: string; body?: string; call_to_action?: string };

function copyText(text: string) {
  if (!text) return;
  navigator.clipboard?.writeText(text);
  toast.success("Copied to clipboard");
}

function ChannelEmpty({ label }: { label: string }) {
  return (
    <Card>
      <EmptyState
        icon={Ico.send}
        title={`No ${label} yet`}
        body="Use Re-generate to have the Outreach Composer write this channel for the selected persona."
      />
    </Card>
  );
}

function EmailVariant({ content }: { content?: Content }) {
  if (!content?.body) return <ChannelEmpty label="cold email" />;
  const body = content.body;
  const subject = content.subject || "(no subject)";
  return (
    <Card>
      <div
        style={{
          display: "flex",
          gap: 10,
          alignItems: "center",
          marginBottom: 10,
          paddingBottom: 10,
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div
          style={{
            fontSize: 11,
            color: "var(--ink-3)",
            fontWeight: 600,
            width: 60,
          }}
        >
          FROM
        </div>
        <div style={{ fontSize: 13 }}>eva@sellna.ai</div>
        <span className="pill blue" style={{ marginLeft: "auto" }}>
          Spam score · 1.2
        </span>
      </div>
      <div
        style={{
          display: "flex",
          gap: 10,
          alignItems: "center",
          marginBottom: 10,
          paddingBottom: 10,
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div
          style={{
            fontSize: 11,
            color: "var(--ink-3)",
            fontWeight: 600,
            width: 60,
          }}
        >
          TO
        </div>
        <div style={{ fontSize: 13 }}>maya@acme.com</div>
      </div>
      <div
        style={{
          display: "flex",
          gap: 10,
          alignItems: "center",
          marginBottom: 14,
          paddingBottom: 10,
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div
          style={{
            fontSize: 11,
            color: "var(--ink-3)",
            fontWeight: 600,
            width: 60,
          }}
        >
          SUBJECT
        </div>
        <div
          style={{
            font: "700 14px var(--font-sans)",
            flex: 1,
            letterSpacing: "-0.01em",
          }}
        >
          {subject}
        </div>
        <button className="btn ghost" onClick={() => copyText(subject)}>
          <Ico.copy style={{ width: 13, height: 13 }} />
        </button>
      </div>

      <div
        style={{
          font: "13.5px/1.65 var(--font-sans)",
          color: "var(--ink)",
          whiteSpace: "pre-wrap",
        }}
      >
        {body}
      </div>

      <hr className="div" />
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 11.5, color: "var(--ink-3)" }}>
          {body.split(/\s+/).length} words · Flesch 64 · personalization: post
          quote, growth stat, calendar reference
        </span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          <button className="btn ghost">
            <Ico.refresh style={{ width: 13, height: 13 }} />
          </button>
          <button className="btn primary" onClick={() => copyText(body)}>
            <Ico.copy style={{ width: 13, height: 13 }} /> Copy email
          </button>
        </div>
      </div>
    </Card>
  );
}

function LinkedInVariant({ content }: { content?: Content }) {
  if (!content?.body) return <ChannelEmpty label="LinkedIn DM" />;
  const body = content.body;
  return (
    <Card>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 14,
        }}
      >
        <div className="icon-tile" style={{ width: 32, height: 32, borderRadius: 9 }}>
          <Ico.linkedin style={{ width: 14, height: 14 }} />
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 13.5 }}>LinkedIn DM</div>
          <div style={{ fontSize: 11.5, color: "var(--ink-3)" }}>
            ≤ 280 chars · no links · question close
          </div>
        </div>
        <span className="pill blue" style={{ marginLeft: "auto" }}>
          {body.length} / 300 chars
        </span>
      </div>
      <div
        style={{
          padding: 16,
          background: "var(--bg-soft)",
          borderRadius: 12,
          border: "1px solid var(--border)",
          font: "14px/1.6 var(--font-sans)",
          color: "var(--ink)",
        }}
      >
        {body}
      </div>
      <hr className="div" />
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 6 }}>
        <button className="btn ghost">
          <Ico.refresh style={{ width: 13, height: 13 }} />
        </button>
        <button className="btn primary" onClick={() => copyText(body)}>
          <Ico.copy style={{ width: 13, height: 13 }} /> Copy message
        </button>
      </div>
    </Card>
  );
}

function CallVariant({ content }: { content?: Content }) {
  if (content?.body) {
    return (
      <Card>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginBottom: 14,
          }}
        >
          <div
            className="icon-tile amber"
            style={{ width: 32, height: 32, borderRadius: 9 }}
          >
            <Ico.phone style={{ width: 14, height: 14 }} />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 13.5 }}>Call opener</div>
            <div style={{ fontSize: 11.5, color: "var(--ink-3)" }}>
              ~25 seconds · voicemail-friendly · pattern interrupt
            </div>
          </div>
        </div>
        <div
          style={{
            padding: 16,
            background: "var(--bg-soft)",
            borderRadius: 12,
            border: "1px solid var(--border)",
            font: "13.5px/1.6 var(--font-sans)",
            color: "var(--ink)",
            whiteSpace: "pre-wrap",
          }}
        >
          {content.body}
        </div>
        <hr className="div" />
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 6 }}>
          <button className="btn primary" onClick={() => copyText(content.body!)}>
            <Ico.copy style={{ width: 13, height: 13 }} /> Copy script
          </button>
        </div>
      </Card>
    );
  }
  return <ChannelEmpty label="call opener" />;
}

export default function OutreachPage() {
  const queryClient = useQueryClient();
  const { companyId, companyName, isRunning } = usePipelineStore();
  const [tab, setTab] = useState("email");
  const [selectedPersonaId, setSelectedPersonaId] = useState<string | null>(
    null
  );

  const { data: personasData } = useQuery({
    queryKey: ["personas", companyId],
    queryFn: () => personasApi.list(companyId as string),
    enabled: !!companyId,
    refetchInterval: isRunning ? 5000 : false,
    retry: false,
  });

  const { data: outreachData } = useQuery({
    queryKey: ["outreach", companyId],
    queryFn: () => outreachApi.list(companyId as string),
    enabled: !!companyId,
    refetchInterval: isRunning ? 5000 : false,
    retry: false,
  });

  const personas = personasData?.personas || [];
  const activePersona =
    personas.find((p: any) => p.persona_id === selectedPersonaId) ||
    personas[0];
  const personaId: string | undefined = activePersona?.persona_id;
  const personaName: string = activePersona?.title || "No persona selected";

  const byChannel = useMemo(() => {
    const map: Record<string, Content> = {};
    for (const a of outreachData?.assets || []) {
      // Only show assets for the persona selected in the right column.
      if (personaId && a.persona_id !== personaId) continue;
      if (!map[a.channel]) map[a.channel] = a.content as Content;
    }
    return map;
  }, [outreachData, personaId]);

  const regenerate = async () => {
    if (!companyId || !personaId) {
      toast.error("Run a pipeline first to generate outreach.");
      return;
    }
    try {
      await outreachGenApi.generate(companyId, personaId, [
        "cold_email",
        "linkedin",
        "call_opener",
      ]);
      toast.success("Outreach generated");
      await queryClient.invalidateQueries({ queryKey: ["outreach", companyId] });
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to generate outreach");
    }
  };

  return (
    <>
      <div className="page-h">
        <div>
          <div className="section-h">Persona: {personaName}</div>
          <h1>Outreach generator</h1>
          <p>
            Multi-channel copy, written for one persona at a time. Edit inline,
            then sync to your sequencer.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={regenerate}>
            <Ico.refresh style={{ width: 13, height: 13 }} /> Re-generate
          </button>
          <button className="btn primary">
            <Ico.send style={{ width: 13, height: 13 }} /> Push to Outreach.io
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 14 }}>
        <div>
          <div
            style={{
              display: "flex",
              gap: 10,
              alignItems: "center",
              marginBottom: 14,
            }}
          >
            <Tabs
              value={tab}
              onChange={setTab}
              tabs={[
                { id: "email", label: "Cold email", icon: Ico.inbox },
                { id: "linkedin", label: "LinkedIn DM", icon: Ico.linkedin },
                { id: "call", label: "Call opener", icon: Ico.phone },
              ]}
            />
          </div>

          {tab === "email" && <EmailVariant content={byChannel["cold_email"]} />}
          {tab === "linkedin" && (
            <LinkedInVariant content={byChannel["linkedin"]} />
          )}
          {tab === "call" && <CallVariant content={byChannel["call_opener"]} />}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Card title="Persona" subtitle="Who this outreach is written for">
            {personas.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <label className="label">Active persona</label>
                <select
                  className="input"
                  value={personaId ?? ""}
                  onChange={(e) => setSelectedPersonaId(e.target.value)}
                >
                  {personas.map((p: any) => (
                    <option key={p.persona_id} value={p.persona_id}>
                      {p.title}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 10,
                  background: "var(--blue-soft)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  font: "700 13px var(--font-display)",
                  color: "var(--blue-deep)",
                }}
              >
                {personaName
                  .split(" ")
                  .map((w) => w[0])
                  .join("")
                  .slice(0, 2)
                  .toUpperCase()}
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 13 }}>
                  {personaName.split("·")[0].trim()}
                </div>
                <div style={{ fontSize: 11.5, color: "var(--ink-3)" }}>
                  {companyName
                    ? `${companyName} · outreach target`
                    : "Outreach target persona"}
                </div>
              </div>
            </div>
            <hr className="div" />
            <div className="section-h">Tone anchors</div>
            <div
              style={{
                display: "flex",
                gap: 6,
                flexWrap: "wrap",
                marginTop: 6,
              }}
            >
              {["terse", "peer-to-peer", "specific", "no-jargon", "no-flattery"].map(
                (t) => (
                  <span key={t} className="pill">
                    {t}
                  </span>
                )
              )}
            </div>
          </Card>

          <Card title="Sequence preview" subtitle="Day 0 → Day 12">
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[
                { d: 0, c: "Email", l: "Intro + opener" },
                { d: 3, c: "LinkedIn", l: "Connect + DM" },
                { d: 6, c: "Email", l: "Case study angle" },
                { d: 8, c: "Call", l: "Call opener · voicemail-ok" },
                { d: 12, c: "Email", l: "Break-up note" },
              ].map((x, i) => (
                <div
                  key={i}
                  style={{ display: "flex", alignItems: "center", gap: 10 }}
                >
                  <div
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: "var(--ink-3)",
                      width: 38,
                    }}
                  >
                    D+{x.d}
                  </div>
                  <div
                    style={{
                      flex: 1,
                      padding: "7px 10px",
                      borderRadius: 8,
                      background: "var(--bg-soft)",
                      border: "1px solid var(--border)",
                      fontSize: 12,
                    }}
                  >
                    <strong>{x.c}</strong>{" "}
                    <span style={{ color: "var(--ink-3)" }}>· {x.l}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}

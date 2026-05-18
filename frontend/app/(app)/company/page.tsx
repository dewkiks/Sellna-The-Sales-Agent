"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Ico, type IconComponent } from "@/components/icons";
import { Card, Steps } from "@/components/primitives";
import { usePipelineStore } from "@/store/pipelineStore";

const NEXT_STEPS: { i: IconComponent; t: string; d: string }[] = [
  { i: Ico.brain, t: "Profile your company", d: "Industry, geo, model." },
  { i: Ico.swords, t: "Hunt competitors", d: "Direct + adjacent." },
  { i: Ico.target, t: "Rank gaps", d: "Positioning openings." },
  { i: Ico.target, t: "Generate ICPs", d: "3 fit-scored profiles." },
  { i: Ico.users, t: "Draft personas", d: "Buyer behavior." },
  { i: Ico.send, t: "Compose outreach", d: "Email · LI · call." },
];

export default function CompanyDomainPage() {
  const router = useRouter();
  const { draft, setDraft } = usePipelineStore();
  const [domain, setDomain] = useState(draft.website || "acme.com");

  const cont = () => {
    setDraft({ website: domain });
    router.push("/company/2");
  };

  return (
    <>
      <div style={{ maxWidth: 760, margin: "0 auto", padding: "24px 0" }}>
        <div style={{ textAlign: "center" }}>
          <div className="icon-tile xl" style={{ margin: "0 auto 18px" }}>
            <Ico.globe style={{ width: 24, height: 24 }} />
          </div>
          <h1
            style={{
              font: "700 28px var(--font-sans)",
              letterSpacing: "-0.03em",
              margin: 0,
            }}
          >
            Which domain should we analyze?
          </h1>
          <p style={{ color: "var(--ink-3)", fontSize: 14, margin: "8px 0 22px" }}>
            Sellna will resolve, verify and enrich it — then run the full 9-agent
            pipeline.
          </p>
        </div>

        <Card noPad>
          <div style={{ padding: 20 }}>
            <Steps current={0} />
            <div style={{ margin: "18px 0 8px" }}>
              <label className="label">Company domain</label>
              <div style={{ display: "flex", gap: 8, alignItems: "stretch" }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    padding: "0 12px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 10,
                    background: "var(--bg-muted)",
                    color: "var(--ink-3)",
                    fontFamily: "var(--font-mono)",
                    fontSize: 13,
                  }}
                >
                  https://
                </div>
                <input
                  className="input"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") cont();
                  }}
                  style={{ flex: 1, fontFamily: "var(--font-mono)" }}
                />
                <span className="pill" style={{ alignSelf: "center" }}>
                  <Ico.globe style={{ width: 11, height: 11 }} />
                  domain
                </span>
              </div>
              <div style={{ fontSize: 11.5, color: "var(--ink-3)", marginTop: 6 }}>
                Sellna will resolve, verify and enrich {domain || "this domain"}{" "}
                when you launch the pipeline.
              </div>
            </div>

            <div
              style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}
            >
              <span
                style={{
                  fontSize: 11.5,
                  color: "var(--ink-3)",
                  alignSelf: "center",
                }}
              >
                Try a sample:
              </span>
              {["Stripe", "SpaceX", "OpenAI", "Linear", "Notion"].map((n) => (
                <button
                  key={n}
                  className="btn"
                  style={{ padding: "5px 10px", fontSize: 11.5 }}
                  onClick={() => setDomain(`${n.toLowerCase()}.com`)}
                >
                  <span
                    style={{
                      width: 12,
                      height: 12,
                      borderRadius: 3,
                      background: "var(--bg-muted)",
                    }}
                  />{" "}
                  {n}
                </button>
              ))}
            </div>

            <hr className="div" />

            <div className="section-h">What happens next</div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3,1fr)",
                gap: 8,
                marginTop: 8,
              }}
            >
              {NEXT_STEPS.map((x, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    gap: 8,
                    padding: "8px 10px",
                    background: "var(--bg-soft)",
                    borderRadius: 9,
                    border: "1px solid var(--border)",
                  }}
                >
                  <div
                    className="icon-tile"
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: 6,
                      flexShrink: 0,
                    }}
                  >
                    <x.i style={{ width: 11, height: 11 }} />
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        letterSpacing: "-0.005em",
                      }}
                    >
                      {x.t}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--ink-3)" }}>{x.d}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div
            style={{
              padding: "12px 20px",
              borderTop: "1px solid var(--border)",
              background: "var(--bg-soft)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span style={{ fontSize: 12, color: "var(--ink-3)" }}>
              Est. runtime: 4 min 12 s · 9 agents
            </span>
            <button className="btn primary" onClick={cont}>
              Continue → Company details{" "}
              <Ico.arrow style={{ width: 13, height: 13 }} />
            </button>
          </div>
        </Card>
      </div>
    </>
  );
}

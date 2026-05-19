import { useState, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { Ico, BrandGlyph, type IconComponent } from "@/components/icons";
import { NAV, AGENTS, AgentRow } from "@/components/primitives";
import { DotField } from "@/components/DotField";
import { SplineAvatar } from "@/components/SplineAvatar";
import { usePipelineStore } from "@/store/pipelineStore";

export default function LandingPage() {
  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        background: "#fff",
        color: "var(--ink)",
        isolation: "isolate",
      }}
    >
      {/* Animated dot-field behind every section except the hero — kept a
          touch fainter than the hero's own field. */}
      <DotField
        baseAlpha={0.2}
        density={30}
        style={{ position: "fixed", inset: 0, zIndex: 0 }}
      />
      <div style={{ position: "relative", zIndex: 1 }}>
        <LandingNav />
        {/* Hero pins full-screen; the pitch section slides up over it on
            scroll, then the page returns to normal scrolling. */}
        <div className="hero-cover-group">
          <LandingHero />
          <LandingPitch />
        </div>
        <LandingMetrics />
        <LandingFeatures />
        <LandingWorkflow />
        <LandingCTA />
        <LandingFooter />
      </div>
    </div>
  );
}

function LandingNav() {
  const navigate = useNavigate();
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "18px 40px",
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 10,
        background: "rgba(255,255,255,.78)",
        backdropFilter: "blur(14px)",
        borderBottom: "1px solid var(--border)",
        // Empty navbar areas let mouse-move pass through to the Spline below
        // so the avatar keeps tracking the cursor over the navbar too.
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          cursor: "pointer",
          pointerEvents: "auto",
        }}
        onClick={() => navigate("/")}
      >
        <div className="brand-mark">
          <BrandGlyph />
        </div>
        <div className="brand-name" style={{ fontSize: 17 }}>
          sellna<span className="dot">.ai</span>
        </div>
      </div>
      <nav
        style={{
          display: "flex",
          gap: 24,
          marginLeft: 36,
          fontSize: 13.5,
          fontWeight: 500,
          color: "var(--ink-2)",
        }}
      >
        {[
          { label: "Features", id: "features" },
          { label: "Workflow", id: "workflow" },
          { label: "Results", id: "results" },
        ].map((x) => (
          <a
            key={x.id}
            href={`#${x.id}`}
            style={{ cursor: "pointer", pointerEvents: "auto" }}
            onClick={(e) => {
              e.preventDefault();
              document
                .getElementById(x.id)
                ?.scrollIntoView({ behavior: "smooth", block: "start" });
            }}
          >
            {x.label}
          </a>
        ))}
      </nav>
      <div style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center" }}>
        <button
          className="btn ghost"
          style={{ pointerEvents: "auto" }}
          onClick={() => navigate("/login")}
        >
          Log in
        </button>
        <button
          className="btn dark"
          style={{ pointerEvents: "auto" }}
          onClick={() => navigate("/signup")}
        >
          Start free →
        </button>
      </div>
    </div>
  );
}

function LandingHero() {
  return (
    <div className="hero-section">
      <div className="hero-spline">
        <SplineAvatar size="100%" />
      </div>

      <FloatingTile style={{ top: 80, left: 60 }} icon={Ico.swords} />
      <FloatingTile style={{ top: 420, left: 120 }} icon={Ico.users} tint="violet" />
      <FloatingTile style={{ top: 140, right: 80 }} icon={Ico.send} tint="amber" />
      <FloatingTile style={{ top: 460, right: 140 }} icon={Ico.target} tint="green" />

      <div className="hero-stack">
        <h1 className="hero-split">
          <span className="hero-word left">WE CAN</span>
          <span className="hero-gap" aria-hidden="true" />
          <span className="hero-word right">SELLNA</span>
        </h1>

        <div className="hero-cta-wrap">
          <DomainCTA />
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              gap: 18,
              marginTop: 14,
              color: "var(--ink-3)",
              fontSize: 12.5,
              // non-interactive — let the cursor reach the Spline beneath
              pointerEvents: "none",
            }}
          >
            <span>✓ No credit card</span>
            <span>✓ First analysis free</span>
            <span>✓ SOC 2 in progress</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function LandingPitch() {
  return (
    <div
      className="pitch-section"
      style={{
        position: "relative",
        zIndex: 2,
        background: "#fff",
        minHeight: "100vh",
        overflow: "hidden",
      }}
    >
      {/* The pitch carries its own (fainter, non-hero) dot-field so the
          animation stays visible on top of the background covering the hero. */}
      <DotField
        baseAlpha={0.2}
        density={30}
        style={{ position: "absolute", inset: 0, zIndex: 0 }}
      />
      <div
        style={{
          position: "relative",
          zIndex: 1,
          maxWidth: 1100,
          margin: "0 auto",
          textAlign: "center",
          padding: "72px 40px 40px",
        }}
      >
        <h2
          style={{
            font: "700 64px var(--font-sans)",
            letterSpacing: "-0.04em",
            margin: 0,
            lineHeight: 1.02,
          }}
        >
          Type a domain.
          <br />
          Ship a{" "}
          <em
            style={{
              fontFamily: "var(--font-display)",
              fontStyle: "italic",
              fontWeight: 400,
              color: "var(--blue)",
            }}
          >
            go-to-market
          </em>
          <br />
          motion in 4 minutes.
        </h2>
        <p
          style={{
            fontSize: 17,
            color: "var(--ink-2)",
            maxWidth: 600,
            margin: "22px auto 0",
            lineHeight: 1.55,
          }}
        >
          Sellna runs nine specialist agents over a single URL — competitor scans,
          ICPs, buyer personas, multi-channel outreach copy — and hands you a
          pipeline that&apos;s ready to send. No CRMs to wire. No prompts to tune.
        </p>

        <div style={{ marginTop: 56, position: "relative" }}>
          <div
            style={{
              border: "1px solid var(--border)",
              borderRadius: 18,
              overflow: "hidden",
              boxShadow:
                "0 30px 80px -20px rgba(20,30,60,.18), 0 2px 0 rgba(255,255,255,.7) inset",
              background: "#fff",
            }}
          >
            <PreviewPanel />
          </div>
          <div
            className="ring-deco"
            style={{
              width: 560,
              height: 560,
              top: -40,
              left: "50%",
              transform: "translateX(-50%)",
              opacity: 0.4,
              zIndex: -1,
            }}
          />
          <div
            className="ring-deco"
            style={{
              width: 760,
              height: 760,
              top: -100,
              left: "50%",
              transform: "translateX(-50%)",
              opacity: 0.25,
              zIndex: -1,
            }}
          />
        </div>
      </div>
    </div>
  );
}

function FloatingTile({
  style,
  icon: Icon,
  tint = "blue",
}: {
  style: CSSProperties;
  icon: IconComponent;
  tint?: string;
}) {
  return (
    <div
      style={{
        position: "absolute",
        ...style,
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "7px 11px 7px 7px",
        borderRadius: 12,
        background: "rgba(255,255,255,.85)",
        backdropFilter: "blur(10px)",
        border: "1px solid var(--border)",
        boxShadow: "0 10px 30px -10px rgba(20,30,60,.15)",
        animation: "waveIn .8s backwards",
      }}
    >
      <div
        className={"icon-tile " + (tint === "blue" ? "" : tint)}
        style={{ width: 24, height: 24, borderRadius: 6 }}
      >
        <Icon style={{ width: 12, height: 12 }} />
      </div>
      <span style={{ fontSize: 11.5, fontWeight: 600 }}>
        {tint === "violet"
          ? "Persona"
          : tint === "amber"
            ? "Outreach"
            : tint === "green"
              ? "ICP"
              : "Competitors"}
      </span>
    </div>
  );
}

function DomainCTA() {
  const navigate = useNavigate();
  const setDraft = usePipelineStore((s) => s.setDraft);
  const [val, setVal] = useState("acme.com");
  const submit = () => {
    setDraft({ website: val });
    navigate("/signup");
  };
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        background: "#fff",
        border: "1px solid var(--border-strong)",
        borderRadius: 14,
        padding: 6,
        boxShadow: "var(--shadow-3)",
        width: "100%",
        maxWidth: 480,
        // The container itself is non-interactive — only the input + button
        // capture the cursor, so the Spline keeps tracking everywhere else.
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          padding: "0 10px",
          color: "var(--ink-4)",
          fontSize: 13,
          fontFamily: "var(--font-mono)",
        }}
      >
        https://
      </div>
      <input
        className="input"
        style={{
          border: "none",
          padding: "12px 4px",
          fontSize: 15,
          boxShadow: "none",
          minWidth: 0,
          pointerEvents: "auto",
        }}
        value={val}
        onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") submit();
        }}
      />
      <button
        className="btn primary"
        style={{
          padding: "10px 16px",
          fontSize: 13.5,
          whiteSpace: "nowrap",
          flexShrink: 0,
          pointerEvents: "auto",
        }}
        onClick={submit}
      >
        Run all agents <Ico.arrow style={{ width: 14, height: 14 }} />
      </button>
    </div>
  );
}

function PreviewPanel() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "180px 1fr", minHeight: 340 }}>
      <div
        style={{
          background: "var(--bg-sidebar)",
          borderRight: "1px solid var(--border)",
          padding: 14,
        }}
      >
        <div
          style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}
        >
          <div className="brand-mark" style={{ width: 22, height: 22, borderRadius: 6 }}>
            <BrandGlyph size={12} />
          </div>
          <div style={{ fontWeight: 700, fontSize: 13 }}>
            sellna<span style={{ color: "var(--blue)" }}>.ai</span>
          </div>
        </div>
        {NAV.slice(0, 5).map((n, i) => (
          <div
            key={n.id}
            className={"sb-item" + (i === 1 ? " active" : "")}
            style={{ padding: "5px 8px", fontSize: 11.5, gap: 7, marginBottom: 2 }}
          >
            <n.icon
              style={{
                width: 13,
                height: 13,
                color: i === 1 ? "var(--blue)" : "var(--ink-3)",
              }}
            />
            <span>{n.label}</span>
          </div>
        ))}
      </div>
      <div style={{ padding: 18, position: "relative" }}>
        <div className="dot-bg" style={{ position: "absolute", inset: 0, opacity: 0.5 }} />
        <div style={{ position: "relative" }}>
          <div
            style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}
          >
            <span className="pill live">
              <span className="dot" />
              Pipeline live · Agent 6 of 9
            </span>
            <span
              style={{ marginLeft: "auto", fontSize: 11.5, color: "var(--ink-3)" }}
            >
              acme.com · t+02:18
            </span>
          </div>
          <div style={{ display: "grid", gap: 6 }}>
            {AGENTS.slice(0, 6).map((a, i) => (
              <AgentRow key={a.id} agent={a} status={i < 5 ? "completed" : "running"} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function LandingMetrics() {
  const m = [
    { v: "4m 12s", l: "Median time, domain → outreach" },
    { v: "9", l: "Specialist agents in the pipeline" },
    { v: "2,400+", l: "Domains analyzed this quarter" },
    { v: "38%", l: "Avg lift on reply rates" },
  ];
  return (
    <div
      id="results"
      style={{
        padding: "40px 40px",
        borderTop: "1px solid var(--border)",
        borderBottom: "1px solid var(--border)",
        background: "transparent",
        scrollMarginTop: 80,
      }}
    >
      <div
        style={{
          maxWidth: 1120,
          margin: "0 auto",
          display: "grid",
          gridTemplateColumns: "repeat(4,1fr)",
          gap: 24,
        }}
      >
        {m.map((x, i) => (
          <div key={i}>
            <div
              style={{
                font: "700 38px var(--font-sans)",
                letterSpacing: "-0.035em",
                background: "linear-gradient(180deg, var(--ink), var(--blue-deep))",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              {x.v}
            </div>
            <div
              style={{
                color: "var(--ink-3)",
                fontSize: 13,
                marginTop: 2,
                maxWidth: 200,
              }}
            >
              {x.l}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function LandingFeatures() {
  const f: { i: IconComponent; t: string; d: string; tint?: string }[] = [
    {
      i: Ico.brain,
      t: "Company intelligence",
      d: "One URL → industry, geo, business model, tech stack, value props. Verified, structured, machine-readable.",
    },
    {
      i: Ico.swords,
      t: "Live competitor scans",
      d: "Auto-discover direct, indirect & adjacent rivals. Headless scrapers pull pricing tiers and feature trees.",
    },
    {
      i: Ico.target,
      t: "Gap-driven ICPs",
      d: "Gap-analysis agent pinpoints unmet positioning, then proposes 3 fit-scored ideal customer profiles.",
      tint: "green",
    },
    {
      i: Ico.users,
      t: "Behavioral personas",
      d: "Each ICP comes with deep buyer personas — goals, pains, objections, day-in-the-life.",
      tint: "violet",
    },
    {
      i: Ico.send,
      t: "Multi-channel copy",
      d: "Cold email, LinkedIn DM and call openers — generated per persona, ready to paste or pipe into your sequencer.",
      tint: "amber",
    },
    {
      i: Ico.chart,
      t: "Feedback loop",
      d: "Open / reply / conversion telemetry flows back. Sellna re-tunes the copy weekly without you lifting a finger.",
    },
  ];
  return (
    <div id="features" style={{ padding: "80px 40px", scrollMarginTop: 80 }}>
      <div style={{ maxWidth: 1120, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <div className="section-h" style={{ justifyContent: "center" }}>
            The pipeline
          </div>
          <h2
            style={{
              font: "700 42px var(--font-sans)",
              letterSpacing: "-0.035em",
              margin: "6px 0 0",
            }}
          >
            Nine agents. One{" "}
            <em
              style={{
                fontFamily: "var(--font-display)",
                fontStyle: "italic",
                fontWeight: 400,
                color: "var(--blue)",
              }}
            >
              handoff.
            </em>
          </h2>
          <p
            style={{
              color: "var(--ink-3)",
              fontSize: 15,
              maxWidth: 540,
              margin: "10px auto 0",
            }}
          >
            Each agent owns a single, narrow job. They pass structured context
            forward — no re-prompting, no lossy summaries.
          </p>
        </div>
        <div
          style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 14 }}
        >
          {f.map((x, i) => (
            <div
              key={i}
              className="card"
              style={{ padding: 22, transition: "transform .25s, box-shadow .25s" }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-4px)";
                e.currentTarget.style.boxShadow = "var(--shadow-3)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "";
                e.currentTarget.style.boxShadow = "";
              }}
            >
              <div
                className={"icon-tile lg " + (x.tint || "")}
                style={{ marginBottom: 14 }}
              >
                <x.i style={{ width: 18, height: 18 }} />
              </div>
              <div
                style={{ fontWeight: 700, fontSize: 15, letterSpacing: "-0.015em" }}
              >
                {x.t}
              </div>
              <div
                style={{
                  color: "var(--ink-3)",
                  fontSize: 13,
                  marginTop: 6,
                  lineHeight: 1.5,
                }}
              >
                {x.d}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function LandingWorkflow() {
  const steps = [
    {
      n: "01",
      t: "Type your domain",
      d: "No CRMs to connect, no spreadsheets to import.",
    },
    { n: "02", t: "Confirm or edit context", d: "4-step wizard. Pre-filled. Editable." },
    {
      n: "03",
      t: "Watch agents stream",
      d: "Tokens, scrape progress and reasoning, in real time.",
    },
    {
      n: "04",
      t: "Send. Measure. Tune.",
      d: "Analytics flow back into the next run, automatically.",
    },
  ];
  return (
    <div
      id="workflow"
      style={{
        padding: "60px 40px",
        background: "transparent",
        borderTop: "1px solid var(--border)",
        borderBottom: "1px solid var(--border)",
        scrollMarginTop: 80,
      }}
    >
      <div style={{ maxWidth: 1120, margin: "0 auto" }}>
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
            marginBottom: 30,
            flexWrap: "wrap",
            gap: 16,
          }}
        >
          <div>
            <div className="section-h">Workflow</div>
            <h2
              style={{
                font: "700 32px var(--font-sans)",
                letterSpacing: "-0.03em",
                margin: "4px 0 0",
              }}
            >
              From cold URL to warm pipeline.
            </h2>
          </div>
          <button className="btn">
            See a live run <Ico.external style={{ width: 13, height: 13 }} />
          </button>
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4,1fr)",
            gap: 14,
            position: "relative",
          }}
        >
          {steps.map((st, i) => (
            <div
              key={i}
              style={{
                padding: 22,
                background: "#fff",
                border: "1px solid var(--border)",
                borderRadius: 16,
                position: "relative",
              }}
            >
              <div
                style={{
                  font: "700 28px var(--font-display)",
                  color: "var(--blue)",
                  letterSpacing: "-0.02em",
                }}
              >
                {st.n}
              </div>
              <div style={{ fontWeight: 700, fontSize: 14, marginTop: 8 }}>{st.t}</div>
              <div style={{ color: "var(--ink-3)", fontSize: 12.5, marginTop: 4 }}>
                {st.d}
              </div>
              {i < 3 && (
                <Ico.arrow
                  style={{
                    position: "absolute",
                    right: -22,
                    top: "50%",
                    transform: "translateY(-50%)",
                    width: 18,
                    height: 18,
                    color: "var(--ink-4)",
                    background: "var(--bg-soft)",
                    zIndex: 2,
                  }}
                />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function LandingCTA() {
  const navigate = useNavigate();
  return (
    <div style={{ padding: "80px 40px" }}>
      <div
        style={{
          maxWidth: 1000,
          margin: "0 auto",
          padding: "56px 48px",
          borderRadius: 24,
          background:
            "linear-gradient(135deg, var(--black) 0%, #1a2244 60%, var(--blue-deep) 100%)",
          color: "#fff",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            opacity: 0.3,
            background:
              "radial-gradient(ellipse at top right, var(--blue-glow), transparent 50%)",
          }}
        />
        <div
          style={{
            position: "relative",
            display: "flex",
            alignItems: "center",
            gap: 32,
            flexWrap: "wrap",
          }}
        >
          <div style={{ flex: "1 1 380px" }}>
            <h2
              style={{
                font: "700 38px var(--font-sans)",
                letterSpacing: "-0.03em",
                margin: 0,
                lineHeight: 1.1,
              }}
            >
              Your next lead lives at{" "}
              <em
                style={{
                  fontFamily: "var(--font-display)",
                  fontStyle: "italic",
                  fontWeight: 400,
                  color: "var(--blue-glow)",
                }}
              >
                a URL you haven&apos;t typed yet.
              </em>
            </h2>
            <p style={{ opacity: 0.7, fontSize: 15, marginTop: 14, maxWidth: 480 }}>
              First analysis is free. No credit card. 4 minutes to your first
              sequenced outreach pack.
            </p>
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <button
              className="btn primary"
              style={{ padding: "12px 18px", fontSize: 14 }}
              onClick={() => navigate("/signup")}
            >
              Start free <Ico.arrow style={{ width: 14, height: 14 }} />
            </button>
            <button
              className="btn"
              style={{
                padding: "12px 18px",
                fontSize: 14,
                background: "rgba(255,255,255,.08)",
                color: "#fff",
                borderColor: "rgba(255,255,255,.18)",
              }}
              onClick={() => navigate("/login")}
            >
              Book a demo
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function LandingFooter() {
  return (
    <div
      style={{
        padding: "40px",
        borderTop: "1px solid var(--border)",
        color: "var(--ink-3)",
        fontSize: 12.5,
        display: "flex",
        alignItems: "center",
        gap: 14,
        flexWrap: "wrap",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div className="brand-mark" style={{ width: 22, height: 22, borderRadius: 6 }}>
          <BrandGlyph size={12} />
        </div>
        <span style={{ fontWeight: 600, color: "var(--ink-2)" }}>sellna.ai</span>
      </div>
      <span>© 2026 Sellna Labs, Inc.</span>
      <span style={{ marginLeft: "auto", display: "flex", gap: 18 }}>
        {["Privacy", "Terms", "Security", "Status"].map((x) => (
          <a key={x}>{x}</a>
        ))}
      </span>
      <span
        style={{
          flex: "1 1 100%",
          color: "var(--ink-4)",
          fontSize: 11.5,
          fontFamily: "var(--font-mono)",
          marginTop: 6,
        }}
      >
        Sellna may scrape publicly accessible competitor sites. We respect
        robots.txt and rate-limit accordingly.
      </span>
    </div>
  );
}


import type { CSSProperties, ReactNode } from "react";
import { Ico, type IconComponent } from "./icons";

/* ---------- nav config ---------- */
export const NAV: {
  id: string;
  label: string;
  icon: IconComponent;
  route: string;
  badge?: string;
}[] = [
  { id: "dashboard", label: "Dashboard", icon: Ico.home, route: "/app" },
  {
    id: "company",
    label: "Company Intelligence",
    icon: Ico.brain,
    route: "/company",
    badge: "LIVE",
  },
  { id: "competitors", label: "Competitors", icon: Ico.swords, route: "/competitors" },
  { id: "icp", label: "ICP Generator", icon: Ico.target, route: "/icp" },
  { id: "personas", label: "Personas", icon: Ico.users, route: "/personas" },
  { id: "outreach", label: "Outreach", icon: Ico.send, route: "/outreach" },
  { id: "analytics", label: "Analytics", icon: Ico.chart, route: "/analytics" },
  {
    id: "web-scraper",
    label: "Web Scraper",
    icon: Ico.globe,
    route: "/web-scraper",
  },
  {
    id: "social-scraper",
    label: "Social Scraper",
    icon: Ico.atSign,
    route: "/social-scraper",
  },
];

/* ---------- agents ---------- */
export const AGENTS = [
  { id: 1, name: "Domain Resolver", desc: "Verifying & enriching domain" },
  { id: 2, name: "Company Profiler", desc: "Industry, geo, model, stack" },
  { id: 3, name: "Product Analyst", desc: "Features, problem, value prop" },
  { id: 4, name: "Competitor Hunter", desc: "Finds direct & adjacent rivals" },
  { id: 5, name: "Web Scraper", desc: "Pulls competitor structured data" },
  { id: 6, name: "Gap Analyst", desc: "Maps unmet positioning gaps" },
  { id: 7, name: "ICP Generator", desc: "3 fit-scored ICPs from gaps" },
  { id: 8, name: "Persona Builder", desc: "Buyer goals, pains, objections" },
  { id: 9, name: "Outreach Composer", desc: "Email, LinkedIn, call openers" },
];

export type AgentStatus = "pending" | "running" | "completed";

/* ---------- Card ---------- */
export function Card({
  title,
  subtitle,
  right,
  children,
  className = "",
  noPad = false,
  style,
  fill = false,
  bodyScroll = true,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  right?: ReactNode;
  children?: ReactNode;
  className?: string;
  noPad?: boolean;
  style?: CSSProperties;
  /** Fill the parent's height; the body flexes to the remaining space. */
  fill?: boolean;
  /** When fill, whether the body itself scrolls (true) or the page handles it (false). */
  bodyScroll?: boolean;
}) {
  const cardStyle: CSSProperties = fill
    ? { height: "100%", display: "flex", flexDirection: "column", ...style }
    : style || {};
  const bodyStyle: CSSProperties = {
    ...(noPad ? { padding: 0 } : {}),
    ...(fill
      ? {
          flex: 1,
          minHeight: 0,
          overflowY: bodyScroll ? "auto" : "hidden",
          ...(bodyScroll ? {} : { display: "flex", flexDirection: "column" }),
        }
      : {}),
  };
  return (
    <div className={"card " + className} style={cardStyle}>
      {(title || right) && (
        <div className="hd" style={fill ? { flexShrink: 0 } : undefined}>
          <div>
            <div className="t">{title}</div>
            {subtitle && <div className="s">{subtitle}</div>}
          </div>
          <div style={{ marginLeft: "auto" }}>{right}</div>
        </div>
      )}
      <div className="bd" style={bodyStyle}>
        {children}
      </div>
    </div>
  );
}

/* ---------- SectionH ---------- */
export function SectionH({
  title,
  kicker,
  right,
}: {
  title: ReactNode;
  kicker?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "space-between",
        marginBottom: 12,
        gap: 12,
      }}
    >
      <div>
        {kicker && <div className="section-h">{kicker}</div>}
        <h2
          style={{
            margin: 0,
            fontSize: 16,
            letterSpacing: "-0.02em",
            fontWeight: 700,
          }}
        >
          {title}
        </h2>
      </div>
      {right}
    </div>
  );
}

/* ---------- Sparkline ---------- */
export function Sparkline({
  points,
  tone = "blue",
  w = 64,
  h = 22,
}: {
  points: number[];
  tone?: string;
  w?: number;
  h?: number;
}) {
  const min = Math.min(...points);
  const max = Math.max(...points);
  const r = max - min || 1;
  const step = w / (points.length - 1);
  const path = points
    .map(
      (p, i) =>
        `${i === 0 ? "M" : "L"} ${i * step} ${h - ((p - min) / r) * h}`
    )
    .join(" ");
  const color =
    tone === "violet"
      ? "var(--violet)"
      : tone === "amber"
        ? "var(--amber)"
        : tone === "green"
          ? "var(--green)"
          : "var(--blue)";
  const soft =
    tone === "violet"
      ? "oklch(95% 0.04 295)"
      : tone === "amber"
        ? "oklch(96% 0.07 80)"
        : tone === "green"
          ? "oklch(95% 0.05 150)"
          : "var(--blue-soft)";
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ overflow: "visible" }}>
      <path d={`${path} L ${w} ${h} L 0 ${h} Z`} fill={soft} opacity=".7" />
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle
        cx={w}
        cy={h - ((points[points.length - 1] - min) / r) * h}
        r="2.2"
        fill={color}
      />
    </svg>
  );
}

/* ---------- StatCard ---------- */
export function StatCard({
  label,
  value,
  delta,
  deltaTone = "up",
  icon: Icon,
  tint = "blue",
  spark,
}: {
  label: ReactNode;
  value: ReactNode;
  delta?: ReactNode;
  deltaTone?: "up" | "down" | "neutral";
  icon?: IconComponent;
  tint?: string;
  spark?: number[];
}) {
  const shineStyle: CSSProperties =
    tint === "violet"
      ? { background: "radial-gradient(circle, oklch(95% 0.04 295), transparent 70%)" }
      : tint === "amber"
        ? { background: "radial-gradient(circle, oklch(96% 0.07 80), transparent 70%)" }
        : tint === "green"
          ? { background: "radial-gradient(circle, oklch(95% 0.05 150), transparent 70%)" }
          : {};
  return (
    <div className="stat">
      <div className="shine" style={shineStyle} />
      <div className="top">
        <div className="lbl">{label}</div>
        {Icon && (
          <div
            className={"icon-tile " + (tint === "blue" ? "" : tint)}
            style={{ width: 26, height: 26, borderRadius: 7 }}
          >
            <Icon style={{ width: 13, height: 13 }} />
          </div>
        )}
      </div>
      <div className="val">{value}</div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        {delta && (
          <div
            className={
              "delta " +
              (deltaTone === "down" ? "down" : deltaTone === "neutral" ? "neutral" : "")
            }
          >
            {deltaTone === "up" ? "↑" : deltaTone === "down" ? "↓" : "·"} {delta}
          </div>
        )}
        {spark && <Sparkline points={spark} tone={tint} />}
      </div>
    </div>
  );
}

/* ---------- AgentRow ---------- */
export function AgentRow({
  agent,
  status,
}: {
  agent: { id: number; name: string; desc: string };
  status: AgentStatus;
}) {
  return (
    <div className={"agent " + status}>
      <div className="num">{String(agent.id).padStart(2, "0")}</div>
      <div style={{ minWidth: 0 }}>
        <div className="name">{agent.name}</div>
        <div className="desc">{agent.desc}</div>
      </div>
      <div className="status">
        {status === "pending" && (
          <span className="pill">
            <span className="dot" style={{ background: "var(--ink-4)" }} />
            pending
          </span>
        )}
        {status === "running" && (
          <span className="pill blue">
            <span className="dot" style={{ background: "var(--blue)" }} />
            thinking ·{" "}
            <span
              className="spin"
              style={{ width: 10, height: 10, marginLeft: 4, verticalAlign: "middle" }}
            />
          </span>
        )}
        {status === "completed" && (
          <span className="pill green">
            <Ico.check style={{ width: 11, height: 11 }} /> done
          </span>
        )}
      </div>
    </div>
  );
}

/* ---------- EmptyState ---------- */
export function EmptyState({
  icon: Icon = Ico.sparkles,
  title,
  body,
  action,
}: {
  icon?: IconComponent;
  title: ReactNode;
  body: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div
      style={{
        padding: "40px 28px",
        textAlign: "center",
        borderRadius: 14,
        border: "1px dashed var(--border-strong)",
        background: "#fff",
      }}
    >
      <div className="icon-tile lg" style={{ margin: "0 auto 12px" }}>
        <Icon style={{ width: 20, height: 20 }} />
      </div>
      <div style={{ fontWeight: 700, fontSize: 14, letterSpacing: "-0.01em" }}>
        {title}
      </div>
      <div
        style={{
          color: "var(--ink-3)",
          fontSize: 12.5,
          maxWidth: 340,
          margin: "4px auto 14px",
        }}
      >
        {body}
      </div>
      {action}
    </div>
  );
}

/* ---------- Tabs ---------- */
export function Tabs({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: string; label: ReactNode; icon?: IconComponent }[];
  value: string;
  onChange?: (id: string) => void;
}) {
  return (
    <div className="tabs">
      {tabs.map((t) => (
        <button
          key={t.id}
          className={value === t.id ? "on" : ""}
          onClick={() => onChange && onChange(t.id)}
        >
          {t.icon && <t.icon style={{ width: 13, height: 13 }} />}
          {t.label}
        </button>
      ))}
    </div>
  );
}

/* ---------- Ring ---------- */
export function Ring({
  value = 70,
  size = 64,
  stroke = 7,
  label,
}: {
  value?: number;
  size?: number;
  stroke?: number;
  label?: string;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const off = c - (value / 100) * c;
  const tone =
    value >= 80
      ? "var(--green)"
      : value >= 60
        ? "var(--blue)"
        : value >= 40
          ? "var(--amber)"
          : "var(--red)";
  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--border)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={tone}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={off}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dashoffset .8s cubic-bezier(.2,.7,.3,1)" }}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          font: "700 18px var(--font-sans)",
          letterSpacing: "-0.02em",
          color: tone,
        }}
      >
        {value}
        {label && (
          <div
            style={{
              fontSize: 9,
              color: "var(--ink-3)",
              fontWeight: 600,
              letterSpacing: "0.05em",
            }}
          >
            {label}
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------- Steps (company wizard) ---------- */
export function Steps({ current = 0 }: { current?: number }) {
  const steps = [
    { id: 0, label: "Domain" },
    { id: 1, label: "Company" },
    { id: 2, label: "Product" },
    { id: 3, label: "Launch" },
  ];
  return (
    <div className="steps">
      {steps.map((st, i) => (
        <div key={st.id} style={{ display: "contents" }}>
          <div className={"step " + (i < current ? "done" : i === current ? "cur" : "")}>
            <div className="ring">
              {i < current ? <Ico.check style={{ width: 13, height: 13 }} /> : i + 1}
            </div>
            <div className="lab">{st.label}</div>
          </div>
          {i < steps.length - 1 && <div className={"bar " + (i < current ? "on" : "")} />}
        </div>
      ))}
    </div>
  );
}

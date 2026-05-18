"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Ico, type IconComponent } from "@/components/icons";
import { Card, Sparkline, EmptyState } from "@/components/primitives";
import { analyticsApi } from "@/lib/api";
import { usePipelineStore } from "@/store/pipelineStore";

function BigStat({
  label,
  value,
  delta,
  icon: Icon,
  tint,
  spark,
}: {
  label: string;
  value: string;
  delta?: string;
  icon: IconComponent;
  tint: string;
  spark?: number[];
}) {
  const shine =
    tint === "violet"
      ? { background: "radial-gradient(circle, oklch(95% 0.04 295), transparent 70%)" }
      : tint === "amber"
        ? { background: "radial-gradient(circle, oklch(96% 0.07 80), transparent 70%)" }
        : tint === "green"
          ? { background: "radial-gradient(circle, oklch(95% 0.05 150), transparent 70%)" }
          : {};
  return (
    <div className="stat">
      <div className="shine" style={shine} />
      <div className="top">
        <div className="lbl">{label}</div>
        <div
          className={"icon-tile " + (tint === "blue" ? "" : tint)}
          style={{ width: 28, height: 28, borderRadius: 7 }}
        >
          <Icon style={{ width: 13, height: 13 }} />
        </div>
      </div>
      <div className="val" style={{ fontSize: 30 }}>
        {value}
      </div>
      {(delta || (spark && spark.length > 0)) && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          {delta ? <span className="delta">↑ {delta}</span> : <span />}
          {spark && spark.length > 0 && (
            <Sparkline points={spark} tone={tint} w={80} h={24} />
          )}
        </div>
      )}
    </div>
  );
}

function LegendDot({ c, l }: { c: string; l: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        color: "var(--ink-2)",
        fontWeight: 500,
      }}
    >
      <span style={{ width: 8, height: 8, borderRadius: 2, background: c }} />
      {l}
    </span>
  );
}

function TrendChart({
  open,
  reply,
  conv,
  weeks,
}: {
  open: number[];
  reply: number[];
  conv: number[];
  weeks: string[];
}) {
  const W = 460;
  const H = 200;
  const P = 24;
  if (open.length === 0) {
    return (
      <div
        style={{
          height: 200,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 12.5,
          color: "var(--ink-3)",
        }}
      >
        Not enough weekly data to chart yet.
      </div>
    );
  }
  const max = Math.max(50, ...open, ...reply, ...conv);
  const x = (i: number) => P + (i * (W - P * 2)) / Math.max(1, weeks.length - 1);
  const y = (v: number) => H - P - (v / max) * (H - P * 2);
  const path = (a: number[]) =>
    a.map((v, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(v)}`).join(" ");
  const last = open.length - 1;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block" }}>
      <defs>
        <linearGradient id="grad-blue" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="var(--blue)" stopOpacity=".35" />
          <stop offset="100%" stopColor="var(--blue)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, max / 2, max].map((v, i) => (
        <g key={i}>
          <line
            x1={P}
            x2={W - P}
            y1={y(v)}
            y2={y(v)}
            stroke="var(--border)"
            strokeDasharray="2 4"
          />
          <text
            x={P - 6}
            y={y(v) + 3}
            fontSize="9"
            textAnchor="end"
            fill="var(--ink-4)"
            fontFamily="var(--font-mono)"
          >
            {Math.round(v)}%
          </text>
        </g>
      ))}
      {weeks.map((w, i) => (
        <text
          key={w + i}
          x={x(i)}
          y={H - 6}
          fontSize="9.5"
          textAnchor="middle"
          fill="var(--ink-3)"
          fontFamily="var(--font-mono)"
        >
          {w}
        </text>
      ))}
      <path
        d={`${path(open)} L ${x(last)} ${H - P} L ${P} ${H - P} Z`}
        fill="url(#grad-blue)"
      />
      <path
        d={path(open)}
        fill="none"
        stroke="var(--blue)"
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <path
        d={path(reply)}
        fill="none"
        stroke="var(--violet)"
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <path
        d={path(conv)}
        fill="none"
        stroke="var(--green)"
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={x(last)} cy={y(open[last])} r="3.5" fill="var(--blue)" />
      <circle cx={x(last)} cy={y(reply[last])} r="3.5" fill="var(--violet)" />
      <circle cx={x(last)} cy={y(conv[last])} r="3.5" fill="var(--green)" />
      <g>
        <rect
          x={x(last) + 8}
          y={y(open[last]) - 12}
          width="56"
          height="22"
          rx="5"
          fill="var(--ink)"
        />
        <text
          x={x(last) + 36}
          y={y(open[last]) + 3}
          fontSize="10"
          fill="#fff"
          textAnchor="middle"
          fontWeight="600"
        >
          {open[last].toFixed(1)}%
        </text>
      </g>
    </svg>
  );
}

function ChannelBars({
  data,
}: {
  data: { ch: string; op: number; rp: number; cv: number }[];
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 14,
        marginTop: 4,
      }}
    >
      {data.map((d) => (
        <div key={d.ch}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: 12,
              marginBottom: 6,
            }}
          >
            <strong>{d.ch}</strong>
            <span
              style={{ fontFamily: "var(--font-mono)", color: "var(--ink-3)" }}
            >
              {d.op ? `${d.op}% open · ` : ""}
              {d.rp}% reply · {d.cv}% conv.
            </span>
          </div>
          <div style={{ display: "flex", gap: 4, height: 22 }}>
            <div
              style={{
                width: `${d.op * 1.3}%`,
                background: "var(--blue)",
                borderRadius: 5,
                display: "flex",
                alignItems: "center",
                justifyContent: "flex-end",
                padding: "0 8px",
                color: "#fff",
                font: "700 10px var(--font-mono)",
              }}
            >
              {d.op ? `${d.op}%` : ""}
            </div>
            <div
              style={{
                width: `${d.rp * 2.5}%`,
                background: "var(--violet)",
                borderRadius: 5,
                display: "flex",
                alignItems: "center",
                justifyContent: "flex-end",
                padding: "0 8px",
                color: "#fff",
                font: "700 10px var(--font-mono)",
              }}
            >
              {d.rp}%
            </div>
            <div
              style={{
                width: `${d.cv * 5}%`,
                background: "var(--green)",
                borderRadius: 5,
                display: "flex",
                alignItems: "center",
                justifyContent: "flex-end",
                padding: "0 8px",
                color: "#fff",
                font: "700 10px var(--font-mono)",
              }}
            >
              {d.cv}%
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function Bar({
  val,
  max = 100,
  label,
  tone = "blue",
}: {
  val: number;
  max?: number;
  label: string;
  tone?: string;
}) {
  const w = Math.min(100, (val / max) * 100);
  const color = tone === "violet" ? "var(--violet)" : "var(--blue)";
  const soft = tone === "violet" ? "oklch(95% 0.04 295)" : "var(--blue-soft)";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        minWidth: 120,
      }}
    >
      <div
        style={{
          flex: 1,
          height: 6,
          borderRadius: 3,
          background: soft,
          overflow: "hidden",
          position: "relative",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            width: `${w}%`,
            background: color,
            borderRadius: 3,
          }}
        />
      </div>
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11.5,
          color: "var(--ink-2)",
          width: 42,
          textAlign: "right",
        }}
      >
        {label}
      </span>
    </div>
  );
}

const ICON_BY_CHANNEL: Record<string, { icon: IconComponent; tint: string }> = {
  "Cold email": { icon: Ico.inbox, tint: "blue" },
  cold_email: { icon: Ico.inbox, tint: "blue" },
  "LinkedIn DM": { icon: Ico.linkedin, tint: "violet" },
  linkedin: { icon: Ico.linkedin, tint: "violet" },
  "Call opener": { icon: Ico.phone, tint: "amber" },
  call_opener: { icon: Ico.phone, tint: "amber" },
};

export default function AnalyticsPage() {
  const { companyId } = usePipelineStore();

  const { data } = useQuery({
    queryKey: ["analytics", "performance", companyId],
    queryFn: () => analyticsApi.performance(companyId as string),
    enabled: !!companyId,
    refetchInterval: 10_000,
    retry: false,
  });

  const trend = useMemo(() => {
    if (data?.weekly && data.weekly.length > 1) {
      return {
        weeks: data.weekly.map((_, i) => `W${i + 1}`),
        open: data.weekly.map((w) => Math.round(w.avg_open_rate * 1000) / 10),
        reply: data.weekly.map((w) => Math.round(w.avg_reply_rate * 1000) / 10),
        conv: data.weekly.map(
          (w) => Math.round(w.avg_conversion_rate * 1000) / 10
        ),
      };
    }
    return {
      weeks: [] as string[],
      open: [] as number[],
      reply: [] as number[],
      conv: [] as number[],
    };
  }, [data]);

  const channelRows = useMemo(() => {
    if (data?.by_channel && Object.keys(data.by_channel).length > 0) {
      return Object.entries(data.by_channel).map(([ch, s]) => ({
        ch,
        sent: String(s.count),
        op: Math.round(s.avg_open_rate * 1000) / 10,
        rp: Math.round(s.avg_reply_rate * 1000) / 10,
        cv: Math.round(s.avg_conversion_rate * 1000) / 10,
      }));
    }
    return [] as { ch: string; sent: string; op: number; rp: number; cv: number }[];
  }, [data]);

  const totalAssets = data?.total_assets ?? 0;
  const empty = !companyId || channelRows.length === 0;
  const avg = (key: "op" | "rp" | "cv") =>
    channelRows.length
      ? channelRows.reduce((a, c) => a + c[key], 0) / channelRows.length
      : 0;

  return (
    <>
      <div className="page-h">
        <div>
          <div className="section-h">Performance · last 8 weeks</div>
          <h1>How outreach is actually performing</h1>
          <p>
            The feedback loop. These numbers flow back into the Outreach Composer
            agent every Monday.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn">
            <Ico.filter style={{ width: 13, height: 13 }} /> Filter
          </button>
          <button className="btn primary">
            <Ico.download style={{ width: 13, height: 13 }} /> Export
          </button>
        </div>
      </div>

      {empty ? (
        <EmptyState
          icon={Ico.chart}
          title={
            !companyId ? "No active company" : "No outreach analytics yet"
          }
          body={
            !companyId
              ? "Run a company analysis (or pick one from the sidebar) to track outreach performance."
              : "Generate and send outreach for this company — performance metrics will appear here once there's data."
          }
        />
      ) : (
        <>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4,1fr)",
          gap: 14,
          marginBottom: 14,
        }}
        className="wave"
      >
        <BigStat
          label="Avg open rate"
          value={`${avg("op").toFixed(1)}%`}
          icon={Ico.inbox}
          tint="blue"
          spark={trend.open}
        />
        <BigStat
          label="Avg reply rate"
          value={`${avg("rp").toFixed(1)}%`}
          icon={Ico.send}
          tint="violet"
          spark={trend.reply}
        />
        <BigStat
          label="Avg conversion"
          value={`${avg("cv").toFixed(1)}%`}
          icon={Ico.target}
          tint="green"
          spark={trend.conv}
        />
        <BigStat
          label="Assets tracked"
          value={String(totalAssets)}
          icon={Ico.layers}
          tint="amber"
        />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.4fr 1fr",
          gap: 14,
          marginBottom: 14,
        }}
      >
        <Card
          title="Weekly performance trend"
          subtitle="Open · Reply · Conversion"
          right={
            <div style={{ display: "flex", gap: 8, fontSize: 11.5 }}>
              <LegendDot c="var(--blue)" l="Open" />
              <LegendDot c="var(--violet)" l="Reply" />
              <LegendDot c="var(--green)" l="Conv." />
            </div>
          }
        >
          <TrendChart
            open={trend.open}
            reply={trend.reply}
            conv={trend.conv}
            weeks={trend.weeks}
          />
        </Card>
        <Card title="Channel performance" subtitle="Open · Reply · Conv. by channel">
          <ChannelBars
            data={channelRows.map((r) => ({
              ch: r.ch,
              op: r.op,
              rp: r.rp,
              cv: r.cv,
            }))}
          />
        </Card>
      </div>

      <Card
        title="Detailed breakdown"
        subtitle="Per-channel performance · last 8 weeks"
      >
        <table
          style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}
        >
          <thead>
            <tr
              style={{
                color: "var(--ink-3)",
                textAlign: "left",
                fontSize: 11,
                letterSpacing: ".05em",
              }}
            >
              {["Channel", "Sent", "Opened %", "Replied %", "Converted", "Conv. rate", "vs last wk"].map(
                (h) => (
                  <th
                    key={h}
                    style={{
                      padding: "10px 8px",
                      fontWeight: 600,
                      textTransform: "uppercase",
                    }}
                  >
                    {h}
                  </th>
                )
              )}
            </tr>
          </thead>
          <tbody>
            {channelRows.map((r, i) => {
              const meta =
                ICON_BY_CHANNEL[r.ch] || { icon: Ico.inbox, tint: "blue" };
              return (
                <tr key={i} style={{ borderTop: "1px solid var(--border)" }}>
                  <td style={{ padding: "12px 8px" }}>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                      }}
                    >
                      <div
                        className={"icon-tile " + meta.tint}
                        style={{ width: 24, height: 24, borderRadius: 6 }}
                      >
                        <meta.icon style={{ width: 12, height: 12 }} />
                      </div>
                      <strong>{r.ch}</strong>
                    </div>
                  </td>
                  <td
                    style={{ padding: "12px 8px", fontFamily: "var(--font-mono)" }}
                  >
                    {r.sent}
                  </td>
                  <td style={{ padding: "12px 8px" }}>
                    <Bar
                      val={r.op}
                      max={50}
                      label={r.op ? `${r.op}%` : "—"}
                    />
                  </td>
                  <td style={{ padding: "12px 8px" }}>
                    <Bar
                      val={r.rp}
                      max={20}
                      label={`${r.rp}%`}
                      tone="violet"
                    />
                  </td>
                  <td
                    style={{ padding: "12px 8px", fontFamily: "var(--font-mono)" }}
                  >
                    {Math.round((r.cv / 100) * parseInt(r.sent.replace(/,/g, "")) || 0)}
                  </td>
                  <td
                    style={{
                      padding: "12px 8px",
                      fontWeight: 700,
                      color: "var(--green)",
                    }}
                  >
                    {r.cv}%
                  </td>
                  <td
                    style={{
                      padding: "12px 8px",
                      fontWeight: 600,
                      color: "var(--ink-4)",
                    }}
                  >
                    —
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
        </>
      )}
    </>
  );
}

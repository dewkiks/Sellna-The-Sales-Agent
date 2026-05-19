import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTopBarSlot } from "@/components/AppShell";
import { Ico, type IconComponent } from "@/components/icons";
import { Card, StatCard, AGENTS } from "@/components/primitives";
import { LiveLogs } from "@/components/LiveLogs";
import { dashboardApi, pipelineApi } from "@/lib/api";
import { usePipelineStore } from "@/store/pipelineStore";
import { useAuth } from "@/context/AuthContext";

function relTime(value: string): string {
  const t = new Date(value).getTime();
  if (Number.isNaN(t)) return value; // already human-readable
  const diff = Date.now() - t;
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} h ago`;
  return `${Math.floor(h / 24)} d ago`;
}

function SmallStat({
  label,
  value,
  sub,
  tone = "blue",
  progress,
}: {
  label: string;
  value: string;
  sub: string;
  tone?: "blue" | "green" | "violet";
  progress?: number;
}) {
  return (
    <div className="stat">
      <div className="top">
        <div className="lbl">{label}</div>
        {tone === "green" && (
          <span className="pill green">
            <span className="dot" style={{ background: "var(--green)" }} />
            OK
          </span>
        )}
        {tone === "violet" && <span className="pill violet">Insight</span>}
        {tone === "blue" && <span className="pill blue">Running</span>}
      </div>
      <div style={{ font: "700 24px var(--font-sans)", letterSpacing: "-0.025em" }}>
        {value}
      </div>
      {progress != null && (
        <div
          style={{
            height: 6,
            borderRadius: 3,
            background: "var(--bg-muted)",
            overflow: "hidden",
            position: "relative",
            marginTop: 2,
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: 0,
              width: `${progress}%`,
              background: "linear-gradient(90deg, var(--blue-glow), var(--blue))",
              borderRadius: 3,
              animation: "shimmer 2s infinite",
            }}
          />
        </div>
      )}
      <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>{sub}</div>
    </div>
  );
}

const ACTIVITY_META: Record<string, { icon: IconComponent; tint: string }> = {
  company: { icon: Ico.building, tint: "blue" },
  competitor: { icon: Ico.swords, tint: "violet" },
  icp: { icon: Ico.target, tint: "green" },
  persona: { icon: Ico.users, tint: "amber" },
  outreach: { icon: Ico.send, tint: "blue" },
  gap: { icon: Ico.target, tint: "violet" },
};

export default function DashboardPage() {
  const navigate = useNavigate();
  const { jobId, companyName } = usePipelineStore();
  const { user } = useAuth();
  const firstName =
    user?.full_name?.split(" ")[0] ||
    user?.email?.split("@")[0] ||
    "";

  const { data: summary } = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: dashboardApi.getSummary,
    refetchInterval: 10_000,
    retry: false,
  });

  const { data: activity } = useQuery({
    queryKey: ["dashboard", "activity"],
    queryFn: () => dashboardApi.getActivity(20),
    refetchInterval: 10_000,
    retry: false,
  });

  const { data: statusData } = useQuery({
    queryKey: ["pipelineStatus", jobId],
    queryFn: () => pipelineApi.getPipelineStatus(jobId as string),
    enabled: !!jobId,
    refetchInterval: 3000,
    retry: false,
  });

  const counts = summary?.counts;
  const total = AGENTS.length;
  const state = statusData?.state;
  const isSuccess = state === "SUCCESS";
  const isActive =
    !!jobId &&
    (state === "RUNNING" ||
      state === "STARTED" ||
      state === "PENDING" ||
      state === "RETRY");
  const progress = isSuccess ? 100 : isActive ? statusData?.progress ?? 0 : 0;
  const completed = isSuccess
    ? total
    : Math.min(total, Math.floor((progress / 100) * total));

  const events = activity?.events ?? [];

  useTopBarSlot(
    isActive ? (
      <span className="pill live">
        <span className="dot" />
        Pipeline live · Agent {Math.min(completed + 1, total)}/{total}
      </span>
    ) : isSuccess ? (
      <span className="pill green">
        <span className="dot" style={{ background: "var(--green)" }} />
        Pipeline complete
      </span>
    ) : (
      <span className="pill">
        <span className="dot" style={{ background: "var(--ink-4)" }} />
        No active run
      </span>
    ),
    [isActive, isSuccess, completed, total],
  );

  return (
    <>
      <div className="page-h" style={{ flexShrink: 0 }}>
        <div>
          <div className="section-h">
            Good morning{firstName ? `, ${firstName}` : ""}
          </div>
          <h1>Command Center</h1>
          <p>
            {isActive
              ? "9 agents are scanning your domain — first results streaming in."
              : isSuccess
                ? "Pipeline complete — all 9 agents have finished this run."
                : "No pipeline running. Start a new analysis to activate the 9-agent pipeline."}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn">
            <Ico.download style={{ width: 13, height: 13 }} /> Export
          </button>
          <button className="btn primary" onClick={() => navigate("/company")}>
            <Ico.plus style={{ width: 13, height: 13 }} /> New analysis
          </button>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4,1fr)",
          gap: 14,
          marginBottom: 14,
          flexShrink: 0,
        }}
        className="wave"
      >
        <StatCard
          label="Companies analyzed"
          value={counts?.companies_analyzed ?? 0}
          icon={Ico.building}
          tint="blue"
        />
        <StatCard
          label="Competitors found"
          value={counts?.competitors_found ?? 0}
          icon={Ico.swords}
          tint="violet"
        />
        <StatCard
          label="ICPs generated"
          value={counts?.icps_generated ?? 0}
          icon={Ico.target}
          tint="green"
        />
        <StatCard
          label="Outreach assets"
          value={counts?.outreach_assets_generated ?? 0}
          icon={Ico.send}
          tint="amber"
        />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3,1fr)",
          gap: 14,
          marginBottom: 18,
          flexShrink: 0,
        }}
        className="wave"
      >
        <SmallStat
          label="Market gaps found"
          value={String(counts?.market_gaps_found ?? 0)}
          tone="violet"
          sub="From the latest gap analysis"
        />
        <SmallStat
          label="Pipeline progress"
          value={`${progress}%`}
          tone="blue"
          sub={
            isActive
              ? `Agent ${Math.min(completed + 1, total)} of ${total} running`
              : isSuccess
                ? "All agents complete"
                : "No active run"
          }
          progress={progress}
        />
        <SmallStat
          label="System status"
          value={summary ? "All systems OK" : "Connecting…"}
          tone="green"
          sub={summary ? "Backend connected" : "Reaching the backend…"}
        />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.1fr 1fr",
          gap: 14,
          flex: 1,
          minHeight: 0,
        }}
      >
        <Card
          fill
          bodyScroll={false}
          title="Pipeline status"
          subtitle={companyName ? `Live run · ${companyName}` : "Live run"}
          right={
            isActive ? (
              <span className="pill live">
                <span className="dot" />
                LIVE
              </span>
            ) : (
              <span className="pill">
                <span className="dot" style={{ background: "var(--ink-4)" }} />
                {isSuccess ? "DONE" : "IDLE"}
              </span>
            )
          }
        >
          <LiveLogs />
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              marginTop: 12,
              paddingTop: 12,
              borderTop: "1px solid var(--border)",
              flexShrink: 0,
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
                  width: `${progress}%`,
                  background: "linear-gradient(90deg, var(--blue-glow), var(--blue))",
                  borderRadius: 3,
                }}
              />
            </div>
            <div style={{ fontSize: 11.5, fontWeight: 600, color: "var(--ink-3)" }}>
              {completed} / {total} done
            </div>
          </div>
        </Card>

        <Card
          fill
          title="Recent activity"
          subtitle="Live feed across all your companies"
          right={
            <button className="btn ghost" style={{ padding: "4px 8px" }}>
              <Ico.refresh style={{ width: 13, height: 13 }} />
            </button>
          }
        >
          <div style={{ display: "flex", flexDirection: "column" }}>
            {events.length === 0 && (
              <div
                style={{
                  fontSize: 12.5,
                  color: "var(--ink-3)",
                  padding: "16px 0",
                }}
              >
                No activity yet — run a pipeline analysis to see live events
                here.
              </div>
            )}
            {events.map((it, i) => {
              const meta = ACTIVITY_META[it.type] || ACTIVITY_META.company;
              return (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "10px 0",
                    borderTop: i ? "1px solid var(--border)" : "none",
                  }}
                >
                  <div
                    className={"icon-tile " + (meta.tint === "blue" ? "" : meta.tint)}
                    style={{ width: 28, height: 28, borderRadius: 8 }}
                  >
                    <meta.icon style={{ width: 13, height: 13 }} />
                  </div>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 600 }}>{it.action}</div>
                    <div
                      style={{
                        fontSize: 11.5,
                        color: "var(--ink-3)",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {it.target}
                    </div>
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--ink-4)",
                      whiteSpace: "nowrap",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    {relTime(it.created_at)}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>
    </>
  );
}

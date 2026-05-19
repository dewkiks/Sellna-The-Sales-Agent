import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Ico, BrandGlyph } from "./icons";
import { NAV, AGENTS } from "./primitives";
import { companyApi } from "@/lib/api";
import { usePipelineStore } from "@/store/pipelineStore";
import { useAgentStream } from "@/hooks/useAgentStream";
import { toast } from "@/lib/toast";

interface CompanyRow {
  id: string;
  name: string;
  industry: string;
  created_at: string;
  has_analysis: boolean;
}

function relTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const diff = Date.now() - t;
  const m = Math.floor(diff / 60000);
  if (m < 1) return "now";
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

function CompanySwitcher({ companies }: { companies: CompanyRow[] }) {
  const { companyId, companyName, setCompanyId, setCompanyName } =
    usePipelineStore();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const active =
    companies.find((c) => c.id === companyId) || null;
  const displayName = active?.name || companyName || "Acme";

  const select = (c: CompanyRow) => {
    setCompanyId(c.id);
    setCompanyName(c.name);
    setOpen(false);
  };

  const remove = async (c: CompanyRow, e: React.MouseEvent) => {
    e.stopPropagation();
    if (deletingId) return;
    if (
      !window.confirm(
        `Delete "${c.name}"? This permanently removes it and all of its ` +
          `data from the database and Qdrant. This cannot be undone.`
      )
    )
      return;
    setDeletingId(c.id);
    try {
      await companyApi.remove(c.id);
      if (companyId === c.id) {
        setCompanyId(null);
        setCompanyName(null);
      }
      await queryClient.invalidateQueries({ queryKey: ["companies"] });
      toast.success(`Deleted ${c.name}`);
    } catch (err: any) {
      toast.error(
        err?.response?.data?.detail || `Failed to delete ${c.name}`
      );
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div ref={ref} style={{ position: "relative", marginBottom: 6 }}>
      <div
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "8px 10px",
          borderRadius: 10,
          border: "1px solid var(--border)",
          background: open ? "var(--bg-soft)" : "#fff",
          cursor: "pointer",
        }}
      >
        <div
          style={{
            width: 24,
            height: 24,
            borderRadius: 6,
            background:
              "linear-gradient(135deg, oklch(80% 0.13 295), oklch(62% 0.18 250))",
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            font: "700 11px var(--font-sans)",
          }}
        >
          {displayName[0]?.toUpperCase()}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 11, color: "var(--ink-3)", fontWeight: 600 }}>
            ACTIVE COMPANY
          </div>
          <div
            style={{
              fontSize: 12.5,
              fontWeight: 700,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {displayName}
          </div>
        </div>
        <Ico.chev
          style={{
            width: 14,
            height: 14,
            color: "var(--ink-3)",
            transform: open ? "rotate(180deg)" : "none",
            transition: "transform .15s",
          }}
        />
      </div>

      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            right: 0,
            zIndex: 50,
            background: "#fff",
            border: "1px solid var(--border)",
            borderRadius: 10,
            boxShadow: "var(--shadow-3)",
            padding: 4,
            maxHeight: 260,
            overflowY: "auto",
          }}
        >
          {companies.length === 0 ? (
            <div
              style={{
                padding: "10px 10px",
                fontSize: 11.5,
                color: "var(--ink-3)",
              }}
            >
              No companies yet — run an analysis to add one.
            </div>
          ) : (
            companies.map((c) => (
              <div
                key={c.id}
                onClick={() => select(c)}
                className="sb-item"
                style={{
                  padding: "7px 9px",
                  background: c.id === companyId ? "var(--bg-soft)" : undefined,
                }}
              >
                <span
                  style={{
                    width: 18,
                    height: 18,
                    borderRadius: 5,
                    flexShrink: 0,
                    background:
                      "linear-gradient(135deg, oklch(80% 0.13 295), oklch(62% 0.18 250))",
                    color: "#fff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    font: "700 9px var(--font-sans)",
                  }}
                >
                  {c.name[0]?.toUpperCase()}
                </span>
                <span
                  style={{
                    flex: 1,
                    minWidth: 0,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    fontSize: 12.5,
                    fontWeight: 600,
                  }}
                >
                  {c.name}
                </span>
                {c.id === companyId && (
                  <Ico.check
                    style={{
                      width: 13,
                      height: 13,
                      color: "var(--blue)",
                      flexShrink: 0,
                    }}
                  />
                )}
                <button
                  title="Delete company (database + Qdrant)"
                  onClick={(e) => remove(c, e)}
                  disabled={deletingId === c.id}
                  style={{
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 20,
                    height: 20,
                    borderRadius: 6,
                    border: "none",
                    background: "transparent",
                    color: "var(--ink-4)",
                    cursor: deletingId === c.id ? "default" : "pointer",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "oklch(95% 0.04 25)";
                    e.currentTarget.style.color = "var(--red)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.color = "var(--ink-4)";
                  }}
                >
                  {deletingId === c.id ? (
                    <span
                      className="spin"
                      style={{ width: 11, height: 11 }}
                    />
                  ) : (
                    <Ico.trash style={{ width: 13, height: 13 }} />
                  )}
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

const SAMPLE_RUNS = [
  { name: "acme.com", color: "var(--green)", t: "2m" },
  { name: "linear.app", color: "var(--blue)", t: "1h" },
  { name: "vercel.com", color: "var(--ink-4)", t: "3d" },
];

export function Sidebar() {
  const navigate = useNavigate();
  const pathname = useLocation().pathname;
  const go = (path: string) => navigate(path);
  const { companyId, setCompanyId, setCompanyName, isRunning, jobId, streamJobId } =
    usePipelineStore();
  const { agents, activeAgent, isDone } = useAgentStream(jobId);
  const [recentOpen, setRecentOpen] = useState(true);
  const activeId = NAV.find(
    (n) => pathname === n.route || pathname.startsWith(n.route + "/"),
  )?.id;
  // Once a run exists, "Company Intelligence" should reopen the live run (with
  // its persisted logs) rather than the empty new-analysis wizard.
  const hasRun = !!(jobId || streamJobId);

  const { data } = useQuery({
    queryKey: ["companies"],
    queryFn: companyApi.list,
    retry: false,
    staleTime: 30_000,
  });
  const companies: CompanyRow[] = data?.companies || [];

  const recentRuns = companies.slice(0, 4);

  /* live pipeline execution status for the sidebar footer */
  const runLive = agents.length > 0;
  const runDone = Math.min(
    AGENTS.length,
    agents.filter((a) => a.status === "done").length,
  );
  const runActiveLabel =
    agents.find((a) => a.name === activeAgent)?.label ||
    agents[agents.length - 1]?.label ||
    "Starting…";
  const runPct = isDone ? 100 : Math.round((runDone / AGENTS.length) * 100);

  return (
    <aside className="sb">
      <div
        className="sb-brand"
        style={{ cursor: "pointer" }}
        onClick={() => go("/")}
      >
        <div className="brand-mark">
          <BrandGlyph />
        </div>
        <div className="brand-name">
          sellna<span className="dot">.ai</span>
        </div>
      </div>

      <button className="sb-new" onClick={() => go("/company")}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <Ico.plus style={{ width: 14, height: 14 }} /> New Analysis
        </span>
        <span className="kbd">⌘N</span>
      </button>

      <CompanySwitcher companies={companies} />

      <div className="sb-group-label">Workspace</div>
      {NAV.map((n) => {
        const href =
          n.id === "company" && hasRun ? "/company/run" : n.route;
        return (
          <Link
            key={n.id}
            to={href}
            className={"sb-item" + (activeId === n.id ? " active" : "")}
          >
            <n.icon className="icon" />
            <span>{n.label}</span>
            {n.id === "company" && isRunning && (
              <span className="badge">LIVE</span>
            )}
          </Link>
        );
      })}

      <div
        className="sb-group-label"
        style={{ cursor: "pointer" }}
        onClick={() => setRecentOpen((o) => !o)}
      >
        <span>Recent runs</span>
        <Ico.chev
          style={{
            width: 12,
            height: 12,
            color: "var(--ink-4)",
            transform: recentOpen ? "none" : "rotate(-90deg)",
            transition: "transform .15s",
          }}
        />
      </div>

      {recentOpen &&
        (recentRuns.length > 0
          ? recentRuns.map((c) => (
              <div
                key={c.id}
                className={
                  "sb-item" + (c.id === companyId ? " active" : "")
                }
                style={{ padding: "5px 10px", fontSize: 12 }}
                onClick={() => {
                  setCompanyId(c.id);
                  setCompanyName(c.name);
                  go("/competitors");
                }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: c.has_analysis
                      ? "var(--green)"
                      : "var(--ink-4)",
                  }}
                />
                <span
                  style={{
                    color: "var(--ink-2)",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {c.name}
                </span>
                <span
                  style={{
                    marginLeft: "auto",
                    fontSize: 10.5,
                    color: "var(--ink-4)",
                  }}
                >
                  {relTime(c.created_at)}
                </span>
              </div>
            ))
          : SAMPLE_RUNS.map((r) => (
              <div
                key={r.name}
                className="sb-item"
                style={{ padding: "5px 10px", fontSize: 12 }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: r.color,
                  }}
                />
                <span style={{ color: "var(--ink-2)" }}>{r.name}</span>
                <span
                  style={{
                    marginLeft: "auto",
                    fontSize: 10.5,
                    color: "var(--ink-4)",
                  }}
                >
                  {r.t}
                </span>
              </div>
            )))}

      {runLive ? (
        <div
          className="sb-foot"
          onClick={() => go("/company/run")}
          style={{ cursor: "pointer" }}
          title="Open the live run"
        >
          <div className="row" style={{ marginBottom: 8 }}>
            <span
              style={{
                width: 9,
                height: 9,
                borderRadius: "50%",
                background: isDone ? "var(--green)" : "var(--blue)",
                boxShadow: isDone ? "none" : "0 0 0 4px var(--blue-soft)",
                flexShrink: 0,
                animation: isDone ? "none" : "pulse 1.6s infinite",
              }}
            />
            <div style={{ minWidth: 0 }}>
              <div className="label">{isDone ? "PIPELINE" : "LIVE RUN"}</div>
              <div
                className="name"
                style={{
                  fontSize: 12,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {isDone ? "Run complete" : runActiveLabel}
              </div>
            </div>
            <span
              style={{
                marginLeft: "auto",
                fontSize: 11,
                fontFamily: "var(--font-mono)",
                color: "var(--ink-3)",
                flexShrink: 0,
              }}
            >
              {runDone}/{AGENTS.length}
            </span>
          </div>
          <div
            style={{
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
                width: `${runPct}%`,
                background: isDone
                  ? "var(--green)"
                  : "linear-gradient(90deg,var(--blue-glow),var(--blue))",
                borderRadius: 3,
                transition: "width .4s ease",
                animation: isDone ? "none" : "shimmer 2s infinite",
              }}
            />
          </div>
        </div>
      ) : (
        <div className="sb-foot">
          <div className="row">
            <div
              className="brand-mark"
              style={{ width: 24, height: 24, borderRadius: 7 }}
            >
              <BrandGlyph size={13} />
            </div>
            <div>
              <div className="label">PIPELINE</div>
              <div className="name" style={{ fontSize: 12 }}>
                No active run
              </div>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}

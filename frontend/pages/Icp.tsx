
import { useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Ico } from "@/components/icons";
import { Ring, EmptyState } from "@/components/primitives";
import { icpApi } from "@/lib/api";
import { usePipelineStore } from "@/store/pipelineStore";
import { toast } from "@/lib/toast";

interface IcpCard {
  fit: number;
  ind: string;
  size: string;
  rev: string;
  stack: string;
  auth: string;
  summary: string;
}

export default function ICPPage() {
  const queryClient = useQueryClient();
  const { companyId, companyName, isRunning } = usePipelineStore();

  const { data, isLoading } = useQuery({
    queryKey: ["icps", companyId],
    queryFn: () => icpApi.list(companyId as string),
    enabled: !!companyId,
    refetchInterval: isRunning ? 5000 : false,
    retry: false,
  });

  const icps: IcpCard[] = useMemo(() => {
    const raw = data?.icps;
    if (!raw || raw.length === 0) return [];
    return raw.map((p: any) => ({
      fit:
        typeof p.fit_score === "number"
          ? p.fit_score <= 1
            ? Math.round(p.fit_score * 100)
            : Math.round(p.fit_score)
          : 70,
      ind: p.industry || "Target segment",
      size: p.company_size || "—",
      rev: p.revenue_range || "—",
      stack: Array.isArray(p.tech_stack)
        ? p.tech_stack.join(" · ")
        : p.tech_stack || "—",
      auth: p.buyer_authority || "—",
      summary: p.summary || p.description || p.rationale || "—",
    }));
  }, [data]);

  const regenerate = async () => {
    if (!companyId) {
      toast.error("Run a pipeline first to generate ICPs.");
      return;
    }
    try {
      await icpApi.generate(companyId, 3);
      toast.success("ICPs generated");
      await queryClient.invalidateQueries({ queryKey: ["icps", companyId] });
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to generate ICPs");
    }
  };

  return (
    <>
      <div className="page-h">
        <div>
          <div className="section-h">
            {icps.length} {icps.length === 1 ? "profile" : "profiles"} ·
            derived from gap analysis
          </div>
          <h1>Ideal Customer Profiles</h1>
          <p>
            Built by the ICP Generator agent
            {companyName ? ` from ${companyName}'s` : " from the"} highest-leverage
            positioning gaps.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn">
            <Ico.download style={{ width: 13, height: 13 }} /> Export CSV
          </button>
          <button className="btn primary" onClick={regenerate}>
            <Ico.sparkles style={{ width: 13, height: 13 }} /> Re-generate
          </button>
        </div>
      </div>

      {!companyId ? (
        <EmptyState
          icon={Ico.target}
          title="No active company"
          body="Run a company analysis (or pick one from the sidebar) to generate fit-scored ICPs."
        />
      ) : isLoading ? (
        <EmptyState
          icon={Ico.target}
          title="Loading ICPs…"
          body="Fetching the ideal customer profiles for this company."
        />
      ) : icps.length === 0 ? (
        <EmptyState
          icon={Ico.target}
          title="No ICPs yet"
          body="The ICP Generator agent hasn't produced any profiles for this company. Use Re-generate to create them."
        />
      ) : (
        <div
          style={{
            display: "grid",
            gap: 14,
            gridTemplateColumns: "repeat(3,1fr)",
          }}
          className="wave"
        >
          {icps.map((p, i) => (
          <div
            key={i}
            className="card"
            style={{ padding: 22, position: "relative", overflow: "hidden" }}
          >
            {i === 0 && (
              <div
                style={{
                  position: "absolute",
                  top: 14,
                  right: 14,
                  fontSize: 10.5,
                  fontWeight: 700,
                  color: "var(--blue)",
                  letterSpacing: ".05em",
                }}
              >
                ★ BEST FIT
              </div>
            )}
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <Ring value={p.fit} size={72} stroke={7} label="FIT" />
              <div>
                <div className="section-h">
                  ICP {String(i + 1).padStart(2, "0")}
                </div>
                <div
                  style={{
                    fontWeight: 700,
                    fontSize: 15,
                    letterSpacing: "-0.015em",
                  }}
                >
                  {p.ind}
                </div>
              </div>
            </div>
            <p
              style={{
                color: "var(--ink-2)",
                fontSize: 12.5,
                lineHeight: 1.55,
                margin: "14px 0 16px",
              }}
            >
              {p.summary}
            </p>

            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 0,
                fontSize: 12.5,
              }}
            >
              {[
                ["Company size", p.size],
                ["Revenue range", p.rev],
                ["Tech stack", p.stack],
                ["Buyer authority", p.auth],
              ].map(([k, v]) => (
                <div
                  key={k}
                  style={{
                    display: "flex",
                    gap: 10,
                    padding: "8px 0",
                    borderTop: "1px solid var(--border)",
                  }}
                >
                  <div
                    style={{
                      width: 110,
                      color: "var(--ink-3)",
                      fontWeight: 600,
                      fontSize: 11.5,
                    }}
                  >
                    {k}
                  </div>
                  <div style={{ flex: 1, color: "var(--ink)" }}>{v}</div>
                </div>
              ))}
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              <a
                className="btn primary"
                href="/personas"
                style={{ flex: 1, justifyContent: "center" }}
              >
                Build personas <Ico.arrow style={{ width: 13, height: 13 }} />
              </a>
              <button className="btn">
                <Ico.copy style={{ width: 13, height: 13 }} />
              </button>
            </div>
          </div>
          ))}
        </div>
      )}
    </>
  );
}

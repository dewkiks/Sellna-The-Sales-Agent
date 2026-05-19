
import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Ico } from "@/components/icons";
import { Ring, Tabs, EmptyState } from "@/components/primitives";
import { competitorsApi } from "@/lib/api";
import { usePipelineStore } from "@/store/pipelineStore";
import { toast } from "@/lib/toast";

interface Comp {
  name: string;
  site: string;
  tag: string;
  score: number;
  status: "scraped" | "pending" | "failed";
  pos: string;
  valueProp?: string;
  features?: string[];
  pricing?: { n: string; p: string; d: string }[];
  expanded?: boolean;
}

function CompetitorCard({ c, defaultOpen }: { c: Comp; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(!!defaultOpen);
  const tagColor =
    c.tag === "Direct" ? "red" : c.tag === "Indirect" ? "amber" : "violet";
  const features = c.features || [];
  const pricing = c.pricing || [];
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 14,
          padding: "14px 16px",
          cursor: "pointer",
        }}
        onClick={() => setOpen((o) => !o)}
      >
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: 11,
            background: "var(--bg-muted)",
            border: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            font: "700 16px var(--font-sans)",
            color: "var(--ink-2)",
            flexShrink: 0,
          }}
        >
          {c.name[0]}
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <strong style={{ fontSize: 14 }}>{c.name}</strong>
            <a
              style={{
                fontSize: 11.5,
                color: "var(--ink-3)",
                display: "flex",
                alignItems: "center",
                gap: 3,
                fontFamily: "var(--font-mono)",
              }}
            >
              {c.site} <Ico.external style={{ width: 11, height: 11 }} />
            </a>
            <span className={"pill " + tagColor}>{c.tag}</span>
            {c.status === "scraped" && (
              <span className="pill green">
                <Ico.check style={{ width: 10, height: 10 }} />
                scraped
              </span>
            )}
            {c.status === "pending" && (
              <span className="pill">
                <span className="dot" />
                pending
              </span>
            )}
            {c.status === "failed" && (
              <span className="pill red">
                <Ico.x style={{ width: 10, height: 10 }} />
                scrape failed
              </span>
            )}
          </div>
          <div
            style={{
              color: "var(--ink-3)",
              fontSize: 12.5,
              marginTop: 4,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {c.pos}
          </div>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            flexShrink: 0,
          }}
        >
          <Ring value={c.score} size={42} stroke={5} />
          <button
            className="btn ghost"
            style={{ padding: "5px 7px" }}
            onClick={(e) => {
              e.stopPropagation();
              setOpen((o) => !o);
            }}
          >
            <Ico.chev
              style={{
                width: 14,
                height: 14,
                transform: open ? "rotate(180deg)" : "rotate(0)",
                transition: "transform .2s",
              }}
            />
          </button>
        </div>
      </div>
      {open && (
        <div style={{ padding: "0 16px 16px", borderTop: "1px solid var(--border)" }}>
          {c.status === "failed" ? (
            <div
              style={{
                padding: 14,
                background: "oklch(97% 0.02 25)",
                borderRadius: 10,
                marginTop: 14,
                color: "oklch(40% 0.18 25)",
                fontSize: 12.5,
                display: "flex",
                gap: 10,
                alignItems: "flex-start",
              }}
            >
              <Ico.x
                style={{ width: 14, height: 14, flexShrink: 0, marginTop: 1 }}
              />
              <div>
                <strong>Scrape failed · status 403</strong>
                <br />
                We were blocked by Cloudflare on /pricing. Retrying with a backoff
                in 6 min, or trigger manually.
              </div>
            </div>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1.2fr 1fr 1fr",
                gap: 14,
                marginTop: 14,
              }}
            >
              <div>
                <div className="section-h">Value proposition</div>
                <p
                  style={{
                    fontSize: 12.5,
                    color: c.valueProp ? "var(--ink-2)" : "var(--ink-4)",
                    lineHeight: 1.55,
                    marginTop: 6,
                  }}
                >
                  {c.valueProp || "No value proposition extracted yet."}
                </p>
              </div>
              <div>
                <div className="section-h">Key features</div>
                {features.length > 0 ? (
                  <ul
                    style={{
                      margin: "6px 0 0",
                      padding: 0,
                      listStyle: "none",
                      display: "flex",
                      flexDirection: "column",
                      gap: 5,
                      fontSize: 12.5,
                    }}
                  >
                    {features.map((f, i) => (
                      <li key={i}>· {f}</li>
                    ))}
                  </ul>
                ) : (
                  <p
                    style={{
                      fontSize: 12.5,
                      color: "var(--ink-4)",
                      marginTop: 6,
                    }}
                  >
                    No features extracted yet.
                  </p>
                )}
              </div>
              <div>
                <div className="section-h">Pricing tiers</div>
                {pricing.length > 0 ? (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                      marginTop: 6,
                    }}
                  >
                    {pricing.map((t, i) => (
                      <div
                        key={t.n + i}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: 12.5,
                          padding: "4px 0",
                          borderBottom: "1px solid var(--border)",
                        }}
                      >
                        <span style={{ fontWeight: 600 }}>{t.n}</span>
                        {(t.p || t.d) && (
                          <span>
                            <span
                              style={{
                                fontFamily: "var(--font-mono)",
                                color: "var(--blue-deep)",
                              }}
                            >
                              {t.p}
                            </span>{" "}
                            {t.d && (
                              <span style={{ color: "var(--ink-3)" }}>
                                · {t.d}
                              </span>
                            )}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p
                    style={{
                      fontSize: 12.5,
                      color: "var(--ink-4)",
                      marginTop: 6,
                    }}
                  >
                    No pricing extracted yet.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function CompetitorsPage() {
  const queryClient = useQueryClient();
  const { companyId, companyName, isRunning } = usePipelineStore();
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState("all");

  const { data, isLoading } = useQuery({
    queryKey: ["competitors", companyId],
    queryFn: () => competitorsApi.list(companyId as string),
    enabled: !!companyId,
    refetchInterval: isRunning ? 5000 : false,
    retry: false,
  });

  const list: Comp[] = useMemo(() => {
    const raw = data?.competitors;
    if (!raw || raw.length === 0) return [];
    return raw.map((c) => {
      const web = c.web_data;
      const clean = c.clean_data;
      const failed = web ? web.scrape_success === false : false;
      const scraped = c.has_clean_data || c.has_web_data;
      const score =
        c.relevance_score <= 1
          ? Math.round(c.relevance_score * 100)
          : Math.round(c.relevance_score);
      const features =
        (web?.features?.length ? web.features : clean?.clean_features) || [];
      const pricingTiers = web?.pricing_tiers?.length
        ? web.pricing_tiers
        : clean?.clean_pricing
          ? [clean.clean_pricing]
          : [];
      return {
        name: c.name,
        site: c.website,
        tag: c.category || "Adjacent",
        score,
        status: failed ? "failed" : scraped ? "scraped" : "pending",
        pos: c.positioning || "—",
        valueProp:
          web?.value_proposition || clean?.clean_value_proposition || undefined,
        features: features.length ? features : undefined,
        pricing: pricingTiers.length
          ? pricingTiers.map((p) => ({ n: p, p: "", d: "" }))
          : undefined,
      } as Comp;
    });
  }, [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    return list.filter((c) => {
      if (q && !c.name.toLowerCase().includes(q)) return false;
      if (tab !== "all" && c.tag.toLowerCase() !== tab) return false;
      return true;
    });
  }, [list, search, tab]);

  const count = (t: string) =>
    t === "all"
      ? list.length
      : list.filter((c) => c.tag.toLowerCase() === t).length;

  const action = async (kind: "scrape" | "discover") => {
    if (!companyId) {
      toast.error("Run a pipeline first to generate competitor intelligence.");
      return;
    }
    try {
      if (kind === "scrape") await competitorsApi.scrape(companyId);
      else await competitorsApi.discover(companyId);
      toast.success(
        kind === "scrape" ? "Re-scrape complete" : "Discovery complete"
      );
      await queryClient.invalidateQueries({ queryKey: ["competitors", companyId] });
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || `Failed to ${kind} competitors`);
    }
  };

  return (
    <>
      <div className="page-h">
        <div>
          <div className="section-h">
            {list.length} found
            {companyName ? ` · scored against ${companyName}` : ""}
          </div>
          <h1>Competitors</h1>
          <p>
            Auto-discovered and validated by the Competitor Hunter and Web Scraper
            agents.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={() => action("scrape")}>
            <Ico.refresh style={{ width: 13, height: 13 }} /> Re-scrape
          </button>
          <button className="btn primary" onClick={() => action("discover")}>
            <Ico.sparkles style={{ width: 13, height: 13 }} /> Discover more
          </button>
        </div>
      </div>

      <div
        style={{
          display: "flex",
          gap: 10,
          marginBottom: 14,
          alignItems: "center",
        }}
      >
        <div className="search" style={{ flex: 1, maxWidth: 380 }}>
          <Ico.search
            style={{ width: 14, height: 14, color: "var(--ink-3)" }}
          />
          <input
            placeholder="Filter competitors by name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { id: "all", label: `All · ${count("all")}` },
            { id: "direct", label: `Direct · ${count("direct")}` },
            { id: "indirect", label: `Indirect · ${count("indirect")}` },
            { id: "adjacent", label: `Adjacent · ${count("adjacent")}` },
          ]}
        />
        <button className="btn ghost" style={{ marginLeft: "auto" }}>
          <Ico.filter style={{ width: 13, height: 13 }} /> Sort: relevance
        </button>
      </div>

      {!companyId ? (
        <EmptyState
          icon={Ico.swords}
          title="No active company"
          body="Run a company analysis (or pick one from the sidebar) to discover and score competitors."
        />
      ) : isLoading ? (
        <EmptyState
          icon={Ico.swords}
          title="Loading competitors…"
          body="Fetching the latest competitor intelligence for this company."
        />
      ) : list.length === 0 ? (
        <EmptyState
          icon={Ico.swords}
          title="No competitors yet"
          body="The Competitor Hunter agent hasn't found any rivals for this company. Run the pipeline or use Discover more."
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Ico.search}
          title="No matches"
          body="No competitors match your current search or filter."
        />
      ) : (
        <div style={{ display: "grid", gap: 10 }} className="wave">
          {filtered.map((c, i) => (
            <CompetitorCard key={c.name + i} c={c} defaultOpen={c.expanded} />
          ))}
        </div>
      )}
    </>
  );
}

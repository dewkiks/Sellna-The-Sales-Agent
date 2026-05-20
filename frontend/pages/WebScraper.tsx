
import { useState, type CSSProperties, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Ico } from "@/components/icons";
import {
  competitorsApi,
  scrapersApi,
  type CompetitorWebData,
  type WebScrapeResult,
} from "@/lib/api";
import { usePipelineStore } from "@/store/pipelineStore";
import { toast } from "@/lib/toast";

const PIPE_RAW_STYLE: CSSProperties = {
  margin: "8px 0 0",
  padding: 12,
  background: "var(--bg-soft)",
  border: "1px solid var(--border)",
  borderRadius: 10,
  fontFamily: "var(--font-mono)",
  fontSize: 11.5,
  lineHeight: 1.5,
  color: "var(--ink-2)",
  maxHeight: 320,
  overflow: "auto",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
};

/* ---------- small helpers ---------- */

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: 10,
        padding: "10px 12px",
        background: "#fff",
        minWidth: 0,
      }}
    >
      <div
        style={{
          fontSize: 10.5,
          fontWeight: 700,
          letterSpacing: "0.06em",
          color: "var(--ink-4)",
          textTransform: "uppercase",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 16,
          fontWeight: 700,
          marginTop: 2,
          letterSpacing: "-0.02em",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {value}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div style={{ marginTop: 16 }}>
      <div className="section-h">{title}</div>
      <div style={{ marginTop: 6 }}>{children}</div>
    </div>
  );
}

/* ---------- result ---------- */

function ResultCard({ r }: { r: WebScrapeResult }) {
  const [open, setOpen] = useState(true);
  const [showRaw, setShowRaw] = useState(false);
  const x = r.extracted || {};

  const headingCount = Object.values(x.headings || {}).reduce(
    (n, list) => n + list.length,
    0
  );

  const copyRaw = async () => {
    try {
      await navigator.clipboard.writeText(r.raw_html || "");
      toast.success("Raw HTML copied");
    } catch {
      toast.error("Copy failed");
    }
  };

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      {/* header */}
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
          className="icon-tile"
          style={{ width: 40, height: 40, borderRadius: 10, flexShrink: 0 }}
        >
          <Ico.globe style={{ width: 18, height: 18 }} />
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <strong style={{ fontSize: 14 }}>
              {x.title || "Untitled page"}
            </strong>
            {r.success ? (
              <span className="pill green">
                <Ico.check style={{ width: 10, height: 10 }} /> {r.status}
              </span>
            ) : (
              <span className="pill red">
                <Ico.x style={{ width: 10, height: 10 }} />{" "}
                {r.error || `HTTP ${r.status}`}
              </span>
            )}
            {r.rendered && <span className="pill violet">JS rendered</span>}
          </div>
          <a
            href={r.url}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            style={{
              fontSize: 11.5,
              color: "var(--ink-3)",
              fontFamily: "var(--font-mono)",
              display: "inline-flex",
              alignItems: "center",
              gap: 3,
              marginTop: 3,
              maxWidth: "100%",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {r.url} <Ico.external style={{ width: 11, height: 11 }} />
          </a>
        </div>
        <span style={{ fontSize: 11.5, color: "var(--ink-4)", flexShrink: 0 }}>
          {r.elapsed_ms} ms
        </span>
        <Ico.chev
          style={{
            width: 16,
            height: 16,
            color: "var(--ink-3)",
            flexShrink: 0,
            transform: open ? "rotate(180deg)" : "none",
            transition: "transform .2s",
          }}
        />
      </div>

      {/* expanded body */}
      {open && (
        <div style={{ padding: 16, borderTop: "1px solid var(--border)" }}>
          {!r.success ? (
            <div
              style={{
                padding: 14,
                background: "oklch(97% 0.02 25)",
                borderRadius: 10,
                color: "oklch(40% 0.18 25)",
                fontSize: 12.5,
                display: "flex",
                gap: 10,
              }}
            >
              <Ico.x style={{ width: 14, height: 14, flexShrink: 0 }} />
              <div>
                <strong>Scrape failed</strong>
                <br />
                {r.error || `The server responded with status ${r.status}.`}{" "}
                Try enabling “Render JavaScript”.
              </div>
            </div>
          ) : (
            <>
              {/* in-depth — what was scraped off */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
                  gap: 8,
                }}
              >
                <Stat label="Headings" value={headingCount} />
                <Stat label="Paragraphs" value={(x.paragraphs || []).length} />
                <Stat label="Links" value={(x.links || []).length} />
                <Stat label="Images" value={(x.images || []).length} />
                <Stat label="Tables" value={(x.tables || []).length} />
                <Stat
                  label="HTML size"
                  value={`${Math.round(r.raw_html_bytes / 1024)} KB`}
                />
              </div>

              {x.meta_description && (
                <Section title="Meta description">
                  <p
                    style={{
                      fontSize: 12.5,
                      color: "var(--ink-2)",
                      lineHeight: 1.55,
                      margin: 0,
                    }}
                  >
                    {x.meta_description}
                  </p>
                </Section>
              )}

              {headingCount > 0 && (
                <Section title="Headings">
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 4,
                    }}
                  >
                    {Object.entries(x.headings || {}).flatMap(([tag, list]) =>
                      list.map((h, i) => (
                        <div
                          key={`${tag}-${i}`}
                          style={{
                            fontSize: 12.5,
                            display: "flex",
                            gap: 8,
                            alignItems: "baseline",
                          }}
                        >
                          <span
                            style={{
                              fontFamily: "var(--font-mono)",
                              fontSize: 10,
                              color: "var(--ink-4)",
                              textTransform: "uppercase",
                              minWidth: 22,
                            }}
                          >
                            {tag}
                          </span>
                          <span style={{ color: "var(--ink-2)" }}>{h}</span>
                        </div>
                      ))
                    )}
                  </div>
                </Section>
              )}

              {(x.paragraphs || []).length > 0 && (
                <Section title={`Body text · ${x.paragraphs!.length} paragraphs`}>
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                      maxHeight: 260,
                      overflowY: "auto",
                    }}
                  >
                    {x.paragraphs!.map((p, i) => (
                      <p
                        key={i}
                        style={{
                          fontSize: 12.5,
                          color: "var(--ink-2)",
                          lineHeight: 1.55,
                          margin: 0,
                        }}
                      >
                        {p}
                      </p>
                    ))}
                  </div>
                </Section>
              )}

              {(x.links || []).length > 0 && (
                <Section title={`Links · ${x.links!.length}`}>
                  <div
                    style={{
                      maxHeight: 220,
                      overflowY: "auto",
                      border: "1px solid var(--border)",
                      borderRadius: 10,
                    }}
                  >
                    {x.links!.slice(0, 200).map((l, i) => (
                      <a
                        key={i}
                        href={l.href}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          gap: 12,
                          padding: "6px 10px",
                          fontSize: 12,
                          borderBottom: "1px solid var(--border)",
                        }}
                      >
                        <span
                          style={{
                            color: "var(--ink-2)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {l.text || "(no text)"}
                        </span>
                        <span
                          style={{
                            color: "var(--ink-4)",
                            fontFamily: "var(--font-mono)",
                            fontSize: 11,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                            flexShrink: 0,
                            maxWidth: "55%",
                          }}
                        >
                          {l.href}
                        </span>
                      </a>
                    ))}
                  </div>
                </Section>
              )}

              {(x.images || []).length > 0 && (
                <Section title={`Images · ${x.images!.length}`}>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns:
                        "repeat(auto-fill, minmax(84px, 1fr))",
                      gap: 8,
                      maxHeight: 220,
                      overflowY: "auto",
                    }}
                  >
                    {x.images!.slice(0, 60).map((img, i) => (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        key={i}
                        src={img.src}
                        alt={img.alt}
                        title={img.alt || img.src}
                        style={{
                          width: "100%",
                          height: 64,
                          objectFit: "cover",
                          borderRadius: 8,
                          border: "1px solid var(--border)",
                          background: "var(--bg-muted)",
                        }}
                      />
                    ))}
                  </div>
                </Section>
              )}

              {(x.structured_data || []).length > 0 && (
                <Section title="Structured data (JSON-LD)">
                  <pre className="raw-block">
                    {JSON.stringify(x.structured_data, null, 2)}
                  </pre>
                </Section>
              )}

              {/* raw scraped info — toggled */}
              <div style={{ marginTop: 16 }}>
                <button
                  className="btn ghost"
                  onClick={() => setShowRaw((v) => !v)}
                >
                  <Ico.code style={{ width: 13, height: 13 }} />
                  {showRaw ? "Hide raw HTML" : "Show raw HTML"}
                </button>
                {showRaw && (
                  <button
                    className="btn ghost"
                    style={{ marginLeft: 8 }}
                    onClick={copyRaw}
                  >
                    <Ico.copy style={{ width: 13, height: 13 }} /> Copy
                  </button>
                )}
                {showRaw && (
                  <div style={{ marginTop: 8 }}>
                    {r.raw_html_truncated && (
                      <div
                        style={{
                          fontSize: 11.5,
                          color: "var(--amber)",
                          marginBottom: 6,
                        }}
                      >
                        Raw HTML truncated — showing the first{" "}
                        {Math.round(r.raw_html.length / 1024)} KB of{" "}
                        {Math.round(r.raw_html_bytes / 1024)} KB.
                      </div>
                    )}
                    <pre className="raw-block">{r.raw_html}</pre>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      <style>{`
        .raw-block {
          margin: 0;
          padding: 12px;
          background: var(--bg-soft);
          border: 1px solid var(--border);
          border-radius: 10px;
          font-family: var(--font-mono);
          font-size: 11.5px;
          line-height: 1.5;
          color: var(--ink-2);
          max-height: 360px;
          overflow: auto;
          white-space: pre-wrap;
          word-break: break-word;
        }
      `}</style>
    </div>
  );
}

/* ---------- pipeline-collected web data ---------- */

interface PipelineComp {
  id: string;
  name: string;
  website: string;
  has_web_data: boolean;
  web_data?: CompetitorWebData | null;
}

function PipelineWebRow({ c }: { c: PipelineComp }) {
  const [open, setOpen] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const w = c.web_data || {};
  const ok = w.scrape_success !== false;
  return (
    <div style={{ borderBottom: "1px solid var(--border)" }}>
      <div
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 14px",
          cursor: "pointer",
        }}
      >
        <span style={{ fontSize: 12.5, fontWeight: 600 }}>{c.name}</span>
        <span
          style={{
            fontSize: 11,
            fontFamily: "var(--font-mono)",
            color: "var(--ink-3)",
            minWidth: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {c.website}
        </span>
        {ok ? (
          <span className="pill green" style={{ marginLeft: "auto" }}>
            <Ico.check style={{ width: 10, height: 10 }} /> scraped
          </span>
        ) : (
          <span className="pill red" style={{ marginLeft: "auto" }}>
            <Ico.x style={{ width: 10, height: 10 }} /> failed
          </span>
        )}
        <Ico.chev
          style={{
            width: 14,
            height: 14,
            color: "var(--ink-3)",
            transform: open ? "rotate(180deg)" : "none",
            transition: "transform .2s",
          }}
        />
      </div>
      {open && (
        <div style={{ padding: "0 14px 12px" }}>
          {!ok ? (
            <div style={{ fontSize: 12, color: "var(--red)" }}>
              {w.error || "Scrape failed."}
            </div>
          ) : (
            <>
              {w.value_proposition && (
                <Section title="Value proposition">
                  <p
                    style={{
                      fontSize: 12.5,
                      color: "var(--ink-2)",
                      lineHeight: 1.55,
                      margin: 0,
                    }}
                  >
                    {w.value_proposition}
                  </p>
                </Section>
              )}
              {!!(w.features || []).length && (
                <Section title={`Features · ${w.features!.length}`}>
                  <ul
                    style={{
                      margin: 0,
                      paddingLeft: 16,
                      fontSize: 12.5,
                      color: "var(--ink-2)",
                    }}
                  >
                    {w.features!.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                </Section>
              )}
              {!!(w.pricing_tiers || []).length && (
                <Section title={`Pricing signals · ${w.pricing_tiers!.length}`}>
                  <ul
                    style={{
                      margin: 0,
                      paddingLeft: 16,
                      fontSize: 12.5,
                      color: "var(--ink-2)",
                    }}
                  >
                    {w.pricing_tiers!.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </Section>
              )}
            </>
          )}
          <button
            className="btn ghost"
            style={{ marginTop: 10 }}
            onClick={() => setShowRaw((v) => !v)}
          >
            <Ico.code style={{ width: 13, height: 13 }} />
            {showRaw ? "Hide raw data" : "Show raw scraped data"}
          </button>
          {showRaw && (
            <pre style={PIPE_RAW_STYLE}>{JSON.stringify(w, null, 2)}</pre>
          )}
        </div>
      )}
    </div>
  );
}

function PipelineWebData() {
  const companyId = usePipelineStore((s) => s.companyId);

  const { data, isLoading } = useQuery({
    queryKey: ["pipeline-web", companyId],
    queryFn: () => competitorsApi.list(companyId as string),
    enabled: !!companyId,
    retry: false,
  });

  const scraped = ((data?.competitors as PipelineComp[]) || []).filter(
    (c) => c.has_web_data
  );

  return (
    <div style={{ marginTop: 20 }}>
      <div className="section-h" style={{ marginBottom: 8 }}>
        From your last pipeline run
        {data ? ` · ${scraped.length} pages` : ""}
      </div>
      {!companyId ? (
        <div className="card">
          <div className="bd" style={{ fontSize: 12.5, color: "var(--ink-3)" }}>
            Select a company (or run the pipeline) to see the competitor pages
            its Web Intelligence stage scraped.
          </div>
        </div>
      ) : isLoading ? (
        <div className="card">
          <div className="bd">
            <span className="spin" style={{ width: 16, height: 16 }} />
          </div>
        </div>
      ) : scraped.length === 0 ? (
        <div className="card">
          <div className="bd" style={{ fontSize: 12.5, color: "var(--ink-3)" }}>
            No scraped pages yet — run the pipeline for this company and the
            Web Intelligence stage will populate this.
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          {scraped.map((c) => (
            <PipelineWebRow key={c.id} c={c} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------- page ---------- */

export default function WebScraperPage() {
  // The scrape result lives in the persisted store so it survives navigating
  // away and back (and a page refresh) instead of being component-local state.
  const webScrape = usePipelineStore((s) => s.webScrape);
  const setWebScrape = usePipelineStore((s) => s.setWebScrape);
  const [url, setUrl] = useState(() => webScrape.url);
  const [renderJs, setRenderJs] = useState(false);
  const [loading, setLoading] = useState(false);
  const result = webScrape.result;

  const run = async () => {
    const u = url.trim();
    if (!u) {
      toast.error("Enter a URL to scrape");
      return;
    }
    setLoading(true);
    setWebScrape({ url: u, result: null });
    try {
      const data = await scrapersApi.web(u, renderJs);
      setWebScrape({ url: u, result: data });
      if (data.success) toast.success("Page scraped");
      else toast.error(data.error || "Scrape failed");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Scrape request failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="page-h">
        <div>
          <div className="section-h">Crawl any public page</div>
          <h1>Web Scraper</h1>
          <p>
            Fetch a page, extract its structured content, and inspect the raw
            HTML that was scraped off it.
          </p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 14 }}>
        <div className="bd">
          <div
            style={{
              display: "flex",
              gap: 10,
              alignItems: "center",
              flexWrap: "wrap",
            }}
          >
            <div className="search" style={{ flex: 1, minWidth: 280 }}>
              <Ico.globe
                style={{ width: 14, height: 14, color: "var(--ink-3)" }}
              />
              <input
                placeholder="example.com/pricing"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !loading && run()}
              />
            </div>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontSize: 12.5,
                color: "var(--ink-2)",
                cursor: "pointer",
                userSelect: "none",
              }}
            >
              <input
                type="checkbox"
                checked={renderJs}
                onChange={(e) => setRenderJs(e.target.checked)}
              />
              Render JavaScript
            </label>
            <button
              className="btn primary"
              onClick={run}
              disabled={loading}
            >
              {loading ? (
                <span className="spin" style={{ width: 13, height: 13 }} />
              ) : (
                <Ico.search style={{ width: 13, height: 13 }} />
              )}
              {loading ? "Scraping…" : "Scrape"}
            </button>
          </div>
        </div>
      </div>

      {result && <ResultCard r={result} />}

      {!result && !loading && (
        <div
          style={{
            padding: "40px 28px",
            textAlign: "center",
            borderRadius: 14,
            border: "1px dashed var(--border-strong)",
            background: "#fff",
            color: "var(--ink-3)",
            fontSize: 12.5,
          }}
        >
          Enter a URL above to scrape a page. Expand the result to see
          everything that was scraped off — and toggle the raw HTML.
        </div>
      )}

      <PipelineWebData />
    </>
  );
}

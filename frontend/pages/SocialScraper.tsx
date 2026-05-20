
import { useState, type CSSProperties, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Ico } from "@/components/icons";
import {
  API_ROOT,
  scrapersApi,
  type CompanySocialSubject,
  type PipelinePerson,
  type PipelineSocialProfile,
  type SocialScrapeResult,
} from "@/lib/api";
import { usePipelineStore } from "@/store/pipelineStore";
import { toast } from "@/lib/toast";

const RAW_STYLE: CSSProperties = {
  margin: "8px 0 0",
  padding: 12,
  background: "var(--bg-soft)",
  border: "1px solid var(--border)",
  borderRadius: 10,
  fontFamily: "var(--font-mono)",
  fontSize: 11.5,
  lineHeight: 1.5,
  color: "var(--ink-2)",
  maxHeight: 300,
  overflow: "auto",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
};

/* ---------- helpers ---------- */

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: 10,
        padding: "10px 12px",
        background: "#fff",
        flex: 1,
        minWidth: 90,
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
          fontSize: 17,
          fontWeight: 700,
          marginTop: 2,
          letterSpacing: "-0.02em",
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

function fmt(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") return v.toLocaleString();
  return String(v);
}

/* ---------- result ---------- */

function ResultCard({ r }: { r: SocialScrapeResult }) {
  const [open, setOpen] = useState(true);
  const [showRaw, setShowRaw] = useState(false);
  const p = r.profile || {};

  const name =
    p.profile_name || p.full_name || p.username || r.url.split("/").pop() || "Profile";
  const handle = p.username ? `@${p.username}` : p.headline || "";
  const isInstagram = r.platform === "Instagram";
  const posts: any[] = Array.isArray(p.latest_posts) ? p.latest_posts : [];
  const experience: any[] = Array.isArray(p.experience) ? p.experience : [];

  const copyRaw = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(r.raw, null, 2));
      toast.success("Raw JSON copied");
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
        <ProfileAvatar src={p.avatar} alt={name} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <strong style={{ fontSize: 14 }}>{name}</strong>
            {p.is_verified && (
              <span className="pill blue">
                <Ico.check style={{ width: 10, height: 10 }} /> verified
              </span>
            )}
            <span
              className={"pill " + (isInstagram ? "violet" : "blue")}
            >
              {r.platform}
            </span>
            {r.success ? (
              <span className="pill green">
                <Ico.check style={{ width: 10, height: 10 }} /> scraped
              </span>
            ) : (
              <span className="pill red">
                <Ico.x style={{ width: 10, height: 10 }} /> failed
              </span>
            )}
          </div>
          {handle && (
            <div
              style={{
                fontSize: 12,
                color: "var(--ink-3)",
                marginTop: 3,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {handle}
            </div>
          )}
        </div>
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

      {/* expanded */}
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
                <strong>Could not scrape this profile</strong>
                <br />
                {r.error ||
                  "The profile may be private, rate-limited, or unreachable."}
              </div>
            </div>
          ) : (
            <>
              {/* in-depth */}
              {isInstagram && (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <Stat label="Followers" value={fmt(p.followers)} />
                  <Stat label="Following" value={fmt(p.following)} />
                  <Stat label="Posts" value={fmt(p.posts_count)} />
                </div>
              )}

              {(p.about || p.bio) && (
                <Section title={isInstagram ? "Bio" : "About"}>
                  <p
                    style={{
                      fontSize: 12.5,
                      color: "var(--ink-2)",
                      lineHeight: 1.55,
                      margin: 0,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {p.about || p.bio}
                  </p>
                </Section>
              )}

              <Section title="Profile details">
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "6px 16px",
                    fontSize: 12.5,
                  }}
                >
                  {p.headline && <Field k="Headline" v={p.headline} />}
                  {p.location && <Field k="Location" v={p.location} />}
                  {p.external_url && (
                    <Field k="External URL" v={p.external_url} link />
                  )}
                  {isInstagram && (
                    <Field
                      k="Visibility"
                      v={p.is_private ? "Private" : "Public"}
                    />
                  )}
                  {r.source && <Field k="Scrape source" v={r.source} />}
                  <Field k="Profile URL" v={r.url} link />
                </div>
              </Section>

              {experience.length > 0 && (
                <Section title={`Experience · ${experience.length}`}>
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                    }}
                  >
                    {experience.map((e, i) => (
                      <div
                        key={i}
                        style={{
                          fontSize: 12.5,
                          color: "var(--ink-2)",
                          padding: "6px 10px",
                          border: "1px solid var(--border)",
                          borderRadius: 8,
                        }}
                      >
                        {typeof e === "string" ? e : JSON.stringify(e)}
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {posts.length > 0 && (
                <Section title={`Latest posts · ${posts.length}`}>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns:
                        "repeat(auto-fill, minmax(160px, 1fr))",
                      gap: 10,
                    }}
                  >
                    {posts.map((post, i) => (
                      <a
                        key={i}
                        href={post.url || undefined}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          border: "1px solid var(--border)",
                          borderRadius: 10,
                          overflow: "hidden",
                          background: "#fff",
                        }}
                      >
                        <PostImage src={post.media_url} alt={post.type || "post"} />
                        <div style={{ padding: "8px 10px" }}>
                          <div
                            style={{
                              display: "flex",
                              gap: 10,
                              fontSize: 11,
                              color: "var(--ink-3)",
                              marginBottom: 4,
                            }}
                          >
                            <span>♥ {fmt(post.likes)}</span>
                            <span>💬 {fmt(post.comments)}</span>
                            {post.type && (
                              <span style={{ marginLeft: "auto" }}>
                                {post.type}
                              </span>
                            )}
                          </div>
                          <div
                            style={{
                              fontSize: 11.5,
                              color: "var(--ink-2)",
                              lineHeight: 1.45,
                              display: "-webkit-box",
                              WebkitLineClamp: 3,
                              WebkitBoxOrient: "vertical",
                              overflow: "hidden",
                            }}
                          >
                            {post.caption || "(no caption)"}
                          </div>
                          {post.posted_at && (
                            <div
                              style={{
                                fontSize: 10.5,
                                color: "var(--ink-4)",
                                marginTop: 4,
                              }}
                            >
                              {post.posted_at}
                            </div>
                          )}
                        </div>
                      </a>
                    ))}
                  </div>
                </Section>
              )}

              {/* raw scraped info — toggled */}
              <div style={{ marginTop: 16 }}>
                <button
                  className="btn ghost"
                  onClick={() => setShowRaw((v) => !v)}
                >
                  <Ico.code style={{ width: 13, height: 13 }} />
                  {showRaw ? "Hide raw data" : "Show raw scraped data"}
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
                  <pre className="raw-block" style={{ marginTop: 8 }}>
                    {JSON.stringify(r.raw, null, 2)}
                  </pre>
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

/**
 * Route a social-CDN image through the backend proxy. Instagram and LinkedIn
 * hotlink-protect their image hosts, so the browser cannot load the scraped
 * URLs directly — the proxy fetches them server-side and relays the bytes
 * from the API's own origin.
 */
function proxiedImage(url: string): string {
  return `${API_ROOT}/scrapers/image-proxy?url=${encodeURIComponent(url)}`;
}

/**
 * Profile avatar with a graceful fallback. The image is served via the backend
 * proxy so hotlink-protected CDN images load; `onError` swaps to a neutral
 * tile if the image is missing or the proxy fails.
 */
function ProfileAvatar({
  src,
  alt,
  size = 46,
}: {
  src?: string;
  alt: string;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div
        className="icon-tile"
        style={{ width: size, height: size, borderRadius: "50%", flexShrink: 0 }}
      >
        <Ico.atSign style={{ width: size * 0.4, height: size * 0.4 }} />
      </div>
    );
  }
  return (
    <img
      src={proxiedImage(src)}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        objectFit: "cover",
        border: "1px solid var(--border)",
        background: "var(--bg-muted)",
        flexShrink: 0,
      }}
    />
  );
}

/**
 * Square post thumbnail — Instagram posts are square, so a 1:1 tile keeps the
 * grid uniform. Served via the image proxy; shows a fallback panel when the
 * image is missing or blocked.
 */
function PostImage({ src, alt }: { src?: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div
        style={{
          width: "100%",
          aspectRatio: "1 / 1",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--bg-muted)",
          color: "var(--ink-4)",
        }}
      >
        <Ico.layers style={{ width: 22, height: 22 }} />
      </div>
    );
  }
  return (
    <img
      src={proxiedImage(src)}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
      style={{
        display: "block",
        width: "100%",
        aspectRatio: "1 / 1",
        objectFit: "cover",
        background: "var(--bg-muted)",
      }}
    />
  );
}

function Field({ k, v, link }: { k: string; v: string; link?: boolean }) {
  return (
    <div style={{ display: "flex", gap: 6, minWidth: 0 }}>
      <span style={{ color: "var(--ink-4)", fontWeight: 600, flexShrink: 0 }}>
        {k}
      </span>
      {link ? (
        <a
          href={v}
          target="_blank"
          rel="noreferrer"
          style={{
            color: "var(--blue)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {v}
        </a>
      ) : (
        <span
          style={{
            color: "var(--ink-2)",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {v}
        </span>
      )}
    </div>
  );
}

/* ---------- pipeline-collected socials ---------- */

function ProfileRow({ p }: { p: PipelineSocialProfile }) {
  const [open, setOpen] = useState(false);
  const d = p.data || {};
  const label =
    d.profile_name || d.full_name || d.username || d.headline || p.url;
  return (
    <div style={{ borderBottom: "1px solid var(--border)" }}>
      <div
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          cursor: "pointer",
        }}
      >
        <ProfileAvatar src={d.avatar} alt={label} size={30} />
        <span
          className={"pill " + (p.platform === "Instagram" ? "violet" : "blue")}
        >
          {p.platform}
        </span>
        <span className="pill">{p.profile_type}</span>
        <span
          style={{
            fontSize: 12,
            fontWeight: 600,
            minWidth: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {label}
        </span>
        {p.success ? (
          <span className="pill green" style={{ marginLeft: "auto" }}>
            <Ico.check style={{ width: 10, height: 10 }} /> scraped
          </span>
        ) : (
          <span className="pill" style={{ marginLeft: "auto" }}>
            discovered
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
        <div style={{ padding: "0 12px 12px" }}>
          <a
            href={p.url}
            target="_blank"
            rel="noreferrer"
            style={{
              fontSize: 11,
              fontFamily: "var(--font-mono)",
              color: "var(--blue)",
              wordBreak: "break-all",
            }}
          >
            {p.url}
          </a>
          <pre style={RAW_STYLE}>{JSON.stringify(p.data, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

function SubLabel({ text }: { text: string }) {
  return (
    <div
      style={{
        padding: "9px 14px 4px",
        fontSize: 10.5,
        fontWeight: 700,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        color: "var(--ink-4)",
        borderTop: "1px solid var(--border)",
      }}
    >
      {text}
    </div>
  );
}

function PersonRow({ pe }: { pe: PipelinePerson }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 9,
        padding: "7px 14px",
        borderBottom: "1px solid var(--border)",
      }}
    >
      <div
        className="icon-tile"
        style={{ width: 26, height: 26, borderRadius: "50%", flexShrink: 0 }}
      >
        <Ico.users style={{ width: 13, height: 13 }} />
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 12.5, fontWeight: 600 }}>{pe.name}</div>
        {pe.title && (
          <div
            style={{
              fontSize: 11,
              color: "var(--ink-3)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {pe.title}
          </div>
        )}
      </div>
      {pe.linkedin_url && (
        <a
          href={pe.linkedin_url}
          target="_blank"
          rel="noreferrer"
          className="pill blue"
          style={{ marginLeft: "auto" }}
        >
          LinkedIn <Ico.external style={{ width: 10, height: 10 }} />
        </a>
      )}
    </div>
  );
}

function SubjectCard({ s }: { s: CompanySocialSubject }) {
  const [open, setOpen] = useState(true);
  const total =
    s.profiles.length + s.people.length + s.emails.length + s.phones.length;
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "12px 14px",
          cursor: "pointer",
        }}
      >
        <div
          className="icon-tile"
          style={{ width: 32, height: 32, borderRadius: 8, flexShrink: 0 }}
        >
          <Ico.atSign style={{ width: 15, height: 15 }} />
        </div>
        <strong style={{ fontSize: 13.5 }}>{s.subject_name}</strong>
        <span
          className={
            "pill " + (s.subject_type === "company" ? "blue" : "violet")
          }
        >
          {s.subject_type}
        </span>
        <span
          style={{
            marginLeft: "auto",
            fontSize: 11.5,
            color: "var(--ink-4)",
          }}
        >
          {total} found
        </span>
        <Ico.chev
          style={{
            width: 15,
            height: 15,
            color: "var(--ink-3)",
            transform: open ? "rotate(180deg)" : "none",
            transition: "transform .2s",
          }}
        />
      </div>
      {open && (
        <div>
          {total === 0 && (
            <div
              style={{
                padding: 12,
                fontSize: 12,
                color: "var(--ink-3)",
                borderTop: "1px solid var(--border)",
              }}
            >
              Nothing was found on this subject&apos;s website.
            </div>
          )}

          {s.profiles.length > 0 && (
            <>
              <SubLabel text={`Social accounts · ${s.profiles.length}`} />
              {s.profiles.map((p, i) => (
                <ProfileRow key={i} p={p} />
              ))}
            </>
          )}

          {s.people.length > 0 && (
            <>
              <SubLabel text={`People · ${s.people.length}`} />
              {s.people.map((pe, i) => (
                <PersonRow key={i} pe={pe} />
              ))}
            </>
          )}

          {s.emails.length > 0 && (
            <>
              <SubLabel text={`Emails · ${s.emails.length}`} />
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 6,
                  padding: "8px 14px 12px",
                }}
              >
                {s.emails.map((e) => (
                  <a
                    key={e}
                    href={`mailto:${e}`}
                    className="pill"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    {e}
                  </a>
                ))}
              </div>
            </>
          )}

          {s.phones.length > 0 && (
            <>
              <SubLabel text={`Phones · ${s.phones.length}`} />
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 6,
                  padding: "8px 14px 12px",
                }}
              >
                {s.phones.map((p) => (
                  <span
                    key={p}
                    className="pill"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    {p}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function PipelineSocials() {
  const companyId = usePipelineStore((st) => st.companyId);

  const { data, isLoading } = useQuery({
    queryKey: ["company-socials", companyId],
    queryFn: () => scrapersApi.socialByCompany(companyId as string),
    enabled: !!companyId,
    retry: false,
  });

  const subjects = data?.subjects || [];

  return (
    <div style={{ marginTop: 20 }}>
      <div className="section-h" style={{ marginBottom: 8 }}>
        From your last pipeline run
        {data ? ` · ${data.total} profiles` : ""}
      </div>
      {!companyId ? (
        <div className="card">
          <div
            className="bd"
            style={{ fontSize: 12.5, color: "var(--ink-3)" }}
          >
            Select a company (or run the pipeline) to see the social profiles
            its Social Intelligence stage collected for the company and its
            competitors.
          </div>
        </div>
      ) : isLoading ? (
        <div className="card">
          <div className="bd">
            <span className="spin" style={{ width: 16, height: 16 }} />
          </div>
        </div>
      ) : subjects.length === 0 ? (
        <div className="card">
          <div
            className="bd"
            style={{ fontSize: 12.5, color: "var(--ink-3)" }}
          >
            No social profiles collected yet — run the pipeline for this
            company and the Social Intelligence stage will populate this.
          </div>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {subjects.map((s, i) => (
            <SubjectCard key={i} s={s} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------- page ---------- */

export default function SocialScraperPage() {
  // The scrape result lives in the persisted store so it survives navigating
  // away and back (and a page refresh) instead of being component-local state.
  const socialScrape = usePipelineStore((s) => s.socialScrape);
  const setSocialScrape = usePipelineStore((s) => s.setSocialScrape);
  const [url, setUrl] = useState(() => socialScrape.url);
  const [loading, setLoading] = useState(false);
  const result = socialScrape.result;

  const run = async () => {
    const u = url.trim();
    if (!u) {
      toast.error("Enter a profile URL to scrape");
      return;
    }
    if (!/linkedin\.com|instagram\.com/i.test(u)) {
      toast.error("Only LinkedIn and Instagram profile URLs are supported");
      return;
    }
    setLoading(true);
    setSocialScrape({ url: u, result: null });
    try {
      const data = await scrapersApi.social(u);
      setSocialScrape({ url: u, result: data });
      if (data.success) toast.success(`${data.platform} profile scraped`);
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
          <div className="section-h">LinkedIn &amp; Instagram profiles</div>
          <h1>Social Scraper</h1>
          <p>
            Pull a public profile, see the parsed details, and toggle the raw
            scraped data.
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
              <Ico.atSign
                style={{ width: 14, height: 14, color: "var(--ink-3)" }}
              />
              <input
                placeholder="linkedin.com/in/username  ·  instagram.com/username"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !loading && run()}
              />
            </div>
            <button className="btn primary" onClick={run} disabled={loading}>
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
          Paste a LinkedIn or Instagram profile URL above. Expand the result to
          see what was scraped off — and toggle the raw data.
        </div>
      )}

      <PipelineSocials />
    </>
  );
}

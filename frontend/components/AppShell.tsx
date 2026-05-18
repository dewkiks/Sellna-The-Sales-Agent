"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { TopBar, type Crumb } from "./TopBar";
import { CompanionChat } from "./CompanionChat";
import { useAuth } from "@/context/AuthContext";
import { usePipelineStore } from "@/store/pipelineStore";

/* ---- breadcrumb map (keyed by pathname). Crumbs with an `href` are
   clickable; the first crumb's label is replaced with the active company. ---- */
const CI: Crumb = { label: "Company Intelligence", href: "/company" };
const CRUMBS: Record<string, Crumb[]> = {
  "/app": [{ label: "Acme", href: "/app" }, { label: "Dashboard" }],
  "/company": [{ label: "Acme", href: "/app" }, CI, { label: "New analysis" }],
  "/company/run": [{ label: "Acme", href: "/app" }, CI, { label: "Live run" }],
  "/company/2": [{ label: "Acme", href: "/app" }, CI, { label: "New analysis" }],
  "/competitors": [{ label: "Acme", href: "/app" }, { label: "Competitors" }],
  "/icp": [{ label: "Acme", href: "/app" }, { label: "ICP Generator" }],
  "/personas": [{ label: "Acme", href: "/app" }, { label: "Personas" }],
  "/outreach": [{ label: "Acme", href: "/app" }, { label: "Outreach" }],
  "/analytics": [{ label: "Acme", href: "/app" }, { label: "Analytics" }],
  "/web-scraper": [{ label: "Scrapers" }, { label: "Web Scraper" }],
  "/social-scraper": [{ label: "Scrapers" }, { label: "Social Scraper" }],
};

/* routes whose content fills the viewport instead of scrolling */
const FILL_ROUTES = new Set(["/app"]);

/* ---- TopBar slot: lets a page inject content into the persistent top bar ---- */
const TopBarSlotCtx = createContext<(node: ReactNode) => void>(() => {});

/**
 * Render `node` into the persistent top bar from inside a page.
 * `deps` controls when the slot is refreshed (the JSX is recreated each
 * render, so callers pass the reactive values it depends on).
 */
export function useTopBarSlot(node: ReactNode, deps: unknown[]) {
  const setSlot = useContext(TopBarSlotCtx);
  useEffect(() => {
    setSlot(node);
    return () => setSlot(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

/**
 * Persistent application shell. Rendered once by the (app) route-group
 * layout — the sidebar, top bar and 3D avatar stay mounted across route
 * changes; only the page content inside `.route-view` swaps and animates.
 */
export function AppShell({
  children,
  gate = true,
}: {
  children: ReactNode;
  gate?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname() || "";
  const { user, loading, configured } = useAuth();
  const companyName = usePipelineStore((s) => s.companyName);
  const jobId = usePipelineStore((s) => s.jobId);
  const [slot, setSlot] = useState<ReactNode>(null);

  useEffect(() => {
    if (gate && configured && !loading && !user) {
      router.replace("/");
    }
  }, [gate, configured, loading, user, router]);

  if (gate && loading) {
    return (
      <div
        className="screen-root"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--bg)",
        }}
      >
        <span className="spin" style={{ width: 28, height: 28 }} />
      </div>
    );
  }

  if (gate && configured && !user) return null;

  // First crumb is the active company — fall back to the product name.
  const base = CRUMBS[pathname] || [{ label: "Sellna", href: "/app" }];
  let crumbs: Crumb[] = base.map((c, i) =>
    i === 0 ? { ...c, label: companyName || "Sellna" } : c,
  );
  // From the company wizard, expose a link back to an in-progress run.
  if ((pathname === "/company" || pathname === "/company/2") && jobId) {
    crumbs = [...crumbs, { label: "Live run", href: "/company/run" }];
  }
  const fill = FILL_ROUTES.has(pathname);

  return (
    <TopBarSlotCtx.Provider value={setSlot}>
      <div className="site-root">
        <div className="app">
          <Sidebar />
          <div className="main">
            <TopBar crumbs={crumbs} rightExtras={slot} />
            <div className="content dot-bg">
              <div
                key={pathname}
                className={"route-view" + (fill ? " fill" : "")}
              >
                {children}
              </div>
            </div>
          </div>
        </div>
        <CompanionChat />
      </div>
    </TopBarSlotCtx.Provider>
  );
}

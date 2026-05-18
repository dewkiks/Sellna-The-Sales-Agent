"use client";

import {
  Fragment,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Ico } from "./icons";
import { useAuth } from "@/context/AuthContext";
import { usePipelineStore } from "@/store/pipelineStore";
import { companyApi } from "@/lib/api";
import { toast } from "@/lib/toast";

export type Crumb = { label: string; href?: string };

function MenuItem({
  icon,
  label,
  danger = false,
  disabled = false,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  danger?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        width: "100%",
        padding: "8px 10px",
        border: "none",
        background: "transparent",
        borderRadius: 8,
        cursor: disabled ? "default" : "pointer",
        font: "600 12.5px var(--font-sans)",
        color: danger ? "var(--red)" : "var(--ink-2)",
        textAlign: "left",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = danger
          ? "oklch(95% 0.04 25)"
          : "var(--bg-soft)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
      }}
    >
      {icon}
      {label}
    </button>
  );
}

export function TopBar({
  crumbs = [],
  rightExtras,
}: {
  crumbs?: Crumb[];
  rightExtras?: ReactNode;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, signOut } = useAuth();
  const clearStore = usePipelineStore((s) => s.clearStore);
  const [open, setOpen] = useState(false);
  const [wiping, setWiping] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const fullName = (user?.user_metadata?.full_name as string | undefined) || "";
  const email = user?.email || "";
  const initials =
    fullName
      .split(" ")
      .map((w) => w[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() ||
    email[0]?.toUpperCase() ||
    "A";

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const handleSignOut = async () => {
    setOpen(false);
    await signOut();
    router.push("/");
  };

  const handleWipe = async () => {
    if (wiping) return;
    if (
      !window.confirm(
        "Clear ALL data?\n\nThis permanently deletes every company, competitor, " +
          "ICP, persona, outreach asset and analysis from the database and " +
          "Qdrant. This cannot be undone."
      )
    )
      return;
    setWiping(true);
    try {
      const res = await companyApi.wipeAll();
      clearStore();
      await queryClient.invalidateQueries();
      toast.success(
        `All data cleared · ${res.qdrant_collections_deleted} Qdrant collections removed`
      );
      setOpen(false);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to clear data");
    } finally {
      setWiping(false);
    }
  };

  return (
    <div className="topbar">
      <Ico.panel
        className="crumb-icon"
        style={{ cursor: "pointer" }}
        onClick={() => router.push("/app")}
      />
      <div className="crumbs">
        {crumbs.map((c, i) => (
          <Fragment key={i}>
            {i > 0 && <span className="sep">/</span>}
            <span
              className={i === crumbs.length - 1 ? "leaf" : "twig"}
              style={{ cursor: c.href ? "pointer" : "default" }}
              onClick={c.href ? () => router.push(c.href as string) : undefined}
            >
              {c.label}
            </span>
          </Fragment>
        ))}
      </div>
      <div className="right">
        {rightExtras}
        <button className="btn ghost" style={{ padding: "7px 9px" }}>
          <Ico.bell style={{ width: 15, height: 15 }} />
        </button>
        <button className="btn primary">
          <Ico.share style={{ width: 14, height: 14 }} /> Share
        </button>

        <div ref={menuRef} style={{ position: "relative" }}>
          <div
            onClick={() => setOpen((o) => !o)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "3px 5px 3px 3px",
              border: "1px solid var(--border)",
              borderRadius: 999,
              background: open ? "var(--bg-soft)" : "#fff",
              cursor: "pointer",
            }}
          >
            <div
              className="avatar"
              style={{ width: 26, height: 26, fontSize: 11 }}
            >
              {initials}
            </div>
            <Ico.chev
              style={{
                width: 13,
                height: 13,
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
                top: "calc(100% + 6px)",
                right: 0,
                width: 234,
                background: "#fff",
                border: "1px solid var(--border)",
                borderRadius: 12,
                boxShadow: "var(--shadow-3)",
                padding: 6,
                zIndex: 50,
              }}
            >
              {(fullName || email) && (
                <div
                  style={{
                    padding: "8px 10px 10px",
                    borderBottom: "1px solid var(--border)",
                    marginBottom: 4,
                  }}
                >
                  {fullName && (
                    <div style={{ fontSize: 12.5, fontWeight: 700 }}>
                      {fullName}
                    </div>
                  )}
                  {email && (
                    <div
                      style={{
                        fontSize: 11.5,
                        color: "var(--ink-3)",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {email}
                    </div>
                  )}
                </div>
              )}
              <MenuItem
                icon={<Ico.arrow style={{ width: 14, height: 14 }} />}
                label="Sign out"
                onClick={handleSignOut}
              />
              <MenuItem
                icon={
                  wiping ? (
                    <span className="spin" style={{ width: 12, height: 12 }} />
                  ) : (
                    <Ico.trash style={{ width: 14, height: 14 }} />
                  )
                }
                label={wiping ? "Clearing…" : "Clear all data"}
                danger
                disabled={wiping}
                onClick={handleWipe}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

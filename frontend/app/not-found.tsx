"use client";

import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { Ico } from "@/components/icons";

export default function NotFound() {
  const router = useRouter();
  return (
    <AppShell gate={false}>
      <div
        style={{
          minHeight: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          style={{ textAlign: "center", maxWidth: 480, padding: 40, position: "relative" }}
        >
        <div
          style={{ position: "relative", display: "inline-block", marginBottom: 24 }}
        >
          <div
            style={{
              font: "700 120px var(--font-display)",
              color: "var(--blue)",
              letterSpacing: "-0.04em",
              lineHeight: 1,
            }}
          >
            404
          </div>
          <div
            style={{
              position: "absolute",
              top: 14,
              right: -18,
              padding: "3px 8px",
              borderRadius: 6,
              background: "var(--ink)",
              color: "#fff",
              font: "700 10px var(--font-mono)",
              transform: "rotate(8deg)",
            }}
          >
            no agent assigned
          </div>
        </div>
        <h1
          style={{
            font: "700 24px var(--font-sans)",
            letterSpacing: "-0.03em",
            margin: "0 0 8px",
          }}
        >
          This URL isn&apos;t on the pipeline.
        </h1>
        <p
          style={{
            color: "var(--ink-3)",
            fontSize: 14,
            lineHeight: 1.55,
            margin: "0 0 22px",
          }}
        >
          We searched, scraped, and asked all nine agents — no one&apos;s heard of
          this page. The most likely fix is to go somewhere that exists.
        </p>
        <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
          <button className="btn">
            <Ico.search style={{ width: 13, height: 13 }} /> Search docs
          </button>
          <button className="btn primary" onClick={() => router.push("/app")}>
            <Ico.home style={{ width: 13, height: 13 }} /> Back to dashboard
          </button>
        </div>
        </div>
      </div>
    </AppShell>
  );
}

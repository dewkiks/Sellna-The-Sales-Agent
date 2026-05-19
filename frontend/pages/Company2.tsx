import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Ico } from "@/components/icons";
import { Card, Steps, AGENTS } from "@/components/primitives";
import { pipelineApi, type PipelinePayload } from "@/lib/api";
import { usePipelineStore } from "@/store/pipelineStore";
import { toast } from "@/lib/toast";

const CUSTOMER_TYPES = ["B2B", "B2C", "B2B2C", "Government", "Marketplace"];
const PRICING_MODELS: { value: PipelinePayload["pricing_model"]; label: string }[] = [
  { value: "freemium", label: "Freemium" },
  { value: "subscription", label: "Subscription" },
  { value: "usage_based", label: "Usage-based" },
  { value: "enterprise", label: "Enterprise" },
  { value: "one_time", label: "One-time" },
  { value: "other", label: "Other" },
];

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="label">{label}</label>
      <input
        className="input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

export default function CompanyDetailsPage() {
  const navigate = useNavigate();
  const { draft, setDraft, setJobId, setCompanyName, setIsRunning } =
    usePipelineStore();

  const websiteHost = (draft.website || "acme.com").replace(/^https?:\/\//, "");
  const defaultName =
    draft.company_name ||
    websiteHost.split(".")[0].replace(/^./, (c) => c.toUpperCase()) + " Inc.";

  const [name, setName] = useState(defaultName);
  const [industry, setIndustry] = useState(
    draft.industry || "Developer tools · AI infra"
  );
  const [geo, setGeo] = useState(
    draft.target_geography || "North America + Western Europe"
  );
  const [customerType, setCustomerType] = useState<string>(
    draft.customer_type || "B2B"
  );
  const [pricing, setPricing] = useState<PipelinePayload["pricing_model"]>(
    draft.pricing_model || "usage_based"
  );
  const [stack, setStack] = useState(
    (draft.tech_stack || []).join(" · ") ||
      "Next.js · pgvector · Modal · Vercel"
  );
  const [busy, setBusy] = useState(false);

  const launch = async () => {
    setBusy(true);
    const techArr = stack
      .split(/[·,]/)
      .map((s) => s.trim())
      .filter(Boolean);
    const payload: PipelinePayload = {
      company_name: name,
      product_description:
        draft.product_description ||
        `${name} — go-to-market intelligence target at ${websiteHost}.`,
      industry: industry || "B2B SaaS",
      target_geography: geo || "Global",
      pricing_model: pricing,
      customer_type: customerType as PipelinePayload["customer_type"],
      core_problem_solved:
        draft.core_problem_solved || "General process inefficiency",
      product_features: draft.product_features || [],
      tech_stack: techArr,
      website: draft.website || websiteHost,
    };
    setDraft(payload);
    setCompanyName(name.replace(/\s+inc\.?$/i, ""));
    try {
      const res = await pipelineApi.runPipeline(payload);
      setJobId(res.job_id);
      setIsRunning(true);
      toast.success("Intelligence pipeline initiated — 9 agents activated");
      navigate("/company/run");
    } catch (e: any) {
      const detail =
        e?.response?.data?.detail ||
        e?.response?.data?.message ||
        e?.message ||
        "Please ensure the backend is running.";
      toast.error(`Pipeline error: ${detail}`);
      // Still proceed to the live run view so the design flow is visible.
      navigate("/company/run");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="page-h">
        <div>
          <div className="section-h">Step 2 of 4</div>
          <h1>Company details</h1>
          <p>
            Confirm what Sellna detected. Edits here re-rank every downstream
            agent&apos;s output.
          </p>
        </div>
        <button className="btn ghost" onClick={() => navigate("/app")}>
          <Ico.x style={{ width: 13, height: 13 }} /> Cancel
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14 }}>
        <Card>
          <Steps current={1} />
          <hr className="div" />

          <div
            style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}
          >
            <Field label="Company name" value={name} onChange={setName} />
            <Field label="Industry" value={industry} onChange={setIndustry} />
            <Field label="Target geography" value={geo} onChange={setGeo} />
            <div>
              <label className="label">Customer type</label>
              <select
                className="input"
                value={customerType}
                onChange={(e) => setCustomerType(e.target.value)}
              >
                {CUSTOMER_TYPES.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div
            style={{
              marginTop: 14,
              padding: 14,
              background: "var(--bg-soft)",
              borderRadius: 12,
              border: "1px solid var(--border)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginBottom: 10,
              }}
            >
              <Ico.sparkles style={{ width: 14, height: 14, color: "var(--blue)" }} />
              <strong style={{ fontSize: 12.5 }}>Advanced</strong>
              <span
                style={{ marginLeft: "auto", fontSize: 11, color: "var(--ink-3)" }}
              >
                +2 more
              </span>
            </div>
            <div
              style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}
            >
              <div>
                <label className="label">Pricing model</label>
                <select
                  className="input"
                  value={pricing}
                  onChange={(e) =>
                    setPricing(e.target.value as PipelinePayload["pricing_model"])
                  }
                >
                  {PRICING_MODELS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <Field label="Tech stack" value={stack} onChange={setStack} />
            </div>
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginTop: 18,
              gap: 8,
            }}
          >
            <button className="btn" onClick={() => navigate("/company")}>
              <Ico.chev
                style={{ width: 13, height: 13, transform: "rotate(90deg)" }}
              />{" "}
              Back
            </button>
            <button className="btn primary" disabled={busy} onClick={launch}>
              {busy ? "Launching…" : "Continue → Product intelligence"}
            </button>
          </div>
        </Card>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Card title="Pipeline preview" subtitle="What runs when you launch">
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {AGENTS.map((a) => (
                <div
                  key={a.id}
                  style={{ display: "flex", gap: 10, alignItems: "center" }}
                >
                  <div
                    className="num"
                    style={{
                      width: 20,
                      height: 20,
                      borderRadius: 5,
                      background: "var(--bg-muted)",
                      color: "var(--ink-3)",
                      font: "700 10px var(--font-mono)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {String(a.id).padStart(2, "0")}
                  </div>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{a.name}</div>
                </div>
              ))}
            </div>
          </Card>

          <Card title="Sample prefills" subtitle="Skip the typing">
            <div
              style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}
            >
              {["Stripe", "SpaceX", "OpenAI", "Linear"].map((n) => (
                <button
                  key={n}
                  className="btn"
                  style={{ justifyContent: "flex-start" }}
                  onClick={() => setName(`${n} Inc.`)}
                >
                  <span
                    style={{
                      width: 14,
                      height: 14,
                      borderRadius: 3,
                      background: "var(--bg-muted)",
                    }}
                  />
                  {n}
                </button>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}

import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Ico, type IconComponent } from "@/components/icons";
import { EmptyState } from "@/components/primitives";
import { personasApi } from "@/lib/api";
import { usePipelineStore } from "@/store/pipelineStore";
import { toast } from "@/lib/toast";

interface PersonaSection {
  i: IconComponent;
  t: string;
  items: string[];
}
interface PersonaData {
  name: string;
  title: string;
  co: string;
  quote: string;
  tint: "blue" | "violet";
  sections: PersonaSection[];
}

const SECTION_DEFS: { i: IconComponent; t: string; keys: string[] }[] = [
  { i: Ico.target, t: "Goals", keys: ["goals"] },
  { i: Ico.bug, t: "Pain points", keys: ["pain_points", "pains"] },
  { i: Ico.zap, t: "Motivations", keys: ["motivations", "drivers"] },
  { i: Ico.x, t: "Objections", keys: ["objections", "concerns"] },
  {
    i: Ico.inbox,
    t: "Where they live",
    keys: ["channels", "where_they_live", "watering_holes"],
  },
  {
    i: Ico.phone,
    t: "Buying signals",
    keys: ["buying_signals", "signals", "triggers"],
  },
];

function PersonaCard({ p }: { p: PersonaData }) {
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div
        style={{
          padding: "22px 22px 18px",
          display: "flex",
          alignItems: "center",
          gap: 16,
          background:
            p.tint === "violet"
              ? "linear-gradient(135deg, oklch(96% 0.04 295), #fff 80%)"
              : "linear-gradient(135deg, var(--blue-soft), #fff 80%)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 14,
            background: "#fff",
            border: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            font: "700 18px var(--font-display)",
            color: p.tint === "violet" ? "var(--violet)" : "var(--blue-deep)",
          }}
        >
          {p.name
            .split(" ")
            .map((w) => w[0])
            .join("")
            .slice(0, 2)}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: "700 17px var(--font-sans)", letterSpacing: "-0.02em" }}>
            {p.name}
          </div>
          <div style={{ fontSize: 12.5, color: "var(--ink-2)", fontWeight: 500 }}>
            {p.title}
          </div>
          <div style={{ fontSize: 11.5, color: "var(--ink-3)", marginTop: 2 }}>
            {p.co}
          </div>
        </div>
        <button className="btn ghost">
          <Ico.dot3 style={{ width: 14, height: 14 }} />
        </button>
      </div>

      <div
        style={{
          padding: "14px 22px",
          borderBottom: "1px solid var(--border)",
          background: "#fff",
        }}
      >
        <div
          style={{
            font: "italic 500 14px/1.55 var(--font-display)",
            color: "var(--ink-2)",
          }}
        >
          &quot;{p.quote}&quot;
        </div>
      </div>

      <div
        style={{
          padding: 18,
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
        }}
      >
        {p.sections.map((s) => (
          <div key={s.t}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginBottom: 6,
              }}
            >
              <div
                className={"icon-tile " + (p.tint === "violet" ? "violet" : "")}
                style={{ width: 22, height: 22, borderRadius: 6 }}
              >
                <s.i style={{ width: 11, height: 11 }} />
              </div>
              <strong style={{ fontSize: 12, letterSpacing: "-0.005em" }}>
                {s.t}
              </strong>
            </div>
            <ul
              style={{
                margin: 0,
                padding: 0,
                listStyle: "none",
                display: "flex",
                flexDirection: "column",
                gap: 3,
                fontSize: 12,
                color: "var(--ink-2)",
                lineHeight: 1.45,
              }}
            >
              {s.items.map((x, i) => (
                <li key={i}>· {x}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PersonasPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { companyId, companyName, isRunning } = usePipelineStore();

  const { data, isLoading } = useQuery({
    queryKey: ["personas", companyId],
    queryFn: () => personasApi.list(companyId as string),
    enabled: !!companyId,
    refetchInterval: isRunning ? 5000 : false,
    retry: false,
  });

  const personas: PersonaData[] = useMemo(() => {
    const raw = data?.personas;
    if (!raw || raw.length === 0) return [];
    return raw.slice(0, 4).map((p: any, idx: number): PersonaData => {
      const sections: PersonaSection[] = SECTION_DEFS.map((def) => {
        let items: string[] = [];
        for (const k of def.keys) {
          if (Array.isArray(p[k])) {
            items = p[k] as string[];
            break;
          }
        }
        return { i: def.i, t: def.t, items };
      });
      const title: string = p.title || p.role || "Buyer persona";
      const name: string =
        p.name || title.split("·")[0].split(",")[0].trim() || "Persona";
      return {
        name,
        title,
        co: p.company_context || p.company || p.segment || "—",
        quote: p.quote || p.voice || "—",
        tint: idx % 2 === 1 ? "violet" : "blue",
        sections,
      };
    });
  }, [data]);

  const generate = async () => {
    if (!companyId) {
      toast.error("Run a pipeline first to generate personas.");
      return;
    }
    try {
      await personasApi.generate(companyId);
      toast.success("Personas generated");
      await queryClient.invalidateQueries({ queryKey: ["personas", companyId] });
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to generate personas");
    }
  };

  return (
    <>
      <div className="page-h">
        <div>
          <div className="section-h">
            {personas.length} {personas.length === 1 ? "persona" : "personas"}
            {companyName ? ` · ${companyName}` : ""}
          </div>
          <h1>Buyer personas</h1>
          <p>
            Built by the Persona Builder agent. Each persona is grounded in real
            interview snippets when available, or synthetic if not.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={generate}>
            <Ico.users style={{ width: 13, height: 13 }} /> Switch ICP
          </button>
          <button
            className="btn primary"
            onClick={() => navigate("/outreach")}
          >
            <Ico.send style={{ width: 13, height: 13 }} /> Generate outreach
          </button>
        </div>
      </div>

      {!companyId ? (
        <EmptyState
          icon={Ico.users}
          title="No active company"
          body="Run a company analysis (or pick one from the sidebar) to build buyer personas."
        />
      ) : isLoading ? (
        <EmptyState
          icon={Ico.users}
          title="Loading personas…"
          body="Fetching the buyer personas for this company."
        />
      ) : personas.length === 0 ? (
        <EmptyState
          icon={Ico.users}
          title="No personas yet"
          body="The Persona Builder agent hasn't produced any personas for this company. Use Generate outreach after ICPs exist."
        />
      ) : (
        <div
          style={{ display: "grid", gap: 14, gridTemplateColumns: "1fr 1fr" }}
          className="wave"
        >
          {personas.map((p, i) => (
            <PersonaCard key={i} p={p} />
          ))}
        </div>
      )}
    </>
  );
}

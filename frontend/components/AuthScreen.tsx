import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Ico, BrandGlyph, type IconComponent } from "./icons";
import { useAuth } from "@/context/AuthContext";
import { toast } from "@/lib/toast";

export function AuthScreen({ mode }: { mode: "signup" | "login" }) {
  const navigate = useNavigate();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && user) navigate("/app", { replace: true });
  }, [loading, user, navigate]);

  return (
    <div className="site-root">
      <div
        style={{
          width: "100%",
          minHeight: "100vh",
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          background: "#fff",
        }}
      >
        <AuthFormPanel mode={mode} />
        <AuthContextPanel mode={mode} />
      </div>
    </div>
  );
}

function AuthFormPanel({ mode }: { mode: "signup" | "login" }) {
  const isSignup = mode === "signup";
  const navigate = useNavigate();
  const { login, register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!email.trim() || !password) {
      toast.error("Email and password are required.");
      return;
    }
    if (isSignup && password.length < 8) {
      toast.error("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      if (isSignup) {
        await register(email.trim(), password, fullName.trim());
        toast.success("Account created.");
      } else {
        await login(email.trim(), password);
        toast.success("Welcome back.");
      }
      navigate("/app");
    } catch (e: any) {
      toast.error(
        e?.response?.data?.detail || e?.message || "Authentication failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        padding: "32px 56px",
        minWidth: 0,
        overflow: "auto",
      }}
    >
      <div
        style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
        onClick={() => navigate("/")}
      >
        <div className="brand-mark">
          <BrandGlyph />
        </div>
        <div className="brand-name">
          sellna<span className="dot">.ai</span>
        </div>
      </div>
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          maxWidth: 380,
          margin: "0 auto",
          width: "100%",
        }}
      >
        <div className="section-h">{isSignup ? "Get started" : "Welcome back"}</div>
        <h1
          style={{
            margin: "2px 0 6px",
            font: "700 28px var(--font-sans)",
            letterSpacing: "-0.03em",
          }}
        >
          {isSignup ? (
            <>
              Run your first{" "}
              <em
                style={{
                  fontFamily: "var(--font-display)",
                  fontStyle: "italic",
                  fontWeight: 400,
                  color: "var(--blue)",
                }}
              >
                9-agent
              </em>{" "}
              pipeline.
            </>
          ) : (
            <>
              Sign back in to your{" "}
              <em
                style={{
                  fontFamily: "var(--font-display)",
                  fontStyle: "italic",
                  fontWeight: 400,
                  color: "var(--blue)",
                }}
              >
                command center.
              </em>
            </>
          )}
        </h1>
        <div style={{ color: "var(--ink-3)", fontSize: 13, marginBottom: 22 }}>
          {isSignup
            ? "First analysis is free — no credit card required."
            : "Pick up exactly where you left off."}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {isSignup && (
            <div>
              <label className="label">Full name</label>
              <input
                className="input"
                placeholder="Eva Niemi"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </div>
          )}
          <div>
            <label className="label">Work email</label>
            <input
              className="input"
              placeholder="eva@acme.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label
              className="label"
              style={{ display: "flex", justifyContent: "space-between" }}
            >
              <span>Password</span>
              {!isSignup && (
                <a style={{ color: "var(--blue)", fontWeight: 500, fontSize: 11.5 }}>
                  Forgot?
                </a>
              )}
            </label>
            <input
              className="input"
              type="password"
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submit();
              }}
            />
            {isSignup && (
              <div style={{ display: "flex", gap: 4, marginTop: 6 }}>
                {[0, 1, 2, 3, 4].map((i) => {
                  const filled = password.length >= (i + 1) * 3;
                  return (
                    <div
                      key={i}
                      style={{
                        flex: 1,
                        height: 3,
                        borderRadius: 2,
                        background: filled ? "var(--blue)" : "var(--border)",
                      }}
                    />
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <button
          className="btn primary"
          style={{
            marginTop: 20,
            justifyContent: "center",
            padding: "11px",
            fontSize: 13.5,
          }}
          disabled={busy}
          onClick={submit}
        >
          {busy
            ? "Working…"
            : isSignup
              ? "Create account"
              : "Sign in"}{" "}
          <Ico.arrow style={{ width: 14, height: 14 }} />
        </button>

        <div
          style={{
            textAlign: "center",
            marginTop: 14,
            fontSize: 12.5,
            color: "var(--ink-3)",
          }}
        >
          {isSignup ? (
            <>
              Already have an account?{" "}
              <a
                style={{ color: "var(--blue)", fontWeight: 600, cursor: "pointer" }}
                onClick={() => navigate("/login")}
              >
                Sign in
              </a>
            </>
          ) : (
            <>
              New here?{" "}
              <a
                style={{ color: "var(--blue)", fontWeight: 600, cursor: "pointer" }}
                onClick={() => navigate("/signup")}
              >
                Create an account
              </a>
            </>
          )}
        </div>
      </div>

      <div
        style={{
          marginTop: "auto",
          color: "var(--ink-4)",
          fontSize: 11.5,
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <span>© 2026 Sellna Labs</span>
        <span>SOC 2 in progress · GDPR aligned</span>
      </div>
    </div>
  );
}
function AuthContextPanel({ mode }: { mode: "signup" | "login" }) {
  const bullets: { i: IconComponent; t: string; d: string }[] =
    mode === "signup"
      ? [
          {
            i: Ico.zap,
            t: "First run, free",
            d: "Type a domain, get a complete GTM pack — no card.",
          },
          {
            i: Ico.brain,
            t: "9 specialist agents",
            d: "Each one owns a narrow job. Together they replace a 5-person GTM ops team.",
          },
          {
            i: Ico.target,
            t: "Gap-driven ICPs",
            d: 'Not just "decision-maker at SaaS Co". Real, ranked, weighted ICPs from positioning gaps.',
          },
          {
            i: Ico.send,
            t: "Multi-channel from one click",
            d: "Email, LinkedIn DM, call opener — generated per persona.",
          },
        ]
      : [
          {
            i: Ico.refresh,
            t: "Live pipeline",
            d: "Pick back up wherever your agents left off.",
          },
          {
            i: Ico.chart,
            t: "Performance drifted",
            d: "Open rate +6.4% vs. last week. Sellna nudged copy on 2 personas.",
          },
          {
            i: Ico.users,
            t: "3 new personas waiting",
            d: "Generated overnight for the linear.app analysis.",
          },
          {
            i: Ico.inbox,
            t: "12 fresh outreach assets",
            d: "Reviewed and ready to send.",
          },
        ];
  return (
    <div
      style={{
        position: "relative",
        padding: "48px 56px",
        background:
          "linear-gradient(155deg, oklch(95% 0.04 250), oklch(98% 0.01 250))",
        borderLeft: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        minWidth: 0,
        overflow: "hidden",
      }}
    >
      <div className="dot-bg" style={{ position: "absolute", inset: 0, opacity: 0.4 }} />
      <div className="ring-deco" style={{ width: 520, height: 520, top: -160, right: -200 }} />
      <div className="ring-deco" style={{ width: 380, height: 380, bottom: -140, left: -160 }} />

      <div style={{ position: "relative", maxWidth: 460 }}>
        <div className="pill blue" style={{ marginBottom: 18 }}>
          <span className="dot" style={{ background: "var(--blue)" }} />
          Why teams switch to Sellna
        </div>
        <div
          style={{
            font: "700 28px var(--font-sans)",
            letterSpacing: "-0.03em",
            lineHeight: 1.15,
          }}
        >
          {mode === "signup" ? (
            <>
              Stop sequencing on{" "}
              <em
                style={{
                  fontFamily: "var(--font-display)",
                  fontStyle: "italic",
                  fontWeight: 400,
                  color: "var(--blue)",
                }}
              >
                vibes.
              </em>
            </>
          ) : (
            <>
              Welcome back,{" "}
              <em
                style={{
                  fontFamily: "var(--font-display)",
                  fontStyle: "italic",
                  fontWeight: 400,
                  color: "var(--blue)",
                }}
              >
                Eva.
              </em>
            </>
          )}
        </div>
        <p
          style={{
            color: "var(--ink-2)",
            fontSize: 14,
            marginTop: 10,
            lineHeight: 1.55,
          }}
        >
          {mode === "signup"
            ? "Outbound is a research problem before it's a copywriting problem. Sellna closes both."
            : "Your agents have been busy. Here's what changed while you were away."}
        </p>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 12,
            marginTop: 24,
          }}
        >
          {bullets.map((b, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                gap: 12,
                padding: 14,
                borderRadius: 12,
                background: "rgba(255,255,255,.65)",
                backdropFilter: "blur(8px)",
                border: "1px solid var(--border)",
              }}
            >
              <div
                className="icon-tile"
                style={{ width: 32, height: 32, borderRadius: 9 }}
              >
                <b.i style={{ width: 14, height: 14 }} />
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 13 }}>{b.t}</div>
                <div style={{ color: "var(--ink-3)", fontSize: 12.5, marginTop: 2 }}>
                  {b.d}
                </div>
              </div>
            </div>
          ))}
        </div>

        <div
          style={{
            marginTop: 28,
            display: "flex",
            gap: 10,
            alignItems: "center",
            color: "var(--ink-3)",
            fontSize: 12,
          }}
        >
          <div style={{ display: "flex" }}>
            {["EN", "MR", "JK", "SP"].map((x, i) => (
              <div
                key={x}
                className="avatar"
                style={{
                  width: 24,
                  height: 24,
                  fontSize: 10,
                  marginLeft: i ? -6 : 0,
                  border: "2px solid #fff",
                }}
              >
                {x}
              </div>
            ))}
          </div>
          <span>
            Joining <strong style={{ color: "var(--ink-2)" }}>2,400+</strong> revenue
            teams running on Sellna.
          </span>
        </div>
      </div>
    </div>
  );
}


import { useEffect, useState } from "react";
import { subscribeToasts, type ToastMessage } from "@/lib/toast";
import { Ico } from "./icons";

export function Toaster() {
  const [items, setItems] = useState<ToastMessage[]>([]);

  useEffect(() => subscribeToasts(setItems), []);

  if (items.length === 0) return null;

  return (
    <div
      style={{
        position: "fixed",
        bottom: 18,
        right: 18,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        zIndex: 1000,
      }}
    >
      {items.map((t) => (
        <div key={t.id} className="toast" style={{ position: "relative", bottom: 0, right: 0 }}>
          {t.tone === "success" ? (
            <Ico.check className="check" style={{ width: 14, height: 14 }} />
          ) : (
            <Ico.x style={{ width: 14, height: 14, color: "var(--red)" }} />
          )}
          {t.text}
        </div>
      ))}
    </div>
  );
}

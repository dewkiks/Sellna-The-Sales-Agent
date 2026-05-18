"use client";

import { createElement, useEffect, useRef, type CSSProperties } from "react";

const SPLINE_URL =
  "https://prod.spline.design/CUkZYx8TqcIvt8aO/scene.splinecode";

export function SplineAvatar({
  size = 160,
  style,
}: {
  size?: number | string;
  style?: CSSProperties;
}) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // Block scroll-zoom + gestures from reaching the scene.
    const stop = (e: Event) => e.stopPropagation();
    const opts = { capture: true, passive: true } as AddEventListenerOptions;
    el.addEventListener("wheel", stop, opts);
    el.addEventListener("touchmove", stop, opts);
    el.addEventListener("gesturestart", stop, opts);
    el.addEventListener("gesturechange", stop, opts);

    const viewerEl = el.querySelector("spline-viewer");

    // Belt-and-suspenders cursor look-at:
    //  (a) `events-target="global"` makes the viewer listen on window itself.
    //  (b) a bridge that re-dispatches every window mousemove onto the viewer
    //      element + its internal <canvas>, in case (a) is unavailable.
    if (viewerEl) {
      try {
        viewerEl.setAttribute("events-target", "global");
      } catch {
        /* noop */
      }
    }

    let canvas: HTMLCanvasElement | null = null;
    let raf = 0;
    let tries = 0;

    // Hide the "Built with Spline" badge (<a id="logo">) inside the viewer's
    // shadow DOM. An injected <style> keeps it hidden even if the badge is
    // added after we stop polling.
    const hideSplineLogo = (root: ShadowRoot | null) => {
      if (!root) return;
      if (!root.getElementById("tg-hide-spline-logo")) {
        const st = document.createElement("style");
        st.id = "tg-hide-spline-logo";
        st.textContent = "#logo{display:none!important;}";
        root.appendChild(st);
      }
      const logo = root.getElementById("logo") as HTMLElement | null;
      if (logo) logo.style.display = "none";
    };

    const locate = () => {
      const root = (viewerEl as any)?.shadowRoot as ShadowRoot | null;
      hideSplineLogo(root);
      const found =
        (root?.querySelector("canvas") as HTMLCanvasElement | null) ||
        (el.querySelector("canvas") as HTMLCanvasElement | null);
      if (found) {
        canvas = found;
        return;
      }
      if (tries++ < 900) raf = requestAnimationFrame(locate);
    };
    locate();

    const forward = (clientX: number, clientY: number) => {
      const targets: (EventTarget | null)[] = [canvas, viewerEl];
      for (const t of targets) {
        if (!t) continue;
        t.dispatchEvent(
          new PointerEvent("pointermove", {
            clientX,
            clientY,
            bubbles: true,
            cancelable: true,
            pointerType: "mouse",
            view: window,
          })
        );
        t.dispatchEvent(
          new MouseEvent("mousemove", {
            clientX,
            clientY,
            bubbles: true,
            cancelable: true,
            view: window,
          })
        );
      }
    };

    const onMove = (e: MouseEvent) => {
      if (!e.isTrusted) return; // avoid feedback loops
      forward(e.clientX, e.clientY);
    };
    const onTouch = (e: TouchEvent) => {
      if (!e.isTrusted) return;
      const t = e.touches[0];
      if (t) forward(t.clientX, t.clientY);
    };
    window.addEventListener("mousemove", onMove, { passive: true });
    window.addEventListener("touchmove", onTouch, { passive: true });

    return () => {
      el.removeEventListener("wheel", stop, opts);
      el.removeEventListener("touchmove", stop, opts);
      el.removeEventListener("gesturestart", stop, opts);
      el.removeEventListener("gesturechange", stop, opts);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("touchmove", onTouch);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div
      ref={ref}
      className="spline-wrap"
      style={{ width: size, height: size, touchAction: "pan-y", ...style }}
    >
      {createElement("spline-viewer" as any, {
        url: SPLINE_URL,
        "events-target": "global",
        "loading-anim-type": "spinner-big-dark",
        style: {
          width: "100%",
          height: "100%",
          display: "block",
          background: "transparent",
        },
      } as any)}
    </div>
  );
}

export function AvatarDock() {
  return (
    <div className="avatar-dock" aria-label="Sellna companion">
      <div className="bubble">Ask me anything ↘</div>
      <SplineAvatar size={132} />
    </div>
  );
}

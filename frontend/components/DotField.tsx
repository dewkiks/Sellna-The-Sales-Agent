"use client";

// Antigravity-style repel field — donut-shaped force field around the cursor.
// When the cursor is idle, a virtual cursor sweeps the field on a slow
// Lissajous path so the dots are *always* flowing.

import { useEffect, useRef, type CSSProperties } from "react";

export function DotField({
  density = 22,
  color = "oklch(60% 0.18 250)",
  baseAlpha = 0.22,
  style,
  className = "",
}: {
  density?: number;
  color?: string;
  baseAlpha?: number;
  style?: CSSProperties;
  className?: string;
}) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let w = 0;
    let h = 0;
    let dpr = 1;
    let mx = -99999;
    let my = -99999;
    let lastMove = -99999;
    let curX = 0;
    let curY = 0;
    let raf = 0;
    let prev = performance.now();
    let running = true; // paused while the canvas is scrolled off-screen

    // Raw cursor coords — converted to canvas-local once per frame in draw()
    // instead of on every mousemove (a per-event getBoundingClientRect forces
    // a synchronous layout and is a common scroll-jank source).
    let clientX = -99999;
    let clientY = -99999;

    let cols = 0;
    let rows = 0;
    let n = 0;
    let origX!: Float32Array;
    let origY!: Float32Array;
    let posX!: Float32Array;
    let posY!: Float32Array;
    let velX!: Float32Array;
    let velY!: Float32Array;
    let streakLen!: Float32Array;

    const seed = () => {
      cols = Math.ceil(w / density) + 2;
      rows = Math.ceil(h / density) + 2;
      n = cols * rows;
      origX = new Float32Array(n);
      origY = new Float32Array(n);
      posX = new Float32Array(n);
      posY = new Float32Array(n);
      velX = new Float32Array(n);
      velY = new Float32Array(n);
      streakLen = new Float32Array(n);
      for (let j = 0; j < rows; j++) {
        for (let i = 0; i < cols; i++) {
          const k = j * cols + i;
          origX[k] = i * density - density;
          origY[k] = j * density - density;
          posX[k] = origX[k];
          posY[k] = origY[k];
        }
      }
      curX = w / 2;
      curY = h / 2;
    };

    const resize = () => {
      const r = canvas.getBoundingClientRect();
      // Cap DPR — a 2× canvas doubles the fill cost for no visible gain on a
      // faint decorative field.
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      w = Math.max(1, r.width);
      h = Math.max(1, r.height);
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      seed();
    };
    resize();

    const ro = new ResizeObserver(resize);
    ro.observe(canvas.parentElement || canvas);

    // Pause the animation loop entirely when the canvas is scrolled off-screen.
    const io = new IntersectionObserver(
      ([entry]) => {
        const visible = entry.isIntersecting;
        if (visible && !running) {
          running = true;
          prev = performance.now();
          raf = requestAnimationFrame(draw);
        }
        running = visible;
      },
      { threshold: 0 }
    );
    io.observe(canvas);

    const onMove = (e: MouseEvent) => {
      clientX = e.clientX;
      clientY = e.clientY;
      lastMove = performance.now();
    };
    window.addEventListener("mousemove", onMove, { passive: true });

    const STIFFNESS = 35;
    const DAMPING = 6;
    const RING_IN = 200;
    const RING_OUT = 620;
    const RING_OUT2 = RING_OUT * RING_OUT;
    const REPEL = 60;
    const IDLE_MS = 800; // after this with no movement → virtual cursor
    // Soft centre glow around the pivot — opacity + size ramp up there and
    // fade to a faint, tiny far field.
    const GLOW_R = 420;
    const GLOW_BOOST = 0.38;

    function draw(now: number) {
      if (!running) {
        raf = 0;
        return;
      }
      const dt = Math.min(0.05, (now - prev) / 1000);
      prev = now;
      const t = now / 1000;

      // Map the cursor into canvas-local space once per frame.
      if (clientX > -9000) {
        const r = canvas.getBoundingClientRect();
        mx = clientX - r.left;
        my = clientY - r.top;
      }

      // Virtual idle cursor — a brisk Lissajous sweep covering the canvas so
      // the field keeps actively flowing even when the real mouse is still.
      const vx =
        w * 0.5 +
        Math.sin(t * 0.52) * w * 0.36 +
        Math.sin(t * 0.29 + 1.7) * w * 0.16;
      const vy =
        h * 0.5 +
        Math.cos(t * 0.44) * h * 0.34 +
        Math.cos(t * 0.34 + 0.6) * h * 0.16;

      const idle = now - lastMove > IDLE_MS || mx < -9000;
      const targetX = idle ? vx : mx;
      const targetY = idle ? vy : my;
      // Ease toward the target — lively when idle, snappy when actively moving.
      const k = idle ? 0.12 : 0.3;
      curX += (targetX - curX) * k;
      curY += (targetY - curY) * k;

      // Idle orbital wobble — extra life around the donut centre.
      const wobX = Math.cos(t * 0.45) * 30 + Math.sin(t * 0.27) * 14;
      const wobY = Math.sin(t * 0.55) * 28 + Math.cos(t * 0.31 + 1.2) * 16;
      const cmx = curX + wobX;
      const cmy = curY + wobY;

      ctx.clearRect(0, 0, w, h);
      ctx.lineCap = "round";
      ctx.fillStyle = color;
      ctx.strokeStyle = color;

      for (let k2 = 0; k2 < n; k2++) {
        const ox = origX[k2];
        const oy = origY[k2];

        let tx = ox;
        let ty = oy;
        const dx = ox - cmx;
        const dy = oy - cmy;
        const d2 = dx * dx + dy * dy;
        if (d2 < RING_OUT2 * 1.4) {
          const d = Math.sqrt(d2) || 1;
          const ang = Math.atan2(dy, dx);
          const wob =
            Math.sin(ang * 3 + t * 1.7) * 0.1 +
            Math.sin(ang * 5 - t * 1.1 + 1.3) * 0.07 +
            Math.sin(ang * 2 + t * 0.6 + 2.0) * 0.06;
          const inR = RING_IN * (1 + wob);
          const outR = RING_OUT * (1 + wob * 0.6);
          if (d > inR && d < outR) {
            const tt = (d - inR) / (outR - inR);
            const bell = Math.sin(tt * Math.PI);
            const rx = dx / d;
            const ry = dy / d;
            const push = REPEL * bell;
            tx += rx * push;
            ty += ry * push;
          }
        }

        const ax = (tx - posX[k2]) * STIFFNESS - velX[k2] * DAMPING;
        const ay = (ty - posY[k2]) * STIFFNESS - velY[k2] * DAMPING;
        velX[k2] += ax * dt;
        velY[k2] += ay * dt;
        posX[k2] += velX[k2] * dt;
        posY[k2] += velY[k2] * dt;

        const vx2 = velX[k2];
        const vy2 = velY[k2];
        const vmag = Math.sqrt(vx2 * vx2 + vy2 * vy2);
        const cx = posX[k2];
        const cy = posY[k2];

        const targetTrail = Math.min(12, Math.max(0, vmag * 0.028 - 0.9));
        const lerp = targetTrail > streakLen[k2] ? 0.08 : 0.1;
        streakLen[k2] += (targetTrail - streakLen[k2]) * lerp;
        const trail = streakLen[k2];

        // Centre glow — opacity + size ramp up near the pivot, fading to a
        // faint, tiny far field.
        const gdx = cx - cmx;
        const gdy = cy - cmy;
        const gd = Math.sqrt(gdx * gdx + gdy * gdy);
        let prox = 1 - gd / GLOW_R;
        prox = prox > 0 ? prox * prox : 0;
        const dotAlpha = baseAlpha + prox * GLOW_BOOST;

        if (trail < 1.2) {
          ctx.globalAlpha = Math.min(1, dotAlpha);
          ctx.beginPath();
          ctx.arc(cx, cy, 0.95 + prox * 1.5, 0, Math.PI * 2);
          ctx.fill();
        } else {
          const inv = vmag > 0.001 ? 1 / vmag : 0;
          const dirX = vx2 * inv;
          const dirY = vy2 * inv;
          const half = trail * 0.5;
          ctx.globalAlpha = Math.min(1, dotAlpha + Math.min(0.4, trail * 0.05));
          ctx.lineWidth = 1.1 + prox * 1.5;
          ctx.beginPath();
          ctx.moveTo(cx - dirX * half, cy - dirY * half);
          ctx.lineTo(cx + dirX * half, cy + dirY * half);
          ctx.stroke();
        }
      }
      ctx.globalAlpha = 1;
      raf = requestAnimationFrame(draw);
    }
    raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      window.removeEventListener("mousemove", onMove);
    };
  }, [density, color, baseAlpha]);

  return (
    <canvas
      ref={ref}
      className={"dot-field " + className}
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        ...style,
      }}
    />
  );
}

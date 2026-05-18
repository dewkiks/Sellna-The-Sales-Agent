import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const s = (
  d: React.ReactNode,
  stroke = true
): ((p: IconProps) => JSX.Element) => {
  return (p: IconProps) => (
    <svg
      viewBox="0 0 24 24"
      fill={stroke ? "none" : "currentColor"}
      {...(stroke
        ? {
            stroke: "currentColor",
            strokeWidth: 1.6,
            strokeLinecap: "round" as const,
            strokeLinejoin: "round" as const,
          }
        : {})}
      {...p}
    >
      {d}
    </svg>
  );
};

export const Ico = {
  home: s(<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-7h-6v7H4a1 1 0 0 1-1-1z" />),
  brain: s(
    <path d="M9 3a3 3 0 0 0-3 3 3 3 0 0 0-3 3 3 3 0 0 0 1.5 2.6A3 3 0 0 0 6 18a3 3 0 0 0 3 3V3zM15 3a3 3 0 0 1 3 3 3 3 0 0 1 3 3 3 3 0 0 1-1.5 2.6A3 3 0 0 1 18 18a3 3 0 0 1-3 3V3z" />
  ),
  swords: s(
    <>
      <path d="M14.5 17.5 3 6V3h3l11.5 11.5" />
      <path d="M13 19l6-6" />
      <path d="M16 16l4 4" />
      <path d="M19 21l2-2" />
      <path d="M14.5 6.5 18 3h3v3l-3.5 3.5" />
      <path d="M5 14l-2 2v3h3l2-2" />
    </>
  ),
  target: s(
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" />
    </>
  ),
  users: s(
    <>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
      <circle cx="17" cy="7" r="2.5" />
      <path d="M16 13.5a4.5 4.5 0 0 1 5.5 4.5" />
    </>
  ),
  send: s(
    <>
      <path d="M22 2 11 13" />
      <path d="M22 2l-7 20-4-9-9-4z" />
    </>
  ),
  chart: s(
    <>
      <path d="M3 3v18h18" />
      <path d="M7 14l4-4 4 3 5-7" />
    </>
  ),
  search: s(
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </>
  ),
  plus: s(<path d="M12 5v14M5 12h14" />),
  share: s(
    <>
      <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
      <path d="M16 6l-4-4-4 4" />
      <path d="M12 2v14" />
    </>
  ),
  bell: s(
    <>
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </>
  ),
  chev: s(<path d="m6 9 6 6 6-6" />),
  chevR: s(<path d="m9 6 6 6-6 6" />),
  check: s(<path d="M20 6 9 17l-5-5" />),
  x: s(<path d="M18 6 6 18M6 6l12 12" />),
  copy: s(
    <>
      <rect x="9" y="9" width="13" height="13" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </>
  ),
  external: s(
    <>
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    </>
  ),
  globe: s(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3a14 14 0 0 1 0 18" />
      <path d="M12 3a14 14 0 0 0 0 18" />
    </>
  ),
  sparkles: s(
    <>
      <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
      <path d="M5.6 5.6l2 2M16.4 16.4l2 2M5.6 18.4l2-2M16.4 7.6l2-2" />
    </>
  ),
  zap: s(<path d="M13 2 3 14h7l-1 8 10-12h-7z" />),
  flask: s(
    <path d="M9 3h6M10 3v6L4 20a1 1 0 0 0 .9 1.5h14.2A1 1 0 0 0 20 20L14 9V3" />
  ),
  mic: s(
    <>
      <rect x="9" y="3" width="6" height="12" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0" />
      <path d="M12 18v4" />
    </>
  ),
  inbox: s(
    <>
      <path d="M22 12h-6l-2 3h-4l-2-3H2" />
      <path d="M5.5 5h13a2 2 0 0 1 1.9 1.3L22 12v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6l3.6-5.7A2 2 0 0 1 5.5 5z" />
    </>
  ),
  building: s(
    <>
      <rect x="4" y="3" width="16" height="18" rx="1.5" />
      <path d="M9 8h.01M9 12h.01M9 16h.01M14 8h.01M14 12h.01M14 16h.01" />
    </>
  ),
  phone: s(
    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z" />
  ),
  linkedin: s(
    <path d="M6.94 5a2 2 0 1 1-4 0 2 2 0 0 1 4 0M7 8.48H3V21h4zM13.32 8.48H9.34V21h3.94v-6.57c0-3.66 4.77-4 4.77 0V21H22v-7.93c0-6.17-7.06-5.94-8.72-2.91z" />,
    false
  ),
  filter: s(<path d="M22 3H2l8 9.5V19l4 2v-8.5z" />),
  refresh: s(
    <>
      <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
      <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
      <path d="M21 3v5h-5M3 21v-5h5" />
    </>
  ),
  arrow: s(<path d="M5 12h14M13 5l7 7-7 7" />),
  download: s(
    <>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <path d="M7 10l5 5 5-5M12 15V3" />
    </>
  ),
  layers: s(
    <>
      <path d="m12 2 10 6-10 6L2 8z" />
      <path d="m2 14 10 6 10-6" />
    </>
  ),
  bug: s(
    <>
      <rect x="8" y="6" width="8" height="14" rx="4" />
      <path d="M19 7l-3 2M5 7l3 2M19 13h-3M5 13h3M19 19l-3-2M5 19l3-2M9 6V4a3 3 0 0 1 6 0v2" />
    </>
  ),
  star: s(
    <path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z" />
  ),
  panel: s(
    <>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M9 3v18" />
    </>
  ),
  dot3: s(
    <>
      <circle cx="5" cy="12" r="1.6" />
      <circle cx="12" cy="12" r="1.6" />
      <circle cx="19" cy="12" r="1.6" />
    </>,
    false
  ),
  atSign: s(
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M16 8v5a3 3 0 0 0 6 0v-1A10 10 0 1 0 18 19.5" />
    </>
  ),
  code: s(
    <>
      <path d="m8 6-6 6 6 6" />
      <path d="m16 6 6 6-6 6" />
    </>
  ),
  trash: s(
    <>
      <path d="M3 6h18" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
      <path d="M10 11v6M14 11v6" />
    </>
  ),
};

export function BrandGlyph({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path
        d="M7 14.5C7 12 9 11 12 11s5-1 5-3.5S15 4 12 4 7 5.5 7 7.5M17 9.5c0 2.5-2 3.5-5 3.5s-5 1-5 3.5S9 20 12 20s5-1.5 5-3.5"
        stroke="#fff"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export type IconComponent = (p: IconProps) => JSX.Element;

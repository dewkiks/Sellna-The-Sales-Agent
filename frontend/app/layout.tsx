import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Sellna.ai — agentic sales intelligence",
  description: "Type a domain. Ship a go-to-market motion in 4 minutes.",
  icons: {
    icon:
      "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='6' fill='%231e6cf2'/%3E%3Cpath d='M7 14.5C7 12 9 11 12 11s5-1 5-3.5S15 4 12 4 7 5.5 7 7.5M17 9.5c0 2.5-2 3.5-5 3.5s-5 1-5 3.5S9 20 12 20s5-1.5 5-3.5' stroke='white' stroke-width='2.2' stroke-linecap='round' fill='none'/%3E%3C/svg%3E",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700;800&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
        <script
          type="module"
          src="https://unpkg.com/@splinetool/viewer@1.12.94/build/spline-viewer.js"
          async
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

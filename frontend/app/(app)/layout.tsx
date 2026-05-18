import type { ReactNode } from "react";
import { AppShell } from "@/components/AppShell";

/**
 * Layout for every authenticated route. Next.js keeps a layout mounted
 * across navigations between its child routes, so the shell (sidebar,
 * top bar, avatar) renders once and only the page content swaps.
 */
export default function AppGroupLayout({
  children,
}: {
  children: ReactNode;
}) {
  return <AppShell>{children}</AppShell>;
}

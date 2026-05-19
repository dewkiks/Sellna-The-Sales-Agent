import { useState } from "react";
import { Outlet, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/context/AuthContext";
import { Toaster } from "@/components/Toaster";
import { AppShell } from "@/components/AppShell";
import { AuthScreen } from "@/components/AuthScreen";
import Landing from "@/pages/Landing";
import NotFound from "@/pages/NotFound";
import Dashboard from "@/pages/Dashboard";
import Company from "@/pages/Company";
import CompanyRun from "@/pages/CompanyRun";
import Company2 from "@/pages/Company2";
import Competitors from "@/pages/Competitors";
import Icp from "@/pages/Icp";
import Personas from "@/pages/Personas";
import Outreach from "@/pages/Outreach";
import Analytics from "@/pages/Analytics";
import WebScraper from "@/pages/WebScraper";
import SocialScraper from "@/pages/SocialScraper";

/**
 * Layout route for every authenticated page. AppShell renders the persistent
 * sidebar / top bar / avatar once and gates access — unauthenticated visitors
 * are redirected to /login. The active page renders into <Outlet />.
 */
function ProtectedLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

export function App() {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<AuthScreen mode="login" />} />
          <Route path="/signup" element={<AuthScreen mode="signup" />} />

          <Route element={<ProtectedLayout />}>
            <Route path="/app" element={<Dashboard />} />
            <Route path="/company" element={<Company />} />
            <Route path="/company/run" element={<CompanyRun />} />
            <Route path="/company/2" element={<Company2 />} />
            <Route path="/competitors" element={<Competitors />} />
            <Route path="/icp" element={<Icp />} />
            <Route path="/personas" element={<Personas />} />
            <Route path="/outreach" element={<Outreach />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/web-scraper" element={<WebScraper />} />
            <Route path="/social-scraper" element={<SocialScraper />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
        <Toaster />
      </AuthProvider>
    </QueryClientProvider>
  );
}

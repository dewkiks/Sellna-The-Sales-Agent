import axios from "axios";
import type { AgentState } from "./agentStream";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8001/api/v1";

export const API_ROOT = API_BASE_URL;

// ---------------------------------------------------------------------------
// JWT token storage
// ---------------------------------------------------------------------------
// The access token is persisted in localStorage so a page refresh keeps the
// user signed in. It is attached to every API request by the interceptor below.

const TOKEN_KEY = "sellna_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Attach the bearer token (when present) to every outgoing request.
apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export const authApi = {
  register: async (
    email: string,
    password: string,
    fullName: string,
  ): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>("/auth/register", {
      email,
      password,
      full_name: fullName,
    });
    return response.data;
  },
  login: async (email: string, password: string): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>("/auth/login", {
      email,
      password,
    });
    return response.data;
  },
  me: async (): Promise<AuthUser> => {
    const response = await apiClient.get<AuthUser>("/auth/me");
    return response.data;
  },
};

export type UiIconName =
  | "LayoutDashboard"
  | "Building2"
  | "Crosshair"
  | "Users"
  | "UserCircle"
  | "Send"
  | "BarChart3"
  | "Zap"
  | "ChevronLeft"
  | "ChevronRight"
  | "Target"
  | "AlertTriangle"
  | "MessageSquare"
  | "Shield"
  | "Globe"
  | "Sparkles"
  | "Layers";

export interface PipelinePayload {
  company_name: string;
  product_description: string;
  industry: string;
  target_geography: string;
  pricing_model:
    | "freemium"
    | "subscription"
    | "usage_based"
    | "enterprise"
    | "one_time"
    | "other";
  customer_type: "B2B" | "B2C" | "B2B2C" | "Government" | "Marketplace";
  core_problem_solved: string;
  product_features: string[];
  tech_stack: string[];
  website: string;
}

export interface PipelineRunResponse {
  job_id: string;
  status: string;
  company: string;
  poll_url: string;
  message: string;
}

export interface PipelineStatusResponse {
  job_id: string;
  state: "PENDING" | "STARTED" | "RUNNING" | "SUCCESS" | "FAILURE" | "RETRY";
  progress?: number;
  status_msg?: string;
  company_id?: string;
  error?: string;
  result_url?: string;
  message?: string;
}

export interface PipelineResultResponse {
  company_id: string;
  icps: any[];
  personas: any[];
  outreach_assets: any[];
  competitors: any[];
  market_gaps?: any[];
  errors?: string[];
  warnings?: string[];
}

export interface DashboardSummaryResponse {
  counts: {
    companies_analyzed: number;
    competitors_found: number;
    icps_generated: number;
    personas_generated: number;
    outreach_assets_generated: number;
    market_gaps_found: number;
  };
}

export interface DashboardActivityResponse {
  total: number;
  events: Array<{
    type: "company" | "competitor" | "icp" | "persona" | "outreach" | "gap";
    action: string;
    target: string;
    created_at: string;
  }>;
}

export interface LandingConfigResponse {
  app_name: string;
  hero_badge: string;
  hero_title_lines: string[];
  hero_subtitle: string;
  features: Array<{ icon: UiIconName; title: string; desc: string }>;
  metrics: Array<{ value: string; label: string }>;
  workflow_steps: string[];
  hero_visual_labels: string[];
  footer_notice: string;
}

export interface AuthCopyResponse {
  app_name: string;
  login_left: { title: string; subtitle: string; bullets: string[] };
  signup_left: { title: string; subtitle: string; bullets: string[] };
}

export interface CompanyInputConfigResponse {
  steps: Array<{ id: number; label: string; icon: UiIconName }>;
  what_happens_next: Array<{ icon: UiIconName; label: string }>;
  pipeline_agents: string[];
  select_options: {
    customer_type: Array<{ value: string; label: string }>;
    pricing_model: Array<{ value: string; label: string }>;
  };
  defaults: {
    industry: string;
    target_geography: string;
    core_problem_solved: string;
  };
}

export interface OutreachAssetRecord {
  id: string;
  persona_id: string;
  company_id: string;
  channel: string;
  content: any;
  open_rate: number;
  reply_rate: number;
  conversion_rate: number;
  created_at: string;
}

export interface OutreachListResponse {
  company_id: string;
  total: number;
  assets: OutreachAssetRecord[];
}

export interface AnalyticsPerformanceResponse {
  company_id: string;
  total_assets: number;
  by_channel: Record<
    string,
    {
      count: number;
      avg_open_rate: number;
      avg_reply_rate: number;
      avg_conversion_rate: number;
    }
  >;
  weekly: Array<{
    week_start: string;
    assets: number;
    avg_open_rate: number;
    avg_reply_rate: number;
    avg_conversion_rate: number;
  }>;
}

export interface CompetitorWebData {
  website?: string;
  features?: string[];
  pricing_tiers?: string[];
  marketing_copy?: string;
  value_proposition?: string;
  target_audience?: string;
  scrape_success?: boolean;
  error?: string | null;
}

export interface CompetitorCleanData {
  clean_features?: string[];
  clean_pricing?: string;
  clean_positioning?: string;
  clean_value_proposition?: string;
}

export interface CompetitorListResponse {
  company_id: string;
  total: number;
  competitors: Array<{
    id: string;
    name: string;
    website: string;
    category: string;
    positioning: string;
    relevance_score: number;
    has_web_data: boolean;
    has_clean_data: boolean;
    web_data?: CompetitorWebData | null;
    clean_data?: CompetitorCleanData | null;
    created_at: string;
  }>;
}

/** Durable snapshot of a run's agent stream, restored after a page refresh. */
export interface PersistedRunResponse {
  job_id: string;
  company_id: string | null;
  agents: AgentState[];
  active_agent: string | null;
  done: boolean;
}

export const pipelineApi = {
  runPipeline: async (
    payload: PipelinePayload
  ): Promise<PipelineRunResponse> => {
    const response = await apiClient.post<PipelineRunResponse>(
      "/pipeline/run",
      payload
    );
    return response.data;
  },
  getPipelineStatus: async (
    jobId: string
  ): Promise<PipelineStatusResponse> => {
    const response = await apiClient.get<PipelineStatusResponse>(
      `/pipeline/status/${jobId}`
    );
    return response.data;
  },
  getPipelineResult: async (
    jobId: string
  ): Promise<PipelineResultResponse> => {
    const response = await apiClient.get<PipelineResultResponse>(
      `/pipeline/result/${jobId}`
    );
    return response.data;
  },
  abortPipeline: async (
    jobId: string
  ): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post<{ status: string; message: string }>(
      `/pipeline/abort/${jobId}`
    );
    return response.data;
  },
  /** Fetch the server-persisted agent-stream snapshot for a run. */
  getRun: async (jobId: string): Promise<PersistedRunResponse> => {
    const response = await apiClient.get<PersistedRunResponse>(
      `/pipeline/run/${jobId}`
    );
    return response.data;
  },
};

export const dashboardApi = {
  getSummary: async (): Promise<DashboardSummaryResponse> => {
    const response = await apiClient.get<DashboardSummaryResponse>(
      "/dashboard/summary"
    );
    return response.data;
  },
  getActivity: async (limit = 20): Promise<DashboardActivityResponse> => {
    const response = await apiClient.get<DashboardActivityResponse>(
      "/dashboard/activity",
      { params: { limit } }
    );
    return response.data;
  },
};

export const uiApi = {
  getLanding: async (): Promise<LandingConfigResponse> => {
    const response = await apiClient.get<LandingConfigResponse>("/ui/landing");
    return response.data;
  },
  getAuthCopy: async (): Promise<AuthCopyResponse> => {
    const response = await apiClient.get<AuthCopyResponse>("/ui/auth-copy");
    return response.data;
  },
  getCompanyInputConfig: async (): Promise<CompanyInputConfigResponse> => {
    const response = await apiClient.get<CompanyInputConfigResponse>(
      "/ui/company-input"
    );
    return response.data;
  },
  getPersonasConfig: async (): Promise<{
    sections: Array<{
      key: string;
      label: string;
      icon: UiIconName;
      color: string;
      bg: string;
    }>;
  }> => {
    const response = await apiClient.get(`/ui/personas`);
    return response.data;
  },
};

export const competitorsApi = {
  list: async (companyId: string): Promise<CompetitorListResponse> => {
    const response = await apiClient.get<CompetitorListResponse>(
      `/competitors/${companyId}`
    );
    return response.data;
  },
  discover: async (
    companyId: string
  ): Promise<{ company_id: string; total: number }> => {
    const response = await apiClient.post(`/competitors/discover/${companyId}`);
    return response.data;
  },
  scrape: async (companyId: string, renderJs = false): Promise<any> => {
    const response = await apiClient.post(
      `/competitors/scrape/${companyId}`,
      undefined,
      { params: { render_js: renderJs } }
    );
    return response.data;
  },
};

export const icpApi = {
  list: async (
    companyId: string
  ): Promise<{ company_id: string; total: number; icps: any[] }> => {
    const response = await apiClient.get(`/icp/${companyId}`);
    return response.data;
  },
  generate: async (
    companyId: string,
    numProfiles = 3
  ): Promise<{ company_id: string; icps: any[]; market_gaps: any[] }> => {
    const response = await apiClient.post(`/icp/generate`, {
      company_id: companyId,
      num_profiles: numProfiles,
    });
    return response.data;
  },
};

export const personasApi = {
  list: async (
    companyId: string
  ): Promise<{ company_id: string; total: number; personas: any[] }> => {
    const response = await apiClient.get(`/personas/${companyId}`);
    return response.data;
  },
  generate: async (
    companyId: string,
    icpId?: string,
    numPersonas = 2
  ): Promise<{ company_id: string; total: number; personas: any[] }> => {
    const response = await apiClient.post(`/personas/generate`, {
      company_id: companyId,
      icp_id: icpId ?? null,
      num_personas: numPersonas,
    });
    return response.data;
  },
};

export const outreachApi = {
  list: async (companyId: string): Promise<OutreachListResponse> => {
    const response = await apiClient.get<OutreachListResponse>(
      `/outreach/${companyId}`
    );
    return response.data;
  },
  update: async (
    assetId: string,
    fields: { subject?: string; body?: string; call_to_action?: string }
  ): Promise<{ id: string; channel: string; content: any }> => {
    const response = await apiClient.patch(`/outreach/asset/${assetId}`, fields);
    return response.data;
  },
};

export const outreachGenApi = {
  generate: async (
    companyId: string,
    personaId: string,
    channels: string[]
  ) => {
    const response = await apiClient.post(`/outreach/generate`, {
      company_id: companyId,
      persona_id: personaId,
      channels,
    });
    return response.data;
  },
};

export const analyticsApi = {
  performance: async (
    companyId: string
  ): Promise<AnalyticsPerformanceResponse> => {
    const response = await apiClient.get<AnalyticsPerformanceResponse>(
      `/analytics/performance/${companyId}`
    );
    return response.data;
  },
};

export interface WebScrapeResult {
  url: string;
  requested_url: string;
  success: boolean;
  status: number;
  error: string | null;
  rendered: boolean;
  elapsed_ms: number;
  redirect_chain: string[];
  extracted: {
    url?: string;
    title?: string;
    meta_description?: string;
    headings?: Record<string, string[]>;
    paragraphs?: string[];
    text_content?: string;
    links?: Array<{ text: string; href: string }>;
    images?: Array<{ alt: string; src: string }>;
    tables?: string[][][];
    structured_data?: any[];
    meta_tags?: Record<string, string>;
  };
  raw_html: string;
  raw_html_truncated: boolean;
  raw_html_bytes: number;
}

export interface SocialScrapeResult {
  url: string;
  platform: string;
  success: boolean;
  error: string | null;
  source: string | null;
  profile: Record<string, any>;
  raw: Record<string, any>;
}

export interface PipelineSocialProfile {
  platform: string;
  profile_type: string;
  url: string;
  success: boolean;
  data: Record<string, any>;
  created_at: string;
}

export interface PipelinePerson {
  name: string;
  title: string;
  linkedin_url: string;
  source: string;
}

export interface CompanySocialSubject {
  subject_type: string;
  subject_id: string | null;
  subject_name: string;
  profiles: PipelineSocialProfile[];
  people: PipelinePerson[];
  emails: string[];
  phones: string[];
}

export interface CompanySocialsResponse {
  company_id: string;
  total: number;
  subjects: CompanySocialSubject[];
}

export const scrapersApi = {
  web: async (url: string, renderJs = false): Promise<WebScrapeResult> => {
    const response = await apiClient.post<WebScrapeResult>("/scrapers/web", {
      url,
      render_js: renderJs,
    });
    return response.data;
  },
  social: async (url: string): Promise<SocialScrapeResult> => {
    const response = await apiClient.post<SocialScrapeResult>(
      "/scrapers/social",
      { url }
    );
    return response.data;
  },
  socialByCompany: async (
    companyId: string
  ): Promise<CompanySocialsResponse> => {
    const response = await apiClient.get<CompanySocialsResponse>(
      `/scrapers/social/${companyId}`
    );
    return response.data;
  },
};

export const companyApi = {
  list: async (): Promise<{
    total: number;
    companies: Array<{
      id: string;
      name: string;
      industry: string;
      created_at: string;
      has_analysis: boolean;
    }>;
  }> => {
    const response = await apiClient.get("/company/");
    return response.data;
  },
  remove: async (
    companyId: string
  ): Promise<{ company_id: string; status: string }> => {
    const response = await apiClient.delete(`/company/${companyId}`);
    return response.data;
  },
  wipeAll: async (): Promise<{
    status: string;
    qdrant_collections_deleted: number;
  }> => {
    const response = await apiClient.post("/company/wipe-all");
    return response.data;
  },
};

export const exportApi = {
  /** Download a company's full data set as an .xlsx workbook (binary blob). */
  companyXlsx: async (companyId: string): Promise<Blob> => {
    const response = await apiClient.get(
      `/export/company/${companyId}/xlsx`,
      { responseType: "blob" }
    );
    return response.data as Blob;
  },
};

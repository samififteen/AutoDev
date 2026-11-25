import type {
  AgentLog,
  DashboardStats,
  DiffResponse,
  ExecutionDetail,
  ExecutionSummary,
  HealthInfo,
  Issue,
  Paginated,
  PullRequest,
  PullRequestDraft,
  PullRequestListItem,
  Repository,
  RepositoryAnalysis,
  SettingsPayload,
  SystemInfo,
  SystemStatus,
  Task,
} from "../types";

export const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
const TOKEN_KEY = "autodev.apiToken";

export function getApiToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setApiToken(token: string): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token.trim());
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage can be unavailable in privacy modes; the API will report 401 instead
  }
}

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(status: number, message: string, code = "request_failed", details: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function authHeaders(): Record<string, string> {
  const token = getApiToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = getApiToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      0,
      "Cannot reach the AutoDev backend. Is the API server running?",
      "network_error",
    );
  }
  if (!response.ok) {
    let payload: any = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    const message =
      payload?.error?.message ??
      payload?.detail ??
      (typeof payload?.detail === "string" ? payload.detail : null) ??
      `Request failed with HTTP ${response.status}`;
    throw new ApiError(
      response.status,
      typeof message === "string" ? message : JSON.stringify(message),
      payload?.error?.code ?? "request_failed",
      payload?.error?.details ?? payload?.detail ?? null,
    );
  }
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

export const api = {
  health: () => request<HealthInfo>("/api/health"),
  systemInfo: () => request<SystemInfo>("/api/system/info"),
  systemStatus: () => request<SystemStatus>("/api/system/status"),
  dashboard: () => request<DashboardStats>("/api/dashboard/stats"),

  repositories: (params: { search?: string; visibility?: string; language?: string; page?: number; page_size?: number } = {}) =>
    request<Paginated<Repository>>(`/api/repositories${query(params)}`),
  repository: (id: number) => request<Repository>(`/api/repositories/${id}`),
  connectRepository: (body: { full_name: string; default_branch?: string | null }) =>
    request<Repository>("/api/repositories/connect", { method: "POST", body: JSON.stringify(body) }),
  analyzeRepository: (id: number) =>
    request<{ repository: Repository; summary: RepositoryAnalysis }>(
      `/api/repositories/${id}/analyze`,
      { method: "POST" },
    ),
  refreshRepository: (id: number) =>
    request<Repository>(`/api/repositories/${id}/refresh`, { method: "POST" }),
  issues: (id: number, state = "open") =>
    request<Issue[]>(`/api/repositories/${id}/issues?state=${state}`),

  tasks: (
    params: {
      repository_id?: number;
      status?: string;
      priority?: string;
      search?: string;
      page?: number;
      page_size?: number;
    } = {},
  ) => request<Paginated<Task>>(`/api/tasks${query(params)}`),
  createTask: (body: {
    repository_id: number;
    title: string;
    description: string;
    priority: string;
    github_issue_number?: number | null;
    labels?: string[];
  }) => request<Task>("/api/tasks", { method: "POST", body: JSON.stringify(body) }),
  executeTask: (id: number) =>
    request<ExecutionDetail>(`/api/tasks/${id}/execute`, { method: "POST" }),

  executions: (
    params: {
      status?: string;
      repository_id?: number;
      search?: string;
      sort?: string;
      order?: string;
      page?: number;
      page_size?: number;
    } = {},
  ) => request<Paginated<ExecutionSummary>>(`/api/executions${query(params)}`),
  execution: (id: number) => request<ExecutionDetail>(`/api/executions/${id}`),
  logs: (id: number, limit = 400) =>
    request<{ items: AgentLog[]; total: number }>(`/api/executions/${id}/logs?limit=${limit}`),
  approvePlan: (id: number) =>
    request<ExecutionDetail>(`/api/executions/${id}/approve-plan`, { method: "POST" }),
  cancelExecution: (id: number) =>
    request<ExecutionDetail>(`/api/executions/${id}/cancel`, { method: "POST" }),
  retryExecution: (id: number) =>
    request<ExecutionDetail>(`/api/executions/${id}/retry`, { method: "POST" }),
  diff: (id: number) => request<DiffResponse>(`/api/executions/${id}/diff`),
  pullRequestDraft: (id: number) =>
    request<PullRequestDraft>(`/api/executions/${id}/pr-draft`),
  createPullRequest: (id: number, body: { confirm: boolean; title?: string; body?: string }) =>
    request<PullRequest>(`/api/executions/${id}/create-pr`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  pullRequests: (params: { search?: string; status?: string; page?: number; page_size?: number } = {}) =>
    request<Paginated<PullRequestListItem>>(`/api/pull-requests${query(params)}`),

  settings: () => request<SettingsPayload>("/api/settings"),
  updateSettings: (body: Partial<Pick<SettingsPayload, "agent" | "testing">>) =>
    request<SettingsPayload>("/api/settings", { method: "PUT", body: JSON.stringify(body) }),

  streamUrl: (executionId: number) => {
    const token = getApiToken();
    return `${API_BASE}/api/executions/${executionId}/stream${token ? `?token=${encodeURIComponent(token)}` : ""}`;
  },

  async downloadPatch(executionId: number): Promise<void> {
    const response = await fetch(
      `${API_BASE}/api/executions/${executionId}/diff/patch`,
      { headers: authHeaders() },
    );
    if (!response.ok) {
      throw new ApiError(response.status, "Could not download the patch file");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `autodev-execution-${executionId}.patch`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  },
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong";
}

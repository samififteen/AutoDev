import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/ToastProvider";
import { api } from "../services/api";
import type { DashboardStats, SystemInfo, SystemStatus } from "../types";
import Overview from "./Overview";

vi.mock("../services/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../services/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      dashboard: vi.fn(),
      systemStatus: vi.fn(),
      systemInfo: vi.fn(),
    },
  };
});

const stats: DashboardStats = {
  repositories_connected: 2,
  tasks_total: 9,
  tasks_processed: 7,
  tasks_completed: 5,
  tasks_failed: 2,
  pull_requests_created: 1,
  average_duration_seconds: 42,
  active_executions: 0,
  recent_activity: [
    {
      execution_id: 11,
      task_id: 3,
      task_title: "Fix multiplication in calculator",
      repository: "octocat/demo-calculator",
      status: "completed",
      started_at: "2026-01-01T00:00:00Z",
      duration_seconds: 12,
      pull_request_url: null,
    },
  ],
  chart: [{ date: "2026-01-01", completed: 5, failed: 2, pull_requests: 1 }],
};

const status = {
  backend: { name: "Backend", status: "ok", detail: "API responding" },
  database: { name: "Database", status: "ok", detail: "SQLite connected" },
  github: { name: "GitHub", status: "unverified", detail: "GitHub is not configured" },
  ai_provider: { name: "AI", status: "configured", detail: "Demo fixtures" },
  sandbox: { name: "Sandbox", status: "ok", detail: "Local sandbox" },
  agent_worker: { name: "Worker", status: "disabled", detail: "Not required in local mode" },
} as SystemStatus;

const info: SystemInfo = {
  app_name: "AutoDev",
  version: "0.1.0",
  environment: "development",
  demo_mode: true,
  ai_provider: "demo",
  ai_model: "deterministic-fixture",
  github_configured: false,
  auth_enabled: false,
  sandbox_mode: "local",
  limits: {},
};

describe("Overview", () => {
  beforeEach(() => {
    vi.mocked(api.dashboard).mockResolvedValue(stats);
    vi.mocked(api.systemStatus).mockResolvedValue(status);
    vi.mocked(api.systemInfo).mockResolvedValue(info);
  });

  it("renders stored metrics and recent activity", async () => {
    render(
      <MemoryRouter>
        <ToastProvider>
          <Overview />
        </ToastProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Fix multiplication in calculator")).toBeInTheDocument();
    expect(screen.getByText("Tasks processed")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getAllByText("Pull requests").length).toBeGreaterThan(0);
    expect(screen.getAllByText("completed").length).toBeGreaterThan(0);
    expect(screen.getByText(/GitHub is not configured/)).toBeInTheDocument();
  });

  it("shows onboarding when no repository is connected", async () => {
    vi.mocked(api.dashboard).mockResolvedValue({
      ...stats,
      repositories_connected: 0,
      recent_activity: [],
    });

    render(
      <MemoryRouter>
        <ToastProvider>
          <Overview />
        </ToastProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Run your first autonomous task")).toBeInTheDocument();
    expect(screen.getByText(/bundled demo repository/i)).toBeInTheDocument();
  });
});

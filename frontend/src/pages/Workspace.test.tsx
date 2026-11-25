import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/ToastProvider";
import { api } from "../services/api";
import type {
  AgentLog,
  DiffResponse,
  ExecutionDetail,
  PullRequestDraft,
  Repository,
} from "../types";
import Workspace from "./Workspace";

vi.mock("../services/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../services/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      execution: vi.fn(),
      logs: vi.fn(),
      diff: vi.fn(),
      pullRequestDraft: vi.fn(),
    },
  };
});

const repository: Repository = {
  id: 1,
  github_id: null,
  owner: "octocat",
  name: "demo-calculator",
  full_name: "octocat/demo-calculator",
  description: "Demo calculator",
  default_branch: "main",
  language: "Python",
  visibility: "public",
  clone_url: null,
  html_url: null,
  is_demo: true,
  connected: true,
  analysis: null,
  analyzed_at: null,
  updated_at: "2026-01-01T00:00:00Z",
  created_at: "2026-01-01T00:00:00Z",
};

const execution: ExecutionDetail = {
  id: 9,
  task_id: 2,
  status: "completed",
  current_stage: "completed",
  started_at: "2026-01-01T00:00:00Z",
  completed_at: "2026-01-01T00:00:12Z",
  duration_seconds: 12.5,
  summary: "All tests passed and validation succeeded.",
  branch_name: "autodev/fix-multiplication-2",
  base_branch: "main",
  ai_provider: "demo",
  ai_model: "deterministic-fixture",
  correction_attempts: 1,
  error_message: null,
  created_at: "2026-01-01T00:00:00Z",
  task: {
    id: 2,
    repository_id: 1,
    github_issue_number: 1,
    title: "Fix multiplication in calculator",
    description: "multiply(2, 3) returns 5.",
    priority: "high",
    status: "completed",
    labels: ["bug"],
    source: "github",
    repository,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  pull_request: null,
  plan: {
    summary: "Correct the multiply implementation and cover it with a regression test.",
    steps: [
      { index: 1, title: "Inspect calculator.py", detail: "Find the multiply function." },
      { index: 2, title: "Fix and test", detail: null },
    ],
    files_likely_affected: ["calculator.py", "tests/test_calculator.py"],
    test_plan: ["python -m pytest -q"],
    risks: [],
  },
  plan_approved: true,
  validation: {
    passed: true,
    checks: [
      { name: "tests", passed: true, detail: "8 tests passed", severity: "error" },
      { name: "secrets", passed: true, detail: "No secrets detected", severity: "error" },
    ],
    files_changed: ["calculator.py"],
    additions: 1,
    deletions: 1,
    secrets: [],
    summary: "All checks passed",
    diff_size: 120,
  },
  files_inspected: ["calculator.py", "tests/test_calculator.py"],
  prompt_tokens: 0,
  completion_tokens: 0,
  error_details: null,
  file_changes: [
    {
      id: 3,
      execution_id: 9,
      file_path: "calculator.py",
      change_type: "modified",
      diff: "@@ -1 +1 @@\n-return a + b\n+return a * b\n",
      additions: 1,
      deletions: 1,
      original_content: "return a + b\n",
      modified_content: "return a * b\n",
      created_at: "2026-01-01T00:00:00Z",
    },
  ],
  test_executions: [
    {
      id: 4,
      execution_id: 9,
      command: "python -m pytest -q",
      status: "passed",
      output: "8 passed in 0.12s",
      summary: "8 passed",
      passed_count: 8,
      failed_count: 0,
      duration_seconds: 0.12,
      attempt: 1,
      created_at: "2026-01-01T00:00:00Z",
    },
  ],
  timeline: [
    { key: "plan", label: "Plan approved", status: "completed" },
    { key: "tests", label: "Tests passed", status: "completed" },
  ],
  actions: {
    approve_plan: false,
    cancel: false,
    retry: true,
    view_diff: true,
    create_pull_request: false,
    preview_pull_request: true,
  },
  demo_mode: true,
};

const logs: AgentLog[] = [
  {
    id: 1,
    level: "info",
    stage: "tests",
    message: "8 passed in 0.12s",
    created_at: "2026-01-01T00:00:05Z",
  },
];

const diff: DiffResponse = {
  execution_id: 9,
  branch: "autodev/fix-multiplication-2",
  base_branch: "main",
  files: [
    {
      path: "calculator.py",
      change_type: "modified",
      additions: 1,
      deletions: 1,
      diff: "@@ -1 +1 @@\n-return a + b\n+return a * b\n",
      original_content: "return a + b\n",
      modified_content: "return a * b\n",
    },
  ],
  unified_diff: "@@ -1 +1 @@\n-return a + b\n+return a * b\n",
  additions: 1,
  deletions: 1,
};

const draft: PullRequestDraft = {
  title: "Fix multiplication",
  body: "## Summary\n- multiply now uses *",
  branch: "autodev/fix-multiplication-2",
  base_branch: "main",
  provider: "demo",
  demo_mode: true,
};

function renderWorkspace() {
  return render(
    <MemoryRouter initialEntries={["/workspace/9"]}>
      <ToastProvider>
        <Routes>
          <Route path="/workspace/:executionId" element={<Workspace />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("Workspace", () => {
  beforeEach(() => {
    vi.mocked(api.execution).mockResolvedValue(execution);
    vi.mocked(api.logs).mockResolvedValue({ items: logs, total: 1 });
    vi.mocked(api.diff).mockResolvedValue(diff);
    vi.mocked(api.pullRequestDraft).mockResolvedValue(draft);
  });

  it("renders the real execution detail, test output and streamed logs", async () => {
    renderWorkspace();

    expect(await screen.findByText("Fix multiplication in calculator")).toBeInTheDocument();
    expect(screen.getByText("Correct the multiply implementation and cover it with a regression test.")).toBeInTheDocument();
    expect(screen.getByText(/8 tests passed/)).toBeInTheDocument();
    expect((await screen.findAllByText(/8 passed in 0\.12s/)).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/demo fixtures/i)).toBeInTheDocument();
    expect(screen.getByText("All tests passed and validation succeeded.")).toBeInTheDocument();
  });

  it("opens the generated diff from the real execution API", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    await screen.findByText("Fix multiplication in calculator");
    await user.click(screen.getByRole("button", { name: /view generated diff/i }));

    expect(await screen.findByText("Generated diff")).toBeInTheDocument();
    expect(await screen.findByText("return a * b")).toBeInTheDocument();
  });

  it("previews the pull request draft without offering to merge", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    await screen.findByText("Fix multiplication in calculator");
    await user.click(screen.getByRole("button", { name: /preview pull request/i }));

    expect(await screen.findByText("Pull request draft")).toBeInTheDocument();
    expect(await screen.findByText(/multiply now uses/)).toBeInTheDocument();
    const createButton = screen.getByRole("button", { name: "Create pull request" });
    expect(createButton).toBeDisabled();
    expect(screen.queryByText(/merge pull request/i)).not.toBeInTheDocument();
  });
});

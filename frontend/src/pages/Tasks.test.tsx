import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/ToastProvider";
import { api } from "../services/api";
import type { Issue, Paginated, Repository, Task } from "../types";
import Tasks from "./Tasks";

vi.mock("../services/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../services/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      repositories: vi.fn(),
      issues: vi.fn(),
      tasks: vi.fn(),
      createTask: vi.fn(),
      executeTask: vi.fn(),
    },
  };
});

const repository: Repository = {
  id: 1,
  github_id: null,
  owner: "octocat",
  name: "demo-calculator",
  full_name: "octocat/demo-calculator",
  description: "A calculator used by the AutoDev demo",
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

const issue: Issue = {
  number: 1,
  title: "Fix multiplication",
  body: "multiply(2, 3) currently returns 5 instead of 6.",
  labels: ["bug"],
  assignees: [],
  state: "open",
  created_at: "2026-01-01T00:00:00Z",
  html_url: null,
  demo: true,
};

const task: Task = {
  id: 4,
  repository_id: 1,
  github_issue_number: null,
  title: "Existing task",
  description: "",
  priority: "medium",
  status: "completed",
  labels: [],
  source: "custom",
  repository,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const page = <T,>(items: T[]): Paginated<T> => ({
  items,
  total: items.length,
  page: 1,
  page_size: 100,
  pages: 1,
});

describe("Tasks", () => {
  beforeEach(() => {
    vi.mocked(api.repositories).mockResolvedValue(page([repository]));
    vi.mocked(api.issues).mockResolvedValue([issue]);
    vi.mocked(api.tasks).mockResolvedValue(page([task]));
    vi.mocked(api.createTask).mockResolvedValue({ ...task, id: 5, title: "Fix multiplication" });
  });

  it("fills the task form from a GitHub issue and creates the task", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/tasks"]}>
        <ToastProvider>
          <Tasks />
        </ToastProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Fix multiplication")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Use issue" }));

    const title = screen.getByLabelText("Title");
    const description = screen.getByLabelText("Description");
    expect(title).toHaveValue("Fix multiplication");
    expect(description).toHaveValue(issue.body);
    expect(screen.getByLabelText("Issue number")).toHaveValue(1);
    expect(screen.getAllByText("bug").length).toBeGreaterThanOrEqual(2);

    await user.click(screen.getByRole("button", { name: "Create task" }));

    await waitFor(() =>
      expect(api.createTask).toHaveBeenCalledWith({
        repository_id: 1,
        title: "Fix multiplication",
        description: issue.body,
        priority: "medium",
        github_issue_number: 1,
        labels: ["bug"],
      }),
    );
    expect(await screen.findByText("Task created")).toBeInTheDocument();
    expect(title).toHaveValue("");
  });

  it("rejects a title that is too short", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/tasks"]}>
        <ToastProvider>
          <Tasks />
        </ToastProvider>
      </MemoryRouter>,
    );

    await screen.findByText("Existing task");
    await user.type(screen.getByLabelText("Title"), "abc");
    await user.click(screen.getByRole("button", { name: "Create task" }));

    expect(screen.getByText("The task title must be at least 4 characters.")).toBeInTheDocument();
    expect(api.createTask).not.toHaveBeenCalled();
  });
});

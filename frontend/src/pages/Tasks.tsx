import {
  ArrowUpRight,
  Bot,
  CircleAlert,
  CircleDot,
  Hash,
  ListChecks,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Section,
  Skeleton,
  buttonStyles,
} from "../components/ui";
import { useToast } from "../components/ToastProvider";
import { useApiQuery } from "../hooks/useApiQuery";
import { api, errorMessage } from "../services/api";
import type { Issue } from "../types";
import { cn, formatRelative, truncate } from "../utils/format";

const priorityTone: Record<string, string> = {
  low: "border-white/10 bg-white/[0.03] text-slate-400",
  medium: "border-sky-400/20 bg-sky-500/10 text-sky-300",
  high: "border-amber-400/20 bg-amber-500/10 text-amber-300",
  critical: "border-rose-400/20 bg-rose-500/10 text-rose-300",
};

export default function Tasks() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const presetRepository = Number(searchParams.get("repository")) || null;
  const [repositoryId, setRepositoryId] = useState<number | null>(presetRepository);
  const [issueSearch, setIssueSearch] = useState("");
  const [taskSearch, setTaskSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [issueNumber, setIssueNumber] = useState("");
  const [labels, setLabels] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [executingId, setExecutingId] = useState<number | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const repositories = useApiQuery(() => api.repositories({ page_size: 100 }), []);
  const issues = useApiQuery(
    () => (repositoryId ? api.issues(repositoryId) : Promise.resolve<Issue[]>([])),
    [repositoryId],
  );
  const tasks = useApiQuery(
    () =>
      api.tasks({
        repository_id: repositoryId ?? undefined,
        status: statusFilter || undefined,
        search: taskSearch || undefined,
        page_size: 100,
      }),
    [repositoryId, statusFilter, taskSearch],
  );

  useEffect(() => {
    if (!repositoryId && repositories.data?.items.length) {
      setRepositoryId(repositories.data.items[0].id);
    }
  }, [repositoryId, repositories.data]);

  const selectedRepository = repositories.data?.items.find((repo) => repo.id === repositoryId);

  const applyIssue = (issue: Issue) => {
    setTitle(issue.title);
    setDescription(issue.body);
    setIssueNumber(String(issue.number));
    setLabels(issue.labels);
    setFormError(null);
    document.getElementById("task-title")?.focus();
  };

  const resetForm = () => {
    setTitle("");
    setDescription("");
    setPriority("medium");
    setIssueNumber("");
    setLabels([]);
    setFormError(null);
  };

  const createTask = async (runImmediately = false) => {
    if (!repositoryId) {
      setFormError("Select a repository first.");
      return;
    }
    if (title.trim().length < 4) {
      setFormError("The task title must be at least 4 characters.");
      return;
    }
    setCreating(true);
    setFormError(null);
    try {
      const task = await api.createTask({
        repository_id: repositoryId,
        title: title.trim(),
        description: description.trim(),
        priority,
        github_issue_number: issueNumber ? Number(issueNumber) : null,
        labels,
      });
      toast.success("Task created", task.title);
      resetForm();
      await tasks.refresh(true);
      if (runImmediately) {
        const execution = await api.executeTask(task.id);
        toast.success("Agent started", `Execution #${execution.id} is running.`);
        navigate(`/workspace/${execution.id}`);
      }
    } catch (error) {
      const message = errorMessage(error);
      setFormError(message);
      toast.error("Could not create the task", message);
    } finally {
      setCreating(false);
    }
  };

  const executeTask = async (taskId: number) => {
    setExecutingId(taskId);
    try {
      const execution = await api.executeTask(taskId);
      toast.success("Agent started", "Follow the execution in the workspace.");
      navigate(`/workspace/${execution.id}`);
    } catch (error) {
      toast.error("Could not start the agent", errorMessage(error));
    } finally {
      setExecutingId(null);
    }
  };

  const filteredIssues = (issues.data ?? []).filter((issue) =>
    `${issue.number} ${issue.title} ${issue.body} ${issue.labels.join(" ")}`
      .toLowerCase()
      .includes(issueSearch.toLowerCase()),
  );

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Work queue"
        title="Issues & Tasks"
        description="Turn GitHub issues or custom development requests into scoped agent executions. The repository is inspected before any code is modified."
        actions={
          <>
            <Button
              variant="secondary"
              size="sm"
              icon={RefreshCw}
              onClick={() => {
                void tasks.refresh();
                void issues.refresh();
              }}
              loading={tasks.loading}
            >
              Refresh
            </Button>
            <Link to="/workspace" className={buttonStyles("secondary", "sm")}>
              <Bot className="h-4 w-4" /> Workspace
            </Link>
          </>
        }
      />

      <Card className="mb-4 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="sm:w-80">
            <label className="label" htmlFor="task-repository">
              Repository
            </label>
            <select
              id="task-repository"
              className="input"
              value={repositoryId ?? ""}
              onChange={(event) => {
                setRepositoryId(Number(event.target.value) || null);
                resetForm();
              }}
            >
              {repositories.data?.items.length ? (
                repositories.data.items.map((repository) => (
                  <option key={repository.id} value={repository.id}>
                    {repository.full_name}
                    {repository.is_demo ? " (demo)" : ""}
                  </option>
                ))
              ) : (
                <option value="">No repositories connected</option>
              )}
            </select>
          </div>
          <div className="flex-1">
            <label className="label" htmlFor="task-search">
              Search tasks
            </label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <input
                id="task-search"
                className="input pl-9"
                placeholder="Search by title or description"
                value={taskSearch}
                onChange={(event) => setTaskSearch(event.target.value)}
              />
            </div>
          </div>
          <div className="sm:w-40">
            <label className="label" htmlFor="task-status">
              Status
            </label>
            <select
              id="task-status"
              className="input"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="queued">Queued</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>
        {selectedRepository ? (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
            <span className="mono">{selectedRepository.full_name}</span>
            <span>·</span>
            <span>{selectedRepository.language ?? "unknown language"}</span>
            <span>·</span>
            <span>base {selectedRepository.default_branch}</span>
            {selectedRepository.is_demo ? (
              <span className="chip border-indigo-400/20 bg-indigo-500/10 py-0 text-indigo-300">
                demo fixtures
              </span>
            ) : null}
            <Link
              to={`/repositories/${selectedRepository.id}`}
              className="ml-auto inline-flex items-center gap-1 text-indigo-300 hover:text-indigo-200"
            >
              Repository analysis <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>
        ) : null}
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <div className="space-y-4">
          <Section
            title="GitHub issues"
            subtitle={
              selectedRepository?.is_demo
                ? "Bundled demo issues — clearly labelled fixtures"
                : "Open issues from the selected repository"
            }
            icon={CircleDot}
            action={<span className="text-[11px] text-slate-500">{issues.data?.length ?? 0} issues</span>}
            bodyClassName="p-0"
          >
            <div className="border-b border-white/[0.06] p-4">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                <input
                  className="input pl-9"
                  placeholder="Filter issues"
                  value={issueSearch}
                  onChange={(event) => setIssueSearch(event.target.value)}
                  aria-label="Filter issues"
                />
              </div>
            </div>
            {issues.error ? (
              <div className="p-4">
                <ErrorState message={issues.error} onRetry={() => void issues.refresh()} />
              </div>
            ) : issues.loading ? (
              <div className="space-y-3 p-4">
                {Array.from({ length: 3 }).map((_, index) => (
                  <Skeleton key={index} className="h-20 w-full" />
                ))}
              </div>
            ) : filteredIssues.length ? (
              <ul className="max-h-[520px] divide-y divide-white/[0.04] overflow-y-auto">
                {filteredIssues.map((issue) => (
                  <li key={issue.number} className="p-4 transition hover:bg-white/[0.02]">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="mono text-[11px] text-slate-500">#{issue.number}</span>
                          <p className="text-sm font-medium text-slate-200">{issue.title}</p>
                          {issue.demo ? (
                            <span className="chip py-0 text-[9px]">demo</span>
                          ) : null}
                        </div>
                        <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-500">
                          {truncate(issue.body || "No description", 220)}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          {issue.labels.map((label) => (
                            <span key={label} className="chip py-0 text-[9px]">
                              {label}
                            </span>
                          ))}
                          <span className="text-[10px] text-slate-600">
                            opened {formatRelative(issue.created_at)}
                          </span>
                        </div>
                      </div>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => applyIssue(issue)}
                        className="shrink-0"
                      >
                        Use issue
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="p-4">
                <EmptyState
                  icon={CircleDot}
                  title={issueSearch ? "No matching issues" : "No open issues"}
                  description={
                    selectedRepository?.is_demo
                      ? "The demo repository ships two fixtures. Configure GitHub for real issues."
                      : "This repository has no open issues, or GitHub is not configured."
                  }
                />
              </div>
            )}
          </Section>

          <Section
            title="Task queue"
            subtitle="Every task and its latest known status"
            icon={ListChecks}
            bodyClassName="p-0"
            action={<span className="text-[11px] text-slate-500">{tasks.data?.total ?? 0} tasks</span>}
          >
            {tasks.error ? (
              <div className="p-4">
                <ErrorState message={tasks.error} onRetry={() => void tasks.refresh()} />
              </div>
            ) : tasks.loading && !tasks.data ? (
              <div className="space-y-3 p-4">
                {Array.from({ length: 4 }).map((_, index) => (
                  <Skeleton key={index} className="h-12 w-full" />
                ))}
              </div>
            ) : tasks.data?.items.length ? (
              <div className="overflow-x-auto">
                <table className="table-base">
                  <thead>
                    <tr>
                      <th>Task</th>
                      <th>Priority</th>
                      <th>Status</th>
                      <th>Created</th>
                      <th className="text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tasks.data.items.map((task) => {
                      const active = task.status === "queued" || task.status === "running";
                      return (
                        <tr key={task.id} className="transition hover:bg-white/[0.02]">
                          <td className="max-w-[360px]">
                            <div className="flex items-center gap-2">
                              {task.github_issue_number ? (
                                <span className="mono text-[10px] text-slate-500">
                                  #{task.github_issue_number}
                                </span>
                              ) : (
                                <Hash className="h-3 w-3 shrink-0 text-accent-400" />
                              )}
                              <span className="truncate text-xs font-medium text-slate-200">
                                {task.title}
                              </span>
                            </div>
                            <p className="mt-0.5 truncate text-[10px] text-slate-500">
                              {task.description || "No description"}
                            </p>
                          </td>
                          <td>
                            <span
                              className={cn(
                                "rounded-sm border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.05em]",
                                priorityTone[task.priority],
                              )}
                            >
                              {task.priority}
                            </span>
                          </td>
                          <td>
                            <StatusBadge status={task.status} />
                          </td>
                          <td className="text-[11px] text-slate-500">
                            {formatRelative(task.created_at)}
                          </td>
                          <td className="text-right">
                            {active ? (
                              <Link
                                to="/workspace"
                                className="inline-flex items-center gap-1 text-[11px] text-indigo-300 hover:text-indigo-200"
                              >
                                View run <ArrowUpRight className="h-3 w-3" />
                              </Link>
                            ) : (
                              <Button
                                variant="secondary"
                                size="sm"
                                icon={Play}
                                loading={executingId === task.id}
                                onClick={() => void executeTask(task.id)}
                              >
                                Run agent
                              </Button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-4">
                <EmptyState
                  icon={ListChecks}
                  title="No tasks yet"
                  description="Use an issue or create a custom development task to get started."
                />
              </div>
            )}
          </Section>
        </div>

        <div className="space-y-4">
          <Section title="Create a development task" icon={Plus} subtitle="Custom tasks work without a GitHub issue">
            <div className="space-y-4">
              <Field
                label="Title"
                htmlFor="task-title"
                hint="Be specific about the desired behaviour."
              >
                <input
                  id="task-title"
                  className="input"
                  placeholder="Fix multiplication in the calculator and add tests"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </Field>
              <Field label="Description" htmlFor="task-description">
                <textarea
                  id="task-description"
                  className="input min-h-[130px] resize-y"
                  placeholder="Describe the current behaviour, the expected behaviour and how it should be tested."
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Priority" htmlFor="task-priority">
                  <select
                    id="task-priority"
                    className="input"
                    value={priority}
                    onChange={(event) => setPriority(event.target.value)}
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </Field>
                <Field label="Issue number" htmlFor="task-issue" hint="Optional link">
                  <input
                    id="task-issue"
                    className="input"
                    type="number"
                    min={1}
                    placeholder="—"
                    value={issueNumber}
                    onChange={(event) => setIssueNumber(event.target.value)}
                  />
                </Field>
              </div>
              {labels.length ? (
                <div className="flex flex-wrap gap-1.5">
                  {labels.map((label) => (
                    <span key={label} className="chip py-0 text-[10px]">
                      {label}
                    </span>
                  ))}
                </div>
              ) : null}
              {formError ? <ErrorState message={formError} /> : null}
              {!repositories.data?.items.length && !repositories.loading ? (
                <div className="flex items-start gap-2 rounded-lg border border-amber-400/20 bg-amber-500/[0.05] p-3 text-[11px] leading-relaxed text-amber-200">
                  <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  No repository is connected. Connect one from the Repositories page.
                </div>
              ) : null}
              <div className="flex flex-col gap-2 border-t border-white/[0.05] pt-4 sm:flex-row">
                <Button
                  className="flex-1"
                  icon={Plus}
                  loading={creating}
                  onClick={() => void createTask(false)}
                  disabled={!repositoryId}
                >
                  Create task
                </Button>
                <Button
                  className="flex-1"
                  variant="secondary"
                  icon={creating ? Loader2 : Bot}
                  loading={creating}
                  onClick={() => void createTask(true)}
                  disabled={!repositoryId}
                >
                  Create &amp; run
                </Button>
              </div>
              <p className="text-[10px] leading-relaxed text-slate-600">
                Creating a task does not modify code. The agent requires plan approval before it
                edits files when that safeguard is enabled in Settings.
              </p>
            </div>
          </Section>

          <Card className="p-4">
            <p className="text-xs font-medium text-slate-200">Safe by construction</p>
            <ul className="mt-2 space-y-2 text-[11px] leading-relaxed text-slate-500">
              <li>• Edits are limited to the selected repository workspace.</li>
              <li>• Generated paths are validated and directory traversal is rejected.</li>
              <li>• Tests run with an allowlisted command policy and scrubbed environment.</li>
              <li>• Pull requests are never merged or approved automatically.</li>
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}

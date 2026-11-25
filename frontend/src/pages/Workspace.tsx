import {
  Activity,
  ArrowLeft,
  ArrowUpRight,
  Bot,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  Clock3,
  FileCode2,
  FileDiff,
  FlaskConical,
  GitBranch,
  GitPullRequest,
  History,
  ListChecks,
  Play,
  RefreshCw,
  ShieldCheck,
  Square,
  TerminalSquare,
  UserCheck,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { DiffModal } from "../components/DiffModal";
import { ExecutionTerminal } from "../components/ExecutionTerminal";
import { ExecutionTimeline } from "../components/ExecutionTimeline";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import {
  Button,
  EmptyState,
  ErrorState,
  InfoRow,
  Modal,
  Section,
  Skeleton,
  buttonStyles,
} from "../components/ui";
import { useToast } from "../components/ToastProvider";
import { useApiQuery } from "../hooks/useApiQuery";
import { useExecutionStream, type StreamEvent } from "../hooks/useExecutionStream";
import { api, errorMessage } from "../services/api";
import type { AgentLog, ExecutionDetail, PullRequestDraft } from "../types";
import { cn, formatDate, formatDuration, formatRelative } from "../utils/format";

function ExecutionPicker() {
  const executions = useApiQuery(() => api.executions({ page_size: 12 }), []);

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Autonomous execution"
        title="Agent Workspace"
        description="A live view of what the agent is doing, which files it inspected, and the real test results from the sandbox."
        actions={
          <>
            <Button
              variant="secondary"
              size="sm"
              icon={RefreshCw}
              loading={executions.loading}
              onClick={() => void executions.refresh()}
            >
              Refresh
            </Button>
            <Link to="/tasks" className={buttonStyles("primary", "sm")}>
              <Play className="h-4 w-4" /> Start a task
            </Link>
          </>
        }
      />
      {executions.error ? (
        <ErrorState message={executions.error} onRetry={() => void executions.refresh()} />
      ) : executions.loading && !executions.data ? (
        <div className="grid gap-3 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-24 w-full" />
          ))}
        </div>
      ) : executions.data?.items.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {executions.data.items.map((execution) => (
            <Link
              key={execution.id}
              to={`/workspace/${execution.id}`}
              className="panel group p-4 transition hover:border-indigo-400/20"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-200">
                    {execution.task?.title ?? `Execution #${execution.id}`}
                  </p>
                  <p className="mt-1 truncate text-[11px] text-slate-500">
                    {execution.task?.repository?.full_name ?? "Unknown repository"} · execution #
                    {execution.id}
                  </p>
                </div>
                <StatusBadge status={execution.status} />
              </div>
              <div className="mt-3 flex items-center gap-3 text-[10px] text-slate-500">
                <span className="inline-flex items-center gap-1">
                  <Clock3 className="h-3 w-3" /> {formatDuration(execution.duration_seconds)}
                </span>
                <span>{formatRelative(execution.created_at)}</span>
                <span className="ml-auto inline-flex items-center gap-1 text-indigo-300 opacity-0 transition group-hover:opacity-100">
                  Open <ArrowUpRight className="h-3 w-3" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Bot}
          title="No executions yet"
          description="Send a task to the agent from Issues & Tasks. The full pipeline will stream here in real time."
          action={
            <Link to="/tasks" className={buttonStyles("primary", "sm")}>
              <Play className="h-4 w-4" /> Start a task
            </Link>
          }
        />
      )}
    </div>
  );
}

function ExecutionView({ executionId }: { executionId: number }) {
  const detail = useApiQuery(() => api.execution(executionId), [executionId]);
  const navigate = useNavigate();
  const toast = useToast();
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [diffOpen, setDiffOpen] = useState(false);
  const [diffPath, setDiffPath] = useState<string | null>(null);
  const [prOpen, setPrOpen] = useState(false);
  const [draft, setDraft] = useState<PullRequestDraft | null>(null);
  const [draftLoading, setDraftLoading] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [creatingPr, setCreatingPr] = useState(false);
  const [prError, setPrError] = useState<string | null>(null);
  const [action, setAction] = useState<string | null>(null);
  const logsInitialised = useRef(false);

  const execution = detail.data;
  const isActive = !!execution && ["queued", "running", "awaiting_approval"].includes(execution.status);

  const mergeLogs = useCallback((incoming: AgentLog[]) => {
    setLogs((previous) => {
      const seen = new Set(previous.map((log) => log.id).filter((id): id is number => id !== null));
      const next = [...previous];
      for (const log of incoming) {
        if (log.id !== null && seen.has(log.id)) continue;
        next.push(log);
        if (log.id !== null) seen.add(log.id);
      }
      return next.sort((a, b) => (a.id ?? 0) - (b.id ?? 0));
    });
  }, []);

  const loadLogs = useCallback(async () => {
    try {
      const page = await api.logs(executionId, 600);
      mergeLogs(page.items);
    } catch {
      // logs are also streamed; a replay failure should not break the workspace
    }
  }, [executionId, mergeLogs]);

  useEffect(() => {
    logsInitialised.current = false;
    setLogs([]);
    void loadLogs().finally(() => {
      logsInitialised.current = true;
    });
  }, [loadLogs]);

  const handleEvent = useCallback(
    (event: StreamEvent) => {
      if (event.type === "log" && event.message) {
        mergeLogs([
          {
            id: event.id ?? null,
            level: event.level ?? "info",
            stage: event.stage ?? null,
            message: event.message,
            created_at: event.created_at ?? new Date().toISOString(),
          },
        ]);
      } else {
        void detail.refresh(true);
      }
    },
    [detail, mergeLogs],
  );

  const { connected } = useExecutionStream(executionId, handleEvent, isActive);

  useEffect(() => {
    if (!isActive) return;
    const timer = window.setInterval(() => void detail.refresh(true), 2500);
    return () => window.clearInterval(timer);
  }, [isActive, detail]);

  const previousStatus = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!execution) return;
    if (
      previousStatus.current &&
      previousStatus.current !== execution.status &&
      !["queued", "running", "awaiting_approval"].includes(execution.status)
    ) {
      void loadLogs();
    }
    previousStatus.current = execution.status;
  }, [execution, loadLogs]);

  const refreshAll = async () => {
    await detail.refresh();
    await loadLogs();
  };

  const runAction = async (
    name: string,
    fn: () => Promise<ExecutionDetail | void>,
    success: string,
  ) => {
    setAction(name);
    try {
      const result = await fn();
      if (result) detail.setData(result);
      toast.success(success);
      await detail.refresh(true);
    } catch (error) {
      toast.error("Action failed", errorMessage(error));
    } finally {
      setAction(null);
    }
  };

  const openDraft = async () => {
    setPrOpen(true);
    setDraft(null);
    setDraftError(null);
    setPrError(null);
    setDraftLoading(true);
    try {
      setDraft(await api.pullRequestDraft(executionId));
    } catch (error) {
      setDraftError(errorMessage(error));
    } finally {
      setDraftLoading(false);
    }
  };

  const createPullRequest = async () => {
    setCreatingPr(true);
    setPrError(null);
    try {
      const pull = await api.createPullRequest(executionId, {
        confirm: true,
        title: draft?.title,
        body: draft?.body,
      });
      toast.success(
        `Pull request #${pull.number} created`,
        "A human reviewer must merge it on GitHub.",
      );
      setPrOpen(false);
      await detail.refresh();
    } catch (error) {
      setPrError(errorMessage(error));
    } finally {
      setCreatingPr(false);
    }
  };

  if (detail.error) {
    return (
      <div>
        <Link
          to="/workspace"
          className="mb-4 inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-200"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Workspace
        </Link>
        <ErrorState message={detail.error} onRetry={() => void detail.refresh()} />
      </div>
    );
  }

  if (detail.loading && !execution) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-80" />
        <div className="grid gap-4 xl:grid-cols-[300px_1fr_300px]">
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      </div>
    );
  }

  if (!execution) return null;

  const filesInspected = execution.files_inspected.length;
  const modified = execution.file_changes.length;
  const testsPassed = execution.test_executions.reduce((sum, test) => sum + test.passed_count, 0);
  const testsFailed = execution.test_executions.reduce((sum, test) => sum + test.failed_count, 0);
  const lastTest = execution.test_executions[execution.test_executions.length - 1];
  const tokens = execution.prompt_tokens + execution.completion_tokens;
  const checks = execution.validation?.checks ?? [];
  const blockedChecks = checks.filter((check) => !check.passed && check.severity === "error");

  return (
    <div className="animate-fade-in">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Link
          to="/workspace"
          className="inline-flex items-center gap-1.5 text-xs text-slate-500 transition hover:text-slate-200"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Workspace
        </Link>
        <Link
          to={`/history?search=${encodeURIComponent(execution.task?.title ?? "")}`}
          className="inline-flex items-center gap-1.5 text-xs text-slate-500 transition hover:text-slate-200"
        >
          <History className="h-3.5 w-3.5" /> History
        </Link>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <StatusBadge status={execution.status} pulse={isActive} />
          {execution.demo_mode ? (
            <span className="chip border-accent-400/30 text-accent-300">
              <FlaskConical className="h-3 w-3" /> demo fixtures
            </span>
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            icon={RefreshCw}
            onClick={() => void refreshAll()}
            loading={detail.loading}
          >
            Refresh
          </Button>
        </div>
      </div>

      <div className="mb-4">
        <p className="font-mono text-[9px] font-medium uppercase tracking-[0.18em] text-accent-400">
          Execution #{execution.id}
        </p>
        <h1 className="mt-2 font-display text-[34px] font-normal leading-[1.05] tracking-[-0.01em] text-slate-50 sm:text-[40px]">
          {execution.task?.title ?? "Unknown task"}
        </h1>
        <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1">
            <GitBranch className="h-3.5 w-3.5" />
            {execution.task?.repository?.full_name ?? "unknown repository"}
          </span>
          <span>base {execution.base_branch ?? execution.task?.repository?.default_branch ?? "—"}</span>
          {execution.branch_name ? (
            <span className="mono text-slate-400">{execution.branch_name}</span>
          ) : null}
        </p>
      </div>

      {execution.status === "awaiting_approval" ? (
        <div className="mb-4 flex flex-col gap-3 rounded-xl border border-amber-400/25 bg-amber-500/[0.07] p-4 sm:flex-row sm:items-center">
          <div className="flex min-w-0 items-start gap-3">
            <UserCheck className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
            <div>
              <p className="text-sm font-medium text-amber-100">Implementation plan ready for review</p>
              <p className="mt-0.5 text-xs leading-relaxed text-amber-200/70">
                The agent has inspected the repository and generated a plan. No files have been
                modified. Review the plan and timeline, then approve to continue.
              </p>
            </div>
          </div>
          {execution.actions.approve_plan ? (
            <Button
              size="sm"
              className="shrink-0 bg-amber-400 text-amber-950 hover:bg-amber-300"
              icon={CheckCircle2}
              loading={action === "approve"}
              onClick={() =>
                void runAction("approve", () => api.approvePlan(executionId), "Plan approved")
              }
            >
              Approve plan
            </Button>
          ) : null}
        </div>
      ) : null}

      {execution.error_message ? (
        <div className="mb-4 rounded-xl border border-rose-400/25 bg-rose-500/[0.07] p-4">
          <p className="flex items-center gap-2 text-sm font-medium text-rose-200">
            <CircleAlert className="h-4 w-4" /> {execution.error_message}
          </p>
          {execution.summary && execution.summary !== execution.error_message ? (
            <p className="mt-1 text-xs leading-relaxed text-rose-200/70">{execution.summary}</p>
          ) : null}
          {execution.error_details ? (
            <details className="mt-2">
              <summary className="cursor-pointer text-[11px] text-rose-300/80">Details</summary>
              <pre className="mono mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-black/30 p-3 text-[10px] leading-relaxed text-rose-200/70">
                {execution.error_details}
              </pre>
            </details>
          ) : null}
        </div>
      ) : null}

      {execution.status === "completed" ? (
        <div className="mb-4 flex flex-col gap-2 rounded-xl border border-emerald-400/20 bg-emerald-500/[0.06] p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="flex items-start gap-2 text-xs leading-relaxed text-emerald-200">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
            {execution.summary ?? "Validation passed. Human approval is required before a pull request."}
          </p>
          {execution.pull_request?.url ? (
            <a
              href={execution.pull_request.url}
              target="_blank"
              rel="noreferrer"
              className={buttonStyles("secondary", "sm")}
            >
              <GitPullRequest className="h-3.5 w-3.5" /> PR #{execution.pull_request.number}
            </a>
          ) : null}
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)_300px]">
        {/* left -------------------------------------------------------- */}
        <div className="space-y-4">
          <Section title="Task" icon={ListChecks}>
            <InfoRow label="Repository">
              {execution.task?.repository?.full_name ?? "—"}
            </InfoRow>
            <InfoRow label="Issue">
              {execution.task?.github_issue_number ? `#${execution.task.github_issue_number}` : "Custom task"}
            </InfoRow>
            <InfoRow label="Priority">{execution.task?.priority ?? "—"}</InfoRow>
            <InfoRow label="Execution">#{execution.id}</InfoRow>
            <InfoRow label="Status">
              <StatusBadge status={execution.status} pulse={isActive} />
            </InfoRow>
            <InfoRow label="AI provider">
              {execution.ai_provider ?? "—"}
              {" "}
              <span className="text-slate-600">{execution.ai_model}</span>
            </InfoRow>
            <InfoRow label="Created">{formatDate(execution.created_at)}</InfoRow>
            {execution.task?.description ? (
              <div className="mt-3 border-t border-white/[0.05] pt-3">
                <p className="label">Description</p>
                <p className="max-h-48 overflow-y-auto whitespace-pre-wrap text-xs leading-relaxed text-slate-400">
                  {execution.task.description}
                </p>
              </div>
            ) : null}
          </Section>

          <Section title="Agent controls" icon={Bot}>
            <div className="space-y-2">
              <Button
                className="w-full"
                icon={CheckCircle2}
                disabled={!execution.actions.approve_plan}
                loading={action === "approve"}
                onClick={() =>
                  void runAction("approve", () => api.approvePlan(executionId), "Plan approved")
                }
              >
                Approve plan
              </Button>
              <Button
                className="w-full"
                variant="secondary"
                icon={FileDiff}
                disabled={!execution.actions.view_diff}
                onClick={() => {
                  setDiffPath(null);
                  setDiffOpen(true);
                }}
              >
                View generated diff
              </Button>
              <Button
                className="w-full"
                variant="secondary"
                icon={GitPullRequest}
                disabled={!execution.actions.preview_pull_request}
                onClick={() => void openDraft()}
              >
                {execution.actions.create_pull_request
                  ? "Create pull request"
                  : "Preview pull request"}
              </Button>
              <Button
                className="w-full"
                variant="secondary"
                icon={RefreshCw}
                disabled={!execution.actions.retry}
                loading={action === "retry"}
                onClick={() =>
                  void runAction(
                    "retry",
                    async () => {
                      const next = await api.retryExecution(executionId);
                      navigate(`/workspace/${next.id}`);
                      return next;
                    },
                    "Retry started",
                  )
                }
              >
                Retry task
              </Button>
              <Button
                className="w-full"
                variant="danger"
                icon={Square}
                disabled={!execution.actions.cancel}
                loading={action === "cancel"}
                onClick={() => {
                  if (!window.confirm("Cancel this agent execution? The workspace and logs are kept.")) {
                    return;
                  }
                  void runAction("cancel", () => api.cancelExecution(executionId), "Cancellation requested");
                }}
              >
                Cancel execution
              </Button>
            </div>
            <p className="mt-3 text-[10px] leading-relaxed text-slate-600">
              Actions are enabled only when the backend state allows them. The UI never fabricates
              progress or test results.
            </p>
          </Section>
        </div>

        {/* center ------------------------------------------------------ */}
        <div className="min-w-0 space-y-4">
          {execution.plan ? (
            <Section
              title="Implementation plan"
              icon={ListChecks}
              subtitle={
                execution.plan_approved ? "Approved by a human reviewer" : "Awaiting review"
              }
              action={<StatusBadge status={execution.plan_approved ? "completed" : "pending"} label={execution.plan_approved ? "approved" : "not approved"} />}
            >
              <p className="text-sm leading-relaxed text-slate-300">{execution.plan.summary}</p>
              <ol className="mt-4 space-y-3">
                {execution.plan.steps.map((step) => (
                  <li key={step.index} className="flex gap-3">
                    <span className="grid h-5 w-5 shrink-0 place-items-center rounded-sm border border-accent-400/30 bg-accent-500/[0.06] font-mono text-[9px] text-accent-300">
                      {String(step.index).padStart(2, "0")}
                    </span>
                    <div>
                      <p className="text-xs font-medium text-slate-200">{step.title}</p>
                      {step.detail ? (
                        <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500">
                          {step.detail}
                        </p>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ol>
              <div className="mt-4 grid gap-3 border-t border-white/[0.05] pt-3 sm:grid-cols-2">
                {execution.plan.files_likely_affected.length ? (
                  <div>
                    <p className="label">Likely affected files</p>
                    <ul className="space-y-1">
                      {execution.plan.files_likely_affected.map((file) => (
                        <li key={file} className="mono truncate text-[10px] text-slate-400">
                          {file}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {execution.plan.test_plan.length ? (
                  <div>
                    <p className="label">Test plan</p>
                    <ul className="space-y-1 text-[10px] text-slate-400">
                      {execution.plan.test_plan.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
              {execution.plan.risks.length ? (
                <p className="mt-3 text-[10px] leading-relaxed text-amber-300/70">
                  Risks: {execution.plan.risks.join(" · ")}
                </p>
              ) : null}
            </Section>
          ) : null}

          <Section
            title="Execution timeline"
            icon={Activity}
            subtitle={`Stage: ${execution.current_stage.replace(/_/g, " ")}`}
            action={
              isActive ? (
                <span className="inline-flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-[0.06em] text-accent-300">
                  <span className="h-1 w-1 animate-pulse-soft bg-accent-400" />
                  running
                </span>
              ) : (
                <span className="text-[10px] text-slate-500">{formatDuration(execution.duration_seconds)}</span>
              )
            }
          >
            <ExecutionTimeline steps={execution.timeline} />
          </Section>

          <Section
            title="Live terminal"
            icon={TerminalSquare}
            subtitle="Actual backend logs, streamed with Server-Sent Events"
            bodyClassName="p-3"
          >
            <ExecutionTerminal logs={logs} connected={connected} running={isActive} />
          </Section>
        </div>

        {/* right ------------------------------------------------------- */}
        <div className="space-y-4">
          <Section title="Execution details" icon={Clock3}>
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: "Inspected", value: filesInspected, icon: FileCode2 },
                { label: "Modified", value: modified, icon: FileDiff },
                { label: "Tests passed", value: testsPassed, icon: CheckCircle2 },
                { label: "Tests failed", value: testsFailed, icon: XCircle },
              ].map((metric) => (
                <div key={metric.label} className="rounded-lg border border-white/[0.05] bg-white/[0.015] p-2.5">
                  <p className="flex items-center gap-1 text-[9px] uppercase tracking-wider text-slate-500">
                    <metric.icon className="h-3 w-3" /> {metric.label}
                  </p>
                  <p className="mt-1 text-lg font-semibold text-slate-100">{metric.value}</p>
                </div>
              ))}
            </div>
            <div className="mt-3">
              <InfoRow label="Duration">{formatDuration(execution.duration_seconds)}</InfoRow>
              <InfoRow label="Started">{formatRelative(execution.started_at)}</InfoRow>
              <InfoRow label="Corrective attempts">{execution.correction_attempts}</InfoRow>
              <InfoRow label="Tokens (total)">{tokens || "—"}</InfoRow>
              <InfoRow label="Sandbox tests">{execution.test_executions.length}</InfoRow>
              {lastTest ? (
                <InfoRow label="Latest test">
                  <StatusBadge status={lastTest.status} />
                </InfoRow>
              ) : null}
            </div>
          </Section>

          <Section
            title="Validation"
            icon={ShieldCheck}
            action={
              execution.validation ? (
                <StatusBadge status={execution.validation.passed ? "passed" : "failed"} />
              ) : (
                <span className="text-[10px] text-slate-500">not run</span>
              )
            }
          >
            {execution.validation ? (
              <div>
                <p className="text-[11px] leading-relaxed text-slate-400">
                  {execution.validation.summary}
                </p>
                <ul className="mt-3 space-y-2">
                  {checks.map((check) => (
                    <li key={check.name} className="flex items-start gap-2 text-[10px] leading-relaxed">
                      {check.passed ? (
                        <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-emerald-400" />
                      ) : (
                        <CircleAlert
                          className={cn(
                            "mt-0.5 h-3 w-3 shrink-0",
                            check.severity === "error" ? "text-rose-400" : "text-amber-400",
                          )}
                        />
                      )}
                      <span className={check.passed ? "text-slate-400" : "text-slate-300"}>
                        <span className="font-medium">{check.name}</span>: {check.detail}
                      </span>
                    </li>
                  ))}
                </ul>
                {blockedChecks.length ? (
                  <p className="mt-2 text-[10px] text-rose-300">
                    {blockedChecks.length} blocking check(s) prevent pull request creation.
                  </p>
                ) : null}
              </div>
            ) : (
              <p className="text-[11px] leading-relaxed text-slate-500">
                Validation runs after tests and before any pull request. It inspects the real git
                diff for secrets, unexpected files and protected paths.
              </p>
            )}
          </Section>

          <Section title="Test executions" icon={TerminalSquare}>
            {execution.test_executions.length ? (
              <div className="space-y-2">
                {execution.test_executions.map((test) => (
                  <details
                    key={test.id}
                    className="rounded-lg border border-white/[0.05] bg-white/[0.015] p-2.5"
                  >
                    <summary className="flex cursor-pointer list-none items-center gap-2">
                      <StatusBadge status={test.status} />
                      <span className="mono truncate text-[10px] text-slate-400">{test.command}</span>
                      <ChevronDown className="ml-auto h-3 w-3 shrink-0 text-slate-500" />
                    </summary>
                    <p className="mt-1.5 text-[10px] text-slate-500">
                      {test.passed_count} passed · {test.failed_count} failed · attempt {test.attempt} ·{" "}
                      {formatDuration(test.duration_seconds)}
                    </p>
                    {test.output ? (
                      <pre className="mono mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-black/40 p-2 text-[9px] leading-relaxed text-slate-500">
                        {test.output.slice(-4000)}
                      </pre>
                    ) : null}
                  </details>
                ))}
              </div>
            ) : (
              <p className="text-[11px] text-slate-500">No tests have run yet.</p>
            )}
          </Section>

          <Section title="Modified files" icon={FileDiff}>
            {execution.file_changes.length ? (
              <ul className="space-y-1.5">
                {execution.file_changes.map((file) => (
                  <li key={file.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setDiffPath(file.file_path);
                        setDiffOpen(true);
                      }}
                      className="flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left transition hover:bg-white/[0.04]"
                    >
                      <FileCode2 className="mt-0.5 h-3 w-3 shrink-0 text-slate-500" />
                      <span className="mono min-w-0 flex-1 break-all text-[10px] text-slate-400">
                        {file.file_path}
                      </span>
                      <span className="shrink-0 text-[9px] text-emerald-400">+{file.additions}</span>
                      <span className="shrink-0 text-[9px] text-rose-400">-{file.deletions}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[11px] text-slate-500">No files modified yet.</p>
            )}
          </Section>
        </div>
      </div>

      {diffOpen ? (
        <DiffModal
          executionId={executionId}
          initialPath={diffPath}
          onClose={() => {
            setDiffOpen(false);
            setDiffPath(null);
          }}
        />
      ) : null}

      <Modal
        open={prOpen}
        onClose={() => setPrOpen(false)}
        size="xl"
        title="Pull request draft"
        description="Generated from the validated diff and test results. AutoDev never merges pull requests."
        footer={
          <>
            <Button variant="ghost" onClick={() => setPrOpen(false)}>
              Close
            </Button>
            <Button
              icon={GitPullRequest}
              loading={creatingPr}
              disabled={!execution.actions.create_pull_request || !draft}
              onClick={() => void createPullRequest()}
            >
              Create pull request
            </Button>
          </>
        }
      >
        {draftLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-6 w-2/3" />
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-3 w-full" />
            ))}
          </div>
        ) : draftError ? (
          <ErrorState message={draftError} onRetry={() => void openDraft()} />
        ) : draft ? (
          <div className="space-y-4">
            {draft.demo_mode ? (
              <div className="rounded-lg border border-amber-400/20 bg-amber-500/[0.06] p-3 text-[11px] leading-relaxed text-amber-200">
                Demo fixture provider: this change set was deterministic and no AI model was called.
                {!execution.actions.create_pull_request
                  ? " The demo repository is local, so only the draft can be previewed."
                  : ""}
              </div>
            ) : null}
            <div>
              <p className="label">Title</p>
              <p className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3 text-sm text-slate-200">
                {draft.title}
              </p>
            </div>
            <div>
              <p className="label">Body</p>
              <pre className="mono max-h-[46vh] overflow-auto whitespace-pre-wrap rounded-lg border border-white/[0.06] bg-black/40 p-4 text-[11px] leading-relaxed text-slate-400">
                {draft.body}
              </pre>
            </div>
            <p className="text-[10px] text-slate-500">
              Branch <span className="mono">{draft.branch}</span> →{" "}
              <span className="mono">{draft.base_branch}</span>
            </p>
            {!execution.actions.create_pull_request ? (
              <p className="text-[10px] leading-relaxed text-slate-500">
                Pull request creation is disabled because GitHub is not configured, validation did
                not pass, or this is the local demo repository.
              </p>
            ) : null}
            {prError ? <ErrorState message={prError} /> : null}
          </div>
        ) : null}
      </Modal>
    </div>
  );
}

export default function Workspace() {
  const { executionId } = useParams();
  const parsed = executionId && /^\d+$/.test(executionId) ? Number(executionId) : null;
  if (!parsed) return <ExecutionPicker />;
  return <ExecutionView executionId={parsed} />;
}

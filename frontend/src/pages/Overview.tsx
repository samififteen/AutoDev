import {
  Activity,
  ArrowUpRight,
  Bot,
  CheckCircle2,
  CircleSlash,
  Cpu,
  Database,
  FolderGit2,
  GitPullRequest,
  Github,
  Plus,
  RefreshCw,
  Server,
  ShieldCheck,
  Timer,
  XCircle,
} from "lucide-react";
import { Link } from "react-router-dom";
import { ActivityChart } from "../components/ActivityChart";
import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Section,
  Skeleton,
  buttonStyles,
} from "../components/ui";
import { useApiQuery } from "../hooks/useApiQuery";
import { api } from "../services/api";
import type { SystemStatus } from "../types";
import { cn, formatDuration, formatRelative } from "../utils/format";

const systemIcons = {
  Backend: Server,
  Database: Database,
  GitHub: Github,
  "AI provider": Cpu,
  Sandbox: ShieldCheck,
  "Agent worker": Bot,
};

function SystemRow({
  name,
  component,
}: {
  name: keyof typeof systemIcons;
  component: SystemStatus[keyof SystemStatus];
}) {
  const Icon = systemIcons[name];
  return (
    <div className="flex gap-3 border-b border-white/[0.04] py-3 last:border-0">
      <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-white/[0.06] bg-white/[0.02] text-slate-400">
        <Icon className="h-3.5 w-3.5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-medium text-slate-200">{name}</p>
          <StatusBadge status={component.status} />
        </div>
        <p className="mt-0.5 break-words text-[11px] leading-relaxed text-slate-500">
          {component.detail}
        </p>
      </div>
    </div>
  );
}

export default function Overview() {
  const stats = useApiQuery(() => api.dashboard(), []);
  const system = useApiQuery(() => api.systemStatus(), []);
  const info = useApiQuery(() => api.systemInfo(), []);

  if (stats.error) {
    return (
      <div>
        <PageHeader title="Overview" description="Autonomous engineering activity across connected repositories." />
        <ErrorState message={stats.error} onRetry={() => void stats.refresh()} />
      </div>
    );
  }

  const data = stats.data;
  const empty = data && data.repositories_connected === 0;

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Operations"
        title="Overview"
        description="Autonomous engineering activity, execution health and platform status — all computed from stored records."
        actions={
          <>
            <Button
              variant="secondary"
              size="sm"
              icon={RefreshCw}
              onClick={() => {
                void stats.refresh();
                void system.refresh();
              }}
              loading={stats.loading}
            >
              Refresh
            </Button>
            <Link to="/tasks" className={buttonStyles("primary", "sm")}>
              <Plus className="h-4 w-4" /> New task
            </Link>
          </>
        }
      />

      {empty ? (
        <Card className="mb-6 overflow-hidden">
          <div className="grid gap-6 p-6 lg:grid-cols-[1.4fr_1fr] lg:p-8">
            <div>
              <span className="mb-4 inline-flex items-center gap-2 border-l-2 border-accent-500 pl-2 font-mono text-[9px] uppercase tracking-[0.14em] text-accent-400">
                <span className="h-1 w-1 bg-accent-500" /> Start here
              </span>
              <h2 className="font-display text-[28px] font-normal leading-tight text-slate-50">
                Run your first autonomous task
              </h2>
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-400">
                {info.data?.demo_mode
                  ? "No GitHub token is configured, so AutoDev is running with the bundled demo repository. The pipeline still clones a real git repository, edits files, runs pytest and produces a real diff."
                  : "Connect a GitHub repository to let AutoDev inspect real code, plan a change, run tests and prepare a pull request for review."}
              </p>
              <div className="mt-5 space-y-3 text-sm">
                {[
                  "Connect a repository (or open the bundled demo).",
                  "Pick an issue or write a custom development task.",
                  "Approve the plan, then review the diff and test results.",
                  "Create a pull request when validation passes.",
                ].map((step, index) => (
                  <div key={step} className="flex items-start gap-3">
                    <span className="grid h-5 w-5 shrink-0 place-items-center rounded-sm border border-accent-400/30 bg-accent-500/[0.06] font-mono text-[9px] text-accent-300">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <p className="text-slate-400">{step}</p>
                  </div>
                ))}
              </div>
              <div className="mt-6 flex flex-wrap gap-2">
                <Link to="/repositories" className={buttonStyles("primary")}>
                  <FolderGit2 className="h-4 w-4" /> Repositories
                </Link>
                <Link to="/tasks" className={buttonStyles("secondary")}>
                  <Plus className="h-4 w-4" /> Create a task
                </Link>
              </div>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-ink-900/60 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                Environment
              </p>
              <dl className="mt-3 space-y-3 text-xs">
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500">AI provider</dt>
                  <dd className="text-right text-slate-300">
                    {info.data?.ai_provider === "demo" ? "Demo fixtures" : info.data?.ai_model}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500">Sandbox</dt>
                  <dd className="text-right capitalize text-slate-300">
                    {info.data?.sandbox_mode ?? "—"}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500">GitHub</dt>
                  <dd className="text-right text-slate-300">
                    {info.data?.github_configured ? "Configured" : "Not configured"}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500">API authentication</dt>
                  <dd className="text-right text-slate-300">
                    {info.data?.auth_enabled ? "Token required" : "Local / open"}
                  </dd>
                </div>
              </dl>
              <p className="mt-4 border-t border-white/[0.06] pt-3 text-[10px] leading-relaxed text-slate-600">
                Demo mode never claims AI-generated code. Plans and edits are deterministic
                fixtures; tests and diffs are real.
              </p>
            </div>
          </div>
        </Card>
      ) : null}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {stats.loading && !data
          ? Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="panel p-4">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="mt-4 h-7 w-12" />
                <Skeleton className="mt-2 h-2.5 w-24" />
              </div>
            ))
          : [
              {
                label: "Repositories",
                value: data?.repositories_connected ?? 0,
                hint: "connected",
                icon: FolderGit2,
                tone: "indigo" as const,
              },
              {
                label: "Tasks processed",
                value: data?.tasks_processed ?? 0,
                hint: `${data?.tasks_total ?? 0} total tasks`,
                icon: Activity,
                tone: "violet" as const,
              },
              {
                label: "Completed",
                value: data?.tasks_completed ?? 0,
                hint: "passed validation",
                icon: CheckCircle2,
                tone: "emerald" as const,
              },
              {
                label: "Failed",
                value: data?.tasks_failed ?? 0,
                hint: "validation failed",
                icon: XCircle,
                tone: "rose" as const,
              },
              {
                label: "Pull requests",
                value: data?.pull_requests_created ?? 0,
                hint: "created for review",
                icon: GitPullRequest,
                tone: "indigo" as const,
              },
              {
                label: "Avg. duration",
                value: formatDuration(data?.average_duration_seconds ?? null),
                hint: data?.active_executions ? `${data.active_executions} active now` : "no active runs",
                icon: Timer,
                tone: "amber" as const,
              },
            ].map((card) => (
              <StatCard
                key={card.label}
                label={card.label}
                value={card.value}
                hint={card.hint}
                icon={card.icon}
                tone={card.tone}
              />
            ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.65fr_1fr]">
        <Section
          title="Agent activity"
          subtitle="Completed and failed executions over the last 14 days"
          icon={Activity}
          action={<span className="text-[11px] text-slate-500">from persisted executions</span>}
        >
          {stats.loading && !data ? (
            <Skeleton className="h-[280px] w-full" />
          ) : (
            <ActivityChart data={data?.chart ?? []} />
          )}
        </Section>

        <Section
          title="System status"
          subtitle="Configured is not the same as verified"
          icon={Server}
        >
          {system.loading && !system.data ? (
            <div className="space-y-4">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="flex gap-3">
                  <Skeleton className="h-7 w-7 rounded-lg" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-3 w-28" />
                    <Skeleton className="h-2.5 w-full" />
                  </div>
                </div>
              ))}
            </div>
          ) : system.error ? (
            <ErrorState message={system.error} onRetry={() => void system.refresh()} />
          ) : system.data ? (
            <div>
              {(
                [
                  ["Backend", system.data.backend],
                  ["Database", system.data.database],
                  ["GitHub", system.data.github],
                  ["AI provider", system.data.ai_provider],
                  ["Sandbox", system.data.sandbox],
                  ["Agent worker", system.data.agent_worker],
                ] as const
              ).map(([name, component]) => (
                <SystemRow key={name} name={name} component={component} />
              ))}
              <p className="mt-3 flex items-start gap-2 text-[10px] leading-relaxed text-slate-600">
                <CircleSlash className="mt-0.5 h-3 w-3 shrink-0" />
                GitHub and the AI provider are only marked verified after an authenticated check or
                a successful execution.
              </p>
            </div>
          ) : null}
        </Section>
      </div>

      <Section
        className="mt-4"
        title="Recent agent activity"
        subtitle="Every run, with its branch outcome and pull request when one exists"
        icon={Bot}
        action={
          <Link
            to="/history"
            className="inline-flex items-center gap-1 text-[11px] text-indigo-300 hover:text-indigo-200"
          >
            All executions <ArrowUpRight className="h-3 w-3" />
          </Link>
        }
        bodyClassName="p-0"
      >
        {stats.loading && !data ? (
          <div className="space-y-3 p-5">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-10 w-full" />
            ))}
          </div>
        ) : data?.recent_activity.length ? (
          <div className="overflow-x-auto">
            <table className="table-base">
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Repository</th>
                  <th>Status</th>
                  <th>Started</th>
                  <th>Duration</th>
                  <th>Pull request</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_activity.map((activity) => (
                  <tr
                    key={activity.execution_id}
                    className="transition hover:bg-white/[0.02]"
                  >
                    <td className="max-w-[320px]">
                      <Link
                        to={`/workspace/${activity.execution_id}`}
                        className="truncate font-medium text-slate-200 hover:text-indigo-300"
                      >
                        {activity.task_title}
                      </Link>
                      <p className="mt-0.5 text-[10px] text-slate-500">
                        execution #{activity.execution_id}
                      </p>
                    </td>
                    <td className="mono text-[11px] text-slate-400">{activity.repository}</td>
                    <td>
                      <StatusBadge status={activity.status} />
                    </td>
                    <td className="text-xs text-slate-400">
                      {formatRelative(activity.started_at)}
                    </td>
                    <td className="text-xs text-slate-400">
                      {formatDuration(activity.duration_seconds)}
                    </td>
                    <td>
                      {activity.pull_request_url ? (
                        <a
                          href={activity.pull_request_url}
                          target="_blank"
                          rel="noreferrer"
                          className={cn(
                            "inline-flex items-center gap-1 text-xs text-indigo-300 hover:text-indigo-200",
                          )}
                        >
                          Open <ArrowUpRight className="h-3 w-3" />
                        </a>
                      ) : (
                        <span className="text-xs text-slate-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-5">
            <EmptyState
              icon={Bot}
              title="No executions yet"
              description="Send a task to the agent and its full execution history will appear here."
              action={
                <Link to="/tasks" className={buttonStyles("secondary", "sm")}>
                  Open Issues &amp; Tasks
                </Link>
              }
            />
          </div>
        )}
      </Section>
    </div>
  );
}

import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Clock3,
  FileCode2,
  GitPullRequest,
  History as HistoryIcon,
  RefreshCw,
  RotateCcw,
  Search,
} from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
  buttonStyles,
} from "../components/ui";
import { useToast } from "../components/ToastProvider";
import { useApiQuery } from "../hooks/useApiQuery";
import { api, errorMessage } from "../services/api";
import { formatDate, formatDuration } from "../utils/format";

const PAGE_SIZE = 15;

export default function History() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const toast = useToast();
  const [search, setSearch] = useState(() => searchParams.get("search") ?? "");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState("created_at");
  const [order, setOrder] = useState("desc");
  const [page, setPage] = useState(1);
  const [retryingId, setRetryingId] = useState<number | null>(null);
  const executions = useApiQuery(
    () =>
      api.executions({
        search: search || undefined,
        status: status || undefined,
        sort,
        order,
        page,
        page_size: PAGE_SIZE,
      }),
    [search, status, sort, order, page],
  );

  const retry = async (executionId: number) => {
    setRetryingId(executionId);
    try {
      const next = await api.retryExecution(executionId);
      toast.success("Retry started", `Execution #${next.id} is queued.`);
      navigate(`/workspace/${next.id}`);
    } catch (error) {
      toast.error("Retry failed", errorMessage(error));
    } finally {
      setRetryingId(null);
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Audit trail"
        title="Execution History"
        description="Every execution is preserved, including failures, correction attempts, logs and generated diffs. Retrying creates a new record."
        actions={
          <Button
            variant="secondary"
            size="sm"
            icon={RefreshCw}
            loading={executions.loading}
            onClick={() => void executions.refresh()}
          >
            Refresh
          </Button>
        }
      />

      <Card className="mb-4 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              className="input pl-9"
              placeholder="Search by task title"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              aria-label="Search executions"
            />
          </div>
          <select
            className="input lg:w-40"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
            aria-label="Filter by status"
          >
            <option value="">All statuses</option>
            <option value="queued">Queued</option>
            <option value="running">Running</option>
            <option value="awaiting_approval">Awaiting approval</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <select
            className="input lg:w-44"
            value={`${sort}:${order}`}
            onChange={(event) => {
              const [nextSort, nextOrder] = event.target.value.split(":");
              setSort(nextSort);
              setOrder(nextOrder);
              setPage(1);
            }}
            aria-label="Sort executions"
          >
            <option value="created_at:desc">Newest first</option>
            <option value="created_at:asc">Oldest first</option>
            <option value="duration:desc">Longest duration</option>
            <option value="duration:asc">Shortest duration</option>
            <option value="status:asc">Status</option>
          </select>
        </div>
      </Card>

      {executions.error ? (
        <ErrorState message={executions.error} onRetry={() => void executions.refresh()} />
      ) : executions.loading && !executions.data ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-14 w-full" />
          ))}
        </div>
      ) : executions.data?.items.length ? (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="table-base">
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Repository</th>
                  <th>Status</th>
                  <th>Started</th>
                  <th>Duration</th>
                  <th>Changes</th>
                  <th>Tests</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {executions.data.items.map((execution) => (
                  <tr
                    key={execution.id}
                    className="cursor-pointer transition hover:bg-white/[0.02]"
                    onClick={() => navigate(`/workspace/${execution.id}`)}
                  >
                    <td className="max-w-[300px]">
                      <p className="truncate text-xs font-medium text-slate-200">
                        {execution.task?.title ?? `Execution #${execution.id}`}
                      </p>
                      <p className="mt-0.5 text-[10px] text-slate-500">
                        execution #{execution.id}
                        {execution.correction_attempts
                          ? ` · ${execution.correction_attempts} correction attempts`
                          : ""}
                      </p>
                    </td>
                    <td className="mono text-[11px] text-slate-400">
                      {execution.task?.repository?.full_name ?? "—"}
                    </td>
                    <td>
                      <StatusBadge status={execution.status} />
                    </td>
                    <td className="text-[11px] text-slate-500">
                      {formatDate(execution.started_at ?? execution.created_at, false)}
                    </td>
                    <td className="text-[11px] text-slate-500">
                      {formatDuration(execution.duration_seconds)}
                    </td>
                    <td className="text-[11px] text-slate-500">
                      {execution.task ? (
                        <span className="inline-flex items-center gap-1">
                          <FileCode2 className="h-3 w-3" /> {execution.branch_name ? "branch" : "—"}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="text-[10px]">
                      {execution.pull_request?.url ? (
                        <a
                          href={execution.pull_request.url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(event) => event.stopPropagation()}
                          className="inline-flex items-center gap-1 text-indigo-300 hover:text-indigo-200"
                        >
                          <GitPullRequest className="h-3 w-3" /> #{execution.pull_request.number}
                        </a>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                    <td className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Link
                          to={`/workspace/${execution.id}`}
                          onClick={(event) => event.stopPropagation()}
                          className="rounded-md p-1 text-slate-500 hover:bg-white/[0.06] hover:text-indigo-300"
                          aria-label={`View execution ${execution.id}`}
                        >
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        </Link>
                        <Button
                          variant="ghost"
                          size="sm"
                          icon={RotateCcw}
                          loading={retryingId === execution.id}
                          disabled={!["completed", "failed", "cancelled"].includes(execution.status)}
                          onClick={(event) => {
                            event.stopPropagation();
                            void retry(execution.id);
                          }}
                        >
                          Retry
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.06] px-4 py-3">
            <p className="text-[11px] text-slate-500">
              Page {executions.data.page} of {executions.data.pages} · {executions.data.total} executions
            </p>
            <div className="flex items-center gap-1.5">
              <Button
                variant="secondary"
                size="sm"
                icon={ChevronLeft}
                disabled={page <= 1}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={page >= executions.data.pages}
                onClick={() => setPage((value) => value + 1)}
              >
                Next <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </Card>
      ) : (
        <EmptyState
          icon={HistoryIcon}
          title="No executions found"
          description="Adjust the filters or send a task to the agent to create the first execution record."
          action={
            <Link to="/tasks" className={buttonStyles("primary", "sm")}>
              Start a task
            </Link>
          }
        />
      )}

      <p className="mt-4 flex items-center gap-2 text-[10px] text-slate-600">
        <Clock3 className="h-3 w-3" /> Historical executions are never overwritten. Retrying always
        creates a new record with its own logs, diff and test results.
      </p>
    </div>
  );
}

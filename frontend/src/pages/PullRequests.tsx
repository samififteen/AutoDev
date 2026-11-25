import {
  ArrowUpRight,
  GitBranch,
  GitPullRequest,
  RefreshCw,
  Search,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
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
import { useApiQuery } from "../hooks/useApiQuery";
import { api } from "../services/api";
import { formatDate, formatRelative } from "../utils/format";

export default function PullRequests() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const pullRequests = useApiQuery(
    () => api.pullRequests({ search: search || undefined, status: status || undefined, page_size: 50 }),
    [search, status],
  );

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Human review"
        title="Pull Requests"
        description="Pull requests created by AutoDev after validation passed. Merging and approval always remain a human decision."
        actions={
          <>
            <Button
              variant="secondary"
              size="sm"
              icon={RefreshCw}
              loading={pullRequests.loading}
              onClick={() => void pullRequests.refresh()}
            >
              Refresh
            </Button>
            <Link to="/history" className={buttonStyles("secondary", "sm")}>
              Executions
            </Link>
          </>
        }
      />

      <Card className="mb-4 p-4">
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              className="input pl-9"
              placeholder="Search pull request titles"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="Search pull requests"
            />
          </div>
          <select
            className="input sm:w-40"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            aria-label="Filter pull request status"
          >
            <option value="">All states</option>
            <option value="open">Open</option>
            <option value="closed">Closed</option>
            <option value="merged">Merged</option>
          </select>
        </div>
      </Card>

      {pullRequests.error ? (
        <ErrorState message={pullRequests.error} onRetry={() => void pullRequests.refresh()} />
      ) : pullRequests.loading && !pullRequests.data ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-14 w-full" />
          ))}
        </div>
      ) : pullRequests.data?.items.length ? (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="table-base">
              <thead>
                <tr>
                  <th>Pull request</th>
                  <th>Repository</th>
                  <th>Branch</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th className="text-right">GitHub</th>
                </tr>
              </thead>
              <tbody>
                {pullRequests.data.items.map((pull) => (
                  <tr key={pull.id} className="transition hover:bg-white/[0.02]">
                    <td className="max-w-[340px]">
                      <div className="flex items-start gap-2">
                        <GitPullRequest className="mt-0.5 h-3.5 w-3.5 shrink-0 text-violet-400" />
                        <div className="min-w-0">
                          <p className="truncate text-xs font-medium text-slate-200">
                            {pull.number ? `#${pull.number} ` : ""}
                            {pull.title}
                          </p>
                          <p className="mt-0.5 truncate text-[10px] text-slate-500">
                            {pull.task_title}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="mono text-[11px] text-slate-400">{pull.repository}</td>
                    <td>
                      <span className="inline-flex items-center gap-1 text-[10px] text-slate-500">
                        <GitBranch className="h-3 w-3" />
                        <span className="mono max-w-[160px] truncate">{pull.branch}</span>
                      </span>
                      <p className="mono mt-0.5 text-[9px] text-slate-600">→ {pull.base_branch}</p>
                    </td>
                    <td>
                      <StatusBadge status={pull.status} />
                    </td>
                    <td className="text-[11px] text-slate-500">
                      {formatDate(pull.created_at)}
                      <p className="text-[9px] text-slate-600">{formatRelative(pull.created_at)}</p>
                    </td>
                    <td className="text-right">
                      {pull.url ? (
                        <a
                          href={pull.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-[11px] text-indigo-300 hover:text-indigo-200"
                        >
                          Open <ArrowUpRight className="h-3 w-3" />
                        </a>
                      ) : (
                        <span className="text-[11px] text-slate-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <EmptyState
          icon={GitPullRequest}
          title="No pull requests yet"
          description="When an execution passes validation, a human can approve pull request creation from the workspace. AutoDev never opens pull requests on its own."
          action={
            <Link to="/workspace" className={buttonStyles("primary", "sm")}>
              Open workspace
            </Link>
          }
        />
      )}

      <p className="mt-4 flex items-start gap-2 text-[10px] leading-relaxed text-slate-600">
        AutoDev never merges, approves or force-pushes. Pull requests are created against the
        configured base branch with human confirmation, and the workspace branch is never deleted
        automatically.
      </p>
    </div>
  );
}

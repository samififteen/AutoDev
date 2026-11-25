import {
  ArrowUpRight,
  BookOpen,
  FolderGit2,
  GitBranch,
  Github,
  Lock,
  Plus,
  RefreshCw,
  ScanSearch,
  Search,
} from "lucide-react";
import { useDeferredValue, useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Modal,
  Section,
  Skeleton,
  buttonStyles,
} from "../components/ui";
import { useToast } from "../components/ToastProvider";
import { useApiQuery } from "../hooks/useApiQuery";
import { api, errorMessage } from "../services/api";
import type { Repository } from "../types";
import { formatRelative } from "../utils/format";

function ConnectRepositoryModal({
  open,
  onClose,
  githubConfigured,
  onConnected,
}: {
  open: boolean;
  onClose: () => void;
  githubConfigured: boolean;
  onConnected: () => void;
}) {
  const toast = useToast();
  const [fullName, setFullName] = useState("");
  const [branch, setBranch] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!fullName.includes("/")) {
      setError("Use the owner/repository format, for example octocat/Hello-World");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const repository = await api.connectRepository({
        full_name: fullName.trim(),
        default_branch: branch.trim() || null,
      });
      toast.success("Repository connected", `${repository.full_name} is ready for analysis.`);
      onConnected();
      setFullName("");
      setBranch("");
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title="Connect a GitHub repository"
      description="AutoDev reads repository metadata and issues with the token configured on the backend. Tokens never reach the browser."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button loading={saving} onClick={submit} disabled={!fullName.trim()}>
            Connect repository
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {!githubConfigured ? (
          <div className="rounded-xl border border-amber-400/20 bg-amber-500/[0.06] p-4 text-xs leading-relaxed text-amber-200">
            <p className="font-medium text-amber-100">GitHub is not configured yet.</p>
            <p className="mt-1 text-amber-200/80">
              Add <code className="mono rounded bg-black/30 px-1">GITHUB_TOKEN</code> to the
              backend environment (or GitHub App credentials) and restart the API. Minimum scopes:
              metadata read, contents read/write, issues read, pull requests read/write.
            </p>
          </div>
        ) : null}

        <Field
          label="Repository"
          htmlFor="repo-full-name"
          hint="The repository must be accessible to the configured token. Access is limited to repositories you explicitly connect."
        >
          <input
            id="repo-full-name"
            className="input mono"
            placeholder="owner/repository"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void submit();
            }}
            autoFocus
          />
        </Field>
        <Field
          label="Default base branch (optional)"
          htmlFor="repo-branch"
          hint="Falls back to the repository default branch and the agent settings."
        >
          <input
            id="repo-branch"
            className="input mono"
            placeholder="main"
            value={branch}
            onChange={(event) => setBranch(event.target.value)}
          />
        </Field>

        {error ? <ErrorState message={error} /> : null}

        <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-4">
          <p className="flex items-center gap-2 text-xs font-medium text-slate-200">
            <Github className="h-4 w-4" /> Exclusive access
          </p>
          <ul className="mt-2 space-y-1.5 text-[11px] leading-relaxed text-slate-500">
            <li>• AutoDev only clones repositories you connect here.</li>
            <li>• Branches are created under the autodev/ namespace.</li>
            <li>• Pull requests are never merged or approved automatically.</li>
            <li>• Secrets are never returned by the API or written to logs.</li>
          </ul>
        </div>
      </div>
    </Modal>
  );
}

function RepositoryCard({
  repository,
  onAnalyze,
  analyzing,
}: {
  repository: Repository;
  onAnalyze: (repository: Repository) => void;
  analyzing: boolean;
}) {
  return (
    <Card className="group flex flex-col p-5 transition hover:border-white/[0.12]">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-white/[0.07] bg-white/[0.03] text-indigo-300">
            {repository.is_demo ? <BookOpen className="h-4 w-4" /> : <FolderGit2 className="h-4 w-4" />}
          </span>
          <div className="min-w-0">
            <Link
              to={`/repositories/${repository.id}`}
              className="block truncate text-sm font-semibold text-slate-100 hover:text-indigo-300"
            >
              {repository.full_name}
            </Link>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              {repository.is_demo ? (
                <StatusBadge status="configured" label="Demo" dot={false} />
              ) : (
                <StatusBadge
                  status={repository.visibility === "private" ? "pending" : "open"}
                  label={repository.visibility}
                  dot={false}
                />
              )}
              {repository.language ? (
                <span className="chip py-0.5">{repository.language}</span>
              ) : null}
              {repository.analysis ? (
                <span className="chip border-emerald-400/20 py-0.5 text-emerald-300">
                  Analyzed
                </span>
              ) : (
                <span className="chip py-0.5 text-slate-500">Not analyzed</span>
              )}
            </div>
          </div>
        </div>
        {repository.visibility === "private" ? (
          <Lock className="h-3.5 w-3.5 shrink-0 text-slate-600" />
        ) : null}
      </div>

      <p className="mt-3 line-clamp-2 min-h-[32px] text-xs leading-relaxed text-slate-500">
        {repository.description || "No description provided by the repository."}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-slate-500">
        <span className="inline-flex items-center gap-1">
          <GitBranch className="h-3 w-3" /> {repository.default_branch}
        </span>
        <span>Updated {formatRelative(repository.updated_at)}</span>
        {repository.analysis ? (
          <span>{repository.analysis.file_count} indexed files</span>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-white/[0.05] pt-4">
        <Link to={`/repositories/${repository.id}`} className={buttonStyles("secondary", "sm")}>
          Open
        </Link>
        <Button
          variant="ghost"
          size="sm"
          icon={ScanSearch}
          loading={analyzing}
          onClick={() => onAnalyze(repository)}
        >
          Analyze
        </Button>
        <Link
          to={`/tasks?repository=${repository.id}`}
          className="ml-auto inline-flex items-center gap-1 text-[11px] text-slate-500 transition hover:text-indigo-300"
        >
          Tasks <ArrowUpRight className="h-3 w-3" />
        </Link>
      </div>
    </Card>
  );
}

export default function Repositories() {
  const toast = useToast();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [visibility, setVisibility] = useState("");
  const [connectOpen, setConnectOpen] = useState(false);
  const [analyzingId, setAnalyzingId] = useState<number | null>(null);
  const repositories = useApiQuery(
    () => api.repositories({ search: deferredSearch || undefined, visibility: visibility || undefined }),
    [deferredSearch, visibility],
  );
  const system = useApiQuery(() => api.systemStatus(), []);
  const githubConfigured = system.data?.github.status === "ok";

  const analyze = async (repository: Repository) => {
    setAnalyzingId(repository.id);
    try {
      const result = await api.analyzeRepository(repository.id);
      toast.success(
        "Repository analyzed",
        `${result.summary.file_count} files indexed · ${result.summary.primary_language ?? "unknown language"}`,
      );
      await repositories.refresh(true);
    } catch (error) {
      toast.error("Analysis failed", errorMessage(error));
    } finally {
      setAnalyzingId(null);
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Source control"
        title="Repositories"
        description="Connect the repositories AutoDev may inspect. Each analysis reads the real directory structure, dependency files and tests — secrets are excluded."
        actions={
          <>
            <Button
              variant="secondary"
              size="sm"
              icon={RefreshCw}
              onClick={() => void repositories.refresh()}
              loading={repositories.loading}
            >
              Refresh
            </Button>
            <Button icon={Plus} size="sm" onClick={() => setConnectOpen(true)}>
              Connect repository
            </Button>
          </>
        }
      />

      <Card className="mb-4 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              className="input pl-9"
              placeholder="Search repositories by name, owner or description"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="Search repositories"
            />
          </div>
          <select
            className="input sm:w-44"
            value={visibility}
            onChange={(event) => setVisibility(event.target.value)}
            aria-label="Filter by visibility"
          >
            <option value="">All visibility</option>
            <option value="public">Public</option>
            <option value="private">Private</option>
          </select>
          <div className="flex items-center gap-2 text-[11px] text-slate-500">
            <Github className="h-3.5 w-3.5" />
            {githubConfigured
              ? system.data?.github.detail
              : "GitHub not configured · demo repository available"}
          </div>
        </div>
      </Card>

      {repositories.error ? (
        <ErrorState message={repositories.error} onRetry={() => void repositories.refresh()} />
      ) : repositories.loading && !repositories.data ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Card key={index} className="p-5">
              <Skeleton className="h-9 w-9 rounded-lg" />
              <Skeleton className="mt-4 h-3 w-40" />
              <Skeleton className="mt-3 h-2.5 w-full" />
              <Skeleton className="mt-2 h-2.5 w-2/3" />
            </Card>
          ))}
        </div>
      ) : repositories.data?.items.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {repositories.data.items.map((repository) => (
            <RepositoryCard
              key={repository.id}
              repository={repository}
              onAnalyze={analyze}
              analyzing={analyzingId === repository.id}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={FolderGit2}
          title={search ? "No repositories match this search" : "No repositories connected"}
          description={
            search
              ? "Try a different name, owner or visibility filter."
              : "Connect a GitHub repository to analyze its code and let the agent prepare pull requests."
          }
          action={
            <Button size="sm" icon={Plus} onClick={() => setConnectOpen(true)}>
              Connect repository
            </Button>
          }
        />
      )}

      <Section
        className="mt-4"
        title="Access model"
        icon={Lock}
        subtitle="Minimum permissions, explicit connections, no browser-side tokens"
      >
        <div className="grid gap-4 text-xs leading-relaxed text-slate-500 md:grid-cols-3">
          <div>
            <p className="mb-1 font-medium text-slate-300">Scoped token</p>
            Use a fine-grained token with metadata read, contents read/write, issues read and pull
            requests read/write. Prefer a GitHub App in production.
          </div>
          <div>
            <p className="mb-1 font-medium text-slate-300">Server-side only</p>
            Tokens live in backend environment variables. They are never sent to this UI, stored in
            the database or written to execution logs.
          </div>
          <div>
            <p className="mb-1 font-medium text-slate-300">Isolated workspaces</p>
            Each execution clones into its own workspace and creates an autodev/* branch. Main is
            never written to and nothing is force-pushed.
          </div>
        </div>
      </Section>

      <ConnectRepositoryModal
        open={connectOpen}
        onClose={() => setConnectOpen(false)}
        githubConfigured={githubConfigured}
        onConnected={() => void repositories.refresh()}
      />
    </div>
  );
}

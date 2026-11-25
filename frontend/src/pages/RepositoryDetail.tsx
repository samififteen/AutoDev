import {
  ArrowLeft,
  ArrowUpRight,
  BookOpen,
  Boxes,
  CheckSquare,
  FileCode2,
  FolderTree,
  GitBranch,
  Github,
  ListChecks,
  Package,
  RefreshCw,
  ScanSearch,
  TerminalSquare,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PageHeader } from "../components/PageHeader";
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
import { useToast } from "../components/ToastProvider";
import { useApiQuery } from "../hooks/useApiQuery";
import { api, errorMessage } from "../services/api";
import { formatDate, formatRelative } from "../utils/format";

export default function RepositoryDetail() {
  const { repositoryId } = useParams();
  const id = Number(repositoryId);
  const toast = useToast();
  const repository = useApiQuery(() => api.repository(id), [id]);
  const [analyzing, setAnalyzing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const data = repository.data;
  const analysis = data?.analysis ?? null;

  const analyze = async () => {
    setAnalyzing(true);
    try {
      const result = await api.analyzeRepository(id);
      repository.setData(result.repository);
      toast.success("Analysis complete", `${result.summary.file_count} files indexed.`);
    } catch (error) {
      toast.error("Analysis failed", errorMessage(error));
    } finally {
      setAnalyzing(false);
    }
  };

  const refresh = async () => {
    setRefreshing(true);
    try {
      const updated = await api.refreshRepository(id);
      repository.setData(updated);
      toast.success("Repository metadata refreshed");
    } catch (error) {
      toast.error("Refresh failed", errorMessage(error));
    } finally {
      setRefreshing(false);
    }
  };

  if (repository.error) {
    return (
      <div>
        <Link
          to="/repositories"
          className="mb-4 inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-200"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Repositories
        </Link>
        <ErrorState message={repository.error} onRetry={() => void repository.refresh()} />
      </div>
    );
  }

  if (repository.loading && !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="animate-fade-in">
      <Link
        to="/repositories"
        className="mb-4 inline-flex items-center gap-1.5 text-xs text-slate-500 transition hover:text-slate-200"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Repositories
      </Link>

      <PageHeader
        eyebrow={data.is_demo ? "Bundled demo repository" : "Connected repository"}
        title={data.full_name}
        description={data.description || "No repository description."}
        actions={
          <>
            {data.html_url ? (
              <a
                href={data.html_url}
                target="_blank"
                rel="noreferrer"
                className={buttonStyles("secondary", "sm")}
              >
                <Github className="h-4 w-4" /> GitHub
              </a>
            ) : null}
            <Link to={`/tasks?repository=${data.id}`} className={buttonStyles("secondary", "sm")}>
              <ListChecks className="h-4 w-4" /> Tasks
            </Link>
            <Button
              variant="secondary"
              size="sm"
              icon={RefreshCw}
              loading={refreshing}
              onClick={refresh}
            >
              Refresh
            </Button>
            <Button size="sm" icon={ScanSearch} loading={analyzing} onClick={analyze}>
              Analyze repository
            </Button>
          </>
        }
      />

      <Card className="mb-4 p-5">
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="label">Default branch</p>
            <p className="inline-flex items-center gap-1.5 text-sm text-slate-200">
              <GitBranch className="h-3.5 w-3.5 text-slate-500" /> {data.default_branch}
            </p>
          </div>
          <div>
            <p className="label">Language</p>
            <p className="text-sm text-slate-200">{data.language ?? "Unknown"}</p>
          </div>
          <div>
            <p className="label">Visibility</p>
            <div className="flex items-center gap-2">
              <StatusBadge status={data.visibility === "private" ? "pending" : "open"} label={data.visibility} dot={false} />
              {data.is_demo ? <span className="chip">demo</span> : null}
            </div>
          </div>
          <div>
            <p className="label">Last analyzed</p>
            <p className="text-sm text-slate-200">
              {data.analyzed_at ? formatRelative(data.analyzed_at) : "Never"}
            </p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-white/[0.05] pt-3 text-[10px] text-slate-500">
          <span>Connected {formatDate(data.created_at, false)}</span>
          <span>Updated {formatDate(data.updated_at, false)}</span>
          {data.clone_url ? <span className="mono truncate">{data.clone_url}</span> : null}
        </div>
      </Card>

      {!analysis ? (
        <EmptyState
          icon={ScanSearch}
          title="This repository has not been analyzed"
          description="Analysis clones the repository into an isolated workspace, indexes source and test files, detects the toolchain and stores a summary. Secret and build directories are excluded."
          action={
            <Button size="sm" icon={ScanSearch} loading={analyzing} onClick={analyze}>
              Analyze repository
            </Button>
          }
        />
      ) : (
        <div className="space-y-4">
          <Section title="Project summary" icon={BookOpen} subtitle="Derived from the README and source layout">
            <p className="max-w-4xl text-sm leading-relaxed text-slate-300">{analysis.purpose}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {analysis.technologies.map((technology) => (
                <span key={technology} className="chip">
                  {technology}
                </span>
              ))}
              <span className="chip">
                <Boxes className="h-3 w-3" /> {analysis.file_count} files · {analysis.source_file_count} source
              </span>
              {analysis.test_framework ? (
                <span className="chip">
                  <CheckSquare className="h-3 w-3" /> {analysis.test_framework}
                </span>
              ) : null}
            </div>
          </Section>

          <div className="grid gap-4 lg:grid-cols-2">
            <Section title="Entry points" icon={TerminalSquare}>
              {analysis.entry_points.length ? (
                <ul className="space-y-2">
                  {analysis.entry_points.map((entry) => (
                    <li key={entry} className="mono break-all rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-xs text-slate-300">
                      {entry}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-slate-500">No conventional entry points detected.</p>
              )}
              <div className="mt-4 space-y-3">
                <div>
                  <p className="label">Test commands</p>
                  {analysis.test_commands.length ? analysis.test_commands.map((command) => (
                    <code key={command} className="mono mb-1.5 block rounded-lg bg-black/30 px-2.5 py-1.5 text-[11px] text-emerald-300">
                      {command}
                    </code>
                  )) : <p className="text-xs text-slate-500">None detected.</p>}
                </div>
                <div>
                  <p className="label">Build / lint commands</p>
                  {[...analysis.build_commands, ...analysis.lint_commands].length ? (
                    [...analysis.build_commands, ...analysis.lint_commands].map((command) => (
                      <code key={command} className="mono mb-1.5 block rounded-lg bg-black/30 px-2.5 py-1.5 text-[11px] text-indigo-300">
                        {command}
                      </code>
                    ))
                  ) : (
                    <p className="text-xs text-slate-500">None detected.</p>
                  )}
                </div>
              </div>
            </Section>

            <Section title="Important modules" icon={FolderTree} subtitle="Ranked by extracted symbols">
              <div className="max-h-[320px] space-y-2 overflow-y-auto pr-1">
                {analysis.important_modules.map((module) => (
                  <div key={module.path} className="rounded-lg border border-white/[0.05] bg-white/[0.015] px-3 py-2.5">
                    <p className="mono break-all text-[11px] text-slate-300">{module.path}</p>
                    <p className="mt-1 text-[10px] leading-relaxed text-slate-500">
                      {module.symbols.length ? module.symbols.join(" · ") : "No top-level symbols"}
                    </p>
                  </div>
                ))}
              </div>
            </Section>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Section title="Dependencies" icon={Package} subtitle={`${analysis.dependencies.length} detected`}>
              {analysis.dependencies.length ? (
                <div className="flex max-h-48 flex-wrap gap-1.5 overflow-y-auto">
                  {analysis.dependencies.map((dependency) => (
                    <span key={dependency} className="chip mono py-0.5 text-[10px]">
                      {dependency}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500">No dependency manifest detected.</p>
              )}
            </Section>

            <Section title="Files" icon={FileCode2} subtitle="Tests and configuration detected">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="label">Test files</p>
                  <ul className="space-y-1 text-[11px] text-slate-400">
                    {analysis.test_files.length ? analysis.test_files.map((file) => (
                      <li key={file} className="mono truncate">{file}</li>
                    )) : <li className="text-slate-600">None</li>}
                  </ul>
                </div>
                <div>
                  <p className="label">Config files</p>
                  <ul className="space-y-1 text-[11px] text-slate-400">
                    {analysis.config_files.length ? analysis.config_files.map((file) => (
                      <li key={file} className="mono truncate">{file}</li>
                    )) : <li className="text-slate-600">None</li>}
                  </ul>
                </div>
              </div>
            </Section>
          </div>

          {analysis.readme_excerpt ? (
            <Section
              title="README excerpt"
              icon={BookOpen}
              action={
                analysis.readme_path ? (
                  <span className="mono text-[10px] text-slate-500">{analysis.readme_path}</span>
                ) : null
              }
            >
              <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-white/[0.05] bg-black/30 p-4 text-[11px] leading-relaxed text-slate-400">
                {analysis.readme_excerpt}
              </pre>
            </Section>
          ) : null}

          <p className="flex items-center gap-2 text-[10px] text-slate-600">
            <Github className="h-3 w-3" /> Analysis generated {formatDate(analysis.generated_at)} · only
            metadata and selected file content are sent to the configured AI provider.
            <ArrowUpRight className="h-3 w-3" />
          </p>
        </div>
      )}
    </div>
  );
}

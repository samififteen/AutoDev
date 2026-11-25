import {
  Bot,
  CheckCircle2,
  CircleAlert,
  Cpu,
  Eye,
  EyeOff,
  FlaskConical,
  Github,
  KeyRound,
  Lock,
  RefreshCw,
  Save,
  Server,
  ShieldCheck,
  TerminalSquare,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import {
  Button,
  Card,
  ErrorState,
  Field,
  Section,
  Skeleton,
  Toggle,
} from "../components/ui";
import { useToast } from "../components/ToastProvider";
import { useApiQuery } from "../hooks/useApiQuery";
import { api, errorMessage, getApiToken, setApiToken } from "../services/api";
import type { AgentSettings, TestingSettings } from "../types";

function NumberInput({
  id,
  label,
  value,
  onChange,
  min,
  max,
  hint,
}: {
  id: string;
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  hint?: string;
}) {
  return (
    <Field label={label} htmlFor={id} hint={hint}>
      <input
        id={id}
        type="number"
        className="input"
        value={value}
        min={min}
        max={max}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </Field>
  );
}

export default function Settings() {
  const toast = useToast();
  const settings = useApiQuery(() => api.settings(), []);
  const info = useApiQuery(() => api.systemInfo(), []);
  const [agent, setAgent] = useState<AgentSettings | null>(null);
  const [testing, setTesting] = useState<TestingSettings | null>(null);
  const [allowedText, setAllowedText] = useState("");
  const [saving, setSaving] = useState<"agent" | "testing" | null>(null);
  const [token, setToken] = useState(() => getApiToken());
  const [showToken, setShowToken] = useState(false);
  const [tokenSaved, setTokenSaved] = useState(false);

  useEffect(() => {
    if (!settings.data) return;
    setAgent(settings.data.agent);
    setTesting(settings.data.testing);
    setAllowedText(settings.data.testing.allowed_commands.join("\n"));
  }, [settings.data]);

  const validateAgent = (value: AgentSettings): string | null => {
    if (value.max_correction_attempts < 0 || value.max_correction_attempts > 5) {
      return "Correction attempts must be between 0 and 5.";
    }
    if (value.execution_timeout_seconds < 30 || value.execution_timeout_seconds > 3600) {
      return "Execution timeout must be between 30 and 3600 seconds.";
    }
    if (value.max_files_modified < 1 || value.max_files_modified > 50) {
      return "Maximum files modified must be between 1 and 50.";
    }
    if (value.max_concurrent_tasks < 1 || value.max_concurrent_tasks > 10) {
      return "Concurrent tasks must be between 1 and 10.";
    }
    if (value.default_base_branch && /\s|\.\./.test(value.default_base_branch)) {
      return "The base branch cannot contain whitespace or '..'.";
    }
    return null;
  };

  const saveAgent = async () => {
    if (!agent) return;
    const error = validateAgent(agent);
    if (error) {
      toast.error("Check the agent settings", error);
      return;
    }
    setSaving("agent");
    try {
      const updated = await api.updateSettings({ agent });
      settings.setData(updated);
      toast.success("Agent settings saved", "They apply to new executions immediately.");
    } catch (err) {
      toast.error("Could not save agent settings", errorMessage(err));
    } finally {
      setSaving(null);
    }
  };

  const saveTesting = async () => {
    if (!testing) return;
    if (testing.test_timeout_seconds < 10 || testing.test_timeout_seconds > 1800) {
      toast.error("Check the test settings", "Test timeout must be between 10 and 1800 seconds.");
      return;
    }
    const commands = allowedText
      .split(/[\n,]/)
      .map((command) => command.trim())
      .filter(Boolean);
    if (!commands.length) {
      toast.error("Check the test settings", "At least one allowed command is required.");
      return;
    }
    setSaving("testing");
    try {
      const updated = await api.updateSettings({
        testing: {
          ...testing,
          allowed_commands: commands,
          default_test_command: testing.default_test_command?.trim() || null,
        },
      });
      settings.setData(updated);
      toast.success("Test settings saved", "The sandbox policy is updated for new tests.");
    } catch (err) {
      toast.error("Could not save test settings", errorMessage(err));
    } finally {
      setSaving(null);
    }
  };

  const saveToken = () => {
    setApiToken(token.trim());
    setTokenSaved(true);
    toast.success(
      token.trim() ? "API token saved" : "API token cleared",
      "The token is stored in this browser only and sent as a Bearer header.",
    );
    window.setTimeout(() => setTokenSaved(false), 3000);
  };

  if (settings.error && !settings.data) {
    return (
      <div>
        <PageHeader title="Settings" description="Runtime agent, sandbox, provider and client configuration." />
        <ErrorState message={settings.error} onRetry={() => void settings.refresh()} />
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Configuration"
        title="Settings"
        description="Runtime agent behaviour and sandbox policy. Provider credentials are read from the backend environment and are never exposed to the browser."
        actions={
          <Button
            variant="secondary"
            size="sm"
            icon={RefreshCw}
            loading={settings.loading}
            onClick={() => void settings.refresh()}
          >
            Reload
          </Button>
        }
      />

      {settings.loading && !settings.data ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-64 w-full" />
          ))}
        </div>
      ) : agent && testing && settings.data ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Section
            title="Agent behaviour"
            subtitle="Applied when a task execution starts"
            icon={Bot}
            action={
              <Button
                size="sm"
                icon={Save}
                loading={saving === "agent"}
                onClick={() => void saveAgent()}
              >
                Save
              </Button>
            }
          >
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <NumberInput
                  id="settings-corrections"
                  label="Max correction attempts"
                  value={agent.max_correction_attempts}
                  min={0}
                  max={5}
                  onChange={(value) => setAgent({ ...agent, max_correction_attempts: value })}
                  hint="0–5. Tests must pass before completion."
                />
                <NumberInput
                  id="settings-exec-timeout"
                  label="Execution timeout (s)"
                  value={agent.execution_timeout_seconds}
                  min={30}
                  max={3600}
                  onChange={(value) => setAgent({ ...agent, execution_timeout_seconds: value })}
                />
                <NumberInput
                  id="settings-max-files"
                  label="Max files modified"
                  value={agent.max_files_modified}
                  min={1}
                  max={50}
                  onChange={(value) => setAgent({ ...agent, max_files_modified: value })}
                />
                <NumberInput
                  id="settings-concurrency"
                  label="Max concurrent tasks"
                  value={agent.max_concurrent_tasks}
                  min={1}
                  max={10}
                  onChange={(value) => setAgent({ ...agent, max_concurrent_tasks: value })}
                />
              </div>
              <Field
                label="Default base branch"
                htmlFor="settings-base-branch"
                hint="Optional. Falls back to each repository's default branch."
              >
                <input
                  id="settings-base-branch"
                  className="input mono"
                  placeholder="main"
                  value={agent.default_base_branch ?? ""}
                  onChange={(event) =>
                    setAgent({ ...agent, default_base_branch: event.target.value || null })
                  }
                />
              </Field>
              <Toggle
                label="Require plan approval"
                description="Pause after repository analysis and planning until a human approves. Strongly recommended."
                checked={agent.require_plan_approval}
                onChange={(value) => setAgent({ ...agent, require_plan_approval: value })}
              />
              <Toggle
                label="Require pull request confirmation"
                description="The create-PR action requires an explicit confirmation flag. AutoDev never merges or force-pushes."
                checked={agent.require_pr_approval}
                onChange={(value) => setAgent({ ...agent, require_pr_approval: value })}
              />
              <p className="flex items-start gap-2 text-[10px] leading-relaxed text-slate-500">
                <ShieldCheck className="mt-0.5 h-3 w-3 shrink-0" />
                Protected files, path traversal, secret scanning and branch rules are enforced
                server-side and cannot be disabled from this UI.
              </p>
            </div>
          </Section>

          <Section
            title="Test execution"
            subtitle="Sandbox command allowlist and timeouts"
            icon={FlaskConical}
            action={
              <Button
                size="sm"
                icon={Save}
                loading={saving === "testing"}
                onClick={() => void saveTesting()}
              >
                Save
              </Button>
            }
          >
            <div className="space-y-4">
              <Field
                label="Sandbox mode"
                htmlFor="settings-sandbox"
                hint="Local runs the test command in a background thread inside the isolated workspace. Docker runs it in the worker container."
              >
                <select
                  id="settings-sandbox"
                  className="input"
                  value={testing.sandbox_mode}
                  onChange={(event) =>
                    setTesting({
                      ...testing,
                      sandbox_mode: event.target.value as TestingSettings["sandbox_mode"],
                    })
                  }
                >
                  <option value="local">Local (in-process sandbox)</option>
                  <option value="docker">Docker worker</option>
                </select>
              </Field>
              <NumberInput
                id="settings-test-timeout"
                label="Test timeout (s)"
                value={testing.test_timeout_seconds}
                min={10}
                max={1800}
                onChange={(value) => setTesting({ ...testing, test_timeout_seconds: value })}
              />
              <Field
                label="Default test command"
                htmlFor="settings-test-command"
                hint="Optional. Must be permitted by the allowlist; the repository test plan can override it."
              >
                <input
                  id="settings-test-command"
                  className="input mono"
                  placeholder="python -m pytest -q"
                  value={testing.default_test_command ?? ""}
                  onChange={(event) =>
                    setTesting({ ...testing, default_test_command: event.target.value || null })
                  }
                />
              </Field>
              <Field
                label="Allowed programs"
                htmlFor="settings-allowed"
                hint="One bare executable per line (for example python, npm, pytest). Shell interpreters and inline code flags are rejected by the backend policy."
              >
                <textarea
                  id="settings-allowed"
                  className="input mono min-h-[110px] resize-y text-xs"
                  value={allowedText}
                  onChange={(event) => setAllowedText(event.target.value)}
                  spellCheck={false}
                />
              </Field>
              {testing.sandbox_mode === "docker" ? (
                <div className="flex items-start gap-2 rounded-lg border border-amber-400/20 bg-amber-500/[0.06] p-3 text-[11px] leading-relaxed text-amber-200">
                  <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  Docker mode requires the worker service (see docker-compose.yml) and a shared
                  workspace volume. The backend reports a configuration error if the worker is
                  unreachable.
                </div>
              ) : null}
            </div>
          </Section>

          <Section title="GitHub integration" icon={Github} subtitle="Credentials are server-side only">
            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.015] p-3">
                <span className="text-xs text-slate-400">Status</span>
                <StatusBadge
                  status={settings.data.github.configured ? (settings.data.github.verified ? "verified" : "unverified") : "disabled"}
                  label={
                    settings.data.github.configured
                      ? settings.data.github.verified
                        ? "Verified"
                        : "Configured — not verified"
                      : "Not configured"
                  }
                />
              </div>
              <dl className="space-y-2 text-xs">
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">Authentication</dt>
                  <dd className="text-slate-300">{settings.data.github.auth_mode}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">Account</dt>
                  <dd className="mono text-slate-300">{settings.data.github.login ?? "—"}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">API URL</dt>
                  <dd className="mono truncate text-slate-300">{settings.data.github.api_url}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">Credentials</dt>
                  <dd className="text-right text-slate-300">
                    {settings.data.github.token_configured ? "Personal access token" : ""}
                    {settings.data.github.token_configured && settings.data.github.app_configured
                      ? " + "
                      : ""}
                    {settings.data.github.app_configured ? "GitHub App" : ""}
                    {!settings.data.github.token_configured && !settings.data.github.app_configured
                      ? "None"
                      : ""}
                  </dd>
                </div>
              </dl>
              {settings.data.github.error ? (
                <ErrorState message={settings.data.github.error} />
              ) : null}
              <div className="rounded-lg border border-white/[0.06] bg-black/20 p-3">
                <p className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  <Lock className="h-3 w-3" /> Backend environment
                </p>
                <code className="mono block text-[11px] leading-relaxed text-slate-400">
                  GITHUB_TOKEN=… # or GITHUB_APP_ID + GITHUB_APP_PRIVATE_KEY + GITHUB_APP_INSTALLATION_ID
                </code>
                <p className="mt-1.5 text-[10px] leading-relaxed text-slate-600">
                  Minimum scopes: metadata read, contents read/write, issues read, pull requests
                  read/write. Restart the API after changing credentials.
                </p>
              </div>
            </div>
          </Section>

          <Section title="AI provider" icon={Cpu} subtitle="Used for analysis, planning and code generation">
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-white/[0.06] bg-white/[0.015] p-3">
                  <p className="text-[10px] uppercase tracking-wider text-slate-500">Provider</p>
                  <p className="mt-1 text-sm font-medium capitalize text-slate-200">
                    {settings.data.ai.provider}
                  </p>
                </div>
                <div className="rounded-lg border border-white/[0.06] bg-white/[0.015] p-3">
                  <p className="text-[10px] uppercase tracking-wider text-slate-500">Model</p>
                  <p className="mono mt-1 truncate text-sm text-slate-200">
                    {settings.data.ai.model}
                  </p>
                </div>
              </div>
              <dl className="space-y-2 text-xs">
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">API key configured</dt>
                  <dd className="inline-flex items-center gap-1.5 text-slate-300">
                    {settings.data.ai.api_key_configured ? (
                      <>
                        <CheckCircle2 className="h-3 w-3 text-emerald-400" /> Yes
                      </>
                    ) : (
                      <>
                        <XCircle className="h-3 w-3 text-slate-500" /> No
                      </>
                    )}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">Base URL</dt>
                  <dd className="mono truncate text-slate-300">{settings.data.ai.base_url}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">Max context (chars)</dt>
                  <dd className="text-slate-300">{settings.data.ai.max_context_chars}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">Temperature</dt>
                  <dd className="text-slate-300">{settings.data.ai.temperature}</dd>
                </div>
              </dl>
              {settings.data.ai.demo_mode ? (
                <div className="rounded-lg border border-indigo-400/20 bg-indigo-500/[0.06] p-3 text-[11px] leading-relaxed text-indigo-200">
                  <p className="flex items-center gap-1.5 font-medium text-indigo-100">
                    <FlaskConical className="h-3.5 w-3.5" /> Demo fixture provider active
                  </p>
                  <p className="mt-1 text-indigo-200/70">
                    No AI API key is configured. AutoDev uses deterministic fixtures for the bundled
                    demo repository. No model is called and no result is presented as AI output.
                    Tests, diffs and git operations are real. Set AI_API_KEY and restart — or set
                    AI_PROVIDER=openai explicitly — to use a model.
                  </p>
                </div>
              ) : (
                <p className="text-[10px] leading-relaxed text-slate-500">
                  OPENAI_API_KEY is read on the server. Repository content is wrapped as untrusted
                  data and cannot alter system instructions.
                </p>
              )}
            </div>
          </Section>

          <Section title="API access" icon={KeyRound} subtitle="Only needed when AUTODEV_API_TOKEN is set on the backend">
            <div className="space-y-3">
              <Field
                label="Client bearer token"
                htmlFor="settings-token"
                hint="Stored in this browser's localStorage (autodev.apiToken). It is sent in the Authorization header and in the SSE stream URL. Clearing it affects this browser only."
              >
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <input
                      id="settings-token"
                      className="input mono pr-10"
                      type={showToken ? "text" : "password"}
                      value={token}
                      onChange={(event) => setToken(event.target.value)}
                      placeholder="Paste the AUTODEV_API_TOKEN value"
                      autoComplete="off"
                      spellCheck={false}
                    />
                    <button
                      type="button"
                      onClick={() => setShowToken((value) => !value)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-slate-500 hover:text-slate-200"
                      aria-label={showToken ? "Hide token" : "Show token"}
                    >
                      {showToken ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                  <Button icon={Save} onClick={saveToken}>
                    {tokenSaved ? "Saved" : "Save"}
                  </Button>
                </div>
              </Field>
              <div className="rounded-lg border border-white/[0.06] bg-black/20 p-3">
                <p className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  <Server className="h-3 w-3" /> Backend environment
                </p>
                <code className="mono block text-[11px] text-slate-400">AUTODEV_API_TOKEN=…</code>
                <p className="mt-1.5 text-[10px] leading-relaxed text-slate-600">
                  When this variable is unset, the API is open on localhost. Do not expose the
                  backend publicly without a token and TLS.
                </p>
              </div>
            </div>
          </Section>

          <Section title="Environment reference" icon={TerminalSquare} subtitle="Configured in backend/.env, never in this UI">
            <pre className="mono overflow-x-auto rounded-lg border border-white/[0.06] bg-black/30 p-4 text-[11px] leading-relaxed text-slate-400">{`# AI provider — auto falls back to deterministic demo fixtures
AI_PROVIDER=auto            # auto | openai | demo
AI_API_KEY=…
AI_MODEL=gpt-4o-mini
AI_BASE_URL=https://api.openai.com/v1

# GitHub — optional; demo mode works without it
GITHUB_TOKEN=…
GITHUB_DEFAULT_BASE_BRANCH=main

# GitHub App alternative
# GITHUB_APP_ID=…
# GITHUB_APP_PRIVATE_KEY=…
# GITHUB_INSTALLATION_ID=…

# Safety
AUTODEV_API_TOKEN=…
SANDBOX_MODE=local          # local | docker
CORS_ORIGINS=http://127.0.0.1:5173`}</pre>
            <p className="mt-3 flex items-start gap-2 text-[10px] leading-relaxed text-slate-500">
              <ShieldCheck className="mt-0.5 h-3 w-3 shrink-0" />
              Secrets are never returned by the API, stored in the database or sent to the frontend.
              Settings on this page persist runtime overrides; environment credentials require a
              backend restart.
            </p>
          </Section>
        </div>
      ) : null}

      <Card className="mt-4 flex flex-col gap-2 p-4 text-[11px] leading-relaxed text-slate-500 sm:flex-row sm:items-center sm:justify-between">
        <span>
          AutoDev v{info.data?.version ?? "—"} · {info.data?.environment ?? "unknown environment"} ·
          branch protection and human review are required by design.
        </span>
        <span className="inline-flex items-center gap-1.5">
          <CheckCircle2 className="h-3 w-3 text-emerald-400" /> No auto-merge · no force-push
        </span>
      </Card>
    </div>
  );
}

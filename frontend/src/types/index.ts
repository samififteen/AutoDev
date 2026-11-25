export type ExecutionStatus =
  | "queued"
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed"
  | "cancelled";

export interface AnalysisModule {
  path: string;
  language?: string | null;
  symbols: string[];
}

export interface RepositoryAnalysis {
  purpose: string;
  primary_language: string | null;
  technologies: string[];
  languages: Record<string, number>;
  entry_points: string[];
  important_modules: AnalysisModule[];
  test_framework: string | null;
  test_commands: string[];
  build_commands: string[];
  lint_commands: string[];
  dependencies: string[];
  file_count: number;
  source_file_count: number;
  test_files: string[];
  config_files: string[];
  readme_path?: string | null;
  readme_excerpt?: string;
  git_log?: string[];
  generated_at: string;
}

export interface Repository {
  id: number;
  github_id: number | null;
  owner: string;
  name: string;
  full_name: string;
  description: string | null;
  default_branch: string;
  language: string | null;
  visibility: "public" | "private";
  clone_url: string | null;
  html_url: string | null;
  is_demo: boolean;
  connected: boolean;
  analysis: RepositoryAnalysis | null;
  analyzed_at: string | null;
  updated_at: string;
  created_at: string;
}

export interface Issue {
  number: number;
  title: string;
  body: string;
  labels: string[];
  assignees: string[];
  state: string;
  created_at: string | null;
  html_url: string | null;
  demo: boolean;
}

export interface Task {
  id: number;
  repository_id: number;
  github_issue_number: number | null;
  title: string;
  description: string;
  priority: "low" | "medium" | "high" | "critical";
  status: string;
  labels: string[];
  source: string;
  repository: Repository | null;
  created_at: string;
  updated_at: string;
}

export interface AgentLog {
  id: number | null;
  execution_id?: number;
  level: "debug" | "info" | "warning" | "error" | string;
  stage: string | null;
  message: string;
  created_at: string;
}

export interface TimelineStep {
  key: string;
  label: string;
  status: "completed" | "active" | "pending" | "skipped" | "failed";
}

export interface FileChange {
  id: number;
  execution_id: number;
  file_path: string;
  change_type: "added" | "modified" | "deleted" | string;
  diff: string;
  additions: number;
  deletions: number;
  original_content: string | null;
  modified_content: string | null;
  created_at: string;
}

export interface TestExecution {
  id: number;
  execution_id: number;
  command: string;
  status: "passed" | "failed" | "error" | "timeout" | string;
  output: string;
  summary: string | null;
  passed_count: number;
  failed_count: number;
  duration_seconds: number;
  attempt: number;
  created_at: string;
}

export interface PullRequest {
  id: number;
  execution_id: number;
  number: number | null;
  title: string;
  body: string;
  url: string | null;
  branch: string;
  base_branch: string;
  status: string;
  created_at: string;
}

export interface PullRequestListItem extends PullRequest {
  task_title: string;
  repository: string;
  execution_status: string;
}

export interface ExecutionActions {
  approve_plan: boolean;
  cancel: boolean;
  retry: boolean;
  view_diff: boolean;
  create_pull_request: boolean;
  preview_pull_request: boolean;
}

export interface ValidationCheck {
  name: string;
  passed: boolean;
  detail: string;
  severity: "error" | "warning";
}

export interface ValidationReport {
  passed: boolean;
  checks: ValidationCheck[];
  files_changed: string[];
  additions: number;
  deletions: number;
  secrets: { type: string; line: string; preview: string }[];
  summary: string;
  diff_size: number;
}

export interface ExecutionSummary {
  id: number;
  task_id: number;
  status: ExecutionStatus;
  current_stage: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  summary: string | null;
  branch_name: string | null;
  base_branch: string | null;
  ai_provider: string | null;
  ai_model: string | null;
  correction_attempts: number;
  error_message: string | null;
  created_at: string;
  task: Task | null;
  pull_request: PullRequest | null;
}

export interface PlanStep {
  index: number;
  title: string;
  detail: string | null;
}

export interface ImplementationPlan {
  summary: string;
  steps: PlanStep[];
  files_likely_affected: string[];
  test_plan: string[];
  risks: string[];
}

export interface ExecutionDetail extends ExecutionSummary {
  plan: ImplementationPlan | null;
  plan_approved: boolean;
  validation: ValidationReport | null;
  files_inspected: string[];
  prompt_tokens: number;
  completion_tokens: number;
  error_details: string | null;
  file_changes: FileChange[];
  test_executions: TestExecution[];
  timeline: TimelineStep[];
  actions: ExecutionActions;
  demo_mode: boolean;
}

export interface RecentActivity {
  execution_id: number;
  task_id: number;
  task_title: string;
  repository: string;
  status: ExecutionStatus;
  started_at: string | null;
  duration_seconds: number | null;
  pull_request_url: string | null;
}

export interface ChartPoint {
  date: string;
  completed: number;
  failed: number;
  pull_requests: number;
}

export interface DashboardStats {
  repositories_connected: number;
  tasks_total: number;
  tasks_processed: number;
  tasks_completed: number;
  tasks_failed: number;
  pull_requests_created: number;
  average_duration_seconds: number | null;
  active_executions: number;
  recent_activity: RecentActivity[];
  chart: ChartPoint[];
}

export interface SystemComponent {
  name: string;
  status: "ok" | "configured" | "error" | "unverified" | "disabled";
  detail: string;
}

export interface SystemStatus {
  backend: SystemComponent;
  database: SystemComponent;
  github: SystemComponent;
  ai_provider: SystemComponent;
  sandbox: SystemComponent;
  agent_worker: SystemComponent;
}

export interface SystemInfo {
  app_name: string;
  version: string;
  environment: string;
  demo_mode: boolean;
  ai_provider: string;
  ai_model: string;
  github_configured: boolean;
  auth_enabled: boolean;
  sandbox_mode: string;
  limits: Record<string, number>;
}

export interface AgentSettings {
  max_correction_attempts: number;
  execution_timeout_seconds: number;
  max_files_modified: number;
  max_concurrent_tasks: number;
  require_plan_approval: boolean;
  require_pr_approval: boolean;
  default_base_branch: string | null;
}

export interface TestingSettings {
  test_timeout_seconds: number;
  allowed_commands: string[];
  default_test_command: string | null;
  sandbox_mode: "local" | "docker";
}

export interface GitHubSettingsInfo {
  configured: boolean;
  auth_mode: string;
  verified: boolean | null;
  login: string | null;
  api_url: string;
  default_base_branch: string | null;
  token_configured: boolean;
  app_configured: boolean;
  error: string | null;
}

export interface AISettingsInfo {
  provider: string;
  model: string;
  base_url: string;
  api_key_configured: boolean;
  demo_mode: boolean;
  max_context_chars: number;
  temperature: number;
}

export interface SettingsPayload {
  agent: AgentSettings;
  testing: TestingSettings;
  github: GitHubSettingsInfo;
  ai: AISettingsInfo;
}

export interface DiffFile {
  path: string;
  change_type: string;
  additions: number;
  deletions: number;
  diff: string;
  original_content: string | null;
  modified_content: string | null;
}

export interface DiffResponse {
  execution_id: number;
  branch: string | null;
  base_branch: string | null;
  files: DiffFile[];
  unified_diff: string;
  additions: number;
  deletions: number;
}

export interface PullRequestDraft {
  title: string;
  body: string;
  branch: string;
  base_branch: string;
  provider: string;
  demo_mode: boolean;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface HealthInfo {
  status: "ok" | "degraded";
  version: string;
  database: boolean;
  demo_mode: boolean;
  ai_provider: string;
  github_configured: boolean;
}

"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


# --------------------------------------------------------------------------- #
# Repositories
# --------------------------------------------------------------------------- #
class RepositoryOut(ORMModel):
    id: int
    github_id: int | None = None
    owner: str
    name: str
    full_name: str
    description: str | None = None
    default_branch: str
    language: str | None = None
    visibility: str
    clone_url: str | None = None
    html_url: str | None = None
    is_demo: bool
    connected: bool
    analysis: dict | None = None
    analyzed_at: datetime | None = None
    updated_at: datetime
    created_at: datetime


class RepositoryConnectRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=300, examples=["octocat/Hello-World"])
    default_branch: str | None = Field(default=None, max_length=200)

    @field_validator("full_name")
    @classmethod
    def _validate_full_name(cls, value: str) -> str:
        value = value.strip()
        parts = value.split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError("full_name must look like 'owner/repository'")
        return value


class AnalyzeRepositoryResponse(BaseModel):
    repository: RepositoryOut
    summary: dict


class RepositoryIssue(BaseModel):
    number: int
    title: str
    body: str = ""
    labels: list[str] = []
    assignees: list[str] = []
    state: str = "open"
    created_at: datetime | None = None
    html_url: str | None = None
    demo: bool = False


# --------------------------------------------------------------------------- #
# Tasks
# --------------------------------------------------------------------------- #
class TaskCreate(BaseModel):
    repository_id: int
    title: str = Field(min_length=4, max_length=500)
    description: str = Field(default="", max_length=20_000)
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    github_issue_number: int | None = Field(default=None, ge=1)
    labels: list[str] = []


class TaskOut(ORMModel):
    id: int
    repository_id: int
    github_issue_number: int | None = None
    title: str
    description: str
    priority: str
    status: str
    labels: list[str] = []
    source: str
    repository: RepositoryOut | None = None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Executions
# --------------------------------------------------------------------------- #
class AgentLogOut(ORMModel):
    id: int
    execution_id: int
    level: str
    stage: str | None = None
    message: str
    created_at: datetime


class FileChangeOut(ORMModel):
    id: int
    execution_id: int
    file_path: str
    change_type: str
    diff: str
    additions: int
    deletions: int
    original_content: str | None = None
    modified_content: str | None = None
    created_at: datetime


class TestExecutionOut(ORMModel):
    id: int
    execution_id: int
    command: str
    status: str
    output: str
    summary: str | None = None
    passed_count: int
    failed_count: int
    duration_seconds: float
    attempt: int
    created_at: datetime


class PullRequestOut(ORMModel):
    id: int
    execution_id: int
    number: int | None = None
    title: str
    body: str
    url: str | None = None
    branch: str
    base_branch: str
    status: str
    created_at: datetime


class TimelineStep(BaseModel):
    key: str
    label: str
    status: Literal["completed", "active", "pending", "skipped", "failed"]


class ExecutionActions(BaseModel):
    approve_plan: bool
    cancel: bool
    retry: bool
    view_diff: bool
    create_pull_request: bool
    preview_pull_request: bool


class ExecutionSummaryOut(ORMModel):
    id: int
    task_id: int
    status: str
    current_stage: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    summary: str | None = None
    branch_name: str | None = None
    base_branch: str | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    correction_attempts: int
    error_message: str | None = None
    created_at: datetime
    task: TaskOut | None = None
    pull_request: PullRequestOut | None = None


class ExecutionDetailOut(ExecutionSummaryOut):
    plan: dict | None = None
    plan_approved: bool
    validation: dict | None = None
    files_inspected: list[str] = []
    prompt_tokens: int
    completion_tokens: int
    error_details: str | None = None
    file_changes: list[FileChangeOut] = []
    test_executions: list[TestExecutionOut] = []
    timeline: list[TimelineStep] = []
    actions: ExecutionActions = Field(
        default_factory=lambda: ExecutionActions(
            approve_plan=False,
            cancel=False,
            retry=False,
            view_diff=False,
            create_pull_request=False,
            preview_pull_request=False,
        )
    )
    demo_mode: bool = False


class ExecutionLogPage(BaseModel):
    items: list[AgentLogOut]
    total: int


class CreatePullRequestRequest(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=20_000)
    base_branch: str | None = Field(default=None, max_length=200)
    confirm: bool = True


class PullRequestDraft(BaseModel):
    title: str
    body: str
    branch: str
    base_branch: str
    provider: str
    demo_mode: bool


class PullRequestListItem(PullRequestOut):
    task_title: str
    repository: str
    execution_status: str


class DiffFile(BaseModel):
    path: str
    change_type: str
    additions: int
    deletions: int
    diff: str
    original_content: str | None = None
    modified_content: str | None = None


class DiffResponse(BaseModel):
    execution_id: int
    branch: str | None = None
    base_branch: str | None = None
    files: list[DiffFile]
    unified_diff: str
    additions: int
    deletions: int


# --------------------------------------------------------------------------- #
# Dashboard / system
# --------------------------------------------------------------------------- #
class RecentActivity(BaseModel):
    execution_id: int
    task_id: int
    task_title: str
    repository: str
    status: str
    started_at: datetime | None = None
    duration_seconds: float | None = None
    pull_request_url: str | None = None


class ChartPoint(BaseModel):
    date: str
    completed: int
    failed: int
    pull_requests: int


class DashboardStats(BaseModel):
    repositories_connected: int
    tasks_total: int
    tasks_processed: int
    tasks_completed: int
    tasks_failed: int
    pull_requests_created: int
    average_duration_seconds: float | None
    active_executions: int
    recent_activity: list[RecentActivity]
    chart: list[ChartPoint]


class ComponentStatus(BaseModel):
    name: str
    status: Literal["ok", "configured", "error", "unverified", "disabled"]
    detail: str


class SystemStatus(BaseModel):
    backend: ComponentStatus
    database: ComponentStatus
    github: ComponentStatus
    ai_provider: ComponentStatus
    sandbox: ComponentStatus
    agent_worker: ComponentStatus


class SystemInfo(BaseModel):
    app_name: str
    version: str
    environment: str
    demo_mode: bool
    ai_provider: str
    ai_model: str
    github_configured: bool
    auth_enabled: bool
    sandbox_mode: str
    limits: dict


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
class AgentSettings(BaseModel):
    max_correction_attempts: int = Field(ge=0, le=5)
    execution_timeout_seconds: int = Field(ge=30, le=3600)
    max_files_modified: int = Field(ge=1, le=50)
    max_concurrent_tasks: int = Field(ge=1, le=10)
    require_plan_approval: bool
    require_pr_approval: bool
    default_base_branch: str | None = None


class TestingSettings(BaseModel):
    test_timeout_seconds: int = Field(ge=10, le=1800)
    allowed_commands: list[str]
    default_test_command: str | None = None
    sandbox_mode: Literal["local", "docker"]


class GitHubSettingsInfo(BaseModel):
    configured: bool
    auth_mode: str
    verified: bool | None = None
    login: str | None = None
    api_url: str
    default_base_branch: str | None = None
    token_configured: bool
    app_configured: bool
    error: str | None = None


class AISettingsInfo(BaseModel):
    provider: str
    model: str
    base_url: str
    api_key_configured: bool
    demo_mode: bool
    max_context_chars: int
    temperature: float


class SettingsOut(BaseModel):
    agent: AgentSettings
    testing: TestingSettings
    github: GitHubSettingsInfo
    ai: AISettingsInfo


class SettingsUpdate(BaseModel):
    agent: AgentSettings | None = None
    testing: TestingSettings | None = None


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: bool
    demo_mode: bool
    ai_provider: str
    github_configured: bool

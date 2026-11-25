"""Execution queries and API serialisation."""

from __future__ import annotations

import math

from app.agent.stages import TERMINAL_STATUSES, build_timeline
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.models import AgentExecution, DevelopmentTask, FileChange, PullRequest
from app.schemas import (
    AgentLogOut,
    DiffFile,
    DiffResponse,
    ExecutionActions,
    ExecutionDetailOut,
    ExecutionSummaryOut,
    FileChangeOut,
    Paginated,
    PullRequestOut,
    TestExecutionOut,
    TimelineStep,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload


def execution_query():
    return select(AgentExecution).options(
        selectinload(AgentExecution.task).selectinload(DevelopmentTask.repository),
        selectinload(AgentExecution.file_changes),
        selectinload(AgentExecution.test_executions),
        selectinload(AgentExecution.pull_request),
    )


def get_execution_or_404(db: Session, execution_id: int) -> AgentExecution:
    execution = db.scalar(execution_query().where(AgentExecution.id == execution_id))
    if execution is None:
        raise NotFoundError(f"Execution {execution_id} was not found")
    return execution


def create_execution(db: Session, task: DevelopmentTask) -> AgentExecution:
    execution = AgentExecution(task_id=task.id, status="queued", current_stage="queued")
    task.status = "queued"
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def build_actions(execution: AgentExecution, settings: Settings) -> ExecutionActions:
    completed = execution.status == "completed"
    report = execution.validation or {}
    validated = completed and bool(report.get("passed"))
    repo = execution.task.repository if execution.task else None
    has_pr = execution.pull_request is not None
    can_pr = validated and not has_pr and repo is not None and not repo.is_demo and settings.github_configured
    return ExecutionActions(
        approve_plan=execution.status == "awaiting_approval"
        and execution.current_stage == "awaiting_plan_approval",
        cancel=execution.status in {"queued", "running", "awaiting_approval"},
        retry=execution.status in TERMINAL_STATUSES,
        view_diff=bool(execution.file_changes),
        create_pull_request=can_pr,
        preview_pull_request=validated and not has_pr,
    )


def _test_out(test) -> TestExecutionOut:
    data = TestExecutionOut.model_validate(test)
    if len(data.output) > 20_000:
        data.output = data.output[:10_000] + "\n... [truncated] ...\n" + data.output[-10_000:]
    return data


def build_execution_summary(
    execution: AgentExecution, settings: Settings | None = None
) -> ExecutionSummaryOut:
    data = ExecutionSummaryOut.model_validate(execution)
    data.pull_request = (
        PullRequestOut.model_validate(execution.pull_request) if execution.pull_request else None
    )
    return data


def build_execution_detail(execution: AgentExecution, settings: Settings | None = None) -> ExecutionDetailOut:
    settings = settings or get_settings()
    data = ExecutionDetailOut.model_validate(execution)
    data.plan = execution.plan
    data.validation = execution.validation
    data.files_inspected = execution.files_inspected
    data.file_changes = [FileChangeOut.model_validate(change) for change in execution.file_changes]
    data.test_executions = [_test_out(test) for test in execution.test_executions]
    data.pull_request = (
        PullRequestOut.model_validate(execution.pull_request) if execution.pull_request else None
    )
    data.timeline = [
        TimelineStep(**step) for step in build_timeline(execution.current_stage, execution.status)
    ]
    data.actions = build_actions(execution, settings)
    data.demo_mode = (
        bool(execution.ai_provider and "demo" in execution.ai_provider.lower()) or settings.demo_mode
    )
    return data


def paginate_executions(
    db: Session,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
    repository_id: int | None = None,
    search: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
) -> Paginated[ExecutionSummaryOut]:
    query = execution_query()
    if status:
        query = query.where(AgentExecution.status == status)
    if repository_id:
        query = query.join(DevelopmentTask).where(DevelopmentTask.repository_id == repository_id)
    if search:
        needle = f"%{search.strip()}%"
        query = query.join(DevelopmentTask).where(DevelopmentTask.title.ilike(needle))

    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    sort_column = {
        "created_at": AgentExecution.created_at,
        "started_at": AgentExecution.started_at,
        "duration": AgentExecution.duration_seconds,
        "status": AgentExecution.status,
    }.get(sort, AgentExecution.created_at)
    query = query.order_by(sort_column.desc() if order != "asc" else sort_column.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    items = db.scalars(query).all()
    return Paginated[ExecutionSummaryOut](
        items=[build_execution_summary(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)) if page_size else 1,
    )


def build_diff(db: Session, execution: AgentExecution) -> DiffResponse:
    changes = db.scalars(
        select(FileChange).where(FileChange.execution_id == execution.id).order_by(FileChange.file_path)
    ).all()
    unified = "\n".join(change.diff for change in changes if change.diff)
    return DiffResponse(
        execution_id=execution.id,
        branch=execution.branch_name,
        base_branch=execution.base_branch,
        files=[
            DiffFile(
                path=change.file_path,
                change_type=change.change_type,
                additions=change.additions,
                deletions=change.deletions,
                diff=change.diff,
                original_content=change.original_content,
                modified_content=change.modified_content,
            )
            for change in changes
        ],
        unified_diff=unified,
        additions=sum(change.additions for change in changes),
        deletions=sum(change.deletions for change in changes),
    )


def execution_logs(
    db: Session, execution_id: int, *, limit: int = 200, after_id: int | None = None
) -> tuple[list[AgentLogOut], int]:
    from app.models import AgentLog

    execution = db.get(AgentExecution, execution_id)
    if execution is None:
        raise NotFoundError(f"Execution {execution_id} was not found")
    base = select(AgentLog).where(AgentLog.execution_id == execution_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    query = base.order_by(AgentLog.id)
    if after_id:
        query = query.where(AgentLog.id > after_id)
    logs = db.scalars(query.limit(limit)).all()
    return [AgentLogOut.model_validate(log) for log in logs], total


def pull_request_query():
    return select(PullRequest).options(selectinload(PullRequest.execution).selectinload(AgentExecution.task))

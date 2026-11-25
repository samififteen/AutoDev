"""Development task creation and dispatch to the agent."""

from __future__ import annotations

import math

from app.agent.orchestrator import get_orchestrator
from app.core.errors import ConflictError, NotFoundError, RateLimitError
from app.database.session import get_db
from app.models import DevelopmentTask, Repository
from app.schemas import ExecutionDetailOut, Paginated, TaskCreate, TaskOut
from app.services.execution_service import build_execution_detail, create_execution
from app.services.settings_service import load_runtime_config
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

router = APIRouter(tags=["tasks"])


def _task_query():
    return select(DevelopmentTask).options(selectinload(DevelopmentTask.repository))


@router.get("/tasks", response_model=Paginated[TaskOut])
def list_tasks(
    db: Session = Depends(get_db),
    repository_id: int | None = None,
    status: str | None = None,
    priority: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Paginated[TaskOut]:
    query = _task_query()
    if repository_id:
        query = query.where(DevelopmentTask.repository_id == repository_id)
    if status:
        query = query.where(DevelopmentTask.status == status)
    if priority:
        query = query.where(DevelopmentTask.priority == priority)
    if search:
        needle = f"%{search.strip()}%"
        query = query.where(
            or_(DevelopmentTask.title.ilike(needle), DevelopmentTask.description.ilike(needle))
        )
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = db.scalars(
        query.order_by(DevelopmentTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Paginated[TaskOut](
        items=[TaskOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> TaskOut:
    repository = db.get(Repository, payload.repository_id)
    if repository is None:
        raise NotFoundError(f"Repository {payload.repository_id} was not found")
    if not repository.connected:
        raise ConflictError("The repository is not connected")
    task = DevelopmentTask(
        repository_id=repository.id,
        github_issue_number=payload.github_issue_number,
        title=payload.title.strip(),
        description=payload.description.strip(),
        priority=payload.priority,
        labels_json=__import__("json").dumps(payload.labels),
        source="github_issue" if payload.github_issue_number else "custom",
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return TaskOut.model_validate(task)


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)) -> TaskOut:
    task = db.scalar(_task_query().where(DevelopmentTask.id == task_id))
    if task is None:
        raise NotFoundError(f"Task {task_id} was not found")
    return TaskOut.model_validate(task)


@router.post("/tasks/{task_id}/execute", response_model=ExecutionDetailOut, status_code=202)
async def execute_task(task_id: int, db: Session = Depends(get_db)) -> ExecutionDetailOut:
    task = db.get(DevelopmentTask, task_id)
    if task is None:
        raise NotFoundError(f"Task {task_id} was not found")
    if task.repository is None or not task.repository.connected:
        raise ConflictError("The task's repository is not connected")
    if task.status in {"queued", "running"}:
        raise ConflictError("This task already has an active execution")

    runtime = load_runtime_config()
    orchestrator = get_orchestrator()
    if not orchestrator.has_capacity(runtime.max_concurrent_tasks):
        raise RateLimitError(
            f"The agent is at its concurrency limit ({runtime.max_concurrent_tasks}). "
            "Wait for a running execution to finish or raise the limit in Settings."
        )
    execution = create_execution(db, task)
    started = await orchestrator.start(execution.id)
    if not started:
        execution.status = "failed"
        execution.error_message = "The agent concurrency limit was reached before the worker started"
        db.commit()
        raise RateLimitError("The agent could not start the execution (concurrency limit)")
    db.refresh(execution)
    return build_execution_detail(execution)

"""Execution inspection, live streaming, approvals and pull request creation."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from app.agent.execution_logger import bus
from app.agent.orchestrator import get_orchestrator
from app.agent.stages import build_timeline
from app.core.errors import ConflictError, NotFoundError, RateLimitError, ValidationFailure
from app.database.session import get_db, session_scope
from app.models import AgentExecution, AgentLog
from app.schemas import (
    CreatePullRequestRequest,
    DiffResponse,
    ExecutionDetailOut,
    ExecutionLogPage,
    ExecutionSummaryOut,
    Paginated,
    PullRequestDraft,
    PullRequestOut,
)
from app.services.execution_service import (
    build_diff,
    build_execution_detail,
    create_execution,
    get_execution_or_404,
    paginate_executions,
)
from app.services.settings_service import load_runtime_config
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

router = APIRouter(tags=["executions"])

TERMINAL = {"completed", "failed", "cancelled"}


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat() + ("Z" if value.tzinfo is None else "")


@router.get("/executions", response_model=Paginated[ExecutionSummaryOut])
def list_executions(
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
    repository_id: int | None = None,
    search: str | None = None,
    sort: str = Query(default="created_at", pattern="^(created_at|started_at|duration|status)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> Paginated[ExecutionSummaryOut]:
    return paginate_executions(
        db,
        page=page,
        page_size=page_size,
        status=status,
        repository_id=repository_id,
        search=search,
        sort=sort,
        order=order,
    )


@router.get("/executions/{execution_id}", response_model=ExecutionDetailOut)
def get_execution(execution_id: int, db: Session = Depends(get_db)) -> ExecutionDetailOut:
    return build_execution_detail(get_execution_or_404(db, execution_id))


@router.get("/executions/{execution_id}/logs", response_model=ExecutionLogPage)
def get_logs(
    execution_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(default=300, ge=1, le=1000),
    after_id: int | None = None,
) -> ExecutionLogPage:
    from app.schemas import AgentLogOut

    execution = db.get(AgentExecution, execution_id)
    if execution is None:
        raise NotFoundError(f"Execution {execution_id} was not found")
    base = select(AgentLog).where(AgentLog.execution_id == execution_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    query = base.order_by(AgentLog.id)
    if after_id:
        query = query.where(AgentLog.id > after_id)
    rows = db.scalars(query.limit(limit)).all()
    return ExecutionLogPage(items=[AgentLogOut.model_validate(row) for row in rows], total=total)


@router.get("/executions/{execution_id}/stream")
async def stream_execution(execution_id: int, request: Request) -> StreamingResponse:
    with session_scope() as db:
        execution = db.get(AgentExecution, execution_id)
        if execution is None:
            raise NotFoundError(f"Execution {execution_id} was not found")

    async def event_generator():
        queue = bus.subscribe(execution_id)
        try:
            with session_scope() as db:
                execution = db.get(AgentExecution, execution_id)
                status = execution.status if execution else "failed"
                stage = execution.current_stage if execution else "failed"
                rows = db.scalars(
                    select(AgentLog)
                    .where(AgentLog.execution_id == execution_id)
                    .order_by(AgentLog.id.desc())
                    .limit(300)
                ).all()
            for row in reversed(rows):
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "type": "log",
                            "id": row.id,
                            "level": row.level,
                            "stage": row.stage,
                            "message": row.message,
                            "created_at": _iso(row.created_at),
                        }
                    )
                    + "\n\n"
                )
            yield "data: " + json.dumps({"type": "state", "status": status, "stage": stage}) + "\n\n"
            if status in TERMINAL:
                yield "data: " + json.dumps({"type": "end", "status": status}) + "\n\n"
                return
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield "data: " + json.dumps(event, default=str) + "\n\n"
                if event.get("type") == "end":
                    break
        finally:
            bus.unsubscribe(execution_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/executions/{execution_id}/approve-plan", response_model=ExecutionDetailOut)
async def approve_plan(execution_id: int, db: Session = Depends(get_db)) -> ExecutionDetailOut:
    execution = get_execution_or_404(db, execution_id)
    if execution.status != "awaiting_approval" or execution.current_stage != "awaiting_plan_approval":
        raise ConflictError("This execution is not waiting for plan approval")
    approved = await get_orchestrator().approve_plan(execution_id)
    if not approved:
        raise ConflictError(
            "The agent worker is not active for this execution (it may have restarted). Retry the task."
        )
    execution.plan_approved = True
    db.commit()
    db.refresh(execution)
    return build_execution_detail(execution)


@router.post("/executions/{execution_id}/cancel", response_model=ExecutionDetailOut)
async def cancel_execution(execution_id: int, db: Session = Depends(get_db)) -> ExecutionDetailOut:
    execution = get_execution_or_404(db, execution_id)
    if execution.status not in {"queued", "running", "awaiting_approval"}:
        raise ConflictError("Only active executions can be cancelled")
    await get_orchestrator().cancel(execution_id)
    if execution.status == "queued":
        execution.status = "cancelled"
        execution.summary = "Cancelled by the user before the worker started."
        execution.completed_at = datetime.utcnow()
        if execution.task is not None:
            execution.task.status = "cancelled"
        db.commit()
    db.refresh(execution)
    return build_execution_detail(execution)


@router.post("/executions/{execution_id}/retry", response_model=ExecutionDetailOut, status_code=201)
async def retry_execution(execution_id: int, db: Session = Depends(get_db)) -> ExecutionDetailOut:
    execution = get_execution_or_404(db, execution_id)
    if execution.status not in TERMINAL:
        raise ConflictError("Only finished executions can be retried")
    task = execution.task
    if task is None or task.repository is None or not task.repository.connected:
        raise ConflictError("The original task or repository is no longer available")
    runtime = load_runtime_config()
    orchestrator = get_orchestrator()
    if not orchestrator.has_capacity(runtime.max_concurrent_tasks):
        raise RateLimitError(f"The agent is at its concurrency limit ({runtime.max_concurrent_tasks})")
    retried = create_execution(db, task)
    started = await orchestrator.start(retried.id)
    if not started:
        retried.status = "failed"
        retried.error_message = "The agent concurrency limit was reached before the worker started"
        db.commit()
        raise RateLimitError("The agent could not start the retry")
    db.refresh(retried)
    return build_execution_detail(retried)


@router.get("/executions/{execution_id}/diff", response_model=DiffResponse)
def get_diff(execution_id: int, db: Session = Depends(get_db)) -> DiffResponse:
    execution = get_execution_or_404(db, execution_id)
    return build_diff(db, execution)


@router.get(
    "/executions/{execution_id}/diff/patch",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/x-patch": {}}}},
)
def download_patch(execution_id: int, db: Session = Depends(get_db)) -> PlainTextResponse:
    execution = get_execution_or_404(db, execution_id)
    diff = build_diff(db, execution)
    if not diff.unified_diff:
        raise ConflictError("This execution has no code changes to download")
    return PlainTextResponse(
        diff.unified_diff,
        media_type="text/x-patch",
        headers={"Content-Disposition": f'attachment; filename="autodev-execution-{execution_id}.patch"'},
    )


@router.get("/executions/{execution_id}/timeline")
def get_timeline(execution_id: int, db: Session = Depends(get_db)) -> dict:
    execution = get_execution_or_404(db, execution_id)
    return {
        "execution_id": execution.id,
        "status": execution.status,
        "current_stage": execution.current_stage,
        "timeline": build_timeline(execution.current_stage, execution.status),
    }


@router.get("/executions/{execution_id}/pr-draft", response_model=PullRequestDraft)
async def pull_request_draft(execution_id: int) -> PullRequestDraft:
    try:
        return await get_orchestrator().build_pull_request_draft(execution_id)
    except ConflictError:
        raise


@router.post("/executions/{execution_id}/create-pr", response_model=PullRequestOut, status_code=201)
async def create_pull_request(
    execution_id: int,
    payload: CreatePullRequestRequest,
    db: Session = Depends(get_db),
) -> PullRequestOut:
    execution = get_execution_or_404(db, execution_id)
    runtime = load_runtime_config()
    if runtime.require_pr_approval and not payload.confirm:
        raise ValidationFailure(
            "Pull request creation requires explicit confirmation (require_pr_approval is enabled)"
        )
    if execution.pull_request is not None:
        raise ConflictError(
            f"A pull request already exists for this execution (#{execution.pull_request.number})"
        )
    return await get_orchestrator().create_pull_request(
        execution_id,
        title=payload.title,
        body=payload.body,
        base_branch=payload.base_branch,
    )

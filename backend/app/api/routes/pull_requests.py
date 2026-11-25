"""Pull request records stored by AutoDev."""

from __future__ import annotations

import math

from app.core.errors import NotFoundError
from app.database.session import get_db
from app.models import AgentExecution, PullRequest
from app.schemas import Paginated, PullRequestListItem
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

router = APIRouter(tags=["pull-requests"])


def _item(pull: PullRequest) -> PullRequestListItem:
    execution = pull.execution
    task = execution.task if execution else None
    repository = task.repository if task and task.repository else None
    return PullRequestListItem(
        id=pull.id,
        execution_id=pull.execution_id,
        number=pull.number,
        title=pull.title,
        body=pull.body,
        url=pull.url,
        branch=pull.branch,
        base_branch=pull.base_branch,
        status=pull.status,
        created_at=pull.created_at,
        task_title=task.title if task else "(deleted task)",
        repository=repository.full_name if repository else "—",
        execution_status=execution.status if execution else "unknown",
    )


@router.get("/pull-requests", response_model=Paginated[PullRequestListItem])
def list_pull_requests(
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    status: str | None = None,
) -> Paginated[PullRequestListItem]:
    query = select(PullRequest).options(selectinload(PullRequest.execution).selectinload(AgentExecution.task))
    if search:
        query = query.where(PullRequest.title.ilike(f"%{search.strip()}%"))
    if status:
        query = query.where(PullRequest.status == status)
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = db.scalars(
        query.order_by(PullRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Paginated[PullRequestListItem](
        items=[_item(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/pull-requests/{pull_request_id}", response_model=PullRequestListItem)
def get_pull_request(pull_request_id: int, db: Session = Depends(get_db)) -> PullRequestListItem:
    pull = db.scalar(
        select(PullRequest)
        .options(selectinload(PullRequest.execution).selectinload(AgentExecution.task))
        .where(PullRequest.id == pull_request_id)
    )
    if pull is None:
        raise NotFoundError(f"Pull request {pull_request_id} was not found")
    return _item(pull)

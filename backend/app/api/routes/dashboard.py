"""Dashboard statistics computed from persisted records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.database.session import get_db
from app.models import AgentExecution, DevelopmentTask, PullRequest, Repository
from app.schemas import ChartPoint, DashboardStats, RecentActivity
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

router = APIRouter(tags=["dashboard"])


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)) -> DashboardStats:
    repositories = (
        db.scalar(select(func.count()).select_from(Repository).where(Repository.connected.is_(True))) or 0
    )
    tasks_total = db.scalar(select(func.count()).select_from(DevelopmentTask)) or 0
    processed = db.scalar(select(func.count()).select_from(AgentExecution)) or 0
    completed = (
        db.scalar(
            select(func.count()).select_from(AgentExecution).where(AgentExecution.status == "completed")
        )
        or 0
    )
    failed = (
        db.scalar(select(func.count()).select_from(AgentExecution).where(AgentExecution.status == "failed"))
        or 0
    )
    pull_requests = db.scalar(select(func.count()).select_from(PullRequest)) or 0
    average = db.scalar(
        select(func.avg(AgentExecution.duration_seconds)).where(AgentExecution.duration_seconds.is_not(None))
    )
    active = (
        db.scalar(
            select(func.count())
            .select_from(AgentExecution)
            .where(AgentExecution.status.in_(["queued", "running", "awaiting_approval"]))
        )
        or 0
    )

    recent_rows = db.scalars(
        select(AgentExecution)
        .options(
            selectinload(AgentExecution.task).selectinload(DevelopmentTask.repository),
            selectinload(AgentExecution.pull_request),
        )
        .order_by(AgentExecution.created_at.desc())
        .limit(8)
    ).all()
    recent = [
        RecentActivity(
            execution_id=row.id,
            task_id=row.task_id,
            task_title=row.task.title if row.task else "(deleted task)",
            repository=row.task.repository.full_name if row.task and row.task.repository else "—",
            status=row.status,
            started_at=row.started_at or row.created_at,
            duration_seconds=row.duration_seconds,
            pull_request_url=row.pull_request.url if row.pull_request else None,
        )
        for row in recent_rows
    ]

    today = _utcnow().date()
    start_date = today - timedelta(days=13)
    buckets: dict[str, ChartPoint] = {}
    for offset in range(14):
        day = (start_date + timedelta(days=offset)).isoformat()
        buckets[day] = ChartPoint(date=day, completed=0, failed=0, pull_requests=0)

    executions = db.scalars(
        select(AgentExecution).where(
            AgentExecution.created_at >= datetime.combine(start_date, datetime.min.time())
        )
    ).all()
    for execution in executions:
        if execution.created_at is None:
            continue
        key = execution.created_at.date().isoformat()
        if key not in buckets:
            continue
        if execution.status == "completed":
            buckets[key].completed += 1
        elif execution.status == "failed":
            buckets[key].failed += 1

    pull_rows = db.scalars(
        select(PullRequest).where(PullRequest.created_at >= datetime.combine(start_date, datetime.min.time()))
    ).all()
    for pull in pull_rows:
        key = pull.created_at.date().isoformat()
        if key in buckets:
            buckets[key].pull_requests += 1

    return DashboardStats(
        repositories_connected=repositories,
        tasks_total=tasks_total,
        tasks_processed=processed,
        tasks_completed=completed,
        tasks_failed=failed,
        pull_requests_created=pull_requests,
        average_duration_seconds=round(float(average), 2) if average is not None else None,
        active_executions=active,
        recent_activity=recent,
        chart=list(buckets.values()),
    )

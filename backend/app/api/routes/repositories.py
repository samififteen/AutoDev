"""Repository connection, listing, analysis and issue retrieval."""

from __future__ import annotations

import math
from datetime import datetime

from app.api.deps import get_github, github_api_error
from app.core.errors import ConfigurationError, NotFoundError
from app.database.base import utcnow
from app.database.session import get_db
from app.integrations.github.service import GitHubIntegrationError, GitHubService
from app.models import Repository
from app.schemas import (
    AnalyzeRepositoryResponse,
    Paginated,
    RepositoryConnectRequest,
    RepositoryIssue,
    RepositoryOut,
)
from app.services import demo_fixtures
from app.services.repository_service import (
    analyze_repository,
    find_repository,
    refresh_repository_metadata,
)
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

router = APIRouter(tags=["repositories"])


@router.get("/repositories", response_model=Paginated[RepositoryOut])
def list_repositories(
    db: Session = Depends(get_db),
    search: str | None = None,
    visibility: str | None = Query(default=None, pattern="^(public|private)$"),
    language: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Paginated[RepositoryOut]:
    query = select(Repository).where(Repository.connected.is_(True))
    if search:
        needle = f"%{search.strip()}%"
        query = query.where(
            or_(
                Repository.name.ilike(needle),
                Repository.owner.ilike(needle),
                Repository.description.ilike(needle),
            )
        )
    if visibility:
        query = query.where(Repository.visibility == visibility)
    if language:
        query = query.where(Repository.language == language)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Repository.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Paginated[RepositoryOut](
        items=[RepositoryOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.post("/repositories/connect", response_model=RepositoryOut, status_code=201)
def connect_repository(
    payload: RepositoryConnectRequest,
    db: Session = Depends(get_db),
    github: GitHubService = Depends(get_github),
) -> RepositoryOut:
    if not github.configured:
        raise ConfigurationError(
            "GitHub is not configured. Add GITHUB_TOKEN (repo scope or fine-grained equivalent) "
            "to the backend environment and restart, or use the bundled demo repository."
        )
    owner, name = payload.full_name.split("/", 1)
    try:
        metadata = github.get_repository(payload.full_name)
    except GitHubIntegrationError as exc:
        raise github_api_error(exc) from exc

    repository = find_repository(db, metadata["owner"], metadata["name"])
    if repository is None and metadata.get("github_id"):
        repository = db.scalar(select(Repository).where(Repository.github_id == metadata["github_id"]))
    if repository is None:
        repository = Repository(
            github_id=metadata.get("github_id"),
            owner=metadata["owner"],
            name=metadata["name"],
            default_branch=payload.default_branch or metadata.get("default_branch") or "main",
            clone_url=metadata.get("clone_url"),
            html_url=metadata.get("html_url"),
            description=metadata.get("description"),
            language=metadata.get("language"),
            visibility=metadata.get("visibility") or "private",
            connected=True,
        )
        db.add(repository)
    else:
        repository.github_id = metadata.get("github_id") or repository.github_id
        repository.description = metadata.get("description")
        repository.default_branch = (
            payload.default_branch or metadata.get("default_branch") or repository.default_branch
        )
        repository.language = metadata.get("language")
        repository.visibility = metadata.get("visibility") or repository.visibility
        repository.clone_url = metadata.get("clone_url") or repository.clone_url
        repository.html_url = metadata.get("html_url") or repository.html_url
        repository.connected = True
        repository.updated_at = utcnow()
    db.commit()
    db.refresh(repository)
    return RepositoryOut.model_validate(repository)


@router.get("/repositories/{repository_id}", response_model=RepositoryOut)
def get_repository(repository_id: int, db: Session = Depends(get_db)) -> RepositoryOut:
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise NotFoundError(f"Repository {repository_id} was not found")
    return RepositoryOut.model_validate(repository)


@router.post("/repositories/{repository_id}/analyze", response_model=AnalyzeRepositoryResponse)
def analyze(
    repository_id: int,
    db: Session = Depends(get_db),
    github: GitHubService = Depends(get_github),
) -> AnalyzeRepositoryResponse:
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise NotFoundError(f"Repository {repository_id} was not found")
    summary = analyze_repository(db, repository, github)
    return AnalyzeRepositoryResponse(repository=RepositoryOut.model_validate(repository), summary=summary)


@router.post("/repositories/{repository_id}/refresh", response_model=RepositoryOut)
def refresh(
    repository_id: int,
    db: Session = Depends(get_db),
    github: GitHubService = Depends(get_github),
) -> RepositoryOut:
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise NotFoundError(f"Repository {repository_id} was not found")
    repository = refresh_repository_metadata(db, repository, github)
    return RepositoryOut.model_validate(repository)


@router.get("/repositories/{repository_id}/issues", response_model=list[RepositoryIssue])
def list_issues(
    repository_id: int,
    db: Session = Depends(get_db),
    github: GitHubService = Depends(get_github),
    state: str = Query(default="open", pattern="^(open|closed|all)$"),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[RepositoryIssue]:
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise NotFoundError(f"Repository {repository_id} was not found")
    if repository.is_demo:
        created = repository.created_at or utcnow()
        return [
            RepositoryIssue(
                number=issue["number"],
                title=issue["title"],
                body=issue["body"],
                labels=issue["labels"],
                assignees=issue["assignees"],
                state=issue["state"],
                created_at=created,
                html_url=None,
                demo=True,
            )
            for issue in demo_fixtures.DEMO_ISSUES
        ]
    if not github.configured:
        raise ConfigurationError(
            "GitHub is not configured; real issues cannot be listed. Configure GITHUB_TOKEN."
        )
    try:
        issues = github.list_issues(repository.full_name, limit=limit, state=state)
    except GitHubIntegrationError as exc:
        raise github_api_error(exc) from exc
    result: list[RepositoryIssue] = []
    for issue in issues:
        created_at = None
        if issue.get("created_at"):
            try:
                created_at = datetime.fromisoformat(issue["created_at"])
            except ValueError:
                created_at = None
        result.append(
            RepositoryIssue(
                number=issue["number"],
                title=issue["title"],
                body=issue.get("body") or "",
                labels=issue.get("labels") or [],
                assignees=issue.get("assignees") or [],
                state=issue.get("state") or "open",
                created_at=created_at,
                html_url=issue.get("html_url"),
                demo=False,
            )
        )
    return result

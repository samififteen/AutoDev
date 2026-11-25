"""Repository metadata refresh and analysis orchestration."""

from __future__ import annotations

from app.agent.git_manager import GitError, GitManager
from app.agent.repository_analyzer import RepositoryAnalyzer
from app.core.config import get_settings
from app.core.errors import AppError, ConfigurationError
from app.core.files import remove_tree
from app.core.logging import get_logger
from app.database.base import utcnow
from app.integrations.github.service import GitHubIntegrationError, GitHubService
from app.models import Repository
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = get_logger(__name__)


def analyze_repository(db: Session, repository: Repository, github: GitHubService) -> dict:
    if not repository.clone_url:
        raise ConfigurationError("This repository has no clone URL; reconnect it first")
    settings = get_settings()
    workspace = settings.workspaces_path / f"analysis-{repository.id}"
    token = None
    if not repository.is_demo:
        if not github.configured:
            raise ConfigurationError(
                "GitHub credentials are required to clone and analyze a GitHub repository"
            )
        try:
            token = github.get_auth_token()
        except GitHubIntegrationError as exc:
            raise ConfigurationError(str(exc)) from exc
    remove_tree(workspace)
    try:
        GitManager.clone(repository.clone_url, workspace, token=token)
        index = RepositoryAnalyzer().index(workspace)
        summary = index.to_summary()
    except GitError as exc:
        raise AppError(f"Repository analysis failed: {exc}", code="analysis_failed", status_code=502) from exc
    finally:
        remove_tree(workspace)

    import json

    repository.analysis_json = json.dumps(summary)
    repository.analyzed_at = utcnow()
    if summary.get("primary_language"):
        repository.language = summary["primary_language"]
    db.commit()
    db.refresh(repository)
    logger.info("Analyzed repository %s (%s files)", repository.full_name, summary.get("file_count"))
    return summary


def refresh_repository_metadata(db: Session, repository: Repository, github: GitHubService) -> Repository:
    if repository.is_demo:
        repository.updated_at = utcnow()
        db.commit()
        db.refresh(repository)
        return repository
    if not github.configured:
        raise ConfigurationError("GitHub is not configured; add GITHUB_TOKEN to refresh repository metadata")
    try:
        metadata = github.get_repository(repository.full_name)
    except GitHubIntegrationError as exc:
        raise AppError(str(exc), code="github_error", status_code=502) from exc
    repository.description = metadata.get("description")
    repository.default_branch = metadata.get("default_branch") or repository.default_branch
    repository.language = metadata.get("language")
    repository.visibility = metadata.get("visibility") or repository.visibility
    repository.clone_url = metadata.get("clone_url") or repository.clone_url
    repository.html_url = metadata.get("html_url") or repository.html_url
    repository.github_id = metadata.get("github_id") or repository.github_id
    repository.updated_at = utcnow()
    db.commit()
    db.refresh(repository)
    return repository


def find_repository(db: Session, owner: str, name: str) -> Repository | None:
    return db.scalar(select(Repository).where(Repository.owner == owner, Repository.name == name))

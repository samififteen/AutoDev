"""Creates the real demo git repository and seeds demo records."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.core.config import get_settings
from app.core.files import remove_tree
from app.core.logging import get_logger
from app.models import AgentExecution, DevelopmentTask, Repository
from app.services import demo_fixtures
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = get_logger(__name__)

DEMO_GIT_ENV = {
    "GIT_AUTHOR_NAME": "AutoDev",
    "GIT_AUTHOR_EMAIL": "autodev@localhost",
    "GIT_COMMITTER_NAME": "AutoDev",
    "GIT_COMMITTER_EMAIL": "autodev@localhost",
}


def ensure_demo_source_repo() -> Path:
    """Materialise the bundled demo project as a real git repository once."""
    settings = get_settings()
    template = settings.demo_repo_path
    target = settings.workspaces_path / "_demo_source"
    if (target / ".git").is_dir():
        return target
    if not template.is_dir():
        raise FileNotFoundError(f"Demo repository template is missing at {template}")
    remove_tree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        template,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"),
    )
    env = {**__import__("os").environ, **DEMO_GIT_ENV}
    commands = [
        ["git", "init", "-b", "main"],
        ["git", "add", "-A"],
        ["git", "commit", "-m", "Initial commit: calculator package with demo bug"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=target, capture_output=True, text=True, env=env, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"Could not initialise demo repository ({' '.join(command)}): "
                f"{result.stderr.strip()[:500]}"
            )
    logger.info("Demo repository initialised at %s", target)
    return target


def seed_demo_data(db: Session) -> Repository | None:
    settings = get_settings()
    if not settings.demo_mode:
        return None
    try:
        source = ensure_demo_source_repo()
    except (OSError, RuntimeError) as exc:
        logger.warning("Demo repository could not be prepared: %s", exc)
        return None

    repository = db.scalar(
        select(Repository).where(
            Repository.is_demo.is_(True),
            Repository.owner == demo_fixtures.DEMO_OWNER,
            Repository.name == demo_fixtures.DEMO_REPO_NAME,
        )
    )
    if repository is None:
        repository = Repository(
            owner=demo_fixtures.DEMO_OWNER,
            name=demo_fixtures.DEMO_REPO_NAME,
            description=demo_fixtures.DEMO_DESCRIPTION,
            default_branch="main",
            language="Python",
            visibility="private",
            clone_url=str(source),
            html_url=None,
            is_demo=True,
            connected=True,
        )
        db.add(repository)
        db.flush()
    else:
        repository.clone_url = str(source)
        repository.connected = True

    for fixture in demo_fixtures.DEMO_TASKS:
        exists = db.scalar(
            select(DevelopmentTask).where(
                DevelopmentTask.repository_id == repository.id,
                DevelopmentTask.title == fixture["title"],
            )
        )
        if exists is None:
            db.add(
                DevelopmentTask(
                    repository_id=repository.id,
                    title=fixture["title"],
                    description=fixture["description"],
                    priority=fixture["priority"],
                    github_issue_number=fixture["github_issue_number"],
                    labels_json=json.dumps(fixture["labels"]),
                    source=fixture["source"],
                    status="pending",
                )
            )
    db.commit()
    return repository


def mark_interrupted_executions(db: Session) -> int:
    """Preserve logs but close executions left running by a server restart."""
    stale = db.scalars(
        select(AgentExecution).where(AgentExecution.status.in_(["queued", "running", "awaiting_approval"]))
    ).all()
    for execution in stale:
        execution.status = "failed"
        execution.error_message = "Execution interrupted by backend restart"
        execution.summary = "The backend restarted while this execution was running."
        execution.completed_at = execution.created_at
        if execution.task is not None:
            execution.task.status = "failed"
    if stale:
        db.commit()
        logger.warning("Marked %s interrupted execution(s) as failed", len(stale))
    return len(stale)

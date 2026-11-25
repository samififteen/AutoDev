from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

SECRET_ENV_KEYS = (
    "GITHUB_TOKEN",
    "AUTODEV_GITHUB_TOKEN",
    "GITHUB_APP_ID",
    "GITHUB_APP_PRIVATE_KEY",
    "GITHUB_APP_INSTALLATION_ID",
    "AI_API_KEY",
    "OPENAI_API_KEY",
    "AUTODEV_API_TOKEN",
)


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    from app.agent.orchestrator import reset_orchestrator
    from app.core.config import get_settings
    from app.database.session import reset_database_engine

    for key in SECRET_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path / "workspaces"))
    monkeypatch.setenv("DEMO_REPO_DIR", str(BACKEND_ROOT / "demo_repo"))
    monkeypatch.setenv("AI_PROVIDER", "demo")
    monkeypatch.setenv("AI_API_KEY", "")
    monkeypatch.setenv("SANDBOX_MODE", "local")
    monkeypatch.setenv("REQUIRE_PLAN_APPROVAL", "false")
    monkeypatch.setenv("REQUIRE_PR_APPROVAL", "true")
    monkeypatch.setenv("AGENT_MAX_CORRECTION_ATTEMPTS", "2")
    monkeypatch.setenv("AGENT_TEST_TIMEOUT", "120")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    get_settings.cache_clear()
    reset_database_engine()
    reset_orchestrator()
    yield
    reset_database_engine()
    reset_orchestrator()
    get_settings.cache_clear()


@pytest.fixture
def client(app_env):
    from app.main import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def demo_task(app_env):
    from app.database.session import create_schema, session_scope
    from app.models import DevelopmentTask, Repository
    from app.services.demo_seed import seed_demo_data
    from sqlalchemy import select

    create_schema()
    with session_scope() as db:
        seed_demo_data(db)
    with session_scope() as db:
        repository = db.scalar(select(Repository).where(Repository.is_demo.is_(True)))
        assert repository is not None
        task = db.scalar(
            select(DevelopmentTask).where(
                DevelopmentTask.repository_id == repository.id,
                DevelopmentTask.title.ilike("%multiplication%"),
            )
        )
        assert task is not None
        return {
            "repository_id": repository.id,
            "task_id": task.id,
            "task_title": task.title,
        }

"""Shared FastAPI dependencies (overridable in tests)."""

from __future__ import annotations

from app.agent.orchestrator import AgentOrchestrator, get_orchestrator
from app.core.errors import AppError
from app.integrations.github.service import GitHubService, get_github_service


def get_github() -> GitHubService:
    return get_github_service()


def get_agent_orchestrator() -> AgentOrchestrator:
    return get_orchestrator()


def github_api_error(exc: Exception) -> AppError:
    return AppError(str(exc), code="github_error", status_code=502)

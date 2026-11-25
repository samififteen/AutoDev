"""Health and system observability endpoints."""

from __future__ import annotations

import httpx
from app.agent.orchestrator import get_orchestrator
from app.core.config import get_settings
from app.database.session import get_db
from app.integrations.github.service import GitHubService, get_github_service
from app.schemas import ComponentStatus, HealthOut, SystemInfo, SystemStatus
from app.services.settings_service import get_runtime_config
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter(tags=["health"])
system_router = APIRouter(tags=["system"])
VERSION = "0.1.0"


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database_ok = True
    except Exception:
        database_ok = False
    return HealthOut(
        status="ok" if database_ok else "degraded",
        version=VERSION,
        database=database_ok,
        demo_mode=settings.demo_mode,
        ai_provider=settings.effective_ai_provider,
        github_configured=settings.github_configured,
    )


@system_router.get("/system/info", response_model=SystemInfo)
def system_info(db: Session = Depends(get_db)) -> SystemInfo:
    settings = get_settings()
    runtime = get_runtime_config(db)
    return SystemInfo(
        app_name=settings.app_name,
        version=VERSION,
        environment=settings.environment,
        demo_mode=settings.demo_mode,
        ai_provider=settings.effective_ai_provider,
        ai_model="deterministic-fixture" if settings.demo_mode else settings.ai_model,
        github_configured=settings.github_configured,
        auth_enabled=bool(settings.api_token),
        sandbox_mode=runtime.sandbox_mode,
        limits={
            "max_correction_attempts": runtime.max_correction_attempts,
            "execution_timeout_seconds": runtime.execution_timeout_seconds,
            "max_files_modified": runtime.max_files_modified,
            "max_concurrent_tasks": runtime.max_concurrent_tasks,
            "test_timeout_seconds": runtime.test_timeout_seconds,
            "ai_max_context_chars": runtime.ai_max_context_chars,
        },
    )


@system_router.get("/system/status", response_model=SystemStatus)
def system_status(db: Session = Depends(get_db)) -> SystemStatus:
    settings = get_settings()
    runtime = get_runtime_config(db)

    backend = ComponentStatus(name="Backend", status="ok", detail=f"AutoDev {VERSION} running")
    try:
        db.execute(text("SELECT 1"))
        database = ComponentStatus(name="Database", status="ok", detail="SQLite reachable")
    except Exception as exc:
        database = ComponentStatus(
            name="Database", status="error", detail=f"Database error: {type(exc).__name__}"
        )

    github_service: GitHubService = get_github_service()
    if not github_service.configured:
        github = ComponentStatus(
            name="GitHub",
            status="disabled",
            detail="Not configured — connect a PAT or GitHub App to use real repositories",
        )
    else:
        verification = github_service.verify()
        github = ComponentStatus(
            name="GitHub",
            status="ok" if verification.get("authenticated") else "error",
            detail=(
                f"Verified as {verification.get('login')} ({github_service.auth_mode})"
                if verification.get("authenticated")
                else f"Configured but verification failed: {verification.get('error') or 'unknown'}"
            ),
        )

    if settings.demo_mode:
        ai = ComponentStatus(
            name="AI provider",
            status="disabled",
            detail="Demo fixture provider (no AI_API_KEY). Deterministic fixtures only.",
        )
    else:
        ai = ComponentStatus(
            name="AI provider",
            status="configured",
            detail=f"{settings.effective_ai_provider} · {settings.ai_model} (not pinged)",
        )

    if runtime.sandbox_mode == "docker":
        try:
            with httpx.Client(timeout=3) as client:
                response = client.get(f"{settings.sandbox_url.rstrip('/')}/health")
            sandbox = ComponentStatus(
                name="Sandbox",
                status="ok" if response.status_code < 400 else "error",
                detail=f"Docker worker at {settings.sandbox_url} (HTTP {response.status_code})",
            )
        except httpx.HTTPError as exc:
            sandbox = ComponentStatus(
                name="Sandbox",
                status="error",
                detail=f"Worker unreachable: {type(exc).__name__}",
            )
    else:
        sandbox = ComponentStatus(
            name="Sandbox",
            status="ok",
            detail="Local sandbox: allowlist, scrubbed env, timeout and resource limits. "
            "Docker mode provides stronger isolation.",
        )

    orchestrator = get_orchestrator()
    worker = ComponentStatus(
        name="Agent worker",
        status="ok",
        detail=f"In-process worker running · {orchestrator.active_count()} active execution(s) "
        f"· limit {runtime.max_concurrent_tasks}",
    )
    return SystemStatus(
        backend=backend,
        database=database,
        github=github,
        ai_provider=ai,
        sandbox=sandbox,
        agent_worker=worker,
    )

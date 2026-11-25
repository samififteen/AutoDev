"""AutoDev FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from app.api.routes import (
    dashboard,
    executions,
    health,
    pull_requests,
    repositories,
    tasks,
)
from app.api.routes import (
    settings as settings_routes,
)
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler, unhandled_error_handler
from app.core.logging import configure_logging, get_logger
from app.core.security import require_api_token
from app.database.session import create_schema, session_scope
from app.services.demo_seed import mark_interrupted_executions, seed_demo_data
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logger = get_logger(__name__)

VERSION = "0.1.0"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.debug)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        create_schema()
        with session_scope() as db:
            seed_demo_data(db)
            mark_interrupted_executions(db)
        logger.info(
            "AutoDev started (%s mode, sandbox=%s, github=%s)",
            "demo" if settings.demo_mode else "live",
            settings.sandbox_mode,
            "configured" if settings.github_configured else "not configured",
        )
        yield
        with session_scope() as db:
            mark_interrupted_executions(db)

    app = FastAPI(
        title="AutoDev API",
        version=VERSION,
        description=(
            "Autonomous AI coding agent: repository analysis, implementation planning, "
            "sandboxed edits, test execution and human-approved pull requests."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    protected = [Depends(require_api_token)]
    app.include_router(health.router, prefix="/api")
    app.include_router(health.system_router, prefix="/api", dependencies=protected)
    app.include_router(dashboard.router, prefix="/api", dependencies=protected)
    app.include_router(repositories.router, prefix="/api", dependencies=protected)
    app.include_router(tasks.router, prefix="/api", dependencies=protected)
    app.include_router(executions.router, prefix="/api", dependencies=protected)
    app.include_router(pull_requests.router, prefix="/api", dependencies=protected)
    app.include_router(settings_routes.router, prefix="/api/settings", dependencies=protected)

    _mount_frontend(app, settings.frontend_dist_path)

    @app.get("/api", include_in_schema=False)
    def api_index() -> JSONResponse:
        return JSONResponse(
            {
                "name": "AutoDev API",
                "version": VERSION,
                "docs": "/docs",
                "health": "/api/health",
            }
        )

    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    if not index.is_file():
        return
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path.startswith("api/") or full_path in {"docs", "redoc", "openapi.json"}:
            return JSONResponse({"error": {"code": "not_found", "message": "Not found"}}, status_code=404)
        candidate = (dist / full_path).resolve()
        try:
            candidate.relative_to(dist.resolve())
        except ValueError:
            candidate = index
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()

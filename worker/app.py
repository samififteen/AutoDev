"""AutoDev sandbox worker.

Runs allowlisted test commands inside a disposable container that shares only the
workspace volume with the backend. This service is internal-only and must never be
published to the host or the internet.
"""

from __future__ import annotations

import hmac
import os
import re
import signal
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

MAX_OUTPUT_CHARS = 200_000
TOKEN = os.environ.get("SANDBOX_TOKEN", "").strip()
WORKSPACES_ROOT = Path(os.environ.get("WORKSPACES_ROOT", "/workspaces")).resolve()
ALLOWED_PROGRAMS = {
    Path(part.strip()).name.lower().removesuffix(".exe")
    for part in os.environ.get(
        "ALLOWED_COMMANDS", "python,python3,pytest,npm,node,yarn,pnpm,ruff,tsc,go,cargo"
    ).split(",")
    if part.strip()
}
PROTECTED_ENV = re.compile(
    r"(?i)(token|secret|password|credential|api[_-]?key|private[_-]?key|^github_|^openai_|"
    r"^ai_|^autodev_|^database_url$)"
)

app = FastAPI(title="AutoDev Sandbox Worker", version="0.1.0", docs_url=None, redoc_url=None)


class ExecuteRequest(BaseModel):
    args: list[str] = Field(min_length=1, max_length=64)
    cwd: str = Field(min_length=1, max_length=500)
    timeout: int = Field(default=180, ge=1, le=1800)


def _authorized(provided: str | None) -> bool:
    if not TOKEN:
        # Fail closed: an unconfigured worker refuses every command.
        return False
    return bool(provided) and hmac.compare_digest(provided, TOKEN)


def _safe_environment() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not PROTECTED_ENV.search(key)}
    env.update(
        {
            "HOME": "/tmp",
            "TMPDIR": "/tmp",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "CI": "true",
            "NO_COLOR": "1",
            "TERM": "dumb",
            "NPM_CONFIG_UPDATE_NOTIFIER": "false",
            "PATH": env.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        }
    )
    return env


def _validate_command(args: list[str]) -> list[str]:
    cleaned = [str(argument) for argument in args]
    for argument in cleaned:
        if "\x00" in argument or "\n" in argument or "\r" in argument:
            raise HTTPException(status_code=400, detail="Command arguments contain control characters")
        if len(argument) > 2000:
            raise HTTPException(status_code=400, detail="Command argument is too long")
    program = cleaned[0]
    if "/" in program or "\\" in program:
        raise HTTPException(status_code=400, detail="Command must name a bare executable")
    normalized = Path(program).name.lower().removesuffix(".exe")
    if normalized not in ALLOWED_PROGRAMS:
        raise HTTPException(
            status_code=400,
            detail=f"Program '{program}' is not in the sandbox allowlist",
        )
    return cleaned


def _resolve_workspace(cwd: str) -> Path:
    candidate = (WORKSPACES_ROOT / cwd).resolve()
    try:
        candidate.relative_to(WORKSPACES_ROOT)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Workspace path escapes the shared volume") from exc
    if not candidate.is_dir():
        raise HTTPException(status_code=404, detail="Workspace directory does not exist")
    return candidate


def _cap(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    head = text[:40_000]
    tail = text[-(MAX_OUTPUT_CHARS - 40_000) :]
    return f"{head}\n... [sandbox output truncated] ...\n{tail}"


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok" if WORKSPACES_ROOT.is_dir() else "degraded",
        "workspace_ready": WORKSPACES_ROOT.is_dir(),
        "token_configured": bool(TOKEN),
    }


@app.post("/execute")
def execute(payload: ExecuteRequest, x_sandbox_token: str | None = Header(default=None)) -> dict[str, object]:
    if not _authorized(x_sandbox_token):
        raise HTTPException(status_code=401, detail="Invalid sandbox token")
    args = _validate_command(payload.args)
    cwd = _resolve_workspace(payload.cwd)
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            args,
            cwd=cwd,
            env=_safe_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        )
    except OSError as exc:
        return {
            "status": "error",
            "exit_code": None,
            "output": f"Could not start command: {type(exc).__name__}",
            "duration_seconds": round(time.monotonic() - started, 3),
        }

    timed_out = False
    try:
        output, _ = process.communicate(timeout=payload.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except OSError:
            process.kill()
        try:
            output, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            output = ""
        output = (output or "") + f"\n[worker] Command exceeded the {payload.timeout}s timeout."

    duration = round(time.monotonic() - started, 3)
    exit_code = process.returncode
    status = "timeout" if timed_out else ("passed" if exit_code == 0 else "failed")
    return {
        "status": status,
        "exit_code": exit_code,
        "output": _cap(output or ""),
        "duration_seconds": duration,
    }

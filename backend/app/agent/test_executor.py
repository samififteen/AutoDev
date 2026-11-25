"""Allowlisted command execution inside a local or Docker sandbox."""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from app.agent.repository_analyzer import RepositoryIndex
from app.core.config import get_settings
from app.core.errors import UnsafeOperationError
from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_OUTPUT_CHARS = 200_000
SHELL_METACHARACTERS = re.compile(r"[;&|<>`\n\r]|\$\(")
PROTECTED_ENV = re.compile(
    r"(?i)(token|secret|password|credential|api[_-]?key|private[_-]?key|^github_|^openai_|"
    r"^anthropic_|^ai_|^autodev_|^database_url$)"
)


@dataclass(slots=True)
class CommandResult:
    command: str
    status: str = "passed"
    exit_code: int | None = None
    output: str = ""
    duration_seconds: float = 0.0
    passed_count: int = 0
    failed_count: int = 0
    failing_tests: list[str] | None = None


@dataclass(slots=True)
class TestSuiteResult:
    results: list[CommandResult]
    passed: bool
    passed_count: int
    failed_count: int
    failing_tests: list[str]
    summary: str
    output: str


def cap_output(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    head = text[:40_000]
    tail = text[-(MAX_OUTPUT_CHARS - 40_000) :]
    return f"{head}\n... [AutoDev truncated {len(text) - MAX_OUTPUT_CHARS} characters] ...\n{tail}"


def parse_test_output(output: str) -> tuple[int, int, list[str]]:
    passed = sum(int(match.group(1)) for match in re.finditer(r"(\d+)\s+passed\b", output))
    failed = sum(int(match.group(1)) for match in re.finditer(r"(\d+)\s+failed\b", output))
    failing: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("FAILED "):
            name = stripped[len("FAILED ") :].split(" - ")[0].strip()
            if name:
                failing.append(name)
        elif stripped.startswith("✕ ") or stripped.startswith("× "):
            failing.append(stripped[2:].strip())
        elif stripped.startswith("● ") and "›" in stripped:
            failing.append(stripped[2:].strip())
    return passed, failed, list(dict.fromkeys(failing))[:25]


def summarize_results(results: list[CommandResult], *, attempt: int = 1) -> TestSuiteResult:
    output = "\n\n".join(f"$ {result.command}\n{result.output}".rstrip() for result in results)
    passed = all(result.status == "passed" for result in results) if results else False
    passed_count = sum(result.passed_count for result in results)
    failed_count = sum(result.failed_count for result in results)
    failing: list[str] = []
    for result in results:
        for test in result.failing_tests or []:
            if test not in failing:
                failing.append(test)
    if results:
        summary = "; ".join(
            f"{result.command}: {result.status}"
            + (
                f" ({result.passed_count} passed, {result.failed_count} failed)"
                if result.passed_count or result.failed_count
                else ""
            )
            for result in results
        )
    else:
        summary = "No test commands were executed."
    return TestSuiteResult(
        results=results,
        passed=passed,
        passed_count=passed_count,
        failed_count=failed_count,
        failing_tests=failing,
        summary=summary,
        output=cap_output(output),
    )


DANGEROUS_PROGRAMS = {
    "bash",
    "sh",
    "zsh",
    "fish",
    "cmd",
    "powershell",
    "pwsh",
    "cscript",
    "wscript",
    "osascript",
}

INLINE_EVAL_FLAGS = {"-c", "--eval", "-e"}

SAFE_PYTHON_MODULES = {"pytest", "ruff", "unittest", "mypy"}

SAFE_PACKAGE_MANAGER_COMMANDS = {"test", "run"}


class CommandPolicy:
    def __init__(self, allowed_programs: list[str]) -> None:
        normalized = set()
        for program in allowed_programs:
            name = Path(program.strip()).name.lower()
            if name.endswith(".exe"):
                name = name[:-4]
            if name:
                normalized.add(name)
        self.allowed = normalized

    def build_args(self, command: str) -> list[str]:
        if not command or not command.strip():
            raise UnsafeOperationError("Empty command")
        if SHELL_METACHARACTERS.search(command):
            raise UnsafeOperationError(
                "Shell metacharacters are not allowed in agent commands; use a single executable"
            )
        try:
            parts = shlex.split(command, posix=True)
        except ValueError as exc:
            raise UnsafeOperationError(f"Could not parse command: {exc}") from exc
        if not parts:
            raise UnsafeOperationError("Empty command")
        program = Path(parts[0]).name.lower()
        if program.endswith(".exe"):
            program = program[:-4]
        if program in DANGEROUS_PROGRAMS:
            raise UnsafeOperationError(f"Shell interpreters are not allowed in agent commands: {parts[0]}")
        if program not in self.allowed:
            raise UnsafeOperationError(
                f"Command '{parts[0]}' is not in the execution allowlist "
                f"({', '.join(sorted(self.allowed))})"
            )
        arguments = parts[1:]
        if program in {"python", "python3"}:
            if arguments and arguments[0] in INLINE_EVAL_FLAGS:
                raise UnsafeOperationError("Inline Python evaluation (-c) is not allowed")
            if "-m" in arguments:
                module_index = arguments.index("-m")
                module = arguments[module_index + 1] if module_index + 1 < len(arguments) else ""
                if module not in SAFE_PYTHON_MODULES:
                    raise UnsafeOperationError(
                        f"Python module '{module}' is not allowlisted for agent execution"
                    )
        if program == "node" and any(flag in INLINE_EVAL_FLAGS for flag in arguments):
            raise UnsafeOperationError("Inline Node evaluation is not allowed")
        if program in {"npm", "yarn", "pnpm"}:
            subcommand = next((item for item in arguments if not item.startswith("-")), "")
            if subcommand not in SAFE_PACKAGE_MANAGER_COMMANDS:
                raise UnsafeOperationError(
                    f"'{program} {subcommand}' is not allowed; only test/run scripts may execute"
                )
        return parts


def _scrubbed_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not PROTECTED_ENV.search(key)}
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "CI": "true",
            "NO_COLOR": "1",
            "TERM": "dumb",
            "NPM_CONFIG_UPDATE_NOTIFIER": "false",
        }
    )
    return env


class LocalSandbox:
    """Runs commands on this machine with scrubbed env, limits and a timeout.

    This is appropriate for trusted local development. For untrusted repository
    code use SANDBOX_MODE=docker, which delegates to the isolated worker.
    """

    async def execute(
        self, args: list[str], cwd: Path, timeout_seconds: int, command_label: str
    ) -> CommandResult:
        # The blocking subprocess is executed in a worker thread so the API event
        # loop keeps serving SSE and requests while tests run.
        return await asyncio.to_thread(self._execute_blocking, args, cwd, timeout_seconds, command_label)

    def _execute_blocking(
        self, args: list[str], cwd: Path, timeout_seconds: int, command_label: str
    ) -> CommandResult:
        settings = get_settings()
        workspaces = settings.workspaces_path.resolve()
        try:
            cwd.resolve().relative_to(workspaces)
        except ValueError as exc:
            raise UnsafeOperationError("Refusing to execute outside the AutoDev workspace") from exc

        run_args = self._platform_args(args)
        env = _scrubbed_env()
        started = time.monotonic()
        preexec = self._preexec(timeout_seconds) if os.name == "posix" else None
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
        try:
            process = subprocess.Popen(
                run_args,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                preexec_fn=preexec,
                start_new_session=os.name == "posix",
                creationflags=creationflags,
            )
        except OSError as exc:
            return CommandResult(
                command=command_label,
                status="error",
                exit_code=None,
                output=f"Could not start command: {type(exc).__name__}",
                duration_seconds=time.monotonic() - started,
            )

        timed_out = False
        try:
            output, _ = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._terminate(process)
            try:
                output, _ = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                output = ""
        duration = time.monotonic() - started
        output = cap_output(output or "")
        exit_code = process.returncode
        status = "timeout" if timed_out else ("passed" if exit_code == 0 else "failed")
        passed, failed, failing = parse_test_output(output)
        return CommandResult(
            command=command_label,
            status=status,
            exit_code=exit_code,
            output=output,
            duration_seconds=round(duration, 3),
            passed_count=passed,
            failed_count=failed,
            failing_tests=failing,
        )

    def _platform_args(self, args: list[str]) -> list[str]:
        resolved = list(args)
        if resolved and resolved[0] in {"python", "python3"}:
            resolved[0] = sys.executable
        elif resolved:
            found = shutil.which(resolved[0])
            if found:
                resolved[0] = found
        if os.name == "nt" and resolved and resolved[0].lower().endswith((".cmd", ".bat")):
            comspec = os.environ.get("COMSPEC", "cmd.exe")
            return [comspec, "/d", "/s", "/c", subprocess.list2cmdline(resolved)]
        return resolved

    def _preexec(self, timeout_seconds: int):  # pragma: no cover - POSIX only
        def limit() -> None:
            try:
                import resource

                cpu = max(1, int(timeout_seconds))
                resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 5))
                memory = 2 * 1024 * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
                resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
                resource.setrlimit(resource.RLIMIT_NOFILE, (512, 512))
            except (ImportError, ValueError, OSError):
                pass

        return limit

    def _terminate(self, process: subprocess.Popen[str]) -> None:
        try:
            if os.name == "posix":
                os.killpg(os.getpgid(process.pid), 9)
            else:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    capture_output=True,
                    check=False,
                )
                process.kill()
        except (OSError, ProcessLookupError):
            pass


class DockerSandbox:
    """Delegates execution to the isolated worker container over HTTP."""

    async def execute(
        self, args: list[str], cwd: Path, timeout_seconds: int, command_label: str
    ) -> CommandResult:
        settings = get_settings()
        try:
            relative = cwd.resolve().relative_to(settings.workspaces_path.resolve()).as_posix()
        except ValueError as exc:
            raise UnsafeOperationError("Refusing to execute outside the AutoDev workspace") from exc
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds + 30) as client:
                response = await client.post(
                    f"{settings.sandbox_url.rstrip('/')}/execute",
                    headers={"X-Sandbox-Token": settings.sandbox_token},
                    json={"args": args, "cwd": relative, "timeout": timeout_seconds},
                )
            if response.status_code >= 400:
                return CommandResult(
                    command=command_label,
                    status="error",
                    output=f"Sandbox worker returned HTTP {response.status_code}: {response.text[:1000]}",
                    duration_seconds=time.monotonic() - started,
                )
            data = response.json()
        except httpx.HTTPError as exc:
            return CommandResult(
                command=command_label,
                status="error",
                output=f"Sandbox worker unreachable: {type(exc).__name__}",
                duration_seconds=time.monotonic() - started,
            )
        output = cap_output(str(data.get("output") or ""))
        passed, failed, failing = parse_test_output(output)
        return CommandResult(
            command=command_label,
            status=str(data.get("status") or "error"),
            exit_code=data.get("exit_code"),
            output=output,
            duration_seconds=round(time.monotonic() - started, 3),
            passed_count=passed,
            failed_count=failed,
            failing_tests=failing,
        )


class SandboxExecutor:
    def __init__(
        self,
        *,
        allowed_commands: list[str] | None = None,
        mode: str | None = None,
    ) -> None:
        settings = get_settings()
        self.policy = CommandPolicy(allowed_commands or settings.allowed_command_list)
        self.mode = mode or settings.sandbox_mode
        self.sandbox = DockerSandbox() if self.mode == "docker" else LocalSandbox()

    async def run_command(self, command: str, repo_path: Path, timeout_seconds: int) -> CommandResult:
        args = self.policy.build_args(command)
        return await self.sandbox.execute(args, repo_path, timeout_seconds, command)

    async def run_commands(
        self,
        commands: list[str],
        repo_path: Path,
        timeout_seconds: int,
        *,
        cancel_check=None,
    ) -> TestSuiteResult:
        results: list[CommandResult] = []
        for command in commands:
            if cancel_check is not None:
                cancel_check()
            logger.info("Running sandbox command: %s", command)
            results.append(await self.run_command(command, repo_path, timeout_seconds))
        return summarize_results(results)


def detect_execution_commands(
    index: RepositoryIndex, *, default_test_command: str | None = None
) -> tuple[list[str], list[str]]:
    summary = index.to_summary()
    tests: list[str] = [default_test_command] if default_test_command else list(summary["test_commands"])
    checks: list[str] = list(summary["build_commands"]) + list(summary["lint_commands"])
    return tests, checks

"""All git operations used by the agent. Never force-pushes, never pushes to a base branch."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from app.core.redaction import redact_secrets

BRANCH_RE = re.compile(r"^autodev/[a-z0-9][a-z0-9._-]{0,120}$")


class GitError(RuntimeError):
    pass


def _redact_url(text: str) -> str:
    return re.sub(r"(?i)(https?://)([^/@\s]+)@", r"\1***@", text)


def authenticated_url(clone_url: str, token: str | None) -> str:
    """Return a one-shot authenticated https URL; never logged or persisted."""
    if not token:
        return clone_url
    parts = urlsplit(clone_url)
    if parts.scheme not in {"http", "https"}:
        return clone_url
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    netloc = f"x-access-token:{quote(token, safe='')}@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


class GitManager:
    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path.resolve()

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def _env(self) -> dict[str, str]:
        env = {
            key: value
            for key, value in os.environ.items()
            if not re.search(r"(?i)(token|secret|password|credential|api[_-]?key|private[_-]?key)", key)
        }
        env.update(
            {
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_ASKPASS": "echo",
                "GCM_INTERACTIVE": "never",
                "GIT_CONFIG_NOSYSTEM": "0",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        return env

    def _run(
        self, args: list[str], *, timeout: int = 120, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        if not self.repo_path.exists():
            raise GitError("The workspace no longer exists on disk")
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=self._env(),
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise GitError(f"git {args[0]} could not run: {type(exc).__name__}") from exc
        if check and result.returncode != 0:
            message = redact_secrets(_redact_url((result.stderr or result.stdout).strip()[:1500]))
            raise GitError(f"git {args[0]} failed: {message or 'unknown error'}")
        return result

    # ------------------------------------------------------------------ #
    # clone / branch / commit
    # ------------------------------------------------------------------ #
    @classmethod
    def clone(
        cls,
        clone_url: str,
        destination: Path,
        *,
        token: str | None = None,
        timeout: int = 300,
    ) -> GitManager:
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise GitError("Destination workspace already exists")
        is_remote = "://" in clone_url
        url = authenticated_url(clone_url, token) if is_remote else clone_url
        args = ["git", "clone", "--no-hardlinks"] if not is_remote else ["git", "clone", "--depth", "50"]
        args.extend([url, str(destination)])
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env={
                    key: value
                    for key, value in os.environ.items()
                    if not re.search(
                        r"(?i)(token|secret|password|credential|api[_-]?key|private[_-]?key)", key
                    )
                }
                | {"GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "echo", "GCM_INTERACTIVE": "never"},
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise GitError(f"Repository clone failed: {type(exc).__name__}") from exc
        if result.returncode != 0:
            message = redact_secrets(_redact_url((result.stderr or result.stdout).strip()[:1500]))
            raise GitError(f"Repository clone failed: {message or 'unknown error'}")
        manager = cls(destination)
        manager._run(["config", "user.name", "AutoDev Agent"])
        manager._run(["config", "user.email", "autodev@localhost"])
        manager._run(["config", "commit.gpgsign", "false"])
        return manager

    @staticmethod
    def make_branch_name(title: str, execution_id: int) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:36].strip("-") or "task"
        return f"autodev/{slug}-{execution_id}"

    def current_branch(self) -> str:
        return self._run(["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()

    def head_sha(self) -> str:
        return self._run(["rev-parse", "HEAD"]).stdout.strip()

    def create_branch(self, branch: str) -> None:
        if not BRANCH_RE.match(branch):
            raise GitError("Refusing to create a branch outside the autodev/ namespace")
        branches = self._run(["branch", "--list", branch]).stdout.strip()
        if branches:
            raise GitError(f"Branch '{branch}' already exists")
        self._run(["checkout", "-b", branch])

    def branch_exists(self, branch: str, *, remote: bool = False) -> bool:
        ref = f"refs/remotes/origin/{branch}" if remote else f"refs/heads/{branch}"
        return self._run(["show-ref", "--verify", "--quiet", ref], check=False).returncode == 0

    def checkout(self, branch: str) -> None:
        self._run(["checkout", branch])

    def checkout_tracking(self, branch: str) -> None:
        self._run(["checkout", "-B", branch, f"origin/{branch}"])

    def commit(self, message: str) -> str:
        self._run(["commit", "--no-verify", "-m", message], timeout=120)
        return self.head_sha()

    def push_branch(self, branch: str, remote_url: str) -> None:
        if not BRANCH_RE.match(branch):
            raise GitError("Refusing to push a branch outside the autodev/ namespace")
        current = self.current_branch()
        if current != branch:
            raise GitError(f"Refusing to push: checked out branch '{current}' is not '{branch}'")
        self._run(
            ["push", "--no-verify", remote_url, f"HEAD:refs/heads/{branch}"],
            timeout=300,
        )

    # ------------------------------------------------------------------ #
    # staging / diff
    # ------------------------------------------------------------------ #
    def stage_paths(self, paths: list[str]) -> None:
        safe: list[str] = []
        for path in dict.fromkeys(paths):
            if path.startswith("-") or ".." in Path(path).parts or Path(path).is_absolute():
                raise GitError("Refusing to stage an unsafe path")
            safe.append(path)
        if not safe:
            return
        self._run(["add", "-A", "--", *safe], timeout=120)

    def staged_paths(self) -> list[str]:
        output = self._run(["diff", "--cached", "--name-only"], check=False).stdout
        return [line.strip() for line in output.splitlines() if line.strip()]

    def numstat(self) -> tuple[int, int, dict[str, tuple[int, int, bool]]]:
        output = self._run(["diff", "--cached", "--numstat"], check=False).stdout
        total_add = total_del = 0
        per_file: dict[str, tuple[int, int, bool]] = {}
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            added, deleted, path = parts
            binary = added == "-" or deleted == "-"
            add = 0 if binary else int(added)
            rem = 0 if binary else int(deleted)
            per_file[path.strip()] = (add, rem, binary)
            total_add += add
            total_del += rem
        return total_add, total_del, per_file

    def diff_for(self, path: str) -> str:
        return self._run(["diff", "--cached", "--no-color", "-U3", "--", path], check=False).stdout

    def full_diff(self) -> str:
        return self._run(["diff", "--cached", "--no-color", "-U3"], check=False).stdout

    def has_staged_changes(self) -> bool:
        return bool(self.staged_paths())

    def log_oneline(self, limit: int = 10) -> list[str]:
        output = self._run(["log", "--oneline", f"-{limit}"], check=False).stdout
        return [line.strip() for line in output.splitlines() if line.strip()]

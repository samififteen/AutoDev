"""Pre-pull-request validation of the staged diff."""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Literal

from app.agent.git_manager import GitError, GitManager
from app.core.redaction import scan_for_secrets
from pydantic import BaseModel, Field

MAX_DIFF_CHARS = 750_000

FORBIDDEN_PATH_HINTS = (
    ".env",
    "id_rsa",
    "id_ed25519",
    "credentials",
    "secrets.",
    ".pem",
    ".key",
    ".p12",
)

SENSITIVE_PATHS = (
    ".github/workflows/",
    "docker-compose.yml",
    "Dockerfile",
    ".gitignore",
    "package-lock.json",
    "poetry.lock",
    "yarn.lock",
)


class ValidationCheck(BaseModel):
    name: str
    passed: bool
    detail: str
    severity: Literal["error", "warning"] = "error"


class ValidationReport(BaseModel):
    passed: bool = False
    checks: list[ValidationCheck] = Field(default_factory=list)
    files_changed: list[str] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    secrets: list[dict[str, str]] = Field(default_factory=list)
    summary: str = ""
    diff_size: int = 0

    def add(
        self,
        name: str,
        passed: bool,
        detail: str,
        severity: Literal["error", "warning"] = "error",
    ) -> None:
        self.checks.append(ValidationCheck(name=name, passed=passed, detail=detail, severity=severity))

    def finalize(self) -> ValidationReport:
        self.passed = (
            all(check.passed for check in self.checks if check.severity == "error") and not self.secrets
        )
        failures = [check.name for check in self.checks if not check.passed and check.severity == "error"]
        warnings = [check.name for check in self.checks if not check.passed and check.severity == "warning"]
        parts = []
        if self.passed:
            parts.append("All blocking checks passed")
        else:
            parts.append(f"Blocking checks failed: {', '.join(failures) or 'secrets detected'}")
        if warnings:
            parts.append(f"warnings: {', '.join(warnings)}")
        self.summary = "; ".join(parts)
        return self


class PatchValidator:
    def validate(
        self,
        *,
        git: GitManager,
        base_branch: str,
        max_files: int,
        expected_paths: set[str],
        test_summary: str | None = None,
        test_passed: bool | None = None,
        test_output: str = "",
    ) -> ValidationReport:
        report = ValidationReport()

        try:
            branch = git.current_branch()
        except GitError as exc:
            report.add("branch", False, str(exc))
            return report.finalize()

        protected = {"main", "master", "develop", base_branch}
        report.add(
            "working-branch",
            branch.startswith("autodev/") and branch not in protected,
            f"Agent is on branch '{branch}' (base: '{base_branch}')",
        )

        staged = set(git.staged_paths())
        report.files_changed = sorted(staged)
        try:
            additions, deletions, numstat = git.numstat()
            diff = git.full_diff()
        except GitError as exc:
            report.add("diff", False, str(exc))
            return report.finalize()

        report.additions = additions
        report.deletions = deletions
        report.diff_size = len(diff)
        report.add(
            "changes-present",
            bool(staged),
            f"{len(staged)} file(s) staged, +{additions}/-{deletions}",
        )
        report.add(
            "file-limit",
            len(staged) <= max_files,
            f"{len(staged)} of {max_files} allowed files modified",
        )

        unexpected = sorted(staged - expected_paths)
        report.add(
            "unrelated-changes",
            not unexpected,
            "No unexpected files were modified"
            if not unexpected
            else f"Unexpected modified files: {', '.join(unexpected[:10])}",
        )

        forbidden = [path for path in staged if any(hint in path.lower() for hint in FORBIDDEN_PATH_HINTS)]
        report.add(
            "protected-paths",
            not forbidden,
            "No credential or environment files modified"
            if not forbidden
            else f"Refusing to include protected files: {', '.join(forbidden)}",
        )

        binaries = [path for path, (_, _, binary) in numstat.items() if binary]
        report.add(
            "binary-files",
            not binaries,
            "No binary files in the change set" if not binaries else f"Binary files: {', '.join(binaries)}",
        )

        if report.diff_size > MAX_DIFF_CHARS:
            report.add(
                "diff-size",
                False,
                f"Diff is {report.diff_size} characters (limit {MAX_DIFF_CHARS})",
            )
        else:
            report.add("diff-size", True, f"Diff size {report.diff_size} characters")

        sensitive = [path for path in staged if any(hint in path for hint in SENSITIVE_PATHS)]
        report.add(
            "sensitive-files",
            not sensitive,
            "No CI or dependency-lock files modified"
            if not sensitive
            else f"Review carefully: {', '.join(sensitive)}",
            severity="warning",
        )

        deleted_tests = [
            path for path in staged if "test" in path.lower() and numstat.get(path, (0, 0, False))[0] == 0
        ]
        report.add(
            "test-deletions",
            not deleted_tests,
            "No test files deleted"
            if not deleted_tests
            else f"Test files added/changed: {', '.join(deleted_tests)}",
            severity="warning",
        )

        added_lines = "\n".join(
            line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")
        )
        findings = scan_for_secrets(added_lines)
        report.secrets = findings
        report.add(
            "secret-scan",
            not findings,
            "No secrets detected in added lines"
            if not findings
            else f"{len(findings)} potential secret(s) detected: " + json.dumps(findings[:5], default=str),
        )

        if test_passed is not None:
            report.add(
                "tests",
                test_passed,
                test_summary or ("Tests passed" if test_passed else "Tests failed"),
            )
        if not test_passed:
            report.add(
                "failure-details",
                True,
                (test_output or "")[-2000:],
                severity="warning",
            )

        checked_paths = {PurePosixPath(path).suffix for path in staged}
        report.add(
            "file-types",
            not (".zip" in checked_paths or ".exe" in checked_paths),
            "Only source-style files are included",
            severity="warning",
        )
        return report.finalize()
